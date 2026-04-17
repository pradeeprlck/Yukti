# Pushing Yukti to GitHub

This guide walks you through publishing Yukti to your own GitHub repository.

## Prerequisites

- GitHub account (free tier is fine)
- Git installed locally
- SSH key added to GitHub (or use HTTPS with token)

## Steps

### 1. Create a new repository on GitHub

Visit https://github.com/new

- **Repository name:** `yukti`
- **Description:** "Autonomous NSE trading agent — AI-powered, crash-safe, learns from trades"
- **Visibility:** Public (open source) or Private (personal use)
- **Do NOT initialize** with README, .gitignore, or license (we already have these)

Click **Create repository**.

### 2. Add GitHub remote

```bash
cd /path/to/yukti

# If you created a public repo
git remote add origin git@github.com:YOUR_USERNAME/yukti.git

# Or if you prefer HTTPS (will prompt for personal access token)
git remote add origin https://github.com/YOUR_USERNAME/yukti.git

# Verify
git remote -v
```

### 3. Push to GitHub

```bash
git push -u origin master
```

This pushes all commits and sets `master` as the default upstream branch.

### 4. Verify

Visit `https://github.com/YOUR_USERNAME/yukti` — you should see all files.

## GitHub repository settings (optional but recommended)

### Topics (searchability)
Add these tags:
- `trading`
- `algorithmic-trading`
- `nse`
- `india`
- `ai`
- `claude`
- `gemini`
- `async`

### About section
Copy from the README:
> Autonomous NSE trading agent. Reasons like a human, executes with DhanHQ, learns from trades. Multi-AI (Claude/Gemini), crash-safe, paper-tradable.

### Discussions (enable)
Settings → Features → Discussions (on)
- Use for trading strategy questions
- Backtesting discussions
- Feature requests

### Releases (optional)
After going live with capital (v1.0):
- Tag: `v1.0-live`
- Notes: link to live trading rules and risk management

## Keep it updated

```bash
# After any local changes
git add .
git commit -m "description of change"
git push

# Common workflows
git push                          # push current branch
git push origin master            # push master branch
git push origin --all             # push all branches
git tag v0.2 && git push --tags   # push a release tag
```

## .gitignore — what's NOT pushed

These are automatically excluded (see `.gitignore`):
- `.env` files (secrets)
- `__pycache__/` (Python bytecode)
- `logs/` (runtime logs)
- `*.csv` (trade results)
- `node_modules/` (webapp deps)
- `.pytest_cache/` (test artifacts)
- Database files, temp files, etc.

**Never** commit secrets. Use environment variables or Doppler.

## Collaboration (if inviting others)

```bash
# Add a collaborator: Settings → Collaborators → Add people
# They clone with:
git clone git@github.com:YOUR_USERNAME/yukti.git
cd yukti
uv sync
cp .env.example .env
# [edit .env with their own secrets]
```

## Troubleshooting

### "remote already exists"
```bash
git remote rm origin
git remote add origin git@github.com:YOUR_USERNAME/yukti.git
```

### "Permission denied (publickey)"
SSH key not added to GitHub. Either:
1. Add your SSH key: https://github.com/settings/ssh/new
2. Or use HTTPS instead: `git remote set-url origin https://github.com/YOUR_USERNAME/yukti.git`

### "You do not have permission to push"
If repo is not yours, you need write access. Ask the owner to add you as a collaborator.

### "Everything up-to-date"
All local commits are already on GitHub. Make a change first:
```bash
echo "# Updated" >> README.md
git add README.md
git commit -m "docs: minor update"
git push
```

## What happens next

**On your GitHub repo homepage:**
- Green checkmark (CI) if GitHub Actions pass (auto-runs tests)
- README displayed at the bottom
- Clone instructions for others
- Star/fork counts

**Other users can now:**
- Clone your repo: `git clone https://github.com/YOUR_USERNAME/yukti.git`
- Fork it (create their own copy)
- Open issues (bug reports)
- Submit pull requests (improvements)
- Use it for their own trading

---

**Pro tip:** After v0.2 paper validation, consider publishing a blog post or Twitter thread
about your approach. The repo can inspire others, and you'll get feedback before going live.

Happy trading! 🚀
