# Push Yukti to GitHub — Complete Instructions

The entire codebase is ready and already committed locally. Here's how to push it to GitHub in 5 minutes.

## What you're pushing

- **86 files** across 9,400+ lines of Python
- **3 git commits** with full history
- **Documentation**: README.md, GITHUB_SETUP.md, DEPLOYMENT.md
- **All code**: agent, web portal, tests, deployment configs
- **.gitignore** configured to never commit secrets

## Step 1: Create an empty GitHub repository

### Via GitHub web UI (easiest)

1. Go to https://github.com/new
2. Fill in:
   - **Repository name:** `yukti` (or `yukti-trading-agent`)
   - **Description:** "Autonomous NSE/BSE trading agent with Claude/Gemini AI"
   - **Visibility:** `Private` (strongly recommended — contains trading logic)
   - **Initialize this repository with:** *Leave all unchecked*
3. Click "Create repository"

GitHub will show a page with commands like:

```
…or push an existing repository from the command line

git remote add origin https://github.com/YOUR_USERNAME/yukti.git
git branch -M main
git push -u origin main
```

**Copy these commands — you'll use them in Step 2.**

---

## Step 2: Add remote and push

Open a terminal on your machine:

```bash
# Navigate to the local repo
cd /home/claude/yukti

# Add GitHub as remote (copy from Step 1)
git remote add origin https://github.com/YOUR_USERNAME/yukti.git

# Verify the remote was added
git remote -v
```

You should see:
```
origin  https://github.com/YOUR_USERNAME/yukti.git (fetch)
origin  https://github.com/YOUR_USERNAME/yukti.git (push)
```

### If you already have a different remote

```bash
# Remove the old one
git remote remove origin

# Add the new one
git remote add origin https://github.com/YOUR_USERNAME/yukti.git
```

### Push to GitHub

```bash
# Rename branch to 'main' (matches GitHub default)
git branch -M main

# Push all commits and set up tracking
git push -u origin main
```

You'll see output like:

```
Enumerating objects: 89, done.
Counting objects: 100% (89/89), done.
Delta compression using up to 8 threads
Compressing objects: 100% (75/75), done.
Writing objects: 100% (89/89), 145.23 KiB | 18.15 MiB/s, done.
Total 89 (delta 0), reused 0 (delta 0), pack-reused 0
remote: Validating objects: 100%
remote:
To https://github.com/YOUR_USERNAME/yukti.git
 * [new branch]      main -> main
Branch 'main' set up to track remote branch 'main' from 'origin'.
```

**✅ Done! Your code is now on GitHub.**

---

## Step 3: Verify on GitHub

1. Go to https://github.com/YOUR_USERNAME/yukti
2. You should see:
   - **3 commits** in the history
   - **86 files** in the repo
   - README.md displayed on the homepage
   - Folders: `yukti/`, `webapp/`, `scripts/`, `tests/`, `deploy/`, `.github/`

---

## Step 4: Secure your repository (recommended)

### Protect the main branch

1. Go to **Settings** → **Branches**
2. Click "Add rule"
3. Branch name pattern: `main`
4. Enable:
   - ✅ "Require a pull request before merging"
   - ✅ "Require status checks to pass before merging"
   - ✅ "Dismiss stale pull request approvals when new commits are pushed"
5. Save changes

This ensures you review all changes before merging.

### Add GitHub Secrets (optional, for CI/CD)

If you plan to set up automated testing or deployment:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click "New repository secret"
3. Add these (used in CI tests, **not** for the agent itself):
   - `ANTHROPIC_API_KEY` — for test runs
   - `DOPPLER_TOKEN` — if using Doppler for secrets

---

## Step 5: Clone on another machine (optional test)

To verify the push worked, clone on a different machine:

```bash
# On any machine with git
git clone https://github.com/YOUR_USERNAME/yukti.git
cd yukti

# Verify you see all the files
ls -la | head -20

# Verify git history
git log --oneline | head -5
```

