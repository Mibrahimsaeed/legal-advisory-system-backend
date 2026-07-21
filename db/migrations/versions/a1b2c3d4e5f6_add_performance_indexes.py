"""add performance indexes

Revision ID: a1b2c3d4e5f6
Revises: 1b5bf848cf3b
Create Date: 2026-07-16

Phase 6 hardening: composite indexes matching the app's most frequent
query patterns, so lookups stay fast as data grows.

- conversations are always listed per-user ordered by recency
- messages are always fetched per-conversation ordered by time
- documents are always listed per-user ordered by recency
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "1b5bf848cf3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_conversations_user_id_updated_at",
        "conversations",
        ["user_id", "updated_at"],
    )
    op.create_index(
        "ix_messages_conversation_id_created_at",
        "messages",
        ["conversation_id", "created_at"],
    )
    op.create_index(
        "ix_documents_user_id_created_at",
        "documents",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_user_id_created_at", table_name="documents")
    op.drop_index("ix_messages_conversation_id_created_at", table_name="messages")
    op.drop_index("ix_conversations_user_id_updated_at", table_name="conversations")
