"""add billing/usage, rag documents, structured answers and conversation hints

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-10-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e0f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOW = sa.text("(CURRENT_TIMESTAMP)")


def upgrade() -> None:
    # --- chat: structured answers + legal area / analysis type per conversation ---
    with op.batch_alter_table("messages") as batch:
        batch.add_column(sa.Column("answer", sa.JSON(), nullable=True))
    with op.batch_alter_table("conversations") as batch:
        batch.add_column(sa.Column("domain", sa.String(length=20), nullable=False, server_default="general"))
        batch.add_column(sa.Column("archetype", sa.String(length=40), nullable=True))

    # --- billing ---
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_subscriptions_expires_at", "subscriptions", ["expires_at"])

    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=20), nullable=False),
        sa.Column("amount_pkr", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(length=40), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_paid_at", "payments", ["paid_at"])

    op.create_table(
        "free_usage",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False),
        sa.Column("limit_reached_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # --- admin: legal sources submitted for the knowledge base ---
    op.create_table(
        "rag_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("document_type", sa.String(length=20), nullable=False),
        sa.Column("jurisdiction", sa.String(length=120), nullable=False),
        sa.Column("year", sa.String(length=10), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("storage_key", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("submitted_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rag_documents_status", "rag_documents", ["status"])
    op.create_index("ix_rag_documents_created_at", "rag_documents", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_rag_documents_created_at", table_name="rag_documents")
    op.drop_index("ix_rag_documents_status", table_name="rag_documents")
    op.drop_table("rag_documents")
    op.drop_table("free_usage")
    op.drop_index("ix_payments_paid_at", table_name="payments")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_subscriptions_expires_at", table_name="subscriptions")
    op.drop_table("subscriptions")
    with op.batch_alter_table("conversations") as batch:
        batch.drop_column("archetype")
        batch.drop_column("domain")
    with op.batch_alter_table("messages") as batch:
        batch.drop_column("answer")
