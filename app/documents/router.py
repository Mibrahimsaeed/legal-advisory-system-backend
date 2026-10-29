from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.documents import service
from app.documents.schemas import DocumentOut, DocumentUploadResponse
from app.users.models import User

router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    file_bytes = await file.read()
    document = await service.upload_document(db, user.id, file.filename, file_bytes)
    return document


@router.get("", response_model=list[DocumentOut])
async def list_my_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_documents(db, user.id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    document = await service.get_document_or_404(db, document_id, user.id)
    await service.delete_document(db, document)
    return None
