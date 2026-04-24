"""
trainer/rewards.py

Small utilities to derive scalar rewards and labels from exported
`JournalEntry`/`Trade` records. These are intentionally simple; refine
with quant/risk before using for any automated promotion.
"""
from __future__ import annotations

from typing import Optional


def compute_reward(pnl_pct: float, outcome: str, conviction: int = 5, holding_period: str = "intraday") -> float:
    """Compute a simple scalar reward for a trade/journal entry.

    Args:
        pnl_pct: percent PnL for the trade (e.g. 1.5 for +1.5%).
        outcome: 'WIN' or 'LOSS'.
        conviction: integer conviction score (1-10).
        holding_period: one of 'intraday', 'swing', 'overnight'.

    Returns:
        A clipped float reward. Positive for wins, negative for losses.
    """
    try:
        base = float(pnl_pct)
    except Exception:
        base = 0.0

    # conviction scales reward modestly: range ~[0.5,1.5] for conviction 1-10
    conv_scale = 0.5 + (max(1, min(conviction, 10)) / 10.0)

    # horizon weight: prefer slightly longer horizon for more meaningful signals
    horizon_scale = 1.2 if holding_period == "swing" else 1.0

    reward = base * conv_scale * horizon_scale

    # Small normalization: very large pct moves capped to avoid exploding values
    reward = max(min(reward, 100.0), -100.0)
    return float(reward)


def label_from_record(pnl_pct: Optional[float], conviction: Optional[int]) -> dict:
    """Return a simple label dict used by exporters/training pipelines.

    - `outcome`: WIN/LOSS
    - `reward_estimate`: numeric reward using default heuristics
    """
    outcome = "WIN" if (pnl_pct or 0.0) > 0 else "LOSS"
    reward = compute_reward(float(pnl_pct or 0.0), outcome, int(conviction or 5))
    return {"outcome": outcome, "reward_estimate": reward}
