"""Versioned rubrics, durable evaluations/jobs, immutable attempts and review audit."""

import sqlalchemy as sa
from alembic import op

revision = "0002_evaluation_backend"
down_revision = "0001_conversations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rubrics",
        sa.Column("rubric_id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("latest_version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "rubric_versions",
        sa.Column(
            "rubric_id", sa.String(100), sa.ForeignKey("rubrics.rubric_id"), primary_key=True
        ),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
    )
    op.create_table(
        "batches",
        sa.Column("batch_id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(100), nullable=False),
        sa.Column("rubric_id", sa.String(100), nullable=False),
        sa.Column("rubric_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["rubric_id", "rubric_version"],
            ["rubric_versions.rubric_id", "rubric_versions.version"],
        ),
    )
    op.create_table(
        "evaluations",
        sa.Column("evaluation_id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(100), nullable=False),
        sa.Column("conversation_id", sa.String(200), nullable=False),
        sa.Column("rubric_id", sa.String(100), nullable=False),
        sa.Column("rubric_version", sa.Integer(), nullable=False),
        sa.Column("rubric_snapshot", sa.JSON(), nullable=False),
        sa.Column("conversation_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_score", sa.Numeric(7, 2), nullable=True),
        sa.Column("gross_error", sa.Boolean(), nullable=False),
        sa.Column("needs_human_review", sa.Boolean(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("usage", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("batches.batch_id"), nullable=True),
        sa.ForeignKeyConstraint(
            ["group_id", "conversation_id"],
            ["conversations.group_id", "conversations.conversation_id"],
        ),
        sa.ForeignKeyConstraint(
            ["rubric_id", "rubric_version"],
            ["rubric_versions.rubric_id", "rubric_versions.version"],
        ),
    )
    for column in ("status", "batch_id"):
        op.create_index(f"ix_evaluations_{column}", "evaluations", [column])
    op.create_table(
        "model_attempts",
        sa.Column("attempt_id", sa.String(36), primary_key=True),
        sa.Column(
            "evaluation_id",
            sa.String(36),
            sa.ForeignKey("evaluations.evaluation_id"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("raw_output", sa.JSON(), nullable=True),
        sa.Column("usage", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_model_attempts_evaluation_id", "model_attempts", ["evaluation_id"])
    op.create_table(
        "appeals",
        sa.Column("appeal_id", sa.String(36), primary_key=True),
        sa.Column(
            "evaluation_id",
            sa.String(36),
            sa.ForeignKey("evaluations.evaluation_id"),
            nullable=False,
        ),
        sa.Column("criterion_id", sa.String(100), nullable=False),
        sa.Column("comment", sa.String(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_appeals_evaluation_id", "appeals", ["evaluation_id"])
    op.create_table(
        "review_decisions",
        sa.Column("decision_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "appeal_id",
            sa.String(36),
            sa.ForeignKey("appeals.appeal_id"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "evaluation_id",
            sa.String(36),
            sa.ForeignKey("evaluations.evaluation_id"),
            nullable=False,
        ),
        sa.Column("criterion_id", sa.String(100), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_review_decisions_evaluation_id", "review_decisions", ["evaluation_id"])
    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column(
            "evaluation_id",
            sa.String(36),
            sa.ForeignKey("evaluations.evaluation_id"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_evaluation_id", "audit_events", ["evaluation_id"])


def downgrade():
    for table in (
        "audit_events",
        "review_decisions",
        "appeals",
        "model_attempts",
        "evaluations",
        "batches",
        "rubric_versions",
        "rubrics",
    ):
        op.drop_table(table)
