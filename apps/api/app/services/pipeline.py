import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.evaluation_report import EvaluationReport
from app.models.lesson import Lesson, LessonStatus
from app.models.lesson_plan import LessonPlan
from app.models.render_job import RenderJob, RenderJobStatus
from app.models.scene import Scene, SceneStatus, SceneType
from app.models.scene_asset import AssetStatus, AssetType, SceneAsset
from app.models.source_document import (
    SourceDocument,
    SourceDocumentStatus,
    SourceDocumentType,
)
from app.models.source_fragment import FragmentKind, SourceFragment
from app.providers.factory import (
    get_image_provider,
    get_llm_provider,
    get_music_provider,
    get_storage_provider,
    get_tts_provider,
    get_video_provider,
)
from app.services.assembly.service import AssemblyService
from app.services.compilation.service import CompilationService
from app.services.evaluation.service import EvaluationService
from app.services.extraction.service import ExtractionService
from app.services.ingestion.service import IngestionService
from app.services.music.service import MusicService
from app.services.narration.service import NarrationService
from app.services.planning.service import PlanningService
from app.services.rendering.service import RenderingService

logger = logging.getLogger(__name__)


class LessonPipeline:
    """
    Orchestrator that wires individual services into a cohesive lesson
    generation pipeline.

    New interface — provider-initialised, stateless w.r.t. DB session:

        pipeline = LessonPipeline()
        await pipeline.run_extraction(db, lesson)

    Backward-compatible interface (used by existing routes):

        pipeline = LessonPipeline(db)
        await pipeline.extract(lesson_id)
    """

    def __init__(self, db: AsyncSession | None = None):
        self.storage = get_storage_provider()
        self.llm = get_llm_provider()
        self.tts = get_tts_provider()
        self.music_provider = get_music_provider()
        self.image_provider = get_image_provider()
        self.video_provider = get_video_provider()

        self.ingestion = IngestionService(self.storage)
        self.extraction = ExtractionService(self.llm)
        self.planning = PlanningService(self.llm)
        self.compilation = CompilationService(self.llm)
        self.rendering = RenderingService(self.storage)
        self.narration = NarrationService(self.llm, self.tts, self.storage)
        self.music = MusicService(self.music_provider, self.storage)
        self.assembly = AssemblyService(self.storage)
        self.evaluation = EvaluationService(self.llm)

        # Backward compat: store db if passed directly
        self._db = db

    # ------------------------------------------------------------------
    # New interface — each method receives db + lesson
    # ------------------------------------------------------------------

    async def run_extraction(self, db: AsyncSession, lesson: Lesson) -> dict:
        """Run ingestion + concept extraction. Update lesson status."""
        lesson.status = LessonStatus.extracting
        await db.flush()

        source_doc: SourceDocument | None = None

        if lesson.source_document_id:
            result = await db.execute(
                select(SourceDocument)
                .where(SourceDocument.id == lesson.source_document_id)
            )
            source_doc = result.scalar_one_or_none()
            if not source_doc:
                raise ValueError("Source document not found")

            source_doc.status = SourceDocumentStatus.processing
            await db.flush()

            file_path = source_doc.storage_url
            if file_path and file_path.startswith("file://"):
                file_path = file_path[7:]

            raw_fragments = await self.ingestion.extract_fragments(
                source_type=source_doc.type.value,
                file_path=file_path,
                topic=None,
                domain=lesson.domain.value,
                doc_id=str(source_doc.id),
            )

            for frag_data in raw_fragments:
                db.add(SourceFragment(
                    source_document_id=source_doc.id,
                    ref_key=frag_data["ref_key"],
                    page_or_slide_number=frag_data.get("page_or_slide_number"),
                    kind=FragmentKind(frag_data["kind"]),
                    text=frag_data["text"],
                    bbox_json=frag_data.get("bbox"),
                ))

            source_doc.status = SourceDocumentStatus.ready
            await db.flush()
        else:
            source_doc = SourceDocument(
                type=SourceDocumentType.topic,
                title=lesson.input_topic or lesson.title,
                status=SourceDocumentStatus.ready,
            )
            db.add(source_doc)
            await db.flush()

            lesson.source_document_id = source_doc.id

            raw_fragments = await self.ingestion.extract_fragments(
                source_type="topic",
                file_path=None,
                topic=lesson.input_topic or lesson.title,
                domain=lesson.domain.value,
                doc_id=str(source_doc.id),
            )

            for frag_data in raw_fragments:
                db.add(SourceFragment(
                    source_document_id=source_doc.id,
                    ref_key=frag_data["ref_key"],
                    page_or_slide_number=frag_data.get("page_or_slide_number"),
                    kind=FragmentKind(frag_data["kind"]),
                    text=frag_data["text"],
                ))
            await db.flush()

        result = await db.execute(
            select(SourceFragment)
            .where(SourceFragment.source_document_id == source_doc.id)
        )
        fragments = result.scalars().all()
        fragment_dicts = [
            {"ref_key": f.ref_key, "kind": f.kind.value, "text": f.text}
            for f in fragments
        ]

        concepts = await self.extraction.extract(fragment_dicts, lesson.domain.value)

        existing_plan_result = await db.execute(
            select(LessonPlan).where(LessonPlan.lesson_id == lesson.id)
        )
        existing_plan = existing_plan_result.scalar_one_or_none()

        if existing_plan:
            existing_plan.concept_graph_json = concepts.get("concept_graph", {})
            existing_plan.prerequisites_json = concepts.get("prerequisites", [])
            existing_plan.misconceptions_json = concepts.get("misconceptions", [])
        else:
            db.add(LessonPlan(
                lesson_id=lesson.id,
                concept_graph_json=concepts.get("concept_graph", {}),
                prerequisites_json=concepts.get("prerequisites", []),
                misconceptions_json=concepts.get("misconceptions", []),
            ))

        extracted_title = concepts.get("title")
        if extracted_title and extracted_title != lesson.domain.value:
            lesson.title = extracted_title
        if not lesson.summary:
            lesson.summary = f"Lesson about {lesson.title}"

        lesson.status = LessonStatus.created
        await db.flush()
        await db.refresh(lesson)

        logger.info("Pipeline.run_extraction: completed for lesson %s", lesson.id)
        return concepts

    async def run_planning(self, db: AsyncSession, lesson: Lesson) -> dict:
        """Run pedagogy planning. Create/replace LessonPlan record."""
        lesson.status = LessonStatus.planning
        await db.flush()

        plan_result = await db.execute(
            select(LessonPlan).where(LessonPlan.lesson_id == lesson.id)
        )
        existing_plan = plan_result.scalar_one_or_none()

        concept_graph = {}
        if existing_plan and existing_plan.concept_graph_json:
            concept_graph = existing_plan.concept_graph_json

        plan_data = await self.planning.create_plan(
            concepts=concept_graph,
            domain=lesson.domain.value,
            style=lesson.style_preset.value,
        )

        if existing_plan:
            existing_plan.lesson_objectives_json = plan_data.get("objectives", [])
            existing_plan.plan_json = plan_data
        else:
            db.add(LessonPlan(
                lesson_id=lesson.id,
                concept_graph_json=concept_graph,
                lesson_objectives_json=plan_data.get("objectives", []),
                plan_json=plan_data,
            ))

        lesson.status = LessonStatus.planning
        await db.flush()

        logger.info("Pipeline.run_planning: completed for lesson %s", lesson.id)
        return plan_data

    async def run_scene_compilation(
        self, db: AsyncSession, lesson: Lesson
    ) -> list[Scene]:
        """Compile scenes from lesson plan. Create Scene records."""
        lesson.status = LessonStatus.compiling
        await db.flush()

        plan_result = await db.execute(
            select(LessonPlan).where(LessonPlan.lesson_id == lesson.id)
        )
        plan = plan_result.scalar_one_or_none()
        if not plan or not plan.plan_json:
            raise ValueError("Lesson plan not found. Run the planning step first.")

        existing = await db.execute(
            select(Scene).where(Scene.lesson_id == lesson.id)
        )
        for scene in existing.scalars().all():
            await db.delete(scene)
        await db.flush()

        scene_specs = await self.compilation.compile(plan.plan_json, lesson.domain.value)

        scenes: list[Scene] = []
        for idx, spec in enumerate(scene_specs):
            scene_type_str = spec.get("scene_type", "deterministic_animation")
            try:
                scene_type = SceneType(scene_type_str)
            except ValueError:
                scene_type = SceneType.deterministic_animation

            scene = Scene(
                lesson_id=lesson.id,
                scene_order=idx,
                scene_type=scene_type,
                title=spec.get("title", f"Scene {idx + 1}"),
                duration_sec=spec.get("duration_sec", 30),
                render_strategy=spec.get("render_strategy", "default"),
                source_refs_json=spec.get("source_refs", []),
                narration_text=spec.get("narration_text", ""),
                on_screen_text_json=spec.get("on_screen_text", []),
                scene_spec_json=spec,
                status=SceneStatus.pending,
            )
            db.add(scene)
            scenes.append(scene)

        await db.flush()
        for scene in scenes:
            await db.refresh(scene)

        logger.info(
            "Pipeline.run_scene_compilation: %d scenes for lesson %s",
            len(scenes), lesson.id,
        )
        return scenes

    async def run_asset_generation(
        self, db: AsyncSession, lesson: Lesson
    ) -> None:
        """Generate narrations and visual assets for each scene."""
        lesson.status = LessonStatus.generating_assets
        await db.flush()

        result = await db.execute(
            select(Scene)
            .where(Scene.lesson_id == lesson.id)
            .order_by(Scene.scene_order)
        )
        scenes = result.scalars().all()

        scene_specs = [s.scene_spec_json or {} for s in scenes]
        narrations = await self.narration.generate_all_narrations(
            scene_specs, str(lesson.id)
        )

        for scene, narration_result in zip(scenes, narrations):
            scene.narration_text = narration_result["narration_text"]
            scene.status = SceneStatus.generating

            db.add(SceneAsset(
                scene_id=scene.id,
                asset_type=AssetType.audio,
                provider="tts",
                prompt_version="v1",
                storage_url=narration_result["audio_url"],
                metadata_json={
                    "duration_sec": narration_result["duration_sec"],
                    "type": "narration",
                },
                status=AssetStatus.ready,
            ))

            spec = scene.scene_spec_json or {}
            for asset_req in spec.get("asset_requests", []):
                req_type = asset_req.get("type", "")
                prompt = asset_req.get("prompt", "")

                if req_type == "image" and prompt:
                    image_bytes = await self.image_provider.generate_image(
                        prompt=prompt,
                        style=lesson.style_preset.value,
                        width=1920,
                        height=1080,
                    )
                    img_path = f"assets/{lesson.id}/{scene.id}/image.png"
                    img_url = await self.storage.put_file(
                        img_path, image_bytes, "image/png"
                    )
                    db.add(SceneAsset(
                        scene_id=scene.id,
                        asset_type=AssetType.image,
                        provider="image",
                        prompt_version="v1",
                        storage_url=img_url,
                        metadata_json={"prompt": prompt},
                        status=AssetStatus.ready,
                    ))

                elif req_type == "video" and prompt:
                    video_bytes = await self.video_provider.generate_from_text(
                        prompt=prompt,
                        duration_sec=scene.duration_sec,
                    )
                    vid_path = f"assets/{lesson.id}/{scene.id}/video.mp4"
                    vid_url = await self.storage.put_file(
                        vid_path, video_bytes, "video/mp4"
                    )
                    db.add(SceneAsset(
                        scene_id=scene.id,
                        asset_type=AssetType.video,
                        provider="video",
                        prompt_version="v1",
                        storage_url=vid_url,
                        metadata_json={"prompt": prompt},
                        status=AssetStatus.ready,
                    ))

            scene.status = SceneStatus.rendered

        await db.flush()
        logger.info(
            "Pipeline.run_asset_generation: completed for lesson %s", lesson.id
        )

    async def run_render(
        self, db: AsyncSession, lesson: Lesson, mode: str = "preview"
    ) -> str:
        """Render video. Create RenderJob. Return video URL."""
        lesson.status = LessonStatus.rendering
        await db.flush()

        job = RenderJob(
            lesson_id=lesson.id,
            job_type=mode,
            status=RenderJobStatus.running,
            progress=0.0,
            started_at=datetime.now(timezone.utc),
        )
        db.add(job)
        await db.flush()

        result = await db.execute(
            select(Scene)
            .where(Scene.lesson_id == lesson.id)
            .order_by(Scene.scene_order)
        )
        scenes = result.scalars().all()
        scene_specs = [s.scene_spec_json or {} for s in scenes]

        audio_result = await db.execute(
            select(SceneAsset)
            .where(SceneAsset.scene_id.in_([s.id for s in scenes]))
            .where(SceneAsset.asset_type == AssetType.audio)
        )
        audio_urls = [a.storage_url for a in audio_result.scalars().all()]

        total_duration = sum(s.duration_sec for s in scenes)
        predominant_mood = "neutral"
        if scene_specs:
            moods = [s.get("music_mood", "neutral") for s in scene_specs]
            predominant_mood = max(set(moods), key=moods.count)

        music_url: str | None = None
        if total_duration > 0:
            music_url = await self.music.generate_background_track(
                mood=predominant_mood,
                duration_sec=total_duration,
                lesson_id=str(lesson.id),
            )

        if mode == "preview":
            video_url = await self.rendering.render_preview(scene_specs, lesson.style_preset.value)
        else:
            video_url = await self.rendering.render_final(
                scene_specs, lesson.style_preset.value, audio_urls, music_url
            )

        job.status = RenderJobStatus.completed
        job.progress = 100.0
        job.completed_at = datetime.now(timezone.utc)
        lesson.status = LessonStatus.completed

        await db.flush()
        await db.refresh(job)

        logger.info(
            "Pipeline.run_render: %s render completed for lesson %s -> %s",
            mode, lesson.id, video_url,
        )
        return video_url

    async def run_evaluation(self, db: AsyncSession, lesson: Lesson) -> dict:
        """Evaluate lesson quality. Create EvaluationReport."""
        plan_result = await db.execute(
            select(LessonPlan).where(LessonPlan.lesson_id == lesson.id)
        )
        plan = plan_result.scalar_one_or_none()

        result = await db.execute(
            select(Scene)
            .where(Scene.lesson_id == lesson.id)
            .order_by(Scene.scene_order)
        )
        scenes = result.scalars().all()

        lesson_data = {
            "title": lesson.title,
            "domain": lesson.domain.value,
            "plan": plan.plan_json if plan else {},
            "scenes": [
                {
                    "title": s.title,
                    "scene_type": s.scene_type.value,
                    "duration_sec": s.duration_sec,
                    "narration_text": s.narration_text or "",
                    "on_screen_text": s.on_screen_text_json or [],
                    "source_refs": s.source_refs_json or [],
                    **(s.scene_spec_json or {}),
                }
                for s in scenes
            ],
        }

        report_data = await self.evaluation.evaluate(lesson_data)

        report = EvaluationReport(
            lesson_id=lesson.id,
            report_json=report_data,
            score_overall=report_data.get("overall_score", 0.0),
            flags_json=report_data.get("flags", []),
        )
        db.add(report)
        await db.flush()
        await db.refresh(report)

        logger.info(
            "Pipeline.run_evaluation: score=%.2f for lesson %s",
            report.score_overall, lesson.id,
        )
        return report_data

    async def generate_quiz(self, db: AsyncSession, lesson: Lesson) -> list[dict]:
        """Generate quiz questions for the lesson."""
        plan_result = await db.execute(
            select(LessonPlan).where(LessonPlan.lesson_id == lesson.id)
        )
        plan = plan_result.scalar_one_or_none()

        result = await db.execute(
            select(Scene)
            .where(Scene.lesson_id == lesson.id)
            .order_by(Scene.scene_order)
        )
        scenes = result.scalars().all()

        plan_json = plan.plan_json if plan else {"lesson_title": lesson.title}
        scene_dicts = [
            {
                "title": s.title,
                "scene_type": s.scene_type.value,
                "narration_text": s.narration_text or "",
                "on_screen_text": s.on_screen_text_json or [],
            }
            for s in scenes
        ]

        quiz = await self.llm.generate_quiz(plan_json, scene_dicts)

        logger.info(
            "Pipeline.generate_quiz: %d questions for lesson %s",
            len(quiz), lesson.id,
        )
        return quiz

    async def generate_transcript(
        self, db: AsyncSession, lesson: Lesson
    ) -> dict:
        """Generate transcript from scene narrations."""
        result = await db.execute(
            select(Scene)
            .where(Scene.lesson_id == lesson.id)
            .order_by(Scene.scene_order)
        )
        scenes = result.scalars().all()

        scene_dicts = [
            {
                "scene_id": str(s.id),
                "title": s.title,
                "narration_text": s.narration_text or "",
                "duration_sec": s.duration_sec,
            }
            for s in scenes
        ]

        transcript = await self.narration.generate_transcript(scene_dicts)

        logger.info(
            "Pipeline.generate_transcript: %d scenes for lesson %s",
            len(scenes), lesson.id,
        )
        return transcript

    # ------------------------------------------------------------------
    # Backward-compatible interface (used by existing routes)
    # ------------------------------------------------------------------

    async def _get_lesson(self, lesson_id: uuid.UUID) -> Lesson:
        """Fetch lesson with eager-loaded relationships."""
        assert self._db is not None, "DB session required for backward-compat methods"
        result = await self._db.execute(
            select(Lesson)
            .options(selectinload(Lesson.scenes), selectinload(Lesson.lesson_plan))
            .where(Lesson.id == lesson_id)
        )
        lesson = result.scalar_one_or_none()
        if not lesson:
            raise ValueError(f"Lesson {lesson_id} not found")
        return lesson

    async def extract(self, lesson_id: uuid.UUID) -> Lesson:
        """Backward-compat: run extraction and return lesson."""
        assert self._db is not None
        lesson = await self._get_lesson(lesson_id)
        await self.run_extraction(self._db, lesson)
        await self._db.refresh(lesson)
        return lesson

    async def plan(self, lesson_id: uuid.UUID) -> LessonPlan:
        """Backward-compat: run planning and return LessonPlan."""
        assert self._db is not None
        lesson = await self._get_lesson(lesson_id)
        await self.run_planning(self._db, lesson)

        result = await self._db.execute(
            select(LessonPlan).where(LessonPlan.lesson_id == lesson_id)
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise ValueError("Lesson plan not found after planning step")
        await self._db.refresh(plan)
        return plan

    async def compile_scenes(self, lesson_id: uuid.UUID) -> list[Scene]:
        """Backward-compat: compile scenes and return Scene list."""
        assert self._db is not None
        lesson = await self._get_lesson(lesson_id)
        return await self.run_scene_compilation(self._db, lesson)

    async def generate_assets(self, lesson_id: uuid.UUID) -> Lesson:
        """Backward-compat: generate assets and return lesson."""
        assert self._db is not None
        lesson = await self._get_lesson(lesson_id)
        await self.run_asset_generation(self._db, lesson)
        await self._db.refresh(lesson)
        return lesson

    async def render(
        self, lesson_id: uuid.UUID, mode: str = "preview"
    ) -> RenderJob:
        """Backward-compat: render and return RenderJob."""
        assert self._db is not None
        lesson = await self._get_lesson(lesson_id)
        await self.run_render(self._db, lesson, mode)

        result = await self._db.execute(
            select(RenderJob)
            .where(RenderJob.lesson_id == lesson_id)
            .order_by(RenderJob.created_at.desc())
        )
        job = result.scalars().first()
        if not job:
            raise ValueError("Render job not found after rendering")
        return job

    async def evaluate(self, lesson_id: uuid.UUID) -> EvaluationReport:
        """Backward-compat: evaluate and return EvaluationReport."""
        assert self._db is not None
        lesson = await self._get_lesson(lesson_id)
        await self.run_evaluation(self._db, lesson)

        result = await self._db.execute(
            select(EvaluationReport)
            .where(EvaluationReport.lesson_id == lesson_id)
            .order_by(EvaluationReport.created_at.desc())
        )
        report = result.scalars().first()
        if not report:
            raise ValueError("Evaluation report not found")
        return report
