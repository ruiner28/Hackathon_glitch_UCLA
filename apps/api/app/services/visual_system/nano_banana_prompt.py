"""Reusable Nano Banana (image) prompt builder — layout, labels, whitespace, emphasis."""

from __future__ import annotations

from typing import Any

from app.services.visual_system.style_presets import VISUAL_IDENTITY_TOKEN, spec_for_preset


def build_nano_banana_prompt(
    *,
    lesson_title: str,
    scene_title: str,
    learning_objective: str,
    key_visual_idea: str,
    style_preset: str,
    scene_type: str,
    scene_index: int,
    total_scenes: int,
    continuity_anchor: str | None = None,
    on_screen_bullets: list[str] | None = None,
    extra_constraints: str | None = None,
) -> str:
    """
    Produce a single structured prompt for gemini-2.5-flash-image (Nano Banana).

    Enforces: layout direction, arrows, labels, whitespace, educational clarity.
    """
    spec = spec_for_preset(style_preset)
    layout = _layout_for_scene_type(scene_type)

    bullets = ""
    if on_screen_bullets:
        bullets = "On-screen labels (short phrases only, max 6 words each): " + "; ".join(
            f'"{b[:48]}"' for b in on_screen_bullets[:6]
        )

    anchor = ""
    if continuity_anchor:
        anchor = f"Continuity: echo this motif — {continuity_anchor}. "

    parts = [
        f"16:9 educational infographic, NOT a photograph of people.",
        VISUAL_IDENTITY_TOKEN,
        f"Lesson: {lesson_title}. Scene {scene_index + 1}/{total_scenes}: {scene_title}.",
        f"Objective: {learning_objective[:220]}." if learning_objective else "",
        f"Style preset — {spec['label']}: palette ({spec['palette']}), {spec['line_weight']}, {spec['depth']}.",
        f"Layout: {layout}.",
        f"Central visual idea: {key_visual_idea[:400]}.",
        anchor,
        bullets,
        "Use clear arrows with arrowheads; group related items in rounded panels; leave 12% margin as breathing room.",
        "Emphasis: one focal region 15–20% brighter or thicker stroke than the rest.",
        "No watermarks, no stock photos, no blurry text.",
        extra_constraints or "",
    ]
    return " ".join(p for p in parts if p).strip()


def _layout_for_scene_type(scene_type: str) -> str:
    from app.services.visual_system.scene_types import SCENE_LAYOUT_HINTS

    return SCENE_LAYOUT_HINTS.get(scene_type, SCENE_LAYOUT_HINTS["deterministic_animation"])


def enrich_image_prompt_from_scene_spec(
    scene_spec: dict[str, Any],
    lesson_style: str,
    lesson_title: str,
    scene_index: int,
    total_scenes: int,
) -> str:
    """If scene_spec already has image_prompt, optionally prepend identity; else build full prompt."""
    existing = (scene_spec.get("image_prompt") or "").strip()
    style = scene_spec.get("style_preset") or lesson_style
    st = scene_spec.get("scene_type", "deterministic_animation")
    if existing and len(existing) > 120:
        return f"{VISUAL_IDENTITY_TOKEN} {existing}"

    bullets = scene_spec.get("on_screen_text") or []
    if isinstance(bullets, dict):
        bullets = []
    return build_nano_banana_prompt(
        lesson_title=lesson_title,
        scene_title=scene_spec.get("title", "Scene"),
        learning_objective=scene_spec.get("learning_objective", ""),
        key_visual_idea=existing or scene_spec.get("teaching_note", "") or st,
        style_preset=style,
        scene_type=st,
        scene_index=scene_index,
        total_scenes=total_scenes,
        continuity_anchor=scene_spec.get("continuity_anchor"),
        on_screen_bullets=list(bullets) if bullets else None,
    )
