"""Visual style presets for Nano Banana + on-screen consistency."""

from typing import Any

# Recurring identity token — repeat in every image prompt for brand coherence
VISUAL_IDENTITY_TOKEN = "VisualCS premium technical style: deep slate background (#0f172a), electric teal (#14b8a6) and amber (#f59e0b) accents, crisp white labels, subtle grid, soft vignette, no photorealistic faces."

STYLE_PRESET_SPECS: dict[str, dict[str, Any]] = {
    "clean_academic": {
        "label": "Clean academic",
        "palette": "slate background, teal and amber accent nodes, white primary text",
        "line_weight": "medium strokes, rounded rectangles",
        "depth": "subtle drop shadows, layered cards",
    },
    "modern_technical": {
        "label": "Modern technical",
        "palette": "dark UI chrome, neon cyan edges, high contrast",
        "line_weight": "thin precise lines, monospace-adjacent labels",
        "depth": "glass-morphism panels",
    },
    "cinematic_minimal": {
        "label": "Cinematic minimal",
        "palette": "near-black background, single warm accent, sparse composition",
        "line_weight": "bold silhouettes, generous whitespace",
        "depth": "dramatic spotlight on focal element",
    },
}


def spec_for_preset(style_key: str) -> dict[str, Any]:
    return STYLE_PRESET_SPECS.get(
        style_key, STYLE_PRESET_SPECS["clean_academic"]
    )
