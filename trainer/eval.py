"""
trainer/eval.py

Evaluation harness for trained adapter models. Loads a model + tokenizer and
computes simple prediction accuracy on a held-out JSONL dataset exported by
`scripts/export_training_data.py`.

This is a lightweight scaffold — extend with backtest integration to measure
financial impact before any automated promotion.
"""
from __future__ import annotations

import argparse
import json

from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer


def predict_text(model, tokenizer, prompt: str, max_new_tokens: int = 128) -> str:
    inp = prompt
    input_ids = tokenizer(inp, return_tensors="pt").input_ids
    out = model.generate(input_ids, max_new_tokens=max_new_tokens)
    return tokenizer.decode(out[0], skip_special_tokens=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model_dir", required=True)
    p.add_argument("--data", required=True)
    args = p.parse_args()

    ds = load_dataset("json", data_files={"eval": args.data})
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir)
    model = AutoModelForCausalLM.from_pretrained(args.model_dir)

    total = 0
    correct = 0
    for item in ds["eval"]:
        prompt = item.get("prompt", "")
        target = item.get("target")
        if not target:
            continue
        # For this scaffold we check outcome only
        expected = target.get("outcome")
        gen = predict_text(model, tokenizer, "CONTEXT:\n" + prompt + "\n\nRESPONSE:")
        # Heuristic: check presence of WIN/LOSS in generated text
        guessed = "WIN" if "WIN" in gen.upper() else "LOSS" if "LOSS" in gen.upper() else None
        if guessed is not None and expected is not None:
            total += 1
            if guessed == expected:
                correct += 1

    acc = (correct / total) if total else 0.0
    print(f"Evaluated {total} examples — accuracy (outcome) = {acc:.3f}")


if __name__ == "__main__":
    main()
