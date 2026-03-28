import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

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
from app.core.config import get_settings
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
from app.services.diagram.service import DiagramService
from app.services.evaluation.service import EvaluationService
from app.services.extraction.service import ExtractionService
from app.services.ingestion.service import IngestionService
from app.services.music.service import MusicService
from app.services.narration.service import NarrationService
from app.services.planning.service import PlanningService
from app.services.rendering.service import RenderingService
from app.services.visual_system.nano_banana_prompt import enrich_image_prompt_from_scene_spec

logger = logging.getLogger(__name__)


def _ordered_audio_urls_for_scenes(
    scenes: list[Scene], audio_rows: list[SceneAsset],
) -> list[str]:
    """Map narration assets to scene order (fixes nondeterministic query order)."""
    by_scene = {str(a.scene_id): a.storage_url for a in audio_rows}
    return [by_scene.get(str(s.id), "") for s in scenes]


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
        self.diagram = DiagramService(self.llm)

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

            # Topic-based lessons reuse an existing SourceDocument; must pass the topic string
            # (extract_fragments(..., source_type="topic", topic=None) raises).
            topic_arg: str | None = None
            if source_doc.type == SourceDocumentType.topic:
                topic_arg = (
                    (lesson.input_topic or source_doc.title or lesson.title or "").strip()
                    or None
                )
                if not topic_arg:
                    raise ValueError(
                        "Topic lesson is missing input_topic/title on the lesson or source document."
                    )

            raw_fragments = await self.ingestion.extract_fragments(
                source_type=source_doc.type.value,
                file_path=file_path,
                topic=topic_arg,
                domain=lesson.domain.value,
                doc_id=str(source_doc.id),
            )

            for frag_data in raw_fragments:
                meta = {}
                if frag_data.get("bbox"):
                    meta["bbox"] = frag_data["bbox"]
                if frag_data.get("academic_section"):
                    meta["academic_section"] = frag_data["academic_section"]
                if frag_data.get("font_size"):
                    meta["font_size"] = frag_data["font_size"]

                db.add(SourceFragment(
                    source_document_id=source_doc.id,
                    ref_key=frag_data["ref_key"],
                    page_or_slide_number=frag_data.get("page_or_slide_number"),
                    kind=FragmentKind(frag_data["kind"]),
                    text=frag_data["text"],
                    bbox_json=meta or None,
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
        fragment_dicts = []
        for f in fragments:
            fd = {"ref_key": f.ref_key, "kind": f.kind.value, "text": f.text}
            if f.bbox_json and isinstance(f.bbox_json, dict):
                if f.bbox_json.get("academic_section"):
                    fd["academic_section"] = f.bbox_json["academic_section"]
            fragment_dicts.append(fd)

        concepts = await self.extraction.extract(fragment_dicts, lesson.domain.value)

        existing_plan_result = await db.execute(
            select(LessonPlan).where(LessonPlan.lesson_id == lesson.id)
        )
        existing_plan = existing_plan_result.scalar_one_or_none()

        concept_graph = concepts.get("concept_graph", {})
        if concepts.get("is_paper"):
            concept_graph["is_paper"] = True
            concept_graph["paper_sections"] = concepts.get("paper_sections", {})

        if existing_plan:
            existing_plan.concept_graph_json = concept_graph
            existing_plan.prerequisites_json = concepts.get("prerequisites", [])
            existing_plan.misconceptions_json = concepts.get("misconceptions", [])
        else:
            db.add(LessonPlan(
                lesson_id=lesson.id,
                concept_graph_json=concept_graph,
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

        topic_context = lesson.title or lesson.input_topic or lesson.domain.value
        plan_data = await self.planning.create_plan(
            concepts=concept_graph,
            domain=topic_context,
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

    def _is_diagram_topic(self, lesson: Lesson, plan: LessonPlan | None = None) -> bool:
        """Decide whether this lesson should use the diagram-based path."""
        topic = (lesson.input_topic or lesson.title or "").lower()
        from app.services.diagram.rate_limiter import get_curated_diagram
        if get_curated_diagram(topic):
            return True
        if lesson.domain and lesson.domain.value == "system_design":
            return True
        if plan and plan.plan_json:
            sections = plan.plan_json.get("sections", [])
            sys_types = {"system_design_graph", "primary_visual_walkthrough"}
            if any(s.get("scene_type") in sys_types for s in sections):
                return True
        return False

    async def run_diagram_generation(
        self, db: AsyncSession, lesson: Lesson
    ) -> tuple[dict, list[dict]] | None:
        """Generate diagram spec + walkthrough states if topic qualifies.

        Returns ``(diagram_spec, walkthrough_states)`` or ``None`` if
        the lesson is not a diagram topic.
        """
        plan_result = await db.execute(
            select(LessonPlan).where(LessonPlan.lesson_id == lesson.id)
        )
        plan = plan_result.scalar_one_or_none()

        if not self._is_diagram_topic(lesson, plan):
            logger.info(
                "Pipeline.run_diagram_generation: skipped (not a diagram topic) lesson=%s",
                lesson.id,
            )
            return None

        topic = lesson.input_topic or lesson.title or ""
        concepts = plan.concept_graph_json if plan else None
        sections = (plan.plan_json or {}).get("sections", []) if plan else []

        spec, states = await self.diagram.generate_full(topic, concepts, sections)

        if plan:
            plan.diagram_spec_json = spec
            plan.walkthrough_states_json = states
        else:
            db.add(LessonPlan(
                lesson_id=lesson.id,
                diagram_spec_json=spec,
                walkthrough_states_json=states,
            ))
        await db.flush()

        logger.info(
            "Pipeline.run_diagram_generation: spec + %d states for lesson %s",
            len(states), lesson.id,
        )
        return spec, states

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

        if plan.diagram_spec_json and plan.walkthrough_states_json:
            topic = lesson.input_topic or lesson.title or lesson.domain.value
            scene_specs = self.compilation.compile_from_diagram(
                plan.diagram_spec_json,
                plan.walkthrough_states_json,
                topic,
            )
        else:
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

    async def _generate_diagram_assets(
        self, db: AsyncSession, lesson: Lesson, scenes: list[Scene],
    ) -> None:
        """Generate SVG-to-PNG images + TTS narration for diagram walkthrough scenes.

        Optionally generates one hero image (Gemini) for the first scene and
        one short Veo clip (3-5s) for a dynamic scene if the providers are
        available and the scene qualifies.
        """
        from app.services.diagram.renderer import render_svg_for_state, svg_to_png

        plan_result = await db.execute(
            select(LessonPlan).where(LessonPlan.lesson_id == lesson.id)
        )
        plan = plan_result.scalar_one_or_none()
        if not plan or not plan.diagram_spec_json:
            raise ValueError("Diagram spec missing on LessonPlan")

        diagram_spec = plan.diagram_spec_json

        scene_specs = [s.scene_spec_json or {} for s in scenes]
        narrations = await self.narration.generate_all_narrations(
            scene_specs, str(lesson.id),
        )

        hero_generated = False
        veo_generated = False

        for idx, (scene, narration_result) in enumerate(zip(scenes, narrations)):
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
            walkthrough_state = spec.get("walkthrough_state", {})

            svg_string = render_svg_for_state(diagram_spec, walkthrough_state)
            png_bytes = svg_to_png(svg_string, width=1920, height=1080)

            img_path = f"assets/{lesson.id}/{scene.id}/image.png"
            img_url = await self.storage.put_file(img_path, png_bytes, "image/png")

            db.add(SceneAsset(
                scene_id=scene.id,
                asset_type=AssetType.image,
                provider="svg_renderer",
                prompt_version="v1-diagram",
                storage_url=img_url,
                metadata_json={
                    "state_id": walkthrough_state.get("state_id", ""),
                    "renderer": "svg_diagram",
                },
                status=AssetStatus.ready,
            ))

            if idx == 0 and not hero_generated:
                try:
                    topic = diagram_spec.get("topic", lesson.title or "")
                    comp_names = ", ".join(
                        c.get("label", c.get("id", ""))
                        for c in diagram_spec.get("components", [])
                    )
                    hero_prompt = (
                        f"Create a clean technical architecture diagram that explains how a {topic} works in a modern backend system. "
                        f"Style: professional system design diagram, white or light background, crisp vector look, "
                        f"minimal but polished, blue/gray/green accents, readable labels, balanced spacing, "
                        f"arrows clearly showing request flow. "
                        f"Show these components from left to right: {comp_names}. "
                        f"Demonstrate the working with two paths: an allowed request flow (green, 200 OK) and "
                        f"a blocked request flow (red, 429 Too Many Requests). "
                        f"Include visual annotations for the algorithm logic, per-user/per-IP request counting, "
                        f"time window examples, counter increment, and counter reset. "
                        f"Add a small side panel showing the internal logic steps. "
                        f"Use modern architecture icons, soft shadows, rounded boxes, and directional arrows. "
                        f"Make the diagram easy for an interviewer, engineer, or student to understand at a glance."
                    )
                    hero_bytes = await self.image_provider.generate_image(
                        prompt=hero_prompt,
                        style=lesson.style_preset.value,
                        width=1920,
                        height=1080,
                    )
                    if hero_bytes and len(hero_bytes) > 100:
                        hero_path = f"assets/{lesson.id}/{scene.id}/hero.png"
                        hero_url = await self.storage.put_file(
                            hero_path, hero_bytes, "image/png",
                        )
                        db.add(SceneAsset(
                            scene_id=scene.id,
                            asset_type=AssetType.image,
                            provider="image",
                            prompt_version="v1-hero",
                            storage_url=hero_url,
                            metadata_json={"prompt": hero_prompt, "hero": True},
                            status=AssetStatus.ready,
                        ))
                        hero_generated = True
                        logger.info("Pipeline: hero image generated for lesson %s", lesson.id)
                except Exception as hero_err:
                    logger.warning("Hero image generation failed: %s", hero_err)

            if (
                not veo_generated
                and walkthrough_state.get("overlay_mode")
                and walkthrough_state.get("state_id", "").lower() not in ("overview", "summary")
            ):
                try:
                    state_title = walkthrough_state.get("title", "")
                    veo_prompt = (
                        f"Short 3-second animation showing {state_title} in action. "
                        f"Smooth camera, clean technical style, data flowing through system. "
                        f"Professional educational visualization."
                    )
                    video_bytes = await self.video_provider.generate_from_text(
                        prompt=veo_prompt, duration_sec=3.0,
                    )
                    if video_bytes and len(video_bytes) > 500:
                        vid_path = f"assets/{lesson.id}/{scene.id}/veo.mp4"
                        vid_url = await self.storage.put_file(
                            vid_path, video_bytes, "video/mp4",
                        )
                        db.add(SceneAsset(
                            scene_id=scene.id,
                            asset_type=AssetType.video,
                            provider="video",
                            prompt_version="v1-diagram-veo",
                            storage_url=vid_url,
                            metadata_json={"prompt": veo_prompt, "diagram_veo": True},
                            status=AssetStatus.ready,
                        ))
                        veo_generated = True
                        logger.info("Pipeline: Veo clip generated for state %s", state_title)
                except Exception as veo_err:
                    logger.warning("Veo clip generation failed: %s", veo_err)

            scene.status = SceneStatus.rendered

        await db.flush()
        logger.info(
            "Pipeline._generate_diagram_assets: %d states, hero=%s, veo=%s for lesson %s",
            len(scenes), hero_generated, veo_generated, lesson.id,
        )

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

        is_diagram = all(
            s.scene_type == SceneType.primary_visual_walkthrough for s in scenes
        ) and len(scenes) > 0

        if is_diagram:
            await self._generate_diagram_assets(db, lesson, scenes)
            logger.info(
                "Pipeline.run_asset_generation: diagram path for lesson %s",
                lesson.id,
            )
            return

        from app.services import demo_cache as dc

        slug = dc.resolve_demo_cache_slug(lesson.input_topic)
        if slug and dc.cache_is_ready_for_assets(slug, len(scenes)):
            await self._apply_demo_cached_assets(db, lesson, scenes, slug)
            await db.flush()
            logger.info(
                "Pipeline.run_asset_generation: demo cache hit slug=%s lesson=%s",
                slug,
                lesson.id,
            )
            return

        scene_specs = [s.scene_spec_json or {} for s in scenes]
        narrations = await self.narration.generate_all_narrations(
            scene_specs, str(lesson.id)
        )

        for scene_idx, (scene, narration_result) in enumerate(zip(scenes, narrations)):
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
            generated_image_for_scene = False
            render_mode = spec.get("render_mode", "auto")

            for asset_req in spec.get("asset_requests", []):
                req_type = asset_req.get("type", "")
                prompt = asset_req.get("prompt", "")

                if req_type == "image" and prompt:
                    img_prompt = enrich_image_prompt_from_scene_spec(
                        spec,
                        lesson.style_preset.value,
                        lesson.title,
                        scene_idx,
                        len(scenes),
                    )
                    image_bytes = await self.image_provider.generate_image(
                        prompt=img_prompt,
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
                        metadata_json={"prompt": img_prompt},
                        status=AssetStatus.ready,
                    ))
                    generated_image_for_scene = True

                elif (
                    req_type == "video"
                    and prompt
                    and spec.get("veo_eligible")
                    and render_mode != "force_static"
                ):
                    max_dur = max(
                        3.0,
                        min(asset_req.get("max_duration_sec", 5.0), 5.0),
                    )
                    try:
                        video_bytes = await self.video_provider.generate_from_text(
                            prompt=prompt,
                            duration_sec=max_dur,
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
                            metadata_json={
                                "prompt": prompt,
                                "max_duration_sec": max_dur,
                                "veo_score": spec.get("veo_score", 0),
                            },
                            status=AssetStatus.ready,
                        ))
                    except Exception as veo_err:
                        logger.warning(
                            "Veo generation failed for scene %s, using static fallback: %s",
                            scene.id, veo_err,
                        )

            # Generate Veo clip for veo-eligible scenes that didn't get one via asset_requests
            veo_prompt = spec.get("veo_prompt", "")
            has_video_asset = any(
                ar.get("type") == "video" for ar in spec.get("asset_requests", [])
            )
            if (
                spec.get("veo_eligible")
                and veo_prompt
                and not has_video_asset
                and render_mode != "force_static"
            ):
                try:
                    veo_dur = max(3.0, min(spec.get("duration_sec", 5), 5.0))
                    video_bytes = await self.video_provider.generate_from_text(
                        prompt=veo_prompt, duration_sec=veo_dur,
                    )
                    if video_bytes and len(video_bytes) > 500:
                        vid_path = f"assets/{lesson.id}/{scene.id}/video.mp4"
                        vid_url = await self.storage.put_file(
                            vid_path, video_bytes, "video/mp4"
                        )
                        db.add(SceneAsset(
                            scene_id=scene.id,
                            asset_type=AssetType.video,
                            provider="video",
                            prompt_version="v1-fallback-veo",
                            storage_url=vid_url,
                            metadata_json={"prompt": veo_prompt, "fallback": True},
                            status=AssetStatus.ready,
                        ))
                        logger.info("Pipeline: fallback Veo clip for scene %s", scene.id)
                except Exception as veo_err:
                    logger.warning("Fallback Veo failed for scene %s: %s", scene.id, veo_err)

            # Fallback: generate image for every scene that didn't get one
            if not generated_image_for_scene:
                if not spec.get("image_prompt"):
                    title = spec.get("title", "")
                    narr = spec.get("narration_text", "")
                    scene_type = spec.get("scene_type", "concept")
                    spec = {**spec, "image_prompt": (
                        f"Educational {scene_type} diagram for: {title}. "
                        f"Context: {narr[:200]}. "
                        f"Clean technical illustration, labeled components."
                    )}
                fallback_prompt = enrich_image_prompt_from_scene_spec(
                    spec,
                    lesson.style_preset.value,
                    lesson.title,
                    scene_idx,
                    len(scenes),
                )
                try:
                    image_bytes = await self.image_provider.generate_image(
                        prompt=fallback_prompt,
                        style=lesson.style_preset.value,
                        width=1920,
                        height=1080,
                    )
                    if image_bytes and len(image_bytes) > 100:
                        img_path = f"assets/{lesson.id}/{scene.id}/image.png"
                        img_url = await self.storage.put_file(
                            img_path, image_bytes, "image/png"
                        )
                        db.add(SceneAsset(
                            scene_id=scene.id,
                            asset_type=AssetType.image,
                            provider="image",
                            prompt_version="v1-fallback",
                            storage_url=img_url,
                            metadata_json={"prompt": fallback_prompt, "fallback": True},
                            status=AssetStatus.ready,
                        ))
                        logger.info("Pipeline: fallback image for scene %s", scene.id)
                except Exception as img_err:
                    logger.warning("Fallback image failed for scene %s: %s", scene.id, img_err)

            scene.status = SceneStatus.rendered

        await db.flush()
        logger.info(
            "Pipeline.run_asset_generation: completed for lesson %s", lesson.id
        )

    async def _apply_demo_cached_assets(
        self,
        db: AsyncSession,
        lesson: Lesson,
        scenes: list[Scene],
        slug: str,
    ) -> None:
        """Copy pre-built images, audio, and optional Veo clips from demo disk cache."""
        from app.services import demo_cache as dc

        manifest = dc.load_manifest(slug)
        if not manifest:
            raise RuntimeError(f"demo cache manifest missing for slug={slug}")
        texts: list[str] = manifest.get("narration_texts", [])
        if len(texts) != len(scenes):
            raise RuntimeError(
                f"demo cache narration_texts length {len(texts)} != scenes {len(scenes)}"
            )
        root = dc.demo_cache_root() / slug
        for idx, scene in enumerate(scenes):
            scene_dir = root / "scenes" / str(idx)
            nt = texts[idx]
            scene.narration_text = nt
            spec = dict(scene.scene_spec_json or {})
            spec["narration_text"] = nt
            scene.scene_spec_json = spec
            scene.status = SceneStatus.generating

            scene_id_key = spec.get("scene_id", str(scene.id))

            wav_path = scene_dir / "narration.wav"
            wav_bytes = wav_path.read_bytes()
            dur = dc.wav_duration_sec(wav_path)
            audio_url = await self.storage.put_file(
                f"audio/narrations/{scene_id_key}.wav",
                wav_bytes,
                "audio/wav",
            )
            db.add(
                SceneAsset(
                    scene_id=scene.id,
                    asset_type=AssetType.audio,
                    provider="tts",
                    prompt_version="demo-cache",
                    storage_url=audio_url,
                    metadata_json={
                        "duration_sec": round(dur, 2),
                        "type": "narration",
                        "demo_cache": slug,
                    },
                    status=AssetStatus.ready,
                )
            )

            img_path = scene_dir / "image.png"
            img_bytes = img_path.read_bytes()
            img_url = await self.storage.put_file(
                f"assets/{lesson.id}/{scene.id}/image.png",
                img_bytes,
                "image/png",
            )
            db.add(
                SceneAsset(
                    scene_id=scene.id,
                    asset_type=AssetType.image,
                    provider="image",
                    prompt_version="demo-cache",
                    storage_url=img_url,
                    metadata_json={"demo_cache": slug},
                    status=AssetStatus.ready,
                )
            )

            vid_path = scene_dir / "video.mp4"
            if vid_path.is_file() and vid_path.stat().st_size > 500:
                vid_bytes = vid_path.read_bytes()
                vid_url = await self.storage.put_file(
                    f"assets/{lesson.id}/{scene.id}/video.mp4",
                    vid_bytes,
                    "video/mp4",
                )
                db.add(
                    SceneAsset(
                        scene_id=scene.id,
                        asset_type=AssetType.video,
                        provider="video",
                        prompt_version="demo-cache",
                        storage_url=vid_url,
                        metadata_json={"demo_cache": slug},
                        status=AssetStatus.ready,
                    )
                )

            scene.status = SceneStatus.rendered

    async def regenerate_single_scene_assets(self, scene: Scene) -> None:
        """Re-generate TTS and image/video assets for a single scene."""
        db = self._db
        assert db is not None

        spec = scene.scene_spec_json or {}

        # Re-generate narration
        narrations = await self.narration.generate_all_narrations(
            [spec], str(scene.lesson_id)
        )
        if narrations:
            scene.narration_text = narrations[0]["narration_text"]
            db.add(SceneAsset(
                scene_id=scene.id,
                asset_type=AssetType.audio,
                provider="tts",
                prompt_version="v2-regen",
                storage_url=narrations[0]["audio_url"],
                metadata_json={
                    "duration_sec": narrations[0]["duration_sec"],
                    "type": "narration",
                    "regenerated": True,
                },
                status=AssetStatus.ready,
            ))

        # Re-generate visual assets
        result = await db.execute(
            select(Lesson).where(Lesson.id == scene.lesson_id)
        )
        lesson = result.scalar_one_or_none()
        style_val = lesson.style_preset.value if lesson else "clean_academic"

        for asset_req in spec.get("asset_requests", []):
            req_type = asset_req.get("type", "")
            prompt = asset_req.get("prompt", "")
            if req_type == "image" and prompt:
                image_bytes = await self.image_provider.generate_image(
                    prompt=prompt, style=style_val, width=1920, height=1080,
                )
                img_path = f"assets/{scene.lesson_id}/{scene.id}/image.png"
                img_url = await self.storage.put_file(
                    img_path, image_bytes, "image/png"
                )
                db.add(SceneAsset(
                    scene_id=scene.id,
                    asset_type=AssetType.image,
                    provider="image",
                    prompt_version="v2-regen",
                    storage_url=img_url,
                    metadata_json={"prompt": prompt, "regenerated": True},
                    status=AssetStatus.ready,
                ))
            elif req_type == "video" and prompt and spec.get("veo_eligible"):
                max_dur = min(asset_req.get("max_duration_sec", 5.0), 5.0)
                try:
                    video_bytes = await self.video_provider.generate_from_text(
                        prompt=prompt, duration_sec=max_dur,
                    )
                    vid_path = f"assets/{scene.lesson_id}/{scene.id}/video.mp4"
                    vid_url = await self.storage.put_file(
                        vid_path, video_bytes, "video/mp4"
                    )
                    db.add(SceneAsset(
                        scene_id=scene.id,
                        asset_type=AssetType.video,
                        provider="video",
                        prompt_version="v2-regen",
                        storage_url=vid_url,
                        metadata_json={"prompt": prompt, "regenerated": True},
                        status=AssetStatus.ready,
                    ))
                except Exception as err:
                    logger.warning("Veo regen failed for scene %s: %s", scene.id, err)

        scene.status = SceneStatus.rendered
        await db.flush()
        logger.info("Pipeline: regenerated assets for scene %s", scene.id)

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
        audio_rows = list(audio_result.scalars().all())
        audio_urls = _ordered_audio_urls_for_scenes(scenes, audio_rows)

        # Attach asset URLs to scene specs for composition
        all_assets_result = await db.execute(
            select(SceneAsset)
            .where(SceneAsset.scene_id.in_([s.id for s in scenes]))
            .where(SceneAsset.asset_type.in_([AssetType.video, AssetType.image]))
        )
        video_assets_by_scene: dict[str, str] = {}
        image_assets_by_scene: dict[str, str] = {}
        for asset in all_assets_result.scalars().all():
            sid = str(asset.scene_id)
            if asset.asset_type == AssetType.video:
                video_assets_by_scene[sid] = asset.storage_url
            elif asset.asset_type == AssetType.image:
                image_assets_by_scene[sid] = asset.storage_url
        for spec, scene_obj in zip(scene_specs, scenes):
            spec["_video_asset_url"] = video_assets_by_scene.get(str(scene_obj.id), "")
            spec["_image_asset_url"] = image_assets_by_scene.get(str(scene_obj.id), "")

        from app.services import demo_cache as dc

        slug = dc.resolve_demo_cache_slug(lesson.input_topic)
        cached_mp4 = dc.cached_final_video_path(slug) if slug else None

        if cached_mp4 is not None:
            video_bytes = cached_mp4.read_bytes()
            video_url = await self.storage.put_file(
                f"output/{lesson.id}/lesson.mp4",
                video_bytes,
                "video/mp4",
            )
            srt_path = dc.cached_subtitles_path(slug) if slug else None
            if srt_path and srt_path.is_file():
                await self.storage.put_file(
                    f"output/{lesson.id}/subtitles.srt",
                    srt_path.read_bytes(),
                    "text/srt",
                )
            logger.info(
                "Pipeline.run_render: demo cache final video slug=%s lesson=%s",
                slug,
                lesson.id,
            )
        else:
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
                video_url = await self.rendering.render_preview(
                    scene_specs,
                    lesson.style_preset.value,
                    lesson_id=str(lesson.id),
                    audio_urls=audio_urls,
                )
            else:
                video_url = await self.rendering.render_final(
                    scene_specs,
                    lesson.style_preset.value,
                    audio_urls,
                    music_url,
                    lesson_id=str(lesson.id),
                )

        out_mp4 = (
            Path(get_settings().LOCAL_STORAGE_PATH).resolve()
            / "output"
            / str(lesson.id)
            / "lesson.mp4"
        )
        if not (out_mp4.is_file() and out_mp4.stat().st_size > 512):
            job.status = RenderJobStatus.failed
            job.progress = 0.0
            job.error_message = (
                "No MP4 was written. Install FFmpeg and ensure `ffmpeg` is on your PATH "
                "(Render Final muxes scenes locally; it does not call the Gemini API). "
                "Check API logs for encoding errors."
            )
            job.completed_at = datetime.now(timezone.utc)
            lesson.status = LessonStatus.error
            await db.flush()
            await db.refresh(job)
            logger.error(
                "Pipeline.run_render: missing or empty output at %s (mode=%s)",
                out_mp4,
                mode,
            )
            return video_url

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

        plan_json = plan.plan_json if plan else {}
        concept_graph = plan.concept_graph_json if plan else {}
        if concept_graph.get("is_paper"):
            plan_json["is_paper"] = True

        lesson_data = {
            "title": lesson.title,
            "domain": lesson.domain.value,
            "plan": plan_json,
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
