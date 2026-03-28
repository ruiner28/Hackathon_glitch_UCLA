from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SourceDocumentResponse(BaseModel):
    id: UUID
    type: str
    title: str
    original_filename: str | None = None
    storage_url: str | None = None
    normalized_pdf_url: str | None = None
    metadata_json: dict | None = None
    status: str
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class SceneResponse(BaseModel):
    id: UUID
    lesson_id: UUID
    scene_order: int
    scene_type: str
    title: str
    duration_sec: float
    render_strategy: str
    source_refs_json: list | None = None
    narration_text: str | None = None
    on_screen_text_json: list | dict | None = None
    scene_spec_json: dict | None = None
    status: str
    created_at: datetime
    updated_at: datetime | None = None
    preview_image_url: str | None = None
    """HTTP path to latest scene image thumbnail (see GET /scenes/{id}/thumbnail)."""

    model_config = {"from_attributes": True}


class LessonResponse(BaseModel):
    id: UUID
    source_document_id: UUID | None = None
    input_topic: str | None = None
    domain: str
    title: str
    summary: str | None = None
    target_audience: str
    style_preset: str
    status: str
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class LessonDetailResponse(LessonResponse):
    scenes: list[SceneResponse] = Field(default_factory=list)


class LessonPlanResponse(BaseModel):
    id: UUID
    lesson_id: UUID
    concept_graph_json: dict | None = None
    prerequisites_json: list | None = None
    misconceptions_json: list | None = None
    lesson_objectives_json: list | None = None
    plan_json: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SceneAssetResponse(BaseModel):
    id: UUID
    scene_id: UUID
    asset_type: str
    provider: str
    prompt_version: str | None = None
    storage_url: str
    metadata_json: dict | None = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluationResponse(BaseModel):
    id: UUID
    lesson_id: UUID
    report_json: dict
    score_overall: float
    flags_json: list | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RenderJobResponse(BaseModel):
    id: UUID
    lesson_id: UUID
    job_type: str
    status: str
    progress: float
    logs: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct_index: int
    explanation: str


class QuizResponse(BaseModel):
    questions: list[QuizQuestion] = Field(default_factory=list)


class TranscriptSceneEntry(BaseModel):
    scene_id: UUID
    scene_order: int
    title: str
    text: str
    timestamp: float
    duration_sec: float
    scene_type: str = ""
    learning_objective: str = ""
    teaching_note: str = ""


class TranscriptResponse(BaseModel):
    full_text: str
    total_duration_sec: float = 0.0
    scenes: list[TranscriptSceneEntry] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)


class ProgressResponse(BaseModel):
    stage: str
    progress: float
    message: str = ""
