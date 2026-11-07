"""Initial conversation storage boundary."""

import sqlalchemy as sa
from alembic import op

revision = "0001_conversations"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "conversations",
        sa.Column("group_id", sa.String(100), primary_key=True),
        sa.Column("conversation_id", sa.String(200), primary_key=True),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("channel", sa.String(40), nullable=False),
        sa.Column("audio_url", sa.String(), nullable=True),
        sa.Column("transcript", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("conversations")
