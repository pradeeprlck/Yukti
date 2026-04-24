"""
Local adapter inference provider for Arjun.

This module implements a small provider that can load a base causal LM and
optionally apply a PEFT adapter saved with `peft` so the model can be used
for local inference during backtests or evaluation.

Usage:
  from yukti.agents.local_adapter import LocalArjun
  arjun = LocalArjun(adapter_dir='models/lora-journal', base_model='facebook/opt-125m')
  decision = await arjun.safe_decide(context)

Notes:
  - This code is best-effort and designed to be invoked explicitly; importing
    it does not perform heavy model loads until a LocalArjun instance is
    created.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Optional, Tuple

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

try:
    from peft import PeftModel
except Exception:  # pragma: no cover - optional dependency
    PeftModel = None

from yukti.agents.arjun import BaseProvider, TradeDecision, CallMeta

LOG = logging.getLogger("yukti.agents.local_adapter")


class LocalAdapterProvider(BaseProvider):
    """Provider that runs a local model (and optional PEFT adapter).

    This class loads models lazily in the constructor. Keep in mind loading
    large models may take significant RAM and time — use small base models in CI.
    """

    def __init__(
        self,
        adapter_dir: str,
        base_model: Optional[str] = None,
        device: str = "cpu",
        max_new_tokens: int = 256,
        temperature: float = 0.0,
    ) -> None:
        self.adapter_dir = adapter_dir
        self.base_model = base_model
        self.device = torch.device(device)
        self.max_new_tokens = max_new_tokens
        self.temperature = float(temperature)

        # Tokenizer: prefer adapter_dir (if tokenizer saved), otherwise base_model
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(adapter_dir, use_fast=True)
        except Exception:
            if base_model:
                self.tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True)
            else:
                raise

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Load model
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        """Attempt to load a model using several common patterns.

        - If `peft` is available and `base_model` is provided, load the base
          model and then apply the PEFT adapter with `PeftModel.from_pretrained`.
        - Otherwise, try to load `adapter_dir` as a full model.
        - As a last resort, load `base_model` alone.
        """
        try:
            if PeftModel is not None and self.base_model:
                LOG.info("Loading base model %s and applying PEFT adapter from %s", self.base_model, self.adapter_dir)
                base = AutoModelForCausalLM.from_pretrained(self.base_model, trust_remote_code=True)
                try:
                    self.model = PeftModel.from_pretrained(base, self.adapter_dir)
                except Exception:
                    LOG.exception("PeftModel.from_pretrained failed — attempting to load adapter_dir as full model")
                    self.model = AutoModelForCausalLM.from_pretrained(self.adapter_dir, trust_remote_code=True)
            else:
                LOG.info("Loading model from %s", self.adapter_dir)
                self.model = AutoModelForCausalLM.from_pretrained(self.adapter_dir, trust_remote_code=True)
        except Exception:
            if self.base_model:
                LOG.warning("Failed to load adapter_dir; falling back to base_model %s", self.base_model)
                self.model = AutoModelForCausalLM.from_pretrained(self.base_model, trust_remote_code=True)
            else:
                LOG.exception("Failed to load any model for LocalAdapterProvider")
                raise

        # Move model to device and set eval
        try:
            self.model.to(self.device)
        except Exception:
            LOG.warning("Failed to move model to device %s; continuing on default device", self.device)
        self.model.eval()

    def _generate_sync(self, context: str) -> str:
        """Synchronous generation helper used in threadpool."""
        inputs = self.tokenizer(context, return_tensors="pt", truncation=True)
        input_ids = inputs["input_ids"].to(self.model.device)
        attention_mask = inputs.get("attention_mask")
        if attention_mask is not None:
            attention_mask = attention_mask.to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                temperature=self.temperature,
                eos_token_id=self.tokenizer.eos_token_id,
                pad_token_id=self.tokenizer.pad_token_id,
            )

        # Extract generated portion (strip prompt tokens)
        gen_ids = outputs[0][input_ids.shape[1] :]
        raw = self.tokenizer.decode(gen_ids, skip_special_tokens=True)
        if not raw.strip():
            # fallback: decode entire sequence and remove prefix if present
            whole = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            if whole.startswith(context):
                raw = whole[len(context) :].strip()
            else:
                raw = whole
        return raw

    async def call(self, context: str) -> Tuple[TradeDecision, CallMeta]:
        loop = asyncio.get_event_loop()
        t0 = time.monotonic()
        try:
            raw = await loop.run_in_executor(None, self._generate_sync, context)
            latency_ms = (time.monotonic() - t0) * 1000

            # Parse JSON using BaseProvider helper
            try:
                data = BaseProvider._parse_json(raw, "local_adapter")
            except Exception as exc:
                LOG.warning("Local adapter returned non-JSON output: %s", exc)
                raise

            symbol = BaseProvider._extract_symbol(context)
            decision = TradeDecision(**data)
            meta = CallMeta(
                provider="local_adapter",
                model=self.base_model or self.adapter_dir,
                latency_ms=latency_ms,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
            )
            return decision, meta
        except Exception as exc:  # safe fallback — return SKIP decision
            LOG.exception("Adapter inference failed: %s", exc)
            skip = TradeDecision(
                symbol="UNKNOWN",
                action="SKIP",
                reasoning=f"Adapter inference error: {exc}",
                skip_reason="adapter_error",
                conviction=1,
            )
            meta = CallMeta(
                provider="local_adapter",
                model=self.base_model or self.adapter_dir,
                latency_ms=(time.monotonic() - t0) * 1000,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
            )
            return skip, meta


class LocalArjun:
    """Lightweight wrapper exposing `safe_decide(context)` compatible with
    existing code that expects `arjun.safe_decide()`.
    """

    def __init__(self, adapter_dir: str, base_model: Optional[str] = None, device: str = "cpu", **kwargs) -> None:
        self._prov = LocalAdapterProvider(adapter_dir, base_model=base_model, device=device, **kwargs)

    async def safe_decide(self, context: str):
        decision, _ = await self._prov.call(context)
        return decision
