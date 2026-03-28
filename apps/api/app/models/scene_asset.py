import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class AssetType(str, enum.Enum):
    image = "image"
    video = "video"
    audio = "audio"
    svg = "svg"
    json_data = "json_data"
    subtitle = "subtitle"


class AssetStatus(str, enum.Enum):
    pending = "pending"
    generating = "generating"
    ready = "ready"
    error = "error"


class SceneAsset(Base):
    __tablename__ = "scene_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scene_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scenes.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_type = Column(Enum(AssetType), nullable=False)
    provider = Column(String(100), nullable=False)
    prompt_version = Column(String(100), nullable=True)
    storage_url = Column(String(1000), nullable=False)
    metadata_json = Column(JSON, nullable=True)
    status = Column(Enum(AssetStatus), nullable=False, default=AssetStatus.pending)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    scene = relationship("Scene", back_populates="assets")
