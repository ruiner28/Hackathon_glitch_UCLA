import mimetypes
import os
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db
from app.models.evaluation_report import EvaluationReport
from app.models.lesson import Lesson, LessonDomain, LessonStatus, LessonStylePreset
from app.models.lesson_plan import LessonPlan
from app.models.render_job import RenderJob, RenderJobStatus
from app.models.scene import Scene
from app.models.scene_asset import AssetStatus, AssetType, SceneAsset
from app.models.source_document import SourceDocument
from app.schemas.requests import LessonCreate, LessonStyleUpdate, SceneReorder, SceneUpdate
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


def _scene_response(scene: Scene) -> SceneResponse:
    return SceneResponse.model_validate(scene).model_copy(
        update={"preview_image_url": f"/api/scenes/{scene.id}/thumbnail"}
    )


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
    base = LessonDetailResponse.model_validate(lesson)
    ordered = sorted(lesson.scenes, key=lambda s: s.scene_order)
    return base.model_copy(update={"scenes": [_scene_response(s) for s in ordered]})


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
    return [_scene_response(s) for s in scenes]


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
    return [_scene_response(s) for s in scenes]


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
    spec = dict(scene.scene_spec_json or {})
    spec_updated = False
    if body.veo_eligible is not None:
        spec["veo_eligible"] = body.veo_eligible
        if not body.veo_eligible:
            spec["veo_score"] = 0.0
        spec_updated = True
    if body.render_mode is not None:
        spec["render_mode"] = body.render_mode
        if body.render_mode == "force_veo":
            spec["veo_eligible"] = True
        elif body.render_mode == "force_static":
            spec["veo_eligible"] = False
            spec["veo_score"] = 0.0
        spec_updated = True
    if spec_updated:
        scene.scene_spec_json = spec

    await db.flush()
    await db.refresh(scene)
    return _scene_response(scene)


@router.get("/scenes/{scene_id}/thumbnail")
async def get_scene_thumbnail(scene_id: UUID, db: AsyncSession = Depends(get_db)):
    """Serve the latest ready image asset for editor thumbnails (local file storage)."""
    result = await db.execute(
        select(SceneAsset)
        .where(SceneAsset.scene_id == scene_id)
        .where(SceneAsset.asset_type == AssetType.image)
        .where(SceneAsset.status == AssetStatus.ready)
        .order_by(SceneAsset.created_at.desc())
    )
    asset = result.scalars().first()
    if not asset:
        raise HTTPException(status_code=404, detail="No image asset for this scene.")
    url = asset.storage_url or ""
    path = url[7:] if url.startswith("file://") else url
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Image file not found.")
    media_type, _ = mimetypes.guess_type(path)
    return FileResponse(path, media_type=media_type or "image/png")


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

    return _scene_response(scene)


@router.post("/scenes/{scene_id}/regenerate-assets", response_model=SceneResponse)
async def regenerate_scene_assets(scene_id: UUID, db: AsyncSession = Depends(get_db)):
    """Re-generate just the image/video assets for a single scene."""
    result = await db.execute(select(Scene).where(Scene.id == scene_id))
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    pipeline = LessonPipeline(db)
    await pipeline.regenerate_single_scene_assets(scene)
    await db.refresh(scene)
    return _scene_response(scene)


@router.post("/lessons/{lesson_id}/reorder-scenes", response_model=list[SceneResponse])
async def reorder_scenes(
    lesson_id: UUID, body: SceneReorder, db: AsyncSession = Depends(get_db),
):
    await _get_lesson_or_404(lesson_id, db)
    result = await db.execute(
        select(Scene).where(Scene.lesson_id == lesson_id)
    )
    scenes_map = {s.id: s for s in result.scalars().all()}

    for new_order, sid in enumerate(body.scene_ids):
        scene = scenes_map.get(sid)
        if scene:
            scene.scene_order = new_order

    await db.flush()
    ordered = sorted(scenes_map.values(), key=lambda s: s.scene_order)
    for s in ordered:
        await db.refresh(s)
    return [_scene_response(s) for s in ordered]


