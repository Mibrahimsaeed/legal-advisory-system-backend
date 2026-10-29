"""Admin-submitted legal sources for the AI knowledge base."""

from datetime import datetime, timezone
from pathlib import PurePath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat import pipeline_client
from app.common.exceptions import AppException, NotFoundError
from app.common.storage_client import upload_file
from app.documents.file_types import EXTENSION_TYPES
from app.documents.parser import extract_text
from app.documents.service import validate_upload
from app.rag.models import RagDocument
from db.session import AsyncSessionLocal


async def submit_document(
    db: AsyncSession,
    admin_id: str,
    fields: dict,
    file_name: str | None,
    file_bytes: bytes | None,
) -> RagDocument:
    fields = dict(fields)
    content = (fields.pop("content", "") or "").strip()
    if not content and not file_bytes:
        raise AppException(422, "Add the document text or attach a file")

    storage_key = None
    if file_bytes:
        validate_upload(file_name or "", file_bytes)
        storage_key = upload_file(file_bytes, file_name or "document")

    doc = RagDocument(
        **fields,
        content=content or None,
        file_name=file_name if file_bytes else None,
        file_size=len(file_bytes) if file_bytes else None,
        storage_key=storage_key,
        status="submitted",
        submitted_by=admin_id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def get_job_or_404(db: AsyncSession, job_id: str) -> RagDocument:
    doc = (await db.execute(select(RagDocument).where(RagDocument.id == job_id))).scalar_one_or_none()
    if doc is None:
        raise NotFoundError("Ingestion job not found")
    return doc


async def process_job(job_id: str, file_bytes: bytes | None) -> None:
    """
    Background task: read the text, hand it to the AI pipeline's ingest hook, and
    record the outcome. Uses its own DB session because the request's has closed.
    """
    async with AsyncSessionLocal() as db:
        doc = await get_job_or_404(db, job_id)
        doc.status = "processing"
        await db.commit()
        try:
            text = doc.content or ""
            if file_bytes:
                text = extract_text(file_bytes, EXTENSION_TYPES[PurePath(doc.file_name or "").suffix.lower()])
                doc.content = text
            if not text.strip():
                raise ValueError("No readable text found in the document")
            await pipeline_client.ingest(
                doc.title,
                text,
                {
                    "document_type": doc.document_type, "jurisdiction": doc.jurisdiction, "year": doc.year,
                    "category": doc.category, "description": doc.description, "source": doc.source,
                },
            )
            doc.status = "completed"
            doc.completed_at = datetime.now(timezone.utc)
        except Exception as e:
            doc.status = "failed"
            doc.error_message = str(e)[:500]
        await db.commit()
