import asyncio

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import TokenType, decode_token
from app.chat import service
from app.chat.schemas import ChatRequest, ChatResponse, StreamChunk
from app.common.exceptions import UnauthorizedError
from app.common.rate_limiter import check_rate_limit
from app.conversations import service as conversations_service
from app.dependencies import get_current_user, get_db
from app.users.models import User
from db.session import AsyncSessionLocal

router = APIRouter()


@router.post("/{conversation_id}/message", response_model=ChatResponse)
async def send_chat_message(
    conversation_id: str,
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.send_message(db, user.id, conversation_id, payload)


async def _authenticate_websocket(websocket: WebSocket) -> User | None:
    """
    WebSockets can't send an Authorization header from a browser the same
    way normal requests do, so the access token is passed as a query param
    instead: ws://.../chat/{id}/stream?token=<access_token>
    """
    from sqlalchemy import select
    from app.users.models import User as UserModel

    token = websocket.query_params.get("token")
    if not token:
        return None

    try:
        payload = decode_token(token)
    except JWTError:
        return None

    if payload.get("type") != TokenType.ACCESS.value:
        return None

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UserModel).where(UserModel.id == payload["sub"]))
        return result.scalar_one_or_none()


@router.websocket("/{conversation_id}/stream")
async def stream_chat_message(websocket: WebSocket, conversation_id: str):
    user = await _authenticate_websocket(websocket)
    if user is None:
        await websocket.close(code=4401)  # custom code signalling "unauthorized"
        return

    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()
            question = data.get("question", "")

            async with AsyncSessionLocal() as db:
                try:
                    check_rate_limit(user.id)
                    await conversations_service.get_conversation_or_404(db, conversation_id, user.id)
                except HTTPException as e:
                    await websocket.send_json({"error": e.detail})
                    continue
                except Exception as e:
                    await websocket.send_json({"error": str(e)})
                    continue

                try:
                    payload = ChatRequest(question=question)
                    message = await service.send_message(db, user.id, conversation_id, payload)
                except HTTPException as e:  # e.g. 402 free allowance used up
                    await websocket.send_json({"error": e.detail})
                    continue

            # Simulate streaming by sending the response in small chunks.
            words = message.content.split(" ")
            for i, word in enumerate(words):
                chunk = StreamChunk(delta=word + " ", done=(i == len(words) - 1))
                await websocket.send_json(chunk.model_dump())
                await asyncio.sleep(0.02)

    except WebSocketDisconnect:
        pass
