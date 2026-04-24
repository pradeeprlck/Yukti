"""
trainer/evaluate_vs_baseline.py

Run backtests for a baseline policy and a candidate adapter (optional),
compute summary metrics and a simple bootstrap comparison, and emit a
human-readable Markdown 'paper' report plus JSON artifacts.

This is a lightweight, CI-friendly evaluation harness. It uses synthetic
candles by default (deterministic seed) to allow reproducible CI runs, and
can be pointed at a saved adapter using `--adapter_dir`.

Usage (dry-run / local):
  python trainer/evaluate_vs_baseline.py --out_dir artifacts/eval --symbols RELIANCE HDFCBANK

With adapter:
  python trainer/evaluate_vs_baseline.py --adapter_dir models/lora-candidate --base_model facebook/opt-125m --out_dir artifacts/eval

Note: this script does NOT call remote LLMs; loading an adapter requires
having the base model + PEFT artifacts available locally and appropriate
hardware if the model is large.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import statistics
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def generate_synthetic_candles(symbols: List[str], start: str, end: str, seed: int = 42) -> Dict[str, pd.DataFrame]:
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    dates = pd.date_range(start=start_dt, end=end_dt, freq="D")
    candles: Dict[str, pd.DataFrame] = {}
    rng = np.random.default_rng(seed)
    for i, sym in enumerate(symbols):
        r = np.random.default_rng(seed + i)
        base = 1000.0 + (r.normal(0, 1, len(dates)).cumsum())
        close = np.round(base + r.normal(0, 2, len(dates)), 2)
        openp = np.round(np.roll(close, 1), 2)
        openp[0] = close[0]
        high = np.round(np.maximum(openp, close) + r.uniform(0, 3, len(dates)), 2)
        low = np.round(np.minimum(openp, close) - r.uniform(0, 3, len(dates)), 2)
        volume = r.integers(1000, 10000, size=len(dates))
        df = pd.DataFrame({"time": dates, "open": openp, "high": high, "low": low, "close": close, "volume": volume})
        df = df.set_index("time")
        candles[sym] = df
    return candles


class ProviderWrapper:
    """Wrap a provider with a `safe_decide(context)` method expected by backtests.
    Accepts either an object implementing `call(context)` coroutine (BaseProvider)
    or an object already exposing `safe_decide`.
    """

    def __init__(self, provider):
        self._provider = provider

    async def safe_decide(self, context: str):
        # If provider already exposes safe_decide, use it directly.
        if hasattr(self._provider, "safe_decide"):
            return await self._provider.safe_decide(context)
        # Otherwise call .call() and return the decision part.
        dec, _ = await self._provider.call(context)
        return dec


async def run_backtest_with_agent(cand_name: str, candles: Dict[str, pd.DataFrame], nifty_df: pd.DataFrame, out_dir: str, adapter_dir: str | None = None, base_model: str | None = None, device: str = "cpu") -> Dict:
    """Run BacktestEngine with the requested agent and return metrics dict."""
    from yukti.backtest import BacktestEngine
    import yukti.agents.arjun as arjun_module

    # Configure agent
    if adapter_dir and cand_name == "candidate":
        try:
            from yukti.agents.local_adapter import LocalArjun

            arjun_module.arjun = LocalArjun(adapter_dir=adapter_dir, base_model=base_model, device=device)
            print(f"Loaded LocalArjun adapter from {adapter_dir}")
        except Exception as exc:
            print("Failed to load LocalArjun adapter, falling back to MockProvider:", exc)
            arjun_module.arjun = ProviderWrapper(arjun_module.MockProvider())
    else:
        # baseline: use MockProvider wrapped to provide safe_decide
        arjun_module.arjun = ProviderWrapper(arjun_module.MockProvider())

    engine = BacktestEngine(candles, nifty_df, account_value=500_000.0, claude_sample_rate=1.0)
    report = await engine.run()

    os.makedirs(out_dir, exist_ok=True)
    trades_csv = os.path.join(out_dir, f"{cand_name}_trades.csv")
    try:
        report.to_csv(trades_csv)
    except Exception:
        # Fallback: try to materialize trades list
        try:
            rows = []
            for t in report.trades:
                rows.append({k: getattr(t, k, None) for k in dir(t) if not k.startswith("_") and not callable(getattr(t, k))})
            pd.DataFrame(rows).to_csv(trades_csv, index=False)
        except Exception:
            print("Could not write trades CSV for", cand_name)

    # Compute metrics
    trades = getattr(report, "trades", [])
    total = len(trades)
    winners = [t for t in trades if getattr(t, "pnl", 0) > 0]
    losers = [t for t in trades if getattr(t, "pnl", 0) <= 0]
    win_rate = len(winners) / total if total else 0.0

    gross_profit = sum(getattr(t, "pnl", 0) for t in winners)
    gross_loss = abs(sum(getattr(t, "pnl", 0) for t in losers)) or 1.0
    profit_factor = gross_profit / gross_loss if gross_loss else None

    pnl_pcts = [getattr(t, "pnl_pct", None) for t in trades]
    pnl_pcts = [p for p in pnl_pcts if p is not None]
    avg_win = float(np.mean([p for p in pnl_pcts if p > 0])) if any(p > 0 for p in pnl_pcts) else 0.0
    avg_loss = float(np.mean([p for p in pnl_pcts if p <= 0])) if any(p <= 0 for p in pnl_pcts) else 0.0

    eq = getattr(report, "equity_curve", pd.DataFrame())
    try:
        eq_series = eq["account_value"] if not eq.empty else pd.Series([getattr(report, "initial_value", 500000.0), getattr(report, "final_value", 500000.0)])
        peak = eq_series.cummax()
        dd = ((eq_series - peak) / peak * 100)
        max_dd = float(dd.min()) if not dd.empty else 0.0
    except Exception:
        max_dd = 0.0

    total_return = (getattr(report, "final_value", 0.0) - getattr(report, "initial_value", 0.0)) / max(1.0, getattr(report, "initial_value", 1.0)) * 100

    metrics = {
        "name": cand_name,
        "total_trades": total,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "max_drawdown_pct": max_dd,
        "total_return_pct": total_return,
        "final_value": getattr(report, "final_value", None),
    }

    metrics_path = os.path.join(out_dir, f"{cand_name}_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)

    return {
        "metrics": metrics,
        "pnl_pcts": pnl_pcts,
        "trades_csv": trades_csv,
    }


def bootstrap_compare(a: List[float], b: List[float], n: int = 2000) -> Dict:
    if not a or not b:
        return {"bootstrap_n": n, "p_value_two_sided": None, "mean_diff": None, "ci": None}
    diffs = []
    for _ in range(n):
        sa = np.random.choice(a, size=len(a), replace=True)
        sb = np.random.choice(b, size=len(b), replace=True)
        diffs.append(np.mean(sb) - np.mean(sa))
    diffs = np.array(diffs)
    mean_diff = float(np.mean(diffs))
    lo, hi = np.percentile(diffs, [2.5, 97.5]).tolist()
    p_one = float((diffs <= 0).mean())
    p_two = float(2.0 * min(p_one, 1.0 - p_one))
    return {"bootstrap_n": n, "mean_diff": mean_diff, "ci": [lo, hi], "p_value_two_sided": p_two}


async def main_async(args):
    symbols = args.symbols or ["RELIANCE", "HDFCBANK"]
    candles = generate_synthetic_candles(symbols, args.start, args.end, seed=args.seed)
    nifty_df = pd.DataFrame({"close": np.mean([df["close"].values for df in candles.values()], axis=0)}, index=next(iter(candles.values())).index)

    os.makedirs(args.out_dir, exist_ok=True)

    baseline = await run_backtest_with_agent("baseline", candles, nifty_df, args.out_dir)
    candidate = None
    if args.adapter_dir:
        candidate = await run_backtest_with_agent("candidate", candles, nifty_df, args.out_dir, adapter_dir=args.adapter_dir, base_model=args.base_model, device=args.device)

    # Compare
    if candidate:
        comp = bootstrap_compare(baseline["pnl_pcts"], candidate["pnl_pcts"], n=args.bootstrap)
    else:
        comp = {}

    # Write human report
    report_md = os.path.join(args.out_dir, "compare_report.md")
    with open(report_md, "w", encoding="utf-8") as fh:
        fh.write(f"# Backtest Comparison Report\n\n")
        fh.write(f"Generated: {datetime.utcnow().isoformat()}Z\n\n")
        fh.write("## Baseline metrics\n")
        fh.write(json.dumps(baseline["metrics"], indent=2))
        fh.write("\n\n")
        if candidate:
            fh.write("## Candidate metrics\n")
            fh.write(json.dumps(candidate["metrics"], indent=2))
            fh.write("\n\n")
            fh.write("## Comparison (bootstrap on per-trade pnl %)\n")
            fh.write(json.dumps(comp, indent=2))
            fh.write("\n\n")
            fh.write(f"Baseline trades CSV: {baseline['trades_csv']}\n")
            fh.write(f"Candidate trades CSV: {candidate['trades_csv']}\n")
        else:
            fh.write("No candidate adapter provided; only baseline run completed.\n")

    # Save combined metrics
    combined = {"baseline": baseline["metrics"], "candidate": (candidate["metrics"] if candidate else None), "comparison": comp}
    with open(os.path.join(args.out_dir, "compare_metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(combined, fh, indent=2)

    print("Evaluation complete. Report:", report_md)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--adapter_dir", default=None, help="Path to PEFT adapter or full model directory for candidate")
    p.add_argument("--base_model", default=None, help="Base model id (required if adapter is PEFT) e.g. facebook/opt-125m")
    p.add_argument("--device", default="cpu")
    p.add_argument("--symbols", nargs="*", default=None)
    p.add_argument("--start", default=(datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d"))
    p.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"))
    p.add_argument("--out_dir", default="artifacts/eval")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--bootstrap", type=int, default=2000)
    args = p.parse_args(argv)
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
