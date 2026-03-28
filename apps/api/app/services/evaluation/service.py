import logging
import re
from collections import Counter

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)

_REQUIRED_SYSTEM_DESIGN_SECTIONS = [
    "problem", "architecture", "request flow", "scaling", "tradeoff", "recap",
]

_REQUIRED_PAPER_SECTIONS = [
    "overview", "motivation", "approach", "result", "takeaway",
]


class EvaluationService:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def evaluate(self, lesson_data: dict) -> dict:
        scenes = lesson_data.get("scenes", [])
        plan = lesson_data.get("plan", {})
        domain = lesson_data.get("domain", "cs")
        is_paper = plan.get("is_paper", False) or any(
            "paper" in s.get("title", "").lower() for s in scenes
        )
        target_duration = plan.get("estimated_duration_sec", 300)

        flags: list[dict] = []
        scene_scores: list[dict] = []

        # 1. Scene-level checks
        self._check_scenes(scenes, flags, scene_scores)

        # 2. Structural completeness
        self._check_structure(scenes, domain, is_paper, flags)

        # 3. Narration quality
        self._check_narration(scenes, flags)

        # 4. Veo usage
        self._check_veo_usage(scenes, flags)

        # 5. Duration
        total_duration = sum(s.get("duration_sec", 0) for s in scenes)
        self._check_duration(total_duration, target_duration, flags)

        # 6. Redundancy
        self._check_redundancy(scenes, flags)

        llm_evaluation = await self.llm.evaluate_lesson(lesson_data)

        # Compute overall from deterministic + LLM
        det_score = self._compute_deterministic_score(flags, scenes)
        llm_score = llm_evaluation.get("overall_score", 0.85)
        overall_score = round(0.4 * det_score + 0.6 * llm_score, 3)

        severity_counts = Counter(f["severity"] for f in flags)
        grade = self._score_to_grade(overall_score, severity_counts)

        report = {
            "overall_score": overall_score,
            "grade": grade,
            "deterministic_score": round(det_score, 3),
            "llm_score": round(llm_score, 3),
            "content_accuracy": llm_evaluation.get("content_accuracy", {}),
            "pedagogical_quality": llm_evaluation.get("pedagogical_quality", {}),
            "visual_quality": llm_evaluation.get("visual_quality", {}),
            "narration_quality": llm_evaluation.get("narration_quality", {}),
            "engagement": llm_evaluation.get("engagement", {}),
            "flags": [f["message"] for f in flags],
            "detailed_flags": flags,
            "scene_scores": scene_scores,
            "suggestions": llm_evaluation.get("suggestions", []),
            "scene_count": len(scenes),
            "total_duration_sec": total_duration,
            "target_duration_sec": target_duration,
            "is_paper": is_paper,
            "summary": {
                "errors": severity_counts.get("error", 0),
                "warnings": severity_counts.get("warning", 0),
                "info": severity_counts.get("info", 0),
            },
        }

        logger.info(
            "EvaluationService: score=%.2f grade=%s, %d flags (%d err, %d warn), %d scenes",
            overall_score, grade,
            len(flags), severity_counts.get("error", 0),
            severity_counts.get("warning", 0), len(scenes),
        )
        return report

    def _check_scenes(self, scenes: list[dict], flags: list[dict],
                      scene_scores: list[dict]) -> None:
        if not scenes:
            flags.append({
                "severity": "error",
                "category": "structure",
                "message": "Lesson has no scenes",
            })
            return

        for idx, scene in enumerate(scenes):
            label = f"Scene {idx + 1} ({scene.get('title', 'untitled')})"
            score = 1.0
            scene_flags: list[str] = []

            narration = scene.get("narration_text", "").strip()
            if not narration:
                flags.append({
                    "severity": "error", "category": "content",
                    "scene_index": idx,
                    "message": f"{label}: missing narration text",
                })
                score -= 0.3
                scene_flags.append("no_narration")
            elif len(narration) < 50:
                flags.append({
                    "severity": "warning", "category": "content",
                    "scene_index": idx,
                    "message": f"{label}: narration is very short ({len(narration)} chars)",
                })
                score -= 0.1
                scene_flags.append("short_narration")

            on_screen = scene.get("on_screen_text", [])
            visuals = scene.get("visual_elements", [])
            if not on_screen and not visuals:
                flags.append({
                    "severity": "warning", "category": "visual",
                    "scene_index": idx,
                    "message": f"{label}: no on-screen text or visual elements",
                })
                score -= 0.1
                scene_flags.append("empty_visuals")

            duration = scene.get("duration_sec", 0)
            if duration <= 0:
                flags.append({
                    "severity": "error", "category": "timing",
                    "scene_index": idx,
                    "message": f"{label}: invalid duration ({duration}s)",
                })
                score -= 0.3
            elif duration > 120:
                flags.append({
                    "severity": "warning", "category": "timing",
                    "scene_index": idx,
                    "message": f"{label}: duration ({duration}s) exceeds 120s",
                })
                score -= 0.1

            obj = scene.get("learning_objective", "")
            if not obj:
                score -= 0.05
                scene_flags.append("no_learning_objective")

            scene_scores.append({
                "scene_index": idx,
                "title": scene.get("title", ""),
                "score": round(max(0.0, score), 2),
                "flags": scene_flags,
                "confidence": "high" if score >= 0.8 else "medium" if score >= 0.5 else "low",
            })

    def _check_structure(self, scenes: list[dict], domain: str,
                         is_paper: bool, flags: list[dict]) -> None:
        titles_lower = [s.get("title", "").lower() for s in scenes]
        types = [s.get("scene_type", "") for s in scenes]

        if is_paper:
            required = _REQUIRED_PAPER_SECTIONS
            label = "paper walkthrough"
        elif domain == "system_design":
            required = _REQUIRED_SYSTEM_DESIGN_SECTIONS
            label = "system design lesson"
        else:
            required = []
            label = "lesson"

        for section in required:
            found = any(section in t for t in titles_lower)
            if not found:
                flags.append({
                    "severity": "warning", "category": "structure",
                    "message": f"Missing expected {label} section: '{section}'",
                })

        if not any(t == "summary_scene" for t in types):
            flags.append({
                "severity": "info", "category": "structure",
                "message": "No summary/recap scene found — consider adding one",
            })

        if len(scenes) < 3:
            flags.append({
                "severity": "warning", "category": "structure",
                "message": f"Only {len(scenes)} scenes — lessons typically need 4-8 for depth",
            })

    def _check_narration(self, scenes: list[dict], flags: list[dict]) -> None:
        all_narrations = [s.get("narration_text", "") for s in scenes]

        for i in range(1, len(all_narrations)):
            if not all_narrations[i] or not all_narrations[i - 1]:
                continue
            a = all_narrations[i - 1].strip().lower()
            b = all_narrations[i].strip().lower()
            if a and b and a == b:
                flags.append({
                    "severity": "error", "category": "narration",
                    "scene_index": i,
                    "message": f"Scene {i + 1}: narration is identical to scene {i}",
                })

        opening_words = []
        for n in all_narrations:
            words = n.strip().split()[:4]
            opening_words.append(" ".join(words).lower())
        word_counts = Counter(opening_words)
        for phrase, count in word_counts.items():
            if count >= 3 and phrase:
                flags.append({
                    "severity": "info", "category": "narration",
                    "message": f"Repetitive opener '{phrase}...' used {count} times",
                })

    def _check_veo_usage(self, scenes: list[dict], flags: list[dict]) -> None:
        veo_scenes = [s for s in scenes if s.get("veo_eligible")]
        if len(veo_scenes) > len(scenes) * 0.6 and len(scenes) > 3:
            flags.append({
                "severity": "warning", "category": "veo",
                "message": f"Veo enabled on {len(veo_scenes)}/{len(scenes)} scenes — "
                           "consider reducing to high-impact motion scenes only",
            })

        for idx, s in enumerate(scenes):
            if s.get("veo_eligible") and s.get("scene_type") == "summary_scene":
                flags.append({
                    "severity": "info", "category": "veo",
                    "scene_index": idx,
                    "message": f"Scene {idx + 1}: Veo on a summary scene adds little value",
                })

    def _check_duration(self, total: float, target: float,
                        flags: list[dict]) -> None:
        if target <= 0:
            return
        ratio = total / target
        if ratio < 0.5:
            flags.append({
                "severity": "error", "category": "timing",
                "message": f"Total duration ({total:.0f}s) is far below target ({target:.0f}s)",
            })
        elif ratio < 0.7:
            flags.append({
                "severity": "warning", "category": "timing",
                "message": f"Total duration ({total:.0f}s) is below target ({target:.0f}s)",
            })
        elif ratio > 1.5:
            flags.append({
                "severity": "warning", "category": "timing",
                "message": f"Total duration ({total:.0f}s) exceeds target ({target:.0f}s) by >50%",
            })

    def _check_redundancy(self, scenes: list[dict], flags: list[dict]) -> None:
        titles = [s.get("title", "").strip().lower() for s in scenes]
        title_counts = Counter(titles)
        for title, count in title_counts.items():
            if count > 1 and title:
                flags.append({
                    "severity": "warning", "category": "redundancy",
                    "message": f"Duplicate scene title '{title}' appears {count} times",
                })

    def _compute_deterministic_score(self, flags: list[dict],
                                     scenes: list[dict]) -> float:
        score = 1.0
        for f in flags:
            if f["severity"] == "error":
                score -= 0.08
            elif f["severity"] == "warning":
                score -= 0.03
        return max(0.0, min(1.0, score))

    def _score_to_grade(self, score: float,
                        severity_counts: Counter) -> str:
        if severity_counts.get("error", 0) >= 3:
            return "D"
        if score >= 0.9:
            return "A"
        if score >= 0.8:
            return "B"
        if score >= 0.65:
            return "C"
        return "D"
