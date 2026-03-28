"""Topic-specific diagram briefs — tighten Nano Banana output toward reference-grade system diagrams."""

from __future__ import annotations

import re


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def extra_constraints_for_topic(
    *,
    lesson_title: str,
    scene_title: str,
    scene_type: str,
) -> str:
    """
    Return extra prompt text when title/topic matches known CS teaching patterns.
    Empty string if no enrichment.
    """
    blob = _norm(f"{lesson_title} {scene_title}")
    parts: list[str] = []

    if "rate limit" in blob or "throttl" in blob or "token bucket" in blob or "leaky bucket" in blob:
        parts.append(
            "System-design layout: left-to-right flow — Client icon → API Gateway → "
            "Rate Limiter middleware (highlighted box with lock or gauge) → counter store "
            "(Redis cylinder or key-value) → Application servers. "
            "Show TWO parallel paths vertically stacked: TOP path green accent — allowed traffic "
            "(e.g. 45/100) with HTTP 200 OK toward servers; BOTTOM path red accent — blocked "
            "(e.g. 101/100) with curved arrow back labeled HTTP 429 Too Many Requests. "
            "Add small callouts: fixed or sliding window, per-user key, counter increment. "
            "Use consistent flat icons (not photos). Professional infographic, not a screenshot."
        )

    if "architecture" in blob and scene_type == "system_design_graph":
        parts.append(
            "Tiered architecture: numbered arrows between layers; one legend box (bottom-right) "
            "with 3–4 symbol meanings; no overlapping labels."
        )

    if scene_type == "summary_scene":
        parts.append(
            "Include a compact numbered checklist panel (3–5 steps) in one corner, "
            "matching the lesson theme; keep typography crisp and readable."
        )

    if scene_type == "code_trace" and not parts:
        parts.append(
            "Split layout: left = code or pseudocode block; right = execution state "
            "(stack, variables, or pointer); highlight the active line."
        )

    return " ".join(parts).strip()
