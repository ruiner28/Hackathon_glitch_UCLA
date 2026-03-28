from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TopicInput(BaseModel):
    topic: str
    domain: str | None = None
    style_preset: str | None = None
    target_duration_sec: int | None = None
    music_enabled: bool = True


class LessonCreate(BaseModel):
    source_document_id: UUID | None = None
    topic: str | None = None
    domain: str | None = None
    style_preset: str | None = None


RenderMode = Literal["auto", "force_static", "force_veo"]


class SceneUpdate(BaseModel):
    narration_text: str | None = None
    on_screen_text: list[str] | None = None
    duration_sec: float | None = None
    veo_eligible: bool | None = Field(
        default=None,
        description="When set, updates scene_spec_json and pipeline Veo gating.",
    )
    render_mode: RenderMode | None = Field(
        default=None,
        description="auto: eligibility score; force_static: skip Veo; force_veo: attempt Veo when possible.",
    )


class SceneReorder(BaseModel):
    scene_ids: list[UUID]


class LessonStyleUpdate(BaseModel):
    style_preset: str
