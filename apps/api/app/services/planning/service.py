import logging

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class PlanningService:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def create_plan(
        self,
        concepts: dict,
        domain: str,
        style: str,
        target_duration: int = 180,
    ) -> dict:
        """
        Create pedagogical lesson plan from extracted concepts.

        Calls LLM with concept graph + domain context.
        Returns a LessonPlan dict with sections, objectives, and scene types.
        """
        logger.info(
            "PlanningService: creating plan for domain=%s style=%s target_duration=%ds",
            domain, style, target_duration,
        )

        plan = await self.llm.create_lesson_plan(concepts, domain, style)

        sections = plan.get("sections", [])
        total_duration = sum(s.get("duration_sec", 30) for s in sections)

        if total_duration > 0 and target_duration > 0:
            scale = target_duration / total_duration
            if abs(scale - 1.0) > 0.15:
                for section in sections:
                    section["duration_sec"] = round(
                        section.get("duration_sec", 30) * scale
                    )
                plan["estimated_duration_sec"] = sum(
                    s["duration_sec"] for s in sections
                )

        plan.setdefault("lesson_title", domain)
        plan.setdefault("target_audience", "undergraduate CS student")
        plan.setdefault("estimated_duration_sec", target_duration)
        plan.setdefault("objectives", [])
        plan.setdefault("prerequisites", [])
        plan.setdefault("misconceptions", [])

        logger.info(
            "PlanningService: plan created with %d sections, ~%ds total",
            len(sections), plan["estimated_duration_sec"],
        )
        return plan
