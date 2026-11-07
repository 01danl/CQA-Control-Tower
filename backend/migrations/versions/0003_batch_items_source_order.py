"""Preserve dataset row order; batch membership supports retry of failed items only."""

import sqlalchemy as sa
from alembic import op

revision = "0003_batch_items_source_order"
down_revision = "0002_evaluation_backend"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "conversations", sa.Column("source_order", sa.Integer(), nullable=False, server_default="0")
    )
    op.create_table(
        "batch_items",
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("batches.batch_id"), primary_key=True),
        sa.Column("conversation_id", sa.String(200), primary_key=True),
        sa.Column(
            "evaluation_id",
            sa.String(36),
            sa.ForeignKey("evaluations.evaluation_id"),
            nullable=False,
        ),
    )
    op.create_index("ix_batch_items_evaluation_id", "batch_items", ["evaluation_id"])


def downgrade():
    op.drop_table("batch_items")
    op.drop_column("conversations", "source_order")