@router.patch("/lessons/{lesson_id}/style", response_model=LessonResponse)
async def update_lesson_style(
    lesson_id: UUID, body: LessonStyleUpdate, db: AsyncSession = Depends(get_db),
):
    lesson = await _get_lesson_or_404(lesson_id, db)
    try:
        lesson.style_preset = LessonStylePreset(body.style_preset)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid style preset: {body.style_preset}",
        )
    await db.flush()
    await db.refresh(lesson)
    return LessonResponse.model_validate(lesson)


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
        spec = scene.scene_spec_json or {}
        scene_entries.append(
            TranscriptSceneEntry(
                scene_id=scene.id,
                scene_order=scene.scene_order,
                title=scene.title,
                text=text,
                timestamp=cumulative_time,
                duration_sec=scene.duration_sec,
                scene_type=scene.scene_type.value if scene.scene_type else "",
                learning_objective=spec.get("learning_objective", ""),
                teaching_note=spec.get("teaching_note", ""),
            )
        )
        cumulative_time += scene.duration_sec

    # Extract lesson-level pedagogical metadata from the lesson plan
    plan_result = await db.execute(
        select(LessonPlan).where(LessonPlan.lesson_id == lesson_id)
    )
    plan = plan_result.scalar_one_or_none()
    plan_json = plan.plan_json if plan else {}
    misconceptions = plan_json.get("misconceptions", []) if plan_json else []
    prerequisites = plan_json.get("prerequisites", []) if plan_json else []

    return TranscriptResponse(
        full_text="\n\n".join(full_text_parts),
        total_duration_sec=cumulative_time,
        scenes=scene_entries,
        misconceptions=misconceptions,
        prerequisites=prerequisites,
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


def _find_video_path(lesson_id: UUID) -> Path | None:
    """Locate the rendered MP4 for a lesson in local storage."""
    candidates = [
        Path("./storage/output") / str(lesson_id) / "lesson.mp4",
        Path("./storage") / "output" / str(lesson_id) / "lesson.mp4",
    ]
    for p in candidates:
        if p.exists() and p.stat().st_size > 0:
            return p
    renders_dir = Path("./storage/renders")
    if renders_dir.exists():
        mp4s = sorted(renders_dir.rglob("lesson.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
        if mp4s:
            return mp4s[0]
    return None


@router.head("/lessons/{lesson_id}/video")
@router.get("/lessons/{lesson_id}/video")
async def stream_video(lesson_id: UUID, db: AsyncSession = Depends(get_db)):
    await _get_lesson_or_404(lesson_id, db)
    video_path = _find_video_path(lesson_id)
    if not video_path:
        raise HTTPException(status_code=404, detail="Video not yet rendered.")
    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes"},
    )


@router.get("/lessons/{lesson_id}/scene-interactions")
async def get_scene_interactions(lesson_id: UUID, db: AsyncSession = Depends(get_db)):
    """Return interaction-ready metadata for every scene — designed for future Gemini Live."""
    await _get_lesson_or_404(lesson_id, db)
    result = await db.execute(
        select(Scene).where(Scene.lesson_id == lesson_id).order_by(Scene.scene_order)
    )
    scenes = result.scalars().all()

    plan_result = await db.execute(
        select(LessonPlan).where(LessonPlan.lesson_id == lesson_id)
    )
    plan = plan_result.scalar_one_or_none()
    plan_json = plan.plan_json if plan else {}

    interactions = []
    cumulative = 0.0
    for s in scenes:
        spec = s.scene_spec_json or {}
        interactions.append({
            "scene_id": str(s.id),
            "scene_order": s.scene_order,
            "title": s.title,
            "scene_type": s.scene_type.value if s.scene_type else "",
            "timestamp_sec": round(cumulative, 1),
            "duration_sec": s.duration_sec,
            "learning_objective": spec.get("learning_objective", ""),
            "teaching_note": spec.get("teaching_note", ""),
            "narration_summary": (s.narration_text or "")[:200],
            "visual_elements": spec.get("visual_elements", []),
            "on_screen_text": s.on_screen_text_json or [],
            "diagram_refs": [
                ar.get("prompt", "")
                for ar in spec.get("asset_requests", [])
                if ar.get("type") == "image"
            ],
            "interaction_hooks": {
                "ask_about": f"Explain the concept in '{s.title}' in simpler terms",
                "explain_simpler": f"Give me a beginner-friendly explanation of {s.title}",
                "show_flow": f"Walk me through the visual flow in {s.title} step by step",
                "deeper_dive": f"What are the edge cases and tradeoffs for {s.title}?",
                "quiz_me": f"Ask me a question about {s.title}",
            },
        })
        cumulative += s.duration_sec

    return {
        "lesson_id": str(lesson_id),
        "scene_count": len(interactions),
        "total_duration_sec": round(cumulative, 1),
        "prerequisites": plan_json.get("prerequisites", []),
        "misconceptions": plan_json.get("misconceptions", []),
        "scenes": interactions,
    }


@router.get("/lessons/{lesson_id}/subtitles")
async def get_subtitles(lesson_id: UUID, db: AsyncSession = Depends(get_db)):
    await _get_lesson_or_404(lesson_id, db)
    candidates = [
        Path("./storage/output") / str(lesson_id) / "subtitles.srt",
        Path("./storage") / "output" / str(lesson_id) / "subtitles.srt",
    ]
    for p in candidates:
        if p.exists():
            return FileResponse(
                path=str(p),
                media_type="text/plain",
                headers={"Content-Type": "text/plain; charset=utf-8"},
            )
    raise HTTPException(status_code=404, detail="Subtitles not yet generated.")


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

    video_path = _find_video_path(lesson_id)
    if video_path:
        safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in lesson.title)[:50]
        filename = f"{safe_title or 'lesson'}.mp4"
        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            filename=filename,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return {
        "lesson_id": str(lesson_id),
        "title": lesson.title,
        "status": "completed",
        "job_type": job.job_type,
        "rendered_at": job.completed_at.isoformat() if job.completed_at else None,
        "message": "Video render completed but file not found in storage.",
    }
