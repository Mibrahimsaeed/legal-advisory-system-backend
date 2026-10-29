import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.caselaw import repository as caselaw
from app.common.exceptions import AppException, ForbiddenError, NotFoundError
from app.common.storage_client import delete_file, download_file, upload_file
from app.conversations import service as conversations_service
from app.conversations.models import Conversation, Message
from app.generated_docs import builders
from app.generated_docs.models import GeneratedDocument
from fastapi import status as http_status

MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
CASE_TEXT_LIMIT = 6000  # characters of judgment text per case


def _short(text: str, n: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _safe_filename(title: str, file_format: str) -> str:
    base = re.sub(r"[^A-Za-z0-9 _-]+", "", title).strip().replace(" ", "_")[:60] or "document"
    return f"{base}.{file_format}"


async def _save(
    db: AsyncSession, user_id: str, kind: str, title: str, file_format: str, blocks: list,
    conversation: Conversation | None = None,
) -> GeneratedDocument:
    data = builders.build(blocks, file_format)
    filename = _safe_filename(title, file_format)
    storage_key = upload_file(data, filename)
    doc = GeneratedDocument(
        user_id=user_id, kind=kind, title=title[:255], file_format=file_format, filename=filename,
        size_bytes=len(data), storage_key=storage_key,
        conversation_id=conversation.id if conversation else None,
        source_title=conversation.title[:255] if conversation else None,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def _messages(db: AsyncSession, conversation_id: str) -> list[Message]:
    rows = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
    )
    return list(rows.scalars().all())


async def generate_from_chat(
    db: AsyncSession, user_id: str, source: str, conversation_id: str, message_id: str | None, file_format: str
) -> GeneratedDocument:
    conversation = await conversations_service.get_conversation_or_404(db, conversation_id, user_id)
    messages = await _messages(db, conversation.id)

    if source == "answer":
        idx = next((i for i, m in enumerate(messages) if m.id == message_id), None)
        if idx is None or messages[idx].role != "assistant":
            raise NotFoundError("Answer not found in this conversation")
        answer = messages[idx]
        question = next((m for m in reversed(messages[:idx]) if m.role == "user"), None)
        title = "Answer - " + _short(question.content if question else conversation.title)
        blocks = [
            ("title", "Legal Answer"),
            ("meta", builders.generated_on_line()),
            ("meta", f"From chat: {conversation.title}"),
            ("rule", ""),
        ]
        if question:
            blocks += [("label", "YOUR QUESTION"), ("para", question.content)]
        blocks += [("label", "ANSWER"), ("para", answer.content), ("rule", ""), ("note", builders.DISCLAIMER)]
        return await _save(db, user_id, "answer", title, file_format, blocks, conversation)

    # whole conversation
    if not messages:
        raise AppException(http_status.HTTP_400_BAD_REQUEST, "This conversation has no messages yet")
    blocks = [
        ("title", conversation.title),
        ("meta", builders.generated_on_line()),
        ("meta", f"Full conversation · {sum(m.role == 'user' for m in messages)} questions"),
        ("rule", ""),
    ]
    for m in messages:
        blocks += [("label", "YOU" if m.role == "user" else "LEGAL ASSISTANT"), ("para", m.content)]
    blocks += [("rule", ""), ("note", builders.DISCLAIMER)]
    return await _save(db, user_id, "conversation", "Chat - " + _short(conversation.title), file_format, blocks, conversation)


def case_law_status() -> dict:
    n = len(caselaw.load_cases())
    return {"available": n > 0, "cases": n}


async def generate_case_law(db: AsyncSession, user_id: str, query: str, file_format: str) -> GeneratedDocument:
    if not caselaw.load_cases():
        raise NotFoundError("Case law is not available yet. The case law data hasn't been added to the system.")
    cases = caselaw.search(query)
    if not cases:
        raise NotFoundError(f'Not available: no case law matching "{_short(query, 80)}" was found in our case law data.')

    blocks = [
        ("title", "Case Law"),
        ("meta", f'Search: "{query.strip()}"'),
        ("meta", builders.generated_on_line() + f" · {len(cases)} case{'s' if len(cases) != 1 else ''} found"),
        ("note", "Taken word for word from the project's case law database (PakistanLawSite data). "
                 "Check the original judgment before relying on it."),
        ("rule", ""),
    ]
    for i, c in enumerate(cases, 1):
        blocks.append(("heading", f"{i}. {c.heading}"))
        for name, value in (("Citation", c.citation), ("Court", c.court), ("Date", c.date), ("Judges", c.judges)):
            if value:
                blocks.append(("field", f"{name}|{value}"))
        if c.summary:
            blocks += [("label", "SUMMARY"), ("para", c.summary)]
        if c.text:
            excerpt = c.text if len(c.text) <= CASE_TEXT_LIMIT else c.text[:CASE_TEXT_LIMIT].rstrip() + " …"
            label = "JUDGMENT" if len(c.text) <= CASE_TEXT_LIMIT else "JUDGMENT (EXCERPT)"
            blocks += [("label", label), ("para", excerpt)]
        if c.url:
            blocks.append(("field", f"Source|{c.url}"))
        blocks.append(("rule", ""))
    blocks.append(("note", builders.DISCLAIMER))
    return await _save(db, user_id, "case_law", "Case law - " + _short(query), file_format, blocks)


async def list_generated(db: AsyncSession, user_id: str) -> list[GeneratedDocument]:
    rows = await db.execute(
        select(GeneratedDocument).where(GeneratedDocument.user_id == user_id).order_by(GeneratedDocument.created_at.desc())
    )
    return list(rows.scalars().all())


async def get_or_404(db: AsyncSession, doc_id: str, user_id: str) -> GeneratedDocument:
    doc = (await db.execute(select(GeneratedDocument).where(GeneratedDocument.id == doc_id))).scalar_one_or_none()
    if doc is None:
        raise NotFoundError("Document not found")
    if doc.user_id != user_id:
        raise ForbiddenError("You don't have access to this document")
    return doc


def read_bytes(doc: GeneratedDocument) -> bytes:
    try:
        return download_file(doc.storage_key)
    except FileNotFoundError:
        raise NotFoundError("The file for this document is missing")


async def delete(db: AsyncSession, doc: GeneratedDocument) -> None:
    delete_file(doc.storage_key)
    await db.delete(doc)
    await db.commit()
