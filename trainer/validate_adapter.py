"""
trainer/validate_adapter.py

Quick validator to ensure a saved adapter directory can be loaded and used
for a deterministic sample inference. Returns zero on success and non-zero on
failure. This is useful in CI to verify adapter artifacts before promotion.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime


def _sample_context(symbol: str = "TESTSYM", price: float = 1000.0) -> str:
    return f"STOCK: {symbol} ══ Price: ₹{price}\n\nCONTEXT:\nSample context for adapter validation.\n\nRESPONSE: "


async def _run(adapter_dir: str, base_model: str | None, device: str) -> int:
    try:
        from yukti.agents.local_adapter import LocalArjun
    except Exception as exc:
        print("Failed to import LocalArjun:", exc)
        return 2

    try:
        arjun = LocalArjun(adapter_dir=adapter_dir, base_model=base_model, device=device)
    except Exception as exc:
        print("Failed to initialize LocalArjun:", exc)
        return 3

    ctx = _sample_context()
    try:
        decision = await arjun.safe_decide(ctx)
        print("Adapter produced decision:")
        print(decision.json())
        return 0
    except Exception as exc:
        print("Adapter inference failed:", exc)
        return 4


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--adapter_dir", required=True)
    p.add_argument("--base_model", default=None)
    p.add_argument("--device", default="cpu")
    args = p.parse_args(argv)
    return asyncio.run(_run(args.adapter_dir, args.base_model, args.device))


if __name__ == "__main__":
    raise SystemExit(main())
