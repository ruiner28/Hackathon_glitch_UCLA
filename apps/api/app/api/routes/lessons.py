from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db
from app.models.evaluation_report import EvaluationReport
from app.models.lesson import Lesson, LessonDomain, LessonStatus, LessonStylePreset
from app.models.lesson_plan import LessonPlan
from app.models.render_job import RenderJob, RenderJobStatus
from app.models.scene import Scene
from app.models.source_document import SourceDocument
from app.schemas.requests import LessonCreate, SceneUpdate
from app.schemas.responses import (
    EvaluationResponse,
    LessonDetailResponse,
    LessonPlanResponse,
    LessonResponse,
    QuizQuestion,
    QuizResponse,
    RenderJobResponse,
    SceneResponse,
    TranscriptResponse,
    TranscriptSceneEntry,
)
from app.services.pipeline import LessonPipeline

router = APIRouter()


async def _get_lesson_or_404(lesson_id: UUID, db: AsyncSession) -> Lesson:
    result = await db.execute(
        select(Lesson)
        .options(selectinload(Lesson.scenes))
        .where(Lesson.id == lesson_id)
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson


@router.post("/lessons", response_model=LessonResponse, status_code=201)
async def create_lesson(body: LessonCreate, db: AsyncSession = Depends(get_db)):
    domain = LessonDomain(body.domain) if body.domain else LessonDomain.cs
    style = LessonStylePreset(body.style_preset) if body.style_preset else LessonStylePreset.clean_academic
    title = body.topic or "Untitled Lesson"

    if body.source_document_id:
        result = await db.execute(
            select(SourceDocument).where(SourceDocument.id == body.source_document_id)
        )
        source_doc = result.scalar_one_or_none()
        if not source_doc:
            raise HTTPException(status_code=404, detail="Source document not found")
        title = body.topic or source_doc.title

    lesson = Lesson(
        source_document_id=body.source_document_id,
        input_topic=body.topic,
        domain=domain,
        title=title,
        style_preset=style,
        status=LessonStatus.created,
    )
    db.add(lesson)
    await db.flush()
    await db.refresh(lesson)

    return LessonResponse.model_validate(lesson)


@router.get("/lessons/{lesson_id}", response_model=LessonDetailResponse)
async def get_lesson(lesson_id: UUID, db: AsyncSession = Depends(get_db)):
    lesson = await _get_lesson_or_404(lesson_id, db)
    return LessonDetailResponse.model_validate(lesson)


@router.post("/lessons/{lesson_id}/extract", response_model=LessonResponse)
async def extract_lesson(lesson_id: UUID, db: AsyncSession = Depends(get_db)):
    lesson = await _get_lesson_or_404(lesson_id, db)
    pipeline = LessonPipeline(db)
    lesson = await pipeline.extract(lesson_id)
    return LessonResponse.model_validate(lesson)


@router.post("/lessons/{lesson_id}/plan", response_model=LessonPlanResponse)
async def plan_lesson(lesson_id: UUID, db: AsyncSession = Depends(get_db)):
    lesson = await _get_lesson_or_404(lesson_id, db)
    pipeline = LessonPipeline(db)
    plan = await pipeline.plan(lesson_id)
    return LessonPlanResponse.model_validate(plan)


@router.post("/lessons/{lesson_id}/compile-scenes", response_model=list[SceneResponse])
async def compile_scenes(lesson_id: UUID, db: AsyncSession = Depends(get_db)):
    lesson = await _get_lesson_or_404(lesson_id, db)
    pipeline = LessonPipeline(db)
    scenes = await pipeline.compile_scenes(lesson_id)
    return [SceneResponse.model_validate(s) for s in scenes]


@router.post("/lessons/{lesson_id}/generate-assets", response_model=LessonResponse)
async def generate_assets(lesson_id: UUID, db: AsyncSession = Depends(get_db)):
    lesson = await _get_lesson_or_404(lesson_id, db)
    pipeline = LessonPipeline(db)
    lesson = await pipeline.generate_assets(lesson_id)
    return LessonResponse.model_validate(lesson)


@router.post("/lessons/{lesson_id}/render-preview", response_model=RenderJobResponse)
async def render_preview(lesson_id: UUID, db: AsyncSession = Depends(get_db)):
    lesson = await _get_lesson_or_404(lesson_id, db)
    pipeline = LessonPipeline(db)
    job = await pipeline.render(lesson_id, mode="preview")
    return RenderJobResponse.model_validate(job)


@router.post("/lessons/{lesson_id}/render-final", response_model=RenderJobResponse)
async def render_final(lesson_id: UUID, db: AsyncSession = Depends(get_db)):
    lesson = await _get_lesson_or_404(lesson_id, db)
    pipeline = LessonPipeline(db)
    job = await pipeline.render(lesson_id, mode="final")
    return RenderJobResponse.model_validate(job)


@router.get("/lessons/{lesson_id}/scenes", response_model=list[SceneResponse])
async def get_scenes(lesson_id: UUID, db: AsyncSession = Depends(get_db)):
    lesson = await _get_lesson_or_404(lesson_id, db)
    result = await db.execute(
        select(Scene).where(Scene.lesson_id == lesson_id).order_by(Scene.scene_order)
    )
    scenes = result.scalars().all()
    return [SceneResponse.model_validate(s) for s in scenes]


@router.patch("/scenes/{scene_id}", response_model=SceneResponse)
async def update_scene(scene_id: UUID, body: SceneUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Scene).where(Scene.id == scene_id))
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    if body.narration_text is not None:
        scene.narration_text = body.narration_text
    if body.on_screen_text is not None:
        scene.on_screen_text_json = body.on_screen_text
    if body.duration_sec is not None:
        scene.duration_sec = body.duration_sec

    await db.flush()
    await db.refresh(scene)
    return SceneResponse.model_validate(scene)


