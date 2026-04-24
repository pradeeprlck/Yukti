# Trainer: Adapter fine‑tuning (LoRA)

This folder contains scaffolding to prototype parameter‑efficient adapter
training (LoRA) using exported journal/trade data from Yukti.

Quick start

1. Create a Python venv and install trainer deps:

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r trainer/requirements.txt
```

2. Export data from the DB (example):

```bash
python scripts/export_training_data.py --out data/training/journal_export.jsonl
```

2.5 (optional) Preprocess and split the exported data:

```bash
python trainer/preprocess.py --input data/training/journal_export.jsonl --out_dir data/training/processed --val_frac 0.1 --test_frac 0.05
```

This produces `train.jsonl`, `validation.jsonl` and `test.jsonl` under
`data/training/processed` and a `stats.json` summary. Use `--tokenize` to
pre-tokenize with a tokenizer model id for faster iteration in CI.

Prototype fine-tune orchestration
--------------------------------

Run a lightweight prototype of the full pipeline (preprocess → train → validate).
By default this runs as a dry-run to avoid heavy GPU usage; pass `--execute` to
perform real training.

```bash
python trainer/prototype_finetune.py --input data/training/journal_export.jsonl --out_dir models/lora-proto

# To actually run training (requires GPUs / proper env):
python trainer/prototype_finetune.py --input data/training/journal_export.jsonl --out_dir models/lora-proto --execute --base_model facebook/opt-125m --epochs 3
```

After completion, validate the adapter artifact:

```bash
python trainer/validate_adapter.py --adapter_dir models/lora-proto --base_model facebook/opt-125m
```

Evaluate model vs baseline
-------------------------

Run a backtest comparison between the baseline policy (MockProvider) and a
candidate adapter saved locally. This produces `artifacts/eval/compare_report.md`
and JSON metrics suitable for CI gating.

```bash
# Baseline only
python trainer/evaluate_vs_baseline.py --out_dir artifacts/eval

# With candidate adapter
python trainer/evaluate_vs_baseline.py --adapter_dir models/lora-candidate --base_model facebook/opt-125m --out_dir artifacts/eval
```


Self-learning loop (autonomous)
------------------------------

The system can now run a full self-learning loop automatically (if enabled in config):

1. Export new labeled data from the DB (last 7 days).
2. Retrain a LoRA adapter if enough new data is available (min rows configurable).
3. Evaluate the new adapter vs baseline using deterministic backtest.
4. If metrics pass thresholds (configurable: win_rate, profit_factor), promote (stub).
5. All actions are logged; errors are reported in logs.
6. Safety: Only one run at a time (Redis lock), async subprocesses (non-blocking), GPU detection (defaults to dry-run if no GPU), and all thresholds are configurable in `yukti/config.py`.

This is scheduled as a cron job in `yukti/scheduler/jobs.py` (job_self_learning_loop).
To enable, set `enable_self_learning = True` in your config (default is False for safety).
Configurable options in `yukti/config.py`:

```
enable_self_learning: bool = False
self_learning_min_rows: int = 100
self_learning_thresholds: dict = {"win_rate": 0.55, "profit_factor": 1.2}
```




3. Train an adapter (example):

```bash
python trainer/train_adapter.py --data data/training/journal_export.jsonl --model facebook/opt-125m --out_dir models/lora-journal --use_peft auto
```

4. Evaluate a trained adapter (simple heuristic eval):

```bash
python trainer/eval.py --model_dir models/lora-journal --data data/training/journal_eval.jsonl
```

Notes & safety

- This is a prototype: before any automated promotion, run offline backtests
  and a human review. See `runbook/SelfLearning-Runbook.md` for the safety gates.
- If using large models you'll need proper GPU resources and tuning.
- For secure/private LLM providers (Gemini/Claude) you cannot fine-tune —
  consider adapters on an open base model and proxy inference through your
  production routing if you require exact provider parity.
