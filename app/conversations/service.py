from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ForbiddenError, NotFoundError
from app.conversations.models import Conversation, Message


async def create_conversation(db: AsyncSession, user_id: str, title: str | None) -> Conversation:
    conversation = Conversation(user_id=user_id, title=title or "New Conversation")
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def get_conversation_or_404(db: AsyncSession, conversation_id: str, user_id: str) -> Conversation:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise NotFoundError("Conversation not found")
    if conversation.user_id != user_id:
        # Deliberately 403 rather than leaking existence via 404 vs 403 difference elsewhere,
        # but here we want to be explicit that it exists but isn't theirs.
        raise ForbiddenError("You don't have access to this conversation")

    return conversation


async def list_conversations(
    db: AsyncSession, user_id: str, limit: int, offset: int
) -> tuple[list[Conversation], int]:
    count_result = await db.execute(
        select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    conversations = list(result.scalars().all())
    return conversations, total


async def delete_conversation(db: AsyncSession, conversation: Conversation) -> None:
    await db.delete(conversation)
    await db.commit()


async def list_messages(
    db: AsyncSession, conversation_id: str, limit: int, offset: int
) -> tuple[list[Message], int]:
    count_result = await db.execute(
        select(func.count()).select_from(Message).where(Message.conversation_id == conversation_id)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    messages = list(result.scalars().all())
    return messages, total


async def add_message(db: AsyncSession, conversation_id: str, role: str, content: str) -> Message:
    message = Message(conversation_id=conversation_id, role=role, content=content)
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message
