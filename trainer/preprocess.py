"""
trainer/preprocess.py

Create a cleaned, split dataset from the export JSONL and optionally
pre-tokenize it for faster CI and training runs.

Outputs (under --out_dir):
  - train.jsonl
  - validation.jsonl (if val_frac > 0)
  - test.jsonl
  - stats.json (counts, outcome distribution)
  - tokenized/ (optional, dataset.save_to_disk output)

Usage:
  python trainer/preprocess.py --input data/training/journal_export.jsonl --out_dir data/training/processed --val_frac 0.1 --test_frac 0.05

Optional tokenization (requires transformers):
  python trainer/preprocess.py --input ... --out_dir ... --tokenize --tokenizer facebook/opt-125m

This script is safe to run in CI as a dry-run by using `--dry_run` which only
computes counts and writes `stats.json`.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
from typing import Dict, Optional

from datasets import Dataset, load_dataset

LOG = logging.getLogger("trainer.preprocess")


def _write_jsonl(ds: Dataset, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for rec in ds:
            # Only keep prompt and target to match training pipeline
            out = {"prompt": rec.get("prompt"), "target": rec.get("target")}
            fh.write(json.dumps(out, ensure_ascii=False) + "\n")


def build_splits(ds: Dataset, val_frac: float, test_frac: float, seed: int = 42) -> Dict[str, Dataset]:
    if val_frac < 0 or test_frac < 0 or val_frac + test_frac >= 1.0:
        raise ValueError("val_frac and test_frac must be >=0 and sum < 1.0")

    LOG.info("Shuffling dataset (seed=%s)", seed)
    ds = ds.shuffle(seed=seed)

    if test_frac > 0:
        split = ds.train_test_split(test_size=test_frac, seed=seed)
        train_plus = split["train"]
        test = split["test"]
    else:
        train_plus = ds
        test = Dataset.from_list([])

    if val_frac > 0:
        # val_frac is fraction of original total; convert to relative fraction of train_plus
        rel_val = val_frac / (1.0 - test_frac)
        sub = train_plus.train_test_split(test_size=rel_val, seed=seed)
        train = sub["train"]
        val = sub["test"]
    else:
        train = train_plus
        val = Dataset.from_list([])

    return {"train": train, "validation": val, "test": test}


def tokenize_dataset(ds: Dataset, tokenizer, max_input_length: int = 1024, max_target_length: int = 256):
    # Replicates the build_examples logic used at training time
    def _tokenize_item(example):
        prompt = example.get("prompt") or ""
        target = example.get("target") or {}
        tgt_text = json.dumps(target, ensure_ascii=False)
        input_text = "CONTEXT:\n" + prompt + "\n\nRESPONSE: "
        full = input_text + tgt_text
        tokenized_full = tokenizer(full, truncation=True, max_length=max_input_length + max_target_length)
        full_ids = tokenized_full["input_ids"]
        prompt_ids = tokenizer(input_text, truncation=True, max_length=max_input_length)["input_ids"]
        labels = full_ids.copy()
        for i in range(min(len(prompt_ids), len(labels))):
            labels[i] = -100
        return {"input_ids": full_ids, "labels": labels}

    return ds.map(lambda x: _tokenize_item(x), remove_columns=ds.column_names)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--out_dir", default="data/training/processed")
    p.add_argument("--val_frac", type=float, default=0.1)
    p.add_argument("--test_frac", type=float, default=0.05)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--tokenize", action="store_true", help="Pre-tokenize and save tokenized dataset")
    p.add_argument("--tokenizer", default=None, help="Tokenizer model for pre-tokenization (required if --tokenize)")
    p.add_argument("--max_input_length", type=int, default=1024)
    p.add_argument("--max_target_length", type=int, default=256)
    p.add_argument("--dry_run", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO)

    LOG.info("Loading input dataset %s", args.input)
    ds = load_dataset("json", data_files={"all": args.input})["all"]

    # Basic cleaning: keep records with prompt and target
    LOG.info("Filtering empty prompts/targets")
    ds = ds.filter(lambda x: x.get("prompt") is not None and x.get("target") is not None)

    total = len(ds)
    LOG.info("Total examples after filter: %s", total)

    splits = build_splits(ds, args.val_frac, args.test_frac, seed=args.seed)

    os.makedirs(args.out_dir, exist_ok=True)

    stats = {
        "total": total,
        "train_count": len(splits["train"]) if len(splits["train"]) else 0,
        "validation_count": len(splits["validation"]) if len(splits["validation"]) else 0,
        "test_count": len(splits["test"]) if len(splits["test"]) else 0,
    }

    stats_path = os.path.join(args.out_dir, "stats.json")
    with open(stats_path, "w", encoding="utf-8") as fh:
        json.dump(stats, fh, indent=2)
    LOG.info("Wrote stats to %s", stats_path)

    if args.dry_run:
        LOG.info("Dry run requested; exiting after stats generation")
        return

    # Write JSONL splits
    LOG.info("Writing train/validation/test JSONL files")
    _write_jsonl(splits["train"], os.path.join(args.out_dir, "train.jsonl"))
    if len(splits["validation"]) > 0:
        _write_jsonl(splits["validation"], os.path.join(args.out_dir, "validation.jsonl"))
    _write_jsonl(splits["test"], os.path.join(args.out_dir, "test.jsonl"))

    if args.tokenize:
        if not args.tokenizer:
            raise SystemExit("--tokenize requires --tokenizer model id")
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, use_fast=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        LOG.info("Tokenizing datasets with %s", args.tokenizer)
        tokenized_train = tokenize_dataset(splits["train"], tokenizer, args.max_input_length, args.max_target_length)
        tokenized_val = tokenize_dataset(splits["validation"], tokenizer, args.max_input_length, args.max_target_length) if len(splits["validation"])>0 else None
        tokenized_test = tokenize_dataset(splits["test"], tokenizer, args.max_input_length, args.max_target_length)

        tokenized_dir = os.path.join(args.out_dir, "tokenized")
        os.makedirs(tokenized_dir, exist_ok=True)
        tokenized_train.save_to_disk(os.path.join(tokenized_dir, "train"))
        if tokenized_val is not None:
            tokenized_val.save_to_disk(os.path.join(tokenized_dir, "validation"))
        tokenized_test.save_to_disk(os.path.join(tokenized_dir, "test"))
        LOG.info("Saved tokenized dataset to %s", tokenized_dir)


if __name__ == "__main__":
    main()
