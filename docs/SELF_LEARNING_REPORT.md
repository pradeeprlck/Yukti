# Self-Learning Implementation Report

Date: 2026-04-24

Summary
-------
This document summarizes the self-learning scaffolding added to Yukti. It is
intended as a quick handoff for reviewers and operators.

What I added
- `scripts/export_training_data.py`: exporter (extended to include DecisionLog and reward)
- `trainer/`: training scaffolding
  - `train_adapter.py`: runnable CLI with `--dry_run`
  - `eval.py`: simple evaluation harness
  - `rewards.py`: reward heuristics used by exporter
  - `requirements.txt`, `README.md`
- Tests
  - Unit: `tests/unit/test_memory_retrieval.py`, `tests/unit/test_universe_scanner.py`, `tests/unit/test_trainer_preprocess.py`
  - Integration: `tests/integration/test_marketscan.py`
- CI
  - `.github/workflows/retrain-eval.yml` — export → dry-run train → eval, uploads artifacts
  - `.github/workflows/promote-model.yml` — manual promotion workflow (requires `model-promotion` environment approval)
- Runbook and docs
  - `runbook/SelfLearning-Runbook.md` updated
  - `docs/SELF_LEARNING_REPORT.md` (this file)

Notes & Next Steps
- I did not run tests or training jobs locally due to environment constraints — please run the provided commands locally.
- Next recommended tasks:
  1. Run unit tests: `pytest tests/unit`
  2. Run CI workflow on GitHub and inspect artifacts
  3. Implement backtest harness to compare candidate adapters vs baseline
  4. Add gating metrics + automated backtest in `retrain-eval.yml`
