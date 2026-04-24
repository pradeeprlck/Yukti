"""
yukti/data/migrations/versions/004_journal_embeddings.py
Add pgvector extension & ANN index for `journal_entries.embedding`.

Run: uv run alembic upgrade head
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure pgvector extension exists
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create ANN index for fast similarity search using ivfflat
    # lists parameter may be tuned for production; 100 is a reasonable default
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS journal_entries_embedding_idx
        ON journal_entries USING ivfflat (embedding)
        WITH (lists = 100)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS journal_entries_embedding_idx")
    # We DO NOT drop the vector extension in downgrade to avoid accidental removal
