from pydantic import BaseModel, Field


class ConceptNode(BaseModel):
    id: str
    label: str
    description: str = ""
    importance: float = Field(default=1.0, ge=0.0, le=1.0)
    prerequisites: list[str] = Field(default_factory=list)


class ConceptEdge(BaseModel):
    source: str
    target: str
    relation_type: str = "prerequisite"


class ConceptGraph(BaseModel):
    nodes: list[ConceptNode] = Field(default_factory=list)
    edges: list[ConceptEdge] = Field(default_factory=list)


class LessonPlanSection(BaseModel):
    title: str
    objective: str = ""
    scene_type: str = "deterministic_animation"
    duration_sec: float = 30.0
    key_points: list[str] = Field(default_factory=list)
    visual_strategy: str = ""


class LessonPlanSchema(BaseModel):
    lesson_title: str
    target_audience: str = "undergraduate CS student"
    estimated_duration_sec: float = 300.0
    objectives: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    sections: list[LessonPlanSection] = Field(default_factory=list)


class VisualElement(BaseModel):
    type: str = ""
    description: str = ""
    position: str = ""
    style: str = ""


class AnimationBeat(BaseModel):
    timestamp_sec: float = 0.0
    action: str = ""
    description: str = ""


class AssetRequest(BaseModel):
    type: str = ""
    prompt: str = ""
    provider: str = ""


class SceneSpec(BaseModel):
    scene_id: str = ""
    title: str = ""
    learning_objective: str = ""
    source_refs: list[str] = Field(default_factory=list)
    scene_type: str = "deterministic_animation"
    render_strategy: str = "default"
    duration_sec: float = 30.0
    narration_text: str = ""
    on_screen_text: list[str] = Field(default_factory=list)
    visual_elements: list[VisualElement] = Field(default_factory=list)
    animation_beats: list[AnimationBeat] = Field(default_factory=list)
    asset_requests: list[AssetRequest] = Field(default_factory=list)
    veo_prompt: str | None = None
    image_prompt: str | None = None
    music_mood: str = "neutral"
    validation_notes: str = ""


class CategoryScore(BaseModel):
    score: float = 0.0
    feedback: str = ""


class EvaluationReportSchema(BaseModel):
    overall_score: float = 0.0
    content_accuracy: CategoryScore = Field(default_factory=CategoryScore)
    pedagogical_quality: CategoryScore = Field(default_factory=CategoryScore)
    visual_quality: CategoryScore = Field(default_factory=CategoryScore)
    narration_quality: CategoryScore = Field(default_factory=CategoryScore)
    engagement: CategoryScore = Field(default_factory=CategoryScore)
    flags: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
