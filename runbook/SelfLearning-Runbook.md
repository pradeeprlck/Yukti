# Self‑Learning Runbook (Design & Safety)

This runbook describes the planned parameter‑efficient self‑learning pipeline
for Yukti and the safety/gating procedures required before any automated
model promotion to paper/live.

Overview
--------
- Goal: enable Yukti to improve decision quality over time by retraining an
  adapter (LoRA/adapter/prompt) on historical decisions, journals and outcomes.
- Approach: keep the base LLM frozen; train small adapters on exported CSV/JSONL
  data. Evaluate offline via held‑out tests + paper trading before any rollout.

Data
----
- Source: `journal_entries`, `trades`, and `decision_log` tables.
- Export format: JSONL with fields `prompt` and `target` created by
  `scripts/export_training_data.py`.
- Labels: `outcome` (WIN/LOSS), `pnl_pct`, `conviction`, `setup_type`, `direction`.

Training Pipeline (high level)
------------------------------
1. Export: run `scripts/export_training_data.py` to create training JSONL.
2. Preprocess: tokenization + prompt/target formatting (see `trainer/train_adapter.py`).
3. Train: run a LoRA training job on a GPU instance (local or cloud).
4. Evaluate: run `trainer/eval.py` + backtest/paper simulation to estimate PnL.
5. Human review: PR with metrics + sample decisions for manual sign‑off.
6. Promote: if gates pass, stage model for a canary paper rollout.

Safety & Gating
---------------
- Automatic promotion is disabled by default.
- Required checks before promotion:
  - Accuracy / F1 on held‑out set above threshold
  - Paper trading return over baseline for N trading days
  - No higher-than-allowed take-rate of high‑conviction losing trades
  - Human reviewer approval in PR
- Kill switch: deploy previous model state and pause retrain jobs.

Deployment Strategy
-------------------
- Canary (paper): deploy adapter to a small percentage of paper calls.
- Observe for X days (configurable), then increase coverage if metrics look good.
- Live rollout: manual opt‑in only after sustained performance and security review.

Operational Notes
-----------------
- Use small batch sizes and short schedules initially (weekly retrain).
- Use adapter checkpoints; keep a clear versioning scheme (model+adapter+data-hash).
- Store reproducible metadata for each retrain: git commit, data query, export file, hyperparams.

Promotion & Gating
------------------
- The GitHub Actions environment `model-promotion` is used for manual promotion.
- Promotion workflow: dispatch `.github/workflows/promote-model.yml`, review CI artifacts, and approve the `model-promotion` environment to complete the job.
- Required checks before any promotion:
  - Held-out evaluation accuracy above threshold
  - Backtest results: paper trading performance vs baseline over N trading days
  - Human reviewer approval recorded in PR

Runbook: How to promote
1. Run CI export + dry-run: use `retrain-eval.yml` (workflow_dispatch) or run exporter locally.
2. Inspect artifacts (preprocess summary, eval logs, model files) from the CI run.
3. Open PR with promotion request and include `promotion-report` artifact.
4. Approve the `model-promotion` environment on GitHub to allow the promote workflow to proceed.


Responsible parties
------------------
- Engineering: implement pipeline and CI gating
- Quant / Risk: define reward metrics and backtest rules
- Trading lead: human review and final promotion approval

References
----------
- See `scripts/export_training_data.py` and `trainer/train_adapter.py` for implementation
  scaffolding.

"""
