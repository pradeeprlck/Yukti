#!/usr/bin/env python3
"""
scripts/trigger_workflow.py

Dispatch a GitHub Actions workflow, poll for completion, and download artifacts/logs.

This helper is intended to be run locally (or CI) by the repository owner. It
does NOT require any repository changes and will not run anything on your
machine besides the requests to GitHub's REST API. Provide a token with
`repo` and `workflow` scopes via the `--token` flag or `GITHUB_TOKEN` env var.

Example:
  export GITHUB_TOKEN=...
  python scripts/trigger_workflow.py --owner myorg --repo myrepo --workflow retrain-eval.yml --ref main --wait --out_dir ./ci-artifacts

Notes:
  - Downloads artifacts and logs as zip files and extracts them under `--out_dir`.
  - Requires `requests` package: `pip install requests`
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import requests
except Exception:
    print("Missing dependency: install 'requests' (pip install requests)")
    raise

GITHUB_API = "https://api.github.com"


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


def dispatch_workflow(owner: str, repo: str, workflow: str, ref: str, token: str, inputs: Optional[Dict[str, Any]] = None) -> None:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
    payload: Dict[str, Any] = {"ref": ref}
    if inputs:
        payload["inputs"] = inputs
    r = requests.post(url, headers=_headers(token), json=payload)
    if r.status_code not in (204, 201):
        raise RuntimeError(f"Failed to dispatch workflow: {r.status_code} {r.text}")


def find_recent_run(owner: str, repo: str, workflow: str, token: str, ref: str, since: datetime) -> Optional[Dict[str, Any]]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/workflows/{workflow}/runs"
    params = {"branch": ref, "per_page": 10}
    r = requests.get(url, headers=_headers(token), params=params)
    r.raise_for_status()
    runs = r.json().get("workflow_runs", [])
    for run in runs:
        created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
        if created >= since:
            return run
    return None


def poll_run(owner: str, repo: str, run_id: int, token: str, poll_interval: int = 10, timeout: int = 1800) -> Dict[str, Any]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}"
    deadline = time.time() + timeout
    while True:
        r = requests.get(url, headers=_headers(token))
        r.raise_for_status()
        run = r.json()
        status = run.get("status")
        if status == "completed":
            return run
        if time.time() > deadline:
            raise TimeoutError("Timed out waiting for workflow run to complete")
        time.sleep(poll_interval)


def _download_file(url: str, path: str, token: str) -> None:
    r = requests.get(url, headers=_headers(token), stream=True)
    r.raise_for_status()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as fh:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                fh.write(chunk)


def _unzip(path: str, to_dir: str) -> None:
    try:
        with zipfile.ZipFile(path, "r") as z:
            z.extractall(to_dir)
    except zipfile.BadZipFile:
        # Not a zip file or corrupted; leave as-is
        pass


def download_artifacts(owner: str, repo: str, run_id: int, token: str, out_dir: str) -> List[Dict[str, str]]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts"
    r = requests.get(url, headers=_headers(token))
    r.raise_for_status()
    artifacts = r.json().get("artifacts", [])
    saved: List[Dict[str, str]] = []
    for a in artifacts:
        name = a["name"]
        dl = a.get("archive_download_url")
        if not dl:
            continue
        zip_path = os.path.join(out_dir, f"{name}.zip")
        print(f"Downloading artifact {name} -> {zip_path}")
        _download_file(dl, zip_path, token)
        extract_dir = os.path.join(out_dir, name)
        _unzip(zip_path, extract_dir)
        saved.append({"name": name, "zip": zip_path, "extracted": extract_dir})
    return saved


def download_logs(owner: str, repo: str, run_id: int, token: str, out_dir: str) -> Optional[str]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}/logs"
    zip_path = os.path.join(out_dir, f"run_{run_id}_logs.zip")
    try:
        print(f"Downloading logs -> {zip_path}")
        _download_file(url, zip_path, token)
        _unzip(zip_path, os.path.join(out_dir, f"run_{run_id}_logs"))
        return zip_path
    except Exception as ex:
        print("Failed to download logs:", ex)
        return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--workflow", default="retrain-eval.yml")
    parser.add_argument("--ref", default="main")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--wait", action="store_true", help="Wait for run to finish")
    parser.add_argument("--poll_interval", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--out_dir", default="ci-artifacts")
    args = parser.parse_args(argv)

    if not args.token:
        print("Provide a GitHub token via --token or GITHUB_TOKEN environment variable")
        return 2

    dispatch_time = datetime.now(timezone.utc)
    print(f"Dispatching workflow {args.workflow} on {args.owner}/{args.repo} @ {args.ref}")
    dispatch_workflow(args.owner, args.repo, args.workflow, args.ref, args.token)

    # Poll for the run to appear
    run = None
    start = time.time()
    while run is None and time.time() - start < 60:
        run = find_recent_run(args.owner, args.repo, args.workflow, args.token, args.ref, dispatch_time)
        if run is None:
            time.sleep(2)

    if run is None:
        print("Unable to find the workflow run after dispatch. List recent runs for debugging:")
        debug_url = f"{GITHUB_API}/repos/{args.owner}/{args.repo}/actions/workflows/{args.workflow}/runs"
        try:
            r = requests.get(debug_url, headers=_headers(args.token))
            print(r.text)
        except Exception:
            pass
        raise RuntimeError("Workflow run not found after dispatch")

    run_id = run["id"]
    print(f"Found run id={run_id} status={run.get('status')} url={run.get('html_url')}")

    if args.wait:
        final = poll_run(args.owner, args.repo, run_id, args.token, args.poll_interval, args.timeout)
        print(f"Run finished: conclusion={final.get('conclusion')}")

    os.makedirs(args.out_dir, exist_ok=True)
    artifacts = download_artifacts(args.owner, args.repo, run_id, args.token, args.out_dir)
    logs = download_logs(args.owner, args.repo, run_id, args.token, args.out_dir)
    print("Downloaded artifacts:", json.dumps(artifacts, indent=2))
    print("Downloaded logs:", logs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
