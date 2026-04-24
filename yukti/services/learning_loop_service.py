"""
yukti/services/learning_loop_service.py
Background service to embed journal entries (Voyage AI) and persist vectors into pgvector.

Design goals:
- Batch un-embedded `journal_entries` rows (FOR UPDATE SKIP LOCKED)
- Call the shared embedding helper in `yukti.agents.memory` in bulk
- Persist embeddings back to Postgres (pgvector column)
- Safe to run as a scheduled job (config-gated) or manual runner
"""
from __future__ import annotations

import asyncio
import logging
from typing import List

from sqlalchemy import select

from yukti.config import settings
from yukti.data.database import get_db
from yukti.data.models import JournalEntry
from yukti.agents.memory import _embed

log = logging.getLogger(__name__)


class LearningLoopService:
    """Batch embedding service for post-trade journal entries.

    Use `run_once()` for a single batch run, or `run_forever()` to poll.
    """

    def __init__(self, batch_size: int | None = None) -> None:
        self.batch_size = int(batch_size or getattr(settings, "learning_loop_batch_size", 50))

    async def run_once(self, batch_size: int | None = None) -> int:
        """Process up to `batch_size` un-embedded journal entries and persist vectors.

        Returns the number of entries processed.
        """
        batch = int(batch_size or self.batch_size)

        if not getattr(settings, "voyage_api_key", None):
            log.warning("LearningLoop: Voyage API key not configured; skipping run")
            return 0

        async with get_db() as db:
            # Select rows for update to avoid double-processing across workers
            q = (
                select(JournalEntry)
                .where(JournalEntry.embedding.is_(None))
                .order_by(JournalEntry.created_at)
                .limit(batch)
                .with_for_update(skip_locked=True)
            )

            res = await db.execute(q)
            rows = res.scalars().all()
            if not rows:
                log.debug("LearningLoop: no pending journal entries")
                return 0

            texts: List[str] = [r.entry_text for r in rows]

            try:
                embeddings = await _embed(texts, input_type="document")
            except Exception as exc:  # pragma: no cover - external API
                log.error("LearningLoop: embedding call failed: %s", exc)
                return 0

            # Persist embeddings back to rows
            for row, emb in zip(rows, embeddings):
                row.embedding = emb
                db.add(row)

        log.info("LearningLoop: embedded %d journal entries", len(rows))
        return len(rows)

    async def run_forever(self, poll_seconds: int = 60) -> None:
        """Continuously poll and embed every `poll_seconds`. Intended for long-running worker.

        This method swallows exceptions to keep the loop alive; it's safe to call under a supervisor.
        """
        while True:
            try:
                processed = await self.run_once()
                if processed == 0:
                    await asyncio.sleep(poll_seconds)
                    continue
            except Exception as exc:  # pragma: no cover - defensive
                log.exception("LearningLoop: unexpected error: %s", exc)
            await asyncio.sleep(poll_seconds)


if __name__ == "__main__":  # pragma: no cover - manual runner
    import asyncio

    svc = LearningLoopService()
    count = asyncio.run(svc.run_once())
    print(f"embedded_count={count}")
