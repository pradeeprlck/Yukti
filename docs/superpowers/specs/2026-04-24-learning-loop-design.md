Title: Learning Loop — design
Date: 2026-04-24

Summary
-------
This document describes the Learning Loop service: batch ingestion of post-trade journal entries, embedding via Voyage AI, and persistence to Postgres `pgvector` column for fast similarity retrieval.

Goals
-----
- Produce embeddings for `journal_entries.entry_text` and persist into `journal_entries.embedding` (1024-dim vector).
- Run as a scheduled job (config-gated) and provide an on-demand runner for manual execution.
- Use safe DB locking (`FOR UPDATE SKIP LOCKED`) and small batch sizes to avoid contention.

Architecture
------------
- `LearningLoopService.run_once(batch_size)` — fetch un-embedded rows, call `_embed()` in bulk, and update rows in one transaction.
- `job_learning_loop()` — scheduler job that calls `LearningLoopService.run_once()`; scheduled at 02:00 IST (config flag `enable_learning_loop`).
- Alembic migration ensures `pgvector` extension exists and an IVFFLAT index is created for fast ANN queries.

Operational notes
-----------------
- Configure `VOYAGE_API_KEY` in environment for production runs.
- Default batch size is small (50) to reduce memory and API pressure; tune via `learning_loop_batch_size` setting if needed.
- Use separate integration test matrix in CI for Postgres-backed checks (marked `integration`).

Failure modes
-------------
- Voyage API outages: `run_once()` logs and returns zero processed entries; `run_forever()` continues polling.
- Partial failures: if the embedding call fails for a batch, none are written; failed rows remain eligible for reprocessing.

Scaling
-------
- For large backfills, run the on-demand runner with higher batch size in maintenance windows.
- For high throughput, consider an event-driven approach (DB trigger → Redis stream worker) in a future iteration.
