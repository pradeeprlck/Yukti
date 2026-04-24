Preparing a PR with the self-learning changes

Run these commands locally to prepare a branch and PR. This repository intentionally
does not run CI steps automatically in this script; run tests and inspect artifacts
before pushing.

```bash
git checkout -b feat/self-learning
git add .
git commit -m "feat: self-learning scaffolds (export, trainer, CI, tests)"
git push --set-upstream origin feat/self-learning
# Then open a PR on GitHub with the branch
```

Suggested review checklist:
- Ensure `trainer/requirements.txt` matches available infra
- Run unit tests locally: `pytest tests/unit`
- Review CI artifacts from `.github/workflows/retrain-eval.yml`
- Manually review `runbook/SelfLearning-Runbook.md` and `docs/SELF_LEARNING_REPORT.md`
