"""Veo eligibility scoring and prompt shaping (3–5s clips, educational motion only)."""

from __future__ import annotations

import math
import re

VEO_DURATION_MIN = 3.0
VEO_DURATION_MAX = 5.0
VEO_SCORE_THRESHOLD = 0.42

_MOTION_LEXICON = re.compile(
    r"\b(flow|flowing|flood|burst|stream|packet|request|arrow|animate|"
    r"cycle|drain|fill|token|bucket|leak|slide|orbit|pulse|wave|traffic|"
    r"queue|throttle|spike|movement|travel|handoff)\b",
    re.I,
)

_TYPE_WEIGHT = {
    "veo_cinematic": 0.85,
    "generated_still_with_motion": 0.55,
    "system_design_graph": 0.35,
    "deterministic_animation": 0.45,
    "code_trace": 0.2,
    "summary_scene": 0.05,
}


def score_veo_eligibility(
    *,
    scene_type: str,
    scene_index: int,
    total_scenes: int,
    visual_strategy: str,
    title: str,
    render_mode: str = "auto",
) -> float:
    """
    0.0–1.0 score. Dynamic / flow-heavy scenes score higher; summaries lower.
    """
    if render_mode == "force_static":
        return 0.0
    if render_mode == "force_veo":
        return 0.95

    s = _TYPE_WEIGHT.get(scene_type, 0.25)

    if scene_index == 0:
        s += 0.12
    if scene_index == total_scenes - 1 and scene_type == "summary_scene":
        s -= 0.15

    text = f"{visual_strategy} {title}"
    hits = len(_MOTION_LEXICON.findall(text))
    s += min(0.22, hits * 0.055)

    return float(min(1.0, round(s, 3)))


def pick_veo_duration_sec(score: float) -> float:
    """Map score to 3–5s (shorter when marginal, longer when strong)."""
    t = VEO_DURATION_MIN + (score * (VEO_DURATION_MAX - VEO_DURATION_MIN))
    return float(min(VEO_DURATION_MAX, max(VEO_DURATION_MIN, round(t, 1))))


def build_veo_prompt(
    *,
    lesson_title: str,
    scene_title: str,
    visual_strategy: str,
    objective: str,
    continuity_anchor: str | None,
) -> str:
    """Cinematic but non-factual-hallucination: motion supports the diagram, not the truth."""
    anchor = f" Visual motif: {continuity_anchor}." if continuity_anchor else ""
    return (
        f"Cinematic 4K-style educational motion graphics, 3–5 seconds, dark premium tech aesthetic, "
        f"teal and amber light trails. Topic: {lesson_title} — {scene_title}. "
        f"Motion brief: {visual_strategy[:320]}. "
        f"Pedagogical intent: {objective[:200]}.{anchor} "
        f"Smooth camera push or pan, particles as abstract requests (not literal humans). "
        f"No readable fake text, no faces, no brand logos. Single continuous shot."
    )
