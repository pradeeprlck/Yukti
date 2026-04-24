"""
trainer/prototype_finetune.py

Orchestrate a minimal prototype fine-tune run (preprocess → train → validate).

This script is a convenience for local experimentation and CI dry-runs. By
default it runs in `--dry_run` mode to avoid heavy GPU usage; pass
`--execute` to perform real training (requires GPUs and proper deps).

Example (dry-run):
  python trainer/prototype_finetune.py --input data/training/sample_export.jsonl

Example (execute real training):
  python trainer/prototype_finetune.py --input data/training/journal_export.jsonl --execute --base_model facebook/opt-125m --out_dir models/lora-proto --epochs 3
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import List


def run_cmd(cmd: List[str], env: dict | None = None) -> int:
    print("Running:", " ".join(cmd))
    p = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    print(p.stdout)
    if p.returncode != 0:
        print("ERROR:", p.stderr)
    return p.returncode


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="data/training/sample_export.jsonl")
    p.add_argument("--processed_dir", default="data/training/processed")
    p.add_argument("--base_model", default="facebook/opt-125m")
    p.add_argument("--out_dir", default="models/lora-proto")
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--batch_size", type=int, default=4)
    p.add_argument("--use_peft", choices=["auto", "on", "off"], default="auto")
    p.add_argument("--val_frac", type=float, default=0.1)
    p.add_argument("--test_frac", type=float, default=0.05)
    p.add_argument("--device", default="cpu")
    p.add_argument("--execute", action="store_true", help="Run real training (may require GPU)")
    args = p.parse_args(argv)

    python = sys.executable

    # Step 1: Preprocess
    train_json = os.path.join(args.processed_dir, "train.jsonl")
    if not os.path.exists(train_json):
        cmd = [python, "-m", "trainer.preprocess", "--input", args.input, "--out_dir", args.processed_dir, "--val_frac", str(args.val_frac), "--test_frac", str(args.test_frac)]
        rc = run_cmd(cmd)
        if rc != 0:
            print("Preprocess failed")
            return rc

    # Step 2: Train (dry-run by default)
    train_cmd = [
        python, "-m", "trainer.train_adapter",
        "--data", train_json,
        "--model", args.base_model,
        "--out_dir", args.out_dir,
        "--epochs", str(args.epochs),
        "--batch_size", str(args.batch_size),
        "--use_peft", args.use_peft,
    ]

    if not args.execute:
        train_cmd.append("--dry_run")

    rc = run_cmd(train_cmd)
    if rc != 0:
        print("Training step failed")
        return rc

    # Step 3: Validate adapter artifact
    validate_cmd = [python, "-m", "trainer.validate_adapter", "--adapter_dir", args.out_dir, "--base_model", args.base_model, "--device", args.device]
    rc = run_cmd(validate_cmd)
    if rc != 0:
        print("Adapter validation failed")
        return rc

    print("Prototype fine-tune pipeline complete. Artifacts in:", args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
