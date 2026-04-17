# Codebase Design Review (2026-04-17)

This review focuses on architecture-level design risks and high-leverage improvements for reliability, maintainability, and production readiness.

## Strengths

- Clear modular separation of concerns (`api`, `execution`, `signals`, `risk`, `data`, `scheduler`) and mostly async-first design.
- Good intent toward crash safety in order state handling through staged persistence in `order_sm.py`.
- Runtime configuration is centralized in a typed `Settings` model.

## Key design flaws and improvements

### 1) Runtime state heavily depends on Redis hot keys with non-scalable access patterns

**Issue**
- `get_all_positions()` and `count_open_positions()` use Redis `KEYS` over wildcard patterns, which is O(N) and blocks Redis on large keyspaces.
- Daily and trade counters rely on fixed 24h TTLs rather than market-day boundaries; this can drift vs exchange day and timezone.

**Evidence**
- `data/state.py` uses `keys("yukti:positions:*")` and 86,400-second expiries.

**Recommendation**
- Replace `KEYS` with `SCAN` + batched `MGET`.
- Move authoritative open-position state to PostgreSQL and treat Redis as cache.
- Reset counters by explicit scheduler job at market-day boundary (IST), not TTL.

### 2) API lifecycle/background tasks are not managed for graceful shutdown

**Issue**
- API lifespan starts `_push_loop()` via `asyncio.create_task` but does not keep a task handle or cancel/join it on shutdown.
- WebSocket connection manager may raise errors on duplicate disconnects (`list.remove`) and has no lock around shared mutable list.

**Evidence**
- `api/main.py` creates `_push_loop` task in lifespan without cancellation.
- `ConnectionManager.disconnect()` directly calls `self._active.remove(ws)`.

**Recommendation**
- Store created tasks in app state and cancel them during shutdown.
- Use a set for active connections and guard mutations with an `asyncio.Lock`.
- Add connection-level backpressure/timeouts for slow clients.

### 3) Orchestrator in `__main__.py` is too monolithic and mixes infrastructure wiring with business loops

**Issue**
- Startup, recovery, scheduler, telegram, API server, watchdog, and signal scanning are all orchestrated in one module with large functions and many dynamic imports.
- This makes testing hard and increases coupling between subsystems.

**Evidence**
- `__main__.py` contains large orchestration functions (`_run_paper_or_live`, `_signal_loop`, `_scan_symbol`) and dynamic imports inside functions.

**Recommendation**
- Introduce an explicit `Application`/`Runtime` composition root and separate services:
  - `BootstrapService`
  - `MarketScanService`
  - `ExecutionService`
  - `ControlPlaneService` (API + Telegram + kill-switch)
- Use dependency injection at composition root to simplify test stubbing.

### 4) Signal loop error handling hides failures and weakens observability

**Issue**
- Per-symbol scans run via `asyncio.gather(..., return_exceptions=True)` but exceptions are not aggregated or surfaced as structured error metrics/logs.
- Backpressure flag `cycle_in_progress` is redundant in a single-threaded while loop and may give a false sense of protection.

**Evidence**
- `__main__.py` gathers with `return_exceptions=True` and does not handle returned exceptions.

**Recommendation**
- Capture gathered results and increment error counters per symbol / subsystem.
- Replace ad-hoc backpressure flag with bounded worker queue model.
- Add per-cycle SLO metrics: scan duration, symbols failed, AI latency percentiles, broker API error rate.

### 5) Order lifecycle accounting may overcount trading activity

**Issue**
- `increment_trades_today()` is called immediately after order placement, before confirmed fill.
- Cancelled/unfilled entries can still count as “trades today”, skewing risk gates and analytics.

**Evidence**
- `execution/order_sm.py` increments trade count before `_wait_for_fill` outcome is known.

**Recommendation**
- Split metrics into `orders_placed`, `orders_filled`, and `trades_opened`.
- Only increment risk-gate “trades today” after minimum-fill threshold is met.

### 6) CORS and API surface defaults are unsafe for production by default

**Issue**
- API currently allows any origin/method/header (`"*"`).

**Evidence**
- `api/main.py` configures permissive wildcard CORS.

**Recommendation**
- Configure strict allowlist from environment and fail closed in `live` mode.

### 7) Testing posture is underpowered for a high-risk domain

**Issue**
- Test suite exists but local run fails immediately when dependencies are missing, indicating weak reproducibility and CI preflight.
- Given trading-critical logic, crash recovery and reconciliation need deterministic integration tests with fault injection.

**Evidence**
- `pytest -q` currently fails at import due to missing dependencies.

**Recommendation**
- Add reproducible test environment (`uv sync --extra dev` or CI lock step) and mandatory CI gates.
- Add scenario tests for: partial fills, GTT arm failure, process crash at each checkpoint, Redis/Postgres outage handling.

## Suggested implementation order (highest ROI first)

1. **State/data correctness**: fix trade counters, move authoritative state to Postgres, eliminate `KEYS`.
2. **Resilience**: lifecycle-managed background tasks and stronger scan-loop exception accounting.
3. **Architecture**: split `__main__.py` orchestration into injectable services.
4. **Security/ops**: tighten CORS and add live-mode safety defaults.
5. **Testing**: add fault-injection integration tests and CI reproducibility checks.

## 30-day target outcomes

- Zero silent symbol-scan failures (all exceptions surfaced in metrics).
- No Redis blocking operations in hot paths.
- Accurate distinction between placed vs filled trade counts.
- Graceful shutdown/restart without orphan loops.
- Deterministic recovery tests passing in CI.
