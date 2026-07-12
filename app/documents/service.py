from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import AppException, ForbiddenError, NotFoundError
from app.common.storage_client import delete_file, upload_file
from app.documents.models import Document, DocumentStatus
from app.documents.parser import extract_text
from config.constants import ALLOWED_DOCUMENT_MIME_TYPES
from config.settings import get_settings
from fastapi import status as http_status

settings = get_settings()


def validate_upload(filename: str, mime_type: str, size_bytes: int) -> None:
    if mime_type not in ALLOWED_DOCUMENT_MIME_TYPES:
        raise AppException(
            http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"File type '{mime_type}' isn't supported. Allowed types: PDF, DOCX, TXT.",
        )

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise AppException(
            http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File exceeds the {settings.max_upload_size_mb}MB upload limit.",
        )


async def upload_document(
    db: AsyncSession, user_id: str, filename: str, mime_type: str, file_bytes: bytes
) -> Document:
    validate_upload(filename, mime_type, len(file_bytes))

    storage_key = upload_file(file_bytes, filename)

    document = Document(
        user_id=user_id,
        original_filename=filename,
        mime_type=mime_type,
        size_bytes=len(file_bytes),
        storage_key=storage_key,
        status=DocumentStatus.PROCESSING.value,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Synchronous extraction for now (fine for small files / dev use).
    # For larger files or production, move this to a background task/queue.
    try:
        text = extract_text(file_bytes, mime_type)
        document.extracted_text = text
        document.status = DocumentStatus.READY.value
    except Exception as e:
        document.status = DocumentStatus.FAILED.value
        document.error_message = str(e)[:500]

    await db.commit()
    await db.refresh(document)
    return document


async def list_documents(db: AsyncSession, user_id: str) -> list[Document]:
    result = await db.execute(
        select(Document).where(Document.user_id == user_id).order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


async def get_document_or_404(db: AsyncSession, document_id: str, user_id: str) -> Document:
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if document is None:
        raise NotFoundError("Document not found")
    if document.user_id != user_id:
        raise ForbiddenError("You don't have access to this document")

    return document


async def delete_document(db: AsyncSession, document: Document) -> None:
    delete_file(document.storage_key)
    await db.delete(document)
    await db.commit()
