"""Admin: submit legal sources for the AI knowledge base and track their processing."""

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin, get_db
from app.rag import service
from app.rag.schemas import RagDocumentType, RagJobOut, RagSubmissionOut
from app.users.models import User

router = APIRouter(dependencies=[Depends(get_current_admin)])


def _job(doc) -> dict:
    return {
        "job_id": doc.id, "status": doc.status, "title": doc.title, "document_type": doc.document_type,
        "submitted_at": doc.created_at, "completed_at": doc.completed_at, "error_message": doc.error_message,
    }


@router.post("/documents", response_model=RagSubmissionOut, status_code=status.HTTP_202_ACCEPTED)
async def submit_document(
    background: BackgroundTasks,
    title: str = Form(..., min_length=1, max_length=255),
    document_type: RagDocumentType = Form(...),
    jurisdiction: str = Form("", max_length=120),
    year: str = Form("", max_length=10),
    category: str = Form("", max_length=120),
    description: str = Form(""),
    source: str = Form("", max_length=255),
    content: str = Form(""),
    file: UploadFile | None = File(None),
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    file_bytes = await file.read() if file is not None and file.filename else None
    doc = await service.submit_document(
        db,
        admin.id,
        {
            "title": title.strip(), "document_type": document_type, "jurisdiction": jurisdiction.strip(),
            "year": year.strip(), "category": category.strip(), "description": description.strip(),
            "source": source.strip(),
        } | {"content": content},
        file.filename if file_bytes else None,
        file_bytes,
    )
    background.add_task(service.process_job, doc.id, file_bytes)
    return {
        "job_id": doc.id, "title": doc.title, "document_type": doc.document_type,
        "jurisdiction": doc.jurisdiction, "submitted_at": doc.created_at,
    }


@router.get("/jobs/{job_id}", response_model=RagJobOut)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    return _job(await service.get_job_or_404(db, job_id))
