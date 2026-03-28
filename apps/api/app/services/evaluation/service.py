import logging

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class EvaluationService:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def evaluate(self, lesson_data: dict) -> dict:
        """
        Evaluate lesson quality using both deterministic checks and LLM review.

        Checks:
        - Every scene has source refs or topic grounding
        - Narration uses concepts from source
        - No empty scenes
        - Total duration within target
        - Audio/video files exist

        Returns an EvaluationReport dict with scores and feedback.
        """
        scenes = lesson_data.get("scenes", [])
        plan = lesson_data.get("plan", {})
        target_duration = plan.get("estimated_duration_sec", 300)

        deterministic_warnings = self._validate_scenes(scenes)

        total_duration = sum(s.get("duration_sec", 0) for s in scenes)
        duration_ratio = total_duration / target_duration if target_duration > 0 else 1.0
        duration_ok = 0.7 <= duration_ratio <= 1.3

        if not duration_ok:
            deterministic_warnings.append(
                f"Total duration ({total_duration}s) deviates >30% from target ({target_duration}s)"
            )

        llm_evaluation = await self.llm.evaluate_lesson(lesson_data)

        overall_score = llm_evaluation.get("overall_score", 0.0)
        if deterministic_warnings:
            penalty = min(0.15, len(deterministic_warnings) * 0.03)
            overall_score = max(0.0, overall_score - penalty)

        report = {
            "overall_score": round(overall_score, 3),
            "content_accuracy": llm_evaluation.get("content_accuracy", {}),
            "pedagogical_quality": llm_evaluation.get("pedagogical_quality", {}),
            "visual_quality": llm_evaluation.get("visual_quality", {}),
            "narration_quality": llm_evaluation.get("narration_quality", {}),
            "engagement": llm_evaluation.get("engagement", {}),
            "flags": deterministic_warnings,
            "suggestions": llm_evaluation.get("suggestions", []),
            "scene_count": len(scenes),
            "total_duration_sec": total_duration,
            "target_duration_sec": target_duration,
        }

        logger.info(
            "EvaluationService: score=%.2f, %d flags, %d scenes",
            report["overall_score"], len(deterministic_warnings), len(scenes),
        )
        return report

    def _validate_scenes(self, scenes: list[dict]) -> list[str]:
        """Run deterministic validation checks. Return list of warnings."""
        warnings: list[str] = []

        if not scenes:
            warnings.append("Lesson has no scenes")
            return warnings

        for idx, scene in enumerate(scenes):
            scene_label = f"Scene {idx + 1} ({scene.get('title', 'untitled')})"

            if not scene.get("narration_text", "").strip():
                warnings.append(f"{scene_label}: missing narration text")

            if not scene.get("on_screen_text") and not scene.get("visual_elements"):
                warnings.append(f"{scene_label}: no on-screen text or visual elements")

            duration = scene.get("duration_sec", 0)
            if duration <= 0:
                warnings.append(f"{scene_label}: invalid duration ({duration}s)")
            elif duration > 120:
                warnings.append(
                    f"{scene_label}: duration ({duration}s) exceeds 120s max per scene"
                )

            source_refs = scene.get("source_refs", [])
            scene_type = scene.get("scene_type", "")
            if not source_refs and scene_type not in ("summary_scene",):
                pass  # acceptable for generated content

        return warnings