Expected:
```
158fadc docs: add comprehensive deployment guide for DigitalOcean + ops runbook
df797ce docs: add GitHub setup guide
4fcf47a Initial commit: Yukti autonomous NSE trading agent
```

---

## Ongoing development workflow

After pushing to GitHub, here's how to work with the code:

### Make changes locally

```bash
# Make edits to files
nano yukti/agents/quality.py

# Stage changes
git add yukti/agents/quality.py

# Commit with a meaningful message
git commit -m "feat: improve conviction signal detection"

# Push to GitHub
git push origin main
```

### Create a feature branch (recommended)

For larger changes, use a feature branch:

```bash
# Create and switch to a new branch
git checkout -b feature/shadow-mode-enhancements

# Make changes and commit
git add .
git commit -m "feat: shadow mode now supports partial fills"

# Push the branch
git push -u origin feature/shadow-mode-enhancements

# On GitHub: create a pull request from your branch
# Review → merge to main
```

### Pull latest code

Before starting work, get the latest:

```bash
git pull origin main
```

---

## Common issues and solutions

### "fatal: remote origin already exists"

You already added the remote. Remove it first:

```bash
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/yukti.git
git push -u origin main
```

### "Permission denied (publickey)"

GitHub needs your SSH key or HTTPS credentials.

**Option A: Use HTTPS (easier)**
```bash
# Use the HTTPS URL instead
git remote set-url origin https://github.com/YOUR_USERNAME/yukti.git
git push -u origin main

# GitHub will ask for username + personal access token
# Generate a token: https://github.com/settings/tokens
```

**Option B: Use SSH (more secure)**
1. Generate SSH key: https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-gpg-key
2. Add to GitHub: https://github.com/settings/ssh/new
3. Use SSH URL:
```bash
git remote set-url origin git@github.com:YOUR_USERNAME/yukti.git
git push -u origin main
```

### "fatal: cannot access 'https://github.com/...': Could not resolve host"

Check your internet connection:

```bash
ping github.com
```

If that fails, you're offline. Wait and try again.

### "Updates were rejected because the tip of your current branch is behind..."

Someone else pushed to the same branch. Pull first:

```bash
git pull origin main
git push origin main
```

### Wrong repository URL / need to change it

```bash
git remote set-url origin https://github.com/YOUR_USERNAME/NEW_REPO_NAME.git
git push -u origin main
```

---

## What NOT to commit

The `.gitignore` file already protects these, but double-check:

- ❌ `.env` files with real API keys
- ❌ `logs/` directory with trade logs
- ❌ `*.csv` backtest results
- ❌ `webapp/node_modules/`
- ❌ `__pycache__/` directories
- ❌ Any files containing DhanHQ tokens or Anthropic keys

If you accidentally committed secrets:

```bash
# IMMEDIATELY revoke the compromised token on the provider's website
# Then remove it from git history:
git filter-branch --tree-filter 'rm -f .env' HEAD
git push --force origin main

# But this rewrites history, so do it ASAP before anyone else clones
```

Better: use GitHub Secrets or Doppler for any sensitive data in CI/CD.

---

## Next: Deploy on DigitalOcean

Once the code is on GitHub, deploying is one command:

```bash
# On your DigitalOcean droplet
git clone https://github.com/YOUR_USERNAME/yukti.git
cd yukti
cp .env.example .env
# Edit .env with real credentials
docker compose up -d
```

See `DEPLOYMENT.md` for the full guide.

---

## Summary

You now have:

✅ Code pushed to GitHub  
✅ Repository private (secrets safe)  
✅ Main branch protected (review required)  
✅ Ready to clone on any machine  
✅ Ready to deploy on DigitalOcean / your VM  

**Next step:** Follow `DEPLOYMENT.md` to run the agent on a fresh VM.

Good luck! 🚀
