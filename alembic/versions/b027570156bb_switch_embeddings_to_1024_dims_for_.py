"""switch embeddings to 1024 dims for voyage-3-large

Revision ID: b027570156bb
Revises: a17c58cc50c2
Create Date: 2026-05-19 23:08:00.867673

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "b027570156bb"
down_revision: Union[str, Sequence[str], None] = "a17c58cc50c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop HNSW index first (depends on vector column)
    op.execute("DROP INDEX IF EXISTS idx_embeddings_vector")

    # Change column dimension from 1536 to 1024
    op.alter_column(
        "embeddings",
        "embedding",
        existing_type=Vector(1536),
        type_=Vector(1024),
        existing_nullable=False,
        postgresql_using="embedding::vector(1024)",
    )

    # Recreate HNSW index for new dimension
    op.execute("""
        CREATE INDEX idx_embeddings_vector
        ON embeddings
        USING hnsw (embedding vector_cosine_ops)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_embeddings_vector")
    op.alter_column(
        "embeddings",
        "embedding",
        existing_type=Vector(1024),
        type_=Vector(1536),
        existing_nullable=False,
        postgresql_using="embedding::vector(1536)",
    )
    op.execute("""
        CREATE INDEX idx_embeddings_vector
        ON embeddings
        USING hnsw (embedding vector_cosine_ops)
    """)
