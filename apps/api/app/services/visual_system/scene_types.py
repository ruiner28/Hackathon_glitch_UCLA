"""Scene type taxonomy for lesson composition."""

from enum import Enum


class LessonSceneType(str, Enum):
    """How the scene is pedagogically framed (maps to DB SceneType)."""

    hook = "veo_cinematic"  # often cinematic open
    architecture = "system_design_graph"
    algorithm_deep_dive = "deterministic_animation"
    code_trace = "code_trace"
    request_flow = "generated_still_with_motion"
    throttling_policy = "generated_still_with_motion"
    recap = "summary_scene"


SCENE_LAYOUT_HINTS: dict[str, str] = {
    "veo_cinematic": "Hero composition, single focal metaphor, strong horizon line, motion-ready negative space",
    "system_design_graph": (
        "Professional system diagram: left-to-right swimlanes (client → gateway / edge → core services → datastore). "
        "Use tiered boxes with icons, numbered arrows, color-coded success vs failure paths where relevant, "
        "legend or key bottom-right, generous whitespace, no clutter."
    ),
    "deterministic_animation": "Centered diagram with 3–5 labeled regions, step numbers, clear vertical or horizontal flow",
    "code_trace": "Split panel: pseudocode left, state table or stack visualization right",
    "generated_still_with_motion": "Single clear story beat, arrows showing direction of flow, one emphasis halo",
    "summary_scene": "Checklist or matrix, 2×3 grid max, icon bullets, recap title band",
}
