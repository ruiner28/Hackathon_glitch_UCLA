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


class SceneUpdate(BaseModel):
    narration_text: str | None = None
    on_screen_text: list[str] | None = None
    duration_sec: float | None = None
    veo_eligible: bool | None = None


class SceneReorder(BaseModel):
    scene_ids: list[UUID]


class LessonStyleUpdate(BaseModel):
    style_preset: str
