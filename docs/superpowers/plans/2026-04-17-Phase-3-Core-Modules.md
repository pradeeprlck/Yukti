# Phase 3: Strengthen Core Modules (Risk Gates + AI Brain + Execution) Implementation Plan

> **For agentic workers:** REQUIRED: Use the `subagent-driven-development` agent (recommended) or `executing-plans` agent to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen the 7 risk gates for deterministic enforcement, improve AI brain with structured decisions and conviction scoring, and enhance execution layer with crash-safe state machine and recovery.

**Architecture:** Implement risk gates as pure functions in risk/__init__.py, integrate into decision flow. Enhance agents/arjun.py with Pydantic models and system prompts. Improve execution/order_sm.py and paper_broker.py for state persistence and recovery.

**Tech Stack:** Python, Pydantic v2, Asyncio, PostgreSQL with pgvector (for future learning loop).

---

## File Structure

- Modify: `risk/__init__.py` - Update run_gates function to implement the 7 deterministic risk gates as specified.
- Modify: `agents/arjun.py` - Ensure structured JSON output and add context injection.
- Modify: `data/models.py` - Ensure TradeDecision and Portfolio models are properly defined with Pydantic v2.
- Modify: `execution/order_sm.py` - Strengthen state machine for order lifecycle.
- Modify: `execution/paper_broker.py` - Add persistence and crash recovery logic.
- Modify: `yukti/__main__.py` - Integrate gates into the decision flow.

### Task 1: Update Risk Gates in risk/__init__.py

**Files:**
- Modify: `risk/__init__.py`

- [ ] **Step 1: Update run_gates function to include all 7 gates**

```python
async def run_gates(
    trade_decision: TradeDecision,
    portfolio: Portfolio,
) -> GateResult:
    """
    Run all 7 pre-trade risk checks in order. Return first failure.
    """
    # 1. Daily loss limit not breached
    daily_pnl = await get_daily_pnl_pct()
    if daily_pnl <= -settings.daily_loss_limit_pct:
        return GateResult(False, f"daily_loss_limit: {daily_pnl:.2%} <= -{settings.daily_loss_limit_pct:.2%}")

    # 2. Max open positions / exposure not exceeded
    open_count = await count_open_positions()
    if open_count >= settings.max_open_positions:
        return GateResult(False, f"max_positions: {open_count} >= {settings.max_open_positions}")

    # 3. Conviction score >= minimum threshold
    if trade_decision.conviction < settings.min_conviction:
        return GateResult(False, f"conviction_too_low: {trade_decision.conviction} < {settings.min_conviction}")

    # 4. Reward:Risk ratio >= minimum
    if trade_decision.risk_reward and trade_decision.risk_reward < settings.min_rr:
        return GateResult(False, f"rr_too_low: {trade_decision.risk_reward:.2f} < {settings.min_rr}")

    # 5. Cooldown period passed for the symbol
    if await is_on_cooldown(trade_decision.symbol):
        return GateResult(False, f"cooldown: {trade_decision.symbol} recently traded")

    # 6. Position size fits within per-trade risk %
    position = calculate_position(...)  # Assume calculated
    if position.capital_pct > settings.max_per_trade_risk_pct:
        return GateResult(False, f"position_size_too_large: {position.capital_pct:.2f}% > {settings.max_per_trade_risk_pct:.2f}%")

    # 7. No market halt / circuit breaker conditions
    if await is_market_halted():
        return GateResult(False, "market_halt: market is halted")

    return GateResult(True)
```

- [ ] **Step 2: Add helper function is_market_halted**

```python
async def is_market_halted() -> bool:
    # Mock for now, implement real check later
    return False
```

- [ ] **Step 3: Update imports and settings**

Ensure settings has min_conviction, max_per_trade_risk_pct, etc.

- [ ] **Step 4: Run tests to verify gates work**

Run: `pytest tests/unit/test_risk.py -v`

- [ ] **Step 5: Commit**

```bash
git add risk/__init__.py
git commit -m "feat: implement 7 deterministic risk gates"
```

### Task 2: Enhance AI Brain in agents/arjun.py

**Files:**
- Modify: `agents/arjun.py`

- [ ] **Step 1: Add context injection to the prompt**

Modify the call method to inject performance context.

- [ ] **Step 2: Ensure fallback to mock provider**

Add mock provider that returns structured decisions.

- [ ] **Step 3: Update TradeDecision model if needed**

Ensure it matches the required fields.

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_arjun.py -v`

- [ ] **Step 5: Commit**

```bash
git add agents/arjun.py
git commit -m "feat: enhance AI brain with context injection and mock fallback"
```

### Task 3: Strengthen Execution Layer

**Files:**
- Modify: `execution/order_sm.py`
- Modify: `execution/paper_broker.py`

- [ ] **Step 1: Update order_sm.py for state machine**

Add states: intent, submitted, filled, rejected.

- [ ] **Step 2: Add persistence to paper_broker.py**

Save intents to database.

- [ ] **Step 3: Add crash recovery**

On startup, re-arm pending intents.

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_trade_cycle.py -v`

- [ ] **Step 5: Commit**

```bash
git add execution/order_sm.py execution/paper_broker.py
git commit -m "feat: strengthen execution layer with state machine and recovery"
```

### Task 4: Integrate into Main Flow

**Files:**
- Modify: `yukti/__main__.py`

- [ ] **Step 1: Import and call run_gates in the decision flow**

After AI decision, before execution.

- [ ] **Step 2: Log gate results**

Add rich logging for each gate.

- [ ] **Step 3: Run paper mode test**

Run: `uv run python -m yukti --mode paper`

- [ ] **Step 4: Commit**

```bash
git add yukti/__main__.py
git commit -m "feat: integrate risk gates into decision flow"
```

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-17-Phase-3-Core-Modules.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using the `executing-plans` agent, batch execution with checkpoints

**Which approach?**</content>
<parameter name="filePath">d:\Yukti\docs\superpowers\plans\2026-04-17-Phase-3-Core-Modules.md