from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PaginatedResponse, paginate_params
from app.conversations import service
from app.conversations.schemas import ConversationCreate, ConversationOut, MessageOut
from app.dependencies import get_current_user, get_db
from app.users.models import User

router = APIRouter()


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_conversation(db, user.id, payload.title)


@router.get("", response_model=PaginatedResponse[ConversationOut])
async def list_my_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    limit, offset = paginate_params(limit, offset)
    conversations, total = await service.list_conversations(db, user.id, limit, offset)
    return PaginatedResponse(
        items=conversations, total=total, limit=limit, offset=offset, has_more=offset + limit < total
    )


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_conversation_or_404(db, conversation_id, user.id)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation = await service.get_conversation_or_404(db, conversation_id, user.id)
    await service.delete_conversation(db, conversation)
    return None


@router.get("/{conversation_id}/messages", response_model=PaginatedResponse[MessageOut])
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Confirms the conversation exists AND belongs to this user before showing messages.
    await service.get_conversation_or_404(db, conversation_id, user.id)

    limit, offset = paginate_params(limit, offset)
    messages, total = await service.list_messages(db, conversation_id, limit, offset)
    return PaginatedResponse(
        items=messages, total=total, limit=limit, offset=offset, has_more=offset + limit < total
    )
