import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class LessonDomain(str, enum.Enum):
    cs = "cs"
    system_design = "system_design"
    ppt_lesson = "ppt_lesson"


class LessonStylePreset(str, enum.Enum):
    clean_academic = "clean_academic"
    modern_technical = "modern_technical"
    cinematic_minimal = "cinematic_minimal"


class LessonStatus(str, enum.Enum):
    created = "created"
    extracting = "extracting"
    planning = "planning"
    compiling = "compiling"
    generating_assets = "generating_assets"
    rendering = "rendering"
    completed = "completed"
    error = "error"


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    input_topic = Column(String(500), nullable=True)
    domain = Column(Enum(LessonDomain), nullable=False, default=LessonDomain.cs)
    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=True)
    target_audience = Column(String(255), nullable=False, default="undergraduate CS student")
    style_preset = Column(
        Enum(LessonStylePreset),
        nullable=False,
        default=LessonStylePreset.clean_academic,
    )
    status = Column(Enum(LessonStatus), nullable=False, default=LessonStatus.created)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    source_document = relationship("SourceDocument", back_populates="lessons")
    lesson_plan = relationship("LessonPlan", back_populates="lesson", uselist=False, cascade="all, delete-orphan")
    scenes = relationship("Scene", back_populates="lesson", cascade="all, delete-orphan", order_by="Scene.scene_order")
    render_jobs = relationship("RenderJob", back_populates="lesson", cascade="all, delete-orphan")
    evaluation_reports = relationship("EvaluationReport", back_populates="lesson", cascade="all, delete-orphan")
