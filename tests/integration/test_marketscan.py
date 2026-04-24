import pytest


@pytest.mark.asyncio
async def test_run_single_scan_calls_scan_symbol(monkeypatch):
    from yukti.services.market_scan_service import MarketScanService

    ms = MarketScanService({"ABC": "1", "XYZ": "2"})
    called = []

    async def fake_scan_symbol(symbol, security_id, macro, perf):
        called.append(symbol)

    async def fake_is_halted():
        return False

    async def fake_get_perf():
        return {}

    async def fake_get_macro():
        from yukti.services.macro_context_service import MacroContext

        return MacroContext(nifty_chg_pct=0.0, nifty_trend="UP", headlines=[])

    monkeypatch.setattr(ms, "_scan_symbol", fake_scan_symbol)
    monkeypatch.setattr("yukti.services.market_scan_service.is_halted", fake_is_halted)
    monkeypatch.setattr("yukti.services.market_scan_service.get_performance_state", fake_get_perf)
    monkeypatch.setattr(ms, "_get_macro_context", fake_get_macro)

    await ms.run_single_scan()
    assert set(called) == {"ABC", "XYZ"}
