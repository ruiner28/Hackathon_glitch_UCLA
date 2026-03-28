import enum
import uuid

from sqlalchemy import Column, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class FragmentKind(str, enum.Enum):
    title = "title"
    bullet = "bullet"
    paragraph = "paragraph"
    note = "note"
    figure = "figure"
    synthetic = "synthetic"


class SourceFragment(Base):
    __tablename__ = "source_fragments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    ref_key = Column(String(255), nullable=False)
    page_or_slide_number = Column(Integer, nullable=True)
    kind = Column(Enum(FragmentKind), nullable=False)
    text = Column(Text, nullable=False)
    bbox_json = Column(JSON, nullable=True)
    image_url = Column(String(1000), nullable=True)

    source_document = relationship("SourceDocument", back_populates="fragments")
