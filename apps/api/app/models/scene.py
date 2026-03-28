import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class SceneType(str, enum.Enum):
    deterministic_animation = "deterministic_animation"
    generated_still_with_motion = "generated_still_with_motion"
    veo_cinematic = "veo_cinematic"
    code_trace = "code_trace"
    system_design_graph = "system_design_graph"
    summary_scene = "summary_scene"


class SceneStatus(str, enum.Enum):
    pending = "pending"
    generating = "generating"
    rendered = "rendered"
    error = "error"


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lesson_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
    )
    scene_order = Column(Integer, nullable=False, default=0)
    scene_type = Column(Enum(SceneType), nullable=False)
    title = Column(String(500), nullable=False)
    duration_sec = Column(Float, nullable=False, default=30.0)
    render_strategy = Column(String(255), nullable=False, default="default")
    source_refs_json = Column(JSON, nullable=True, default=list)
    narration_text = Column(Text, nullable=True)
    on_screen_text_json = Column(JSON, nullable=True)
    scene_spec_json = Column(JSON, nullable=True, default=dict)
    status = Column(Enum(SceneStatus), nullable=False, default=SceneStatus.pending)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    lesson = relationship("Lesson", back_populates="scenes")
    assets = relationship("SceneAsset", back_populates="scene", cascade="all, delete-orphan")
