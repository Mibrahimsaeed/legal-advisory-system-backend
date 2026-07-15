from sqlalchemy.ext.asyncio import AsyncSession

from app.chat import pipeline_client
from app.chat.history import build_history
from app.chat.schemas import ChatRequest
from app.common.rate_limiter import check_rate_limit
from app.conversations import service as conversations_service
from app.conversations.models import Message
from app.documents import service as documents_service


async def send_message(
    db: AsyncSession, user_id: str, conversation_id: str, payload: ChatRequest
) -> Message:
    """
    Full chat turn: verify the conversation belongs to this user, save the
    user's question, gather context (history + any attached documents),
    call the AI pipeline (currently simulated), save and return the answer.
    """
    check_rate_limit(user_id)

    # Confirms the conversation exists and belongs to this user.
    await conversations_service.get_conversation_or_404(db, conversation_id, user_id)

    # Save the user's message first, so it's part of history even if the
    # pipeline call below fails.
    await conversations_service.add_message(db, conversation_id, role="user", content=payload.question)

    # Gather prior messages (now including the one we just saved) for context.
    prior_messages, _ = await conversations_service.list_messages(
        db, conversation_id, limit=200, offset=0
    )
    history = build_history(prior_messages)

    # Gather text from any documents the user attached to this query.
    context_docs: list[str] = []
    for document_id in payload.document_ids:
        document = await documents_service.get_document_or_404(db, document_id, user_id)
        if document.extracted_text:
            context_docs.append(document.extracted_text)

    # Call the (currently simulated) AI/RAG pipeline.
    result = await pipeline_client.query(payload.question, context_docs, history)

    # Save and return the assistant's response.
    assistant_message = await conversations_service.add_message(
        db, conversation_id, role="assistant", content=result.content
    )
    return assistant_message
