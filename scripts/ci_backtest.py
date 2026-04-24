"""
scripts/ci_backtest.py

CI-friendly backtest harness that runs a lightweight backtest using synthetic
or repo-provided candles, mocks the AI decision path, and emits a JSON metrics
file suitable for CI gating and human review.

Outputs:
  - artifacts/backtest/backtest_metrics.json
  - artifacts/backtest/backtest_trades.csv
  - artifacts/backtest/backtest_log.txt

This script intentionally avoids calling external LLMs; it injects a simple
deterministic decision policy for reproducible CI evaluation.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd


def generate_synthetic_candles(symbols: List[str], start: str, end: str) -> Dict[str, pd.DataFrame]:
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    dates = pd.date_range(start=start_dt, end=end_dt, freq="D")
    candles: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        rng = np.random.default_rng(abs(hash(sym)) % (2**32))
        base = 1000.0 + (rng.normal(0, 1, len(dates)).cumsum())
        close = np.round(base + rng.normal(0, 2, len(dates)), 2)
        openp = np.round(np.roll(close, 1), 2)
        openp[0] = close[0]
        high = np.round(np.maximum(openp, close) + rng.uniform(0, 3, len(dates)), 2)
        low = np.round(np.minimum(openp, close) - rng.uniform(0, 3, len(dates)), 2)
        volume = rng.integers(1000, 10000, size=len(dates))
        df = pd.DataFrame({"time": dates, "open": openp, "high": high, "low": low, "close": close, "volume": volume})
        df = df.set_index("time")
        candles[sym] = df
    return candles


class FakeArjun:
    """Deterministic decision maker for CI backtests."""

    async def safe_decide(self, context: str):
        # Extract symbol
        try:
            symbol = context.split("STOCK: ")[1].split(" ══")[0].strip()
        except Exception:
            symbol = "UNKNOWN"

        # Extract price
        m = re.search(r"Price\s*:\s*₹([0-9,\.]+)", context)
        price = float(m.group(1).replace(",", "")) if m else 100.0

        stop = round(price * 0.99, 2)
        t1 = round(price * 1.02, 2)
        t2 = round(price * 1.04, 2)

        # Lazy import to avoid heavy module dependencies at top-level
        from yukti.agents.arjun import TradeDecision

        decision = TradeDecision(
            symbol=symbol,
            action="TRADE",
            direction="LONG",
            market_bias="NEUTRAL",
            setup_type="ci_mock",
            reasoning="CI mock decision",
            entry_price=price,
            entry_type="LIMIT",
            stop_loss=stop,
            target_1=t1,
            target_2=t2,
            conviction=7,
            risk_reward=round((t1 - price) / (price - stop), 2) if price != stop else None,
            holding_period="intraday",
        )
        return decision


async def run_backtest(candles: Dict[str, pd.DataFrame], nifty_df: pd.DataFrame, out_dir: str) -> None:
    from yukti.backtest import BacktestEngine
    import yukti.agents.arjun as arjun_module

    # Optionally load a local adapter if environment variable set
    adapter_dir = os.environ.get("CI_ADAPTER_DIR")
    base_model = os.environ.get("CI_BASE_MODEL")
    if adapter_dir:
        try:
            from yukti.agents.local_adapter import LocalArjun

            arjun_module.arjun = LocalArjun(adapter_dir=adapter_dir, base_model=base_model, device=os.environ.get("CI_DEVICE", "cpu"))
            print("Loaded local adapter for backtest from", adapter_dir)
        except Exception as e:
            print("Failed to load local adapter; falling back to FakeArjun:", e)
            arjun_module.arjun = FakeArjun()
    else:
        # Inject fake Arjun to avoid external LLM calls
        arjun_module.arjun = FakeArjun()

    engine = BacktestEngine(candles, nifty_df, account_value=500_000.0, claude_sample_rate=1.0)
    report = await engine.run()

    os.makedirs(out_dir, exist_ok=True)
    trades_csv = os.path.join(out_dir, "backtest_trades.csv")
    report.to_csv(trades_csv)

    # Compute metrics
    trades = report.trades
    total = len(trades)
    winners = [t for t in trades if t.pnl > 0]
    losers = [t for t in trades if t.pnl <= 0]
    win_rate = len(winners) / total if total else 0.0
    gross_profit = sum(t.pnl for t in winners)
    gross_loss = abs(sum(t.pnl for t in losers)) or 1.0
    profit_factor = gross_profit / gross_loss if gross_loss else None

    avg_win = float(np.mean([t.pnl_pct for t in winners])) if winners else 0.0
    avg_loss = float(np.mean([t.pnl_pct for t in losers])) if losers else 0.0

    eq = report.equity_curve["account_value"] if not report.equity_curve.empty else pd.Series([report.initial_value, report.final_value])
    peak = eq.cummax()
    dd = ((eq - peak) / peak * 100)
    max_dd = float(dd.min()) if not dd.empty else 0.0

    total_return = (report.final_value - report.initial_value) / report.initial_value * 100

    metrics = {
        "total_trades": total,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "max_drawdown_pct": max_dd,
        "total_return_pct": total_return,
        "final_value": report.final_value,
    }

    metrics_path = os.path.join(out_dir, "backtest_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)

    print("Backtest complete. Metrics:", json.dumps(metrics, indent=2))


def main():
    parser = argparse.ArgumentParser(description="CI Backtest harness — synthetic candles + deterministic decisions")
    parser.add_argument("--start", default=(datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d"))
    parser.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--symbols", nargs="*", default=["RELIANCE", "HDFCBANK"]) 
    parser.add_argument("--out_dir", default="artifacts/backtest")
    args = parser.parse_args()

    candles = generate_synthetic_candles(args.symbols, args.start, args.end)
    # Nifty DF: simple average of symbol closes
    nifty_df = pd.DataFrame({"close": np.mean([df["close"].values for df in candles.values()], axis=0)}, index=next(iter(candles.values())).index)

    asyncio.run(run_backtest(candles, nifty_df, args.out_dir))


if __name__ == "__main__":
    main()
