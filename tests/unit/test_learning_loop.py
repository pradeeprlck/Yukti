"""tests/unit/test_learning_loop.py — unit tests for LearningLoopService

These tests mock DB access and the embedding call so no external services are used.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import pytest


class FakeRow:
    def __init__(self, id: int, entry_text: str):
        self.id = id
        self.entry_text = entry_text
        self.embedding = None


class FakeSession:
    def __init__(self, rows: list[FakeRow]):
        self._rows = rows
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, q, *args, **kwargs):
        class R:
            def __init__(self, rows):
                self._rows = rows

            def scalars(self):
                return self

            def all(self):
                return self._rows

        return R(self._rows)

    def add(self, obj):
        self.added.append(obj)


@asynccontextmanager
async def fake_get_db_ctx():
    rows = [FakeRow(1, "one"), FakeRow(2, "two")]
    sess = FakeSession(rows)
    yield sess


async def fake_embed(texts, input_type="document"):
    # return deterministic 1024-d vectors for each text
    return [[float(i)] * 1024 for i, _ in enumerate(texts, start=1)]


@pytest.mark.asyncio
async def test_run_once_embeds(monkeypatch):
    # Patch the module-level dependencies in learning_loop_service
    monkeypatch.setattr("yukti.services.learning_loop_service.get_db", fake_get_db_ctx)
    monkeypatch.setattr("yukti.services.learning_loop_service._embed", fake_embed)
    # Ensure the settings check passes
    monkeypatch.setattr("yukti.services.learning_loop_service.settings.voyage_api_key", "fake", raising=False)

    from yukti.services.learning_loop_service import LearningLoopService

    svc = LearningLoopService(batch_size=2)
    processed = await svc.run_once()
    assert processed == 2
