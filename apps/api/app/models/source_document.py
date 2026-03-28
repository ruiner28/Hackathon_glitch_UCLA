import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class SourceDocumentType(str, enum.Enum):
    topic = "topic"
    pdf = "pdf"
    pptx = "pptx"


class SourceDocumentStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    error = "error"


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(Enum(SourceDocumentType), nullable=False)
    title = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=True)
    storage_url = Column(String(1000), nullable=True)
    normalized_pdf_url = Column(String(1000), nullable=True)
    metadata_json = Column(JSON, nullable=True, default=dict)
    status = Column(
        Enum(SourceDocumentStatus),
        nullable=False,
        default=SourceDocumentStatus.uploaded,
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    fragments = relationship("SourceFragment", back_populates="source_document", cascade="all, delete-orphan")
    lessons = relationship("Lesson", back_populates="source_document")
