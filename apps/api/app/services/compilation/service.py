import logging
import uuid

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)

RENDER_STRATEGY_MAP = {
    "deterministic_animation": "remotion",
    "generated_still_with_motion": "image_to_video",
    "veo_cinematic": "veo",
    "code_trace": "remotion",
    "system_design_graph": "remotion",
    "summary_scene": "remotion",
    "primary_visual_walkthrough": "svg_diagram",
}

MUSIC_MOOD_MAP = {
    "deterministic_animation": "focused",
    "code_trace": "focused",
    "system_design_graph": "neutral",
    "veo_cinematic": "dramatic",
    "generated_still_with_motion": "curious",
    "summary_scene": "uplifting",
    "primary_visual_walkthrough": "focused",
}


class CompilationService:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def compile(self, lesson_plan: dict, domain: str) -> list[dict]:
        """
        Convert lesson plan into detailed scene specifications.

        Calls the LLM to compile scenes, then normalises each SceneSpec
        to ensure all required fields are present.
        """
        logger.info(
            "CompilationService: compiling scenes for '%s'",
            lesson_plan.get("lesson_title", domain),
        )

        raw_scenes = await self.llm.compile_scenes(lesson_plan, domain)

        scenes: list[dict] = []
        for idx, raw in enumerate(raw_scenes):
            scene = self._normalise_scene_spec(raw, idx)
            scenes.append(scene)

        logger.info("CompilationService: compiled %d scenes", len(scenes))
        return scenes

    def compile_from_diagram(
        self,
        diagram_spec: dict,
        walkthrough_states: list[dict],
        topic: str,
    ) -> list[dict]:
        """Convert diagram spec + walkthrough states into scene specs.

        Each walkthrough state becomes one scene of type
        ``primary_visual_walkthrough``.  No LLM call needed — the data is
        already structured.
        """
        scenes: list[dict] = []
        for idx, state in enumerate(walkthrough_states):
            spec: dict = {
                "scene_id": str(uuid.uuid4()),
                "title": state.get("title", f"Step {idx + 1}"),
                "learning_objective": "",
                "source_refs": [],
                "scene_type": "primary_visual_walkthrough",
                "style_preset": "clean_academic",
                "render_strategy": "svg_diagram",
                "render_mode": "force_static",
                "duration_sec": state.get("duration_sec", 20),
                "narration_text": state.get("narration", ""),
                "on_screen_text": [],
                "visual_elements": [],
                "animation_beats": [],
                "asset_requests": [],
                "veo_eligible": False,
                "veo_score": 0.0,
                "veo_prompt": None,
                "image_prompt": None,
                "music_mood": "focused",
                "teaching_note": "",
                "walkthrough_state": state,
                "diagram_topic": topic,
            }
            scenes.append(spec)
        logger.info(
            "CompilationService: compiled %d diagram-walkthrough scenes for %r",
            len(scenes), topic,
        )
        return scenes

    def _normalise_scene_spec(self, raw: dict, index: int) -> dict:
        """Ensure every SceneSpec dict has all required fields."""
        scene_type = raw.get("scene_type", "deterministic_animation")
        spec = {
            "scene_id": raw.get("scene_id", str(uuid.uuid4())),
            "lesson_title": raw.get("lesson_title", ""),
            "title": raw.get("title", f"Scene {index + 1}"),
            "learning_objective": raw.get("learning_objective", ""),
            "teaching_note": raw.get("teaching_note", ""),
            "source_refs": raw.get("source_refs", []),
            "scene_type": scene_type,
            "style_preset": raw.get("style_preset", ""),
            "render_strategy": raw.get(
                "render_strategy",
                RENDER_STRATEGY_MAP.get(scene_type, "default"),
            ),
            "render_mode": raw.get("render_mode", "auto"),
            "duration_sec": raw.get("duration_sec", 30),
            "narration_text": raw.get("narration_text", ""),
            "on_screen_text": raw.get("on_screen_text", []),
            "visual_elements": raw.get("visual_elements", []),
            "animation_beats": raw.get("animation_beats", []),
            "asset_requests": raw.get("asset_requests", []),
            "veo_eligible": raw.get("veo_eligible", False),
            "veo_score": raw.get("veo_score", 0.0),
            "veo_prompt": raw.get("veo_prompt"),
            "image_prompt": raw.get("image_prompt"),
            "continuity_anchor": raw.get("continuity_anchor", ""),
            "transition_note": raw.get("transition_note", ""),
            "fallback_plan": raw.get("fallback_plan", ""),
            "transition_metadata": raw.get("transition_metadata", {}),
            "music_mood": raw.get(
                "music_mood",
                MUSIC_MOOD_MAP.get(scene_type, "neutral"),
            ),
            "validation_notes": raw.get("validation_notes", ""),
        }
        return spec
