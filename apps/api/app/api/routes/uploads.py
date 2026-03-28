import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_db
from app.models.source_document import SourceDocument, SourceDocumentType, SourceDocumentStatus
from app.schemas.requests import TopicInput
from app.schemas.responses import SourceDocumentResponse

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "application/pdf": SourceDocumentType.pdf,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": SourceDocumentType.pptx,
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/uploads", response_model=SourceDocumentResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: PDF, PPTX",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB.")

    settings = get_settings()
    storage_dir = Path(settings.LOCAL_STORAGE_PATH) / "uploads"
    storage_dir.mkdir(parents=True, exist_ok=True)

    file_id = uuid.uuid4()
    ext = Path(file.filename or "file").suffix
    stored_filename = f"{file_id}{ext}"
    file_path = storage_dir / stored_filename

    with open(file_path, "wb") as f:
        f.write(contents)

    doc_type = ALLOWED_MIME_TYPES[file.content_type]
    title = Path(file.filename or "Untitled").stem

    doc = SourceDocument(
        id=file_id,
        type=doc_type,
        title=title,
        original_filename=file.filename,
        storage_url=str(file_path),
        status=SourceDocumentStatus.uploaded,
        metadata_json={"size_bytes": len(contents), "content_type": file.content_type},
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    return SourceDocumentResponse.model_validate(doc)


@router.post("/uploads/topic", response_model=SourceDocumentResponse, status_code=201)
async def create_topic_source(
    body: TopicInput,
    db: AsyncSession = Depends(get_db),
):
    doc = SourceDocument(
        type=SourceDocumentType.topic,
        title=body.topic,
        status=SourceDocumentStatus.ready,
        metadata_json={
            "domain": body.domain,
            "style_preset": body.style_preset,
            "target_duration_sec": body.target_duration_sec,
            "music_enabled": body.music_enabled,
        },
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    return SourceDocumentResponse.model_validate(doc)