@router.post("/scenes/{scene_id}/regenerate", response_model=SceneResponse)
async def regenerate_scene(scene_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Scene).where(Scene.id == scene_id))
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    from app.models.scene import SceneStatus
    scene.status = SceneStatus.pending
    await db.flush()
    await db.refresh(scene)

    return SceneResponse.model_validate(scene)


@router.post("/lessons/{lesson_id}/evaluate", response_model=EvaluationResponse)
async def evaluate_lesson(lesson_id: UUID, db: AsyncSession = Depends(get_db)):
    lesson = await _get_lesson_or_404(lesson_id, db)
    pipeline = LessonPipeline(db)
    report = await pipeline.evaluate(lesson_id)
    return EvaluationResponse.model_validate(report)


@router.get("/lessons/{lesson_id}/evaluation", response_model=EvaluationResponse)
async def get_evaluation(lesson_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EvaluationReport)
        .where(EvaluationReport.lesson_id == lesson_id)
        .order_by(EvaluationReport.created_at.desc())
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="No evaluation report found for this lesson")
    return EvaluationResponse.model_validate(report)


@router.get("/lessons/{lesson_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(lesson_id: UUID, db: AsyncSession = Depends(get_db)):
    lesson = await _get_lesson_or_404(lesson_id, db)

    result = await db.execute(
        select(Scene).where(Scene.lesson_id == lesson_id).order_by(Scene.scene_order)
    )
    scenes = result.scalars().all()

    full_text_parts: list[str] = []
    scene_entries: list[TranscriptSceneEntry] = []
    cumulative_time = 0.0

    for scene in scenes:
        text = scene.narration_text or ""
        full_text_parts.append(f"[{scene.title}]\n{text}")
        scene_entries.append(
            TranscriptSceneEntry(
                scene_id=scene.id,
                scene_order=scene.scene_order,
                title=scene.title,
                text=text,
                timestamp=cumulative_time,
                duration_sec=scene.duration_sec,
            )
        )
        cumulative_time += scene.duration_sec

    return TranscriptResponse(
        full_text="\n\n".join(full_text_parts),
        total_duration_sec=cumulative_time,
        scenes=scene_entries,
    )


@router.get("/lessons/{lesson_id}/quiz", response_model=QuizResponse)
async def get_quiz(lesson_id: UUID, db: AsyncSession = Depends(get_db)):
    lesson = await _get_lesson_or_404(lesson_id, db)
    pipeline = LessonPipeline(db)
    quiz_data = await pipeline.generate_quiz(db, lesson)

    questions = []
    for q in quiz_data:
        correct = q.get("correct_answer", q.get("correct_index", 0))
        questions.append(
            QuizQuestion(
                question=q["question"],
                options=q["options"],
                correct_index=correct,
                explanation=q.get("explanation", ""),
            )
        )

    return QuizResponse(questions=questions)


@router.get("/lessons/{lesson_id}/download")
async def download_lesson(lesson_id: UUID, db: AsyncSession = Depends(get_db)):
    lesson = await _get_lesson_or_404(lesson_id, db)

    result = await db.execute(
        select(RenderJob)
        .where(RenderJob.lesson_id == lesson_id)
        .where(RenderJob.status == RenderJobStatus.completed)
        .order_by(RenderJob.completed_at.desc())
        .limit(1)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="No completed render found. Please render the lesson first.")

    return {
        "lesson_id": str(lesson_id),
        "title": lesson.title,
        "status": "completed",
        "job_type": job.job_type,
        "rendered_at": job.completed_at.isoformat() if job.completed_at else None,
        "message": "Video rendered successfully. Full MP4 export coming soon — Remotion/FFmpeg assembly is in progress.",
    }
