import pytest


@pytest.mark.asyncio
async def test_retrieve_similar_formats_results(monkeypatch):
    """Mock embeddings and DB to validate formatted retrieval output."""
    from yukti.agents import memory

    async def fake_embed(texts, input_type="query"):
        return [[0.1, 0.2, 0.3]]

    class FakeRow:
        def __init__(self):
            self.entry_text = "sample journal text"
            self.pnl_pct = 1.5
            self.setup_type = "ORB"
            self.direction = "LONG"
            self.symbol = "ABC"
            self.similarity = 0.87

    def fake_get_db():
        class DBCtx:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def execute(self, sql, params):
                class Res:
                    def fetchall(self):
                        return [FakeRow()]

                return Res()

        return DBCtx()

    monkeypatch.setattr(memory, "_embed", fake_embed)
    monkeypatch.setattr("yukti.data.database.get_db", fake_get_db)

    out = await memory.retrieve_similar("ABC", "ORB", "LONG", top_k=1)
    assert out
    assert "Past Similar Trades" in out
    assert "ABC" in out


@pytest.mark.asyncio
async def test_retrieve_similar_embed_failure_returns_empty(monkeypatch):
    from yukti.agents import memory

    async def fake_embed(texts, input_type="query"):
        raise RuntimeError("embed fail")

    monkeypatch.setattr(memory, "_embed", fake_embed)

    # Ensure DB fallback returns no rows so function yields empty string
    def fake_get_db_empty():
        class DBCtx:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def execute(self, sql, params):
                class Res:
                    def fetchall(self):
                        return []

                return Res()

        return DBCtx()

    monkeypatch.setattr("yukti.data.database.get_db", fake_get_db_empty)

    out = await memory.retrieve_similar("ABC", "ORB", "LONG")
    assert out == ""
