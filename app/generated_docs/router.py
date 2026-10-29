from urllib.parse import quote

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.generated_docs import service
from app.generated_docs.schemas import CaseLawRequest, CaseLawStatus, GenerateFromChatRequest, GeneratedDocumentOut
from app.users.models import User

router = APIRouter()


@router.get("", response_model=list[GeneratedDocumentOut])
async def list_generated_documents(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await service.list_generated(db, user.id)


@router.post("", response_model=GeneratedDocumentOut, status_code=status.HTTP_201_CREATED)
async def generate_from_chat(
    payload: GenerateFromChatRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Save one answer, or a whole conversation, as a PDF or Word file."""
    return await service.generate_from_chat(
        db, user.id, payload.source, payload.conversation_id, payload.message_id, payload.format
    )


@router.get("/case-law/status", response_model=CaseLawStatus)
async def case_law_status(user: User = Depends(get_current_user)):
    return service.case_law_status()


@router.post("/case-law", response_model=GeneratedDocumentOut, status_code=status.HTTP_201_CREATED)
async def generate_case_law(
    payload: CaseLawRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Make a document from real cases in the case law data. 404 'Not available' if none match."""
    return await service.generate_case_law(db, user.id, payload.query, payload.format)


@router.get("/{doc_id}/download")
async def download_generated_document(
    doc_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    doc = await service.get_or_404(db, doc_id, user.id)
    data = service.read_bytes(doc)
    return Response(
        content=data,
        media_type=service.MIME[doc.file_format],
        headers={
            "Content-Disposition": f"attachment; filename=\"{doc.filename}\"; filename*=UTF-8''{quote(doc.filename)}",
            "Cache-Control": "no-store",
        },
    )


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_generated_document(
    doc_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    doc = await service.get_or_404(db, doc_id, user.id)
    await service.delete(db, doc)
    return None
