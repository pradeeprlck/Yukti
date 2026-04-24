"""
yukti/agents/canary.py

Helpers to manage the active canary pointer and traffic ratio.
Uses Redis when available, falls back to files under models/canary/.
"""
from __future__ import annotations

import os
import json
import random
from typing import Optional

from yukti.config import settings

CANARY_DIR = os.path.join("models", "canary")
ACTIVE_KEY = "yukti:canary:active"
PREV_KEY = "yukti:canary:previous"
RATIO_KEY = "yukti:canary:ratio"


async def _get_redis() -> Optional[object]:
    try:
        from yukti.data.state import get_redis
        return await get_redis()
    except Exception:
        return None


async def get_active_canary() -> Optional[str]:
    """Return the active canary model dir or None."""
    r = await _get_redis()
    if r is not None:
        try:
            val = await r.get(ACTIVE_KEY)
            if val:
                return val.decode() if isinstance(val, (bytes, bytearray)) else val
        except Exception:
            pass
    # file fallback
    try:
        p = os.path.join(CANARY_DIR, "active.txt")
        if os.path.exists(p):
            with open(p, "r") as f:
                return f.read().strip() or None
    except Exception:
        pass
    return None


async def set_active_canary(path: Optional[str]) -> None:
    """Set the active canary model dir. Stores previous value for rollback."""
    os.makedirs(CANARY_DIR, exist_ok=True)
    r = await _get_redis()
    prev = None
    if r is not None:
        try:
            prev = await r.get(ACTIVE_KEY)
            if prev and isinstance(prev, (bytes, bytearray)):
                prev = prev.decode()
            await r.set(PREV_KEY, prev or "")
            await r.set(ACTIVE_KEY, path or "")
        except Exception:
            prev = None
    # file fallback
    try:
        p = os.path.join(CANARY_DIR, "active.txt")
        prev_p = os.path.join(CANARY_DIR, "previous.txt")
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    prev = f.read()
            except Exception:
                prev = None
        with open(prev_p, "w") as f:
            f.write(prev or "")
        with open(p, "w") as f:
            f.write(path or "")
    except Exception:
        pass


async def get_canary_ratio() -> float:
    r = await _get_redis()
    if r is not None:
        try:
            v = await r.get(RATIO_KEY)
            if v:
                v = v.decode() if isinstance(v, (bytes, bytearray)) else v
                return float(v)
        except Exception:
            pass
    # file fallback
    try:
        p = os.path.join(CANARY_DIR, "ratio.json")
        if os.path.exists(p):
            with open(p, "r") as f:
                data = json.load(f)
                return float(data.get("ratio", settings.canary_ratio))
    except Exception:
        pass
    return float(settings.canary_ratio)


async def set_canary_ratio(ratio: float) -> None:
    os.makedirs(CANARY_DIR, exist_ok=True)
    r = await _get_redis()
    if r is not None:
        try:
            await r.set(RATIO_KEY, str(ratio))
        except Exception:
            pass
    # file fallback
    try:
        p = os.path.join(CANARY_DIR, "ratio.json")
        with open(p, "w") as f:
            json.dump({"ratio": float(ratio)}, f)
    except Exception:
        pass


async def should_route_to_canary() -> bool:
    """Return True if this call should be routed to canary, based on ratio."""
    ratio = await get_canary_ratio()
    try:
        r = float(ratio)
    except Exception:
        r = float(settings.canary_ratio)
    if r <= 0.0:
        return False
    if r >= 1.0:
        return True
    return random.random() < r


async def get_previous_active() -> Optional[str]:
    r = await _get_redis()
    if r is not None:
        try:
            prev = await r.get(PREV_KEY)
            if prev:
                return prev.decode() if isinstance(prev, (bytes, bytearray)) else prev
        except Exception:
            pass
    try:
        prev_p = os.path.join(CANARY_DIR, "previous.txt")
        if os.path.exists(prev_p):
            with open(prev_p, "r") as f:
                return f.read().strip() or None
    except Exception:
        pass
    return None
