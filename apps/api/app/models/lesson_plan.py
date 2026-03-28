import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class LessonPlan(Base):
    __tablename__ = "lesson_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lesson_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    concept_graph_json = Column(JSON, nullable=True, default=dict)
    prerequisites_json = Column(JSON, nullable=True, default=list)
    misconceptions_json = Column(JSON, nullable=True, default=list)
    lesson_objectives_json = Column(JSON, nullable=True, default=list)
    plan_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    lesson = relationship("Lesson", back_populates="lesson_plan")
