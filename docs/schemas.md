# VisualCS JSON Schemas

This document describes the **canonical JSON shapes** used across the pipeline. They are enforced in Python with Pydantic models in `apps/api/app/schemas/common.py` (names there: `ConceptGraph`, `LessonPlanSchema`, `SceneSpec`, `EvaluationReportSchema`). In API responses, the same structures appear inside database JSON columns such as `concept_graph_json`, `plan_json`, `scene_spec_json`, and `report_json`.

---

## ConceptGraphSchema

A directed graph of concepts with prerequisite-style edges. Produced by extraction and stored in `LessonPlan.concept_graph_json`.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `nodes` | `ConceptNode[]` | Vertices (ideas, definitions, mechanisms) |
| `edges` | `ConceptEdge[]` | Relationships, typically learning order |

**ConceptNode**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | string | required | Stable identifier referenced by edges and prerequisites |
| `label` | string | required | Short name |
| `description` | string | `""` | Teaching-oriented gloss |
| `importance` | number | `1.0` | Relative weight for planning (0–∞; typically ~1) |
| `prerequisites` | string[] | `[]` | Node ids that should be understood first |

**ConceptEdge**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source` | string | required | Source node `id` |
| `target` | string | required | Target node `id` |
| `relation_type` | string | `"prerequisite"` | e.g. `prerequisite`, `part_of`, `example_of` |

### Example

```json
{
  "nodes": [
    {
      "id": "deadlock",
      "label": "Deadlock",
      "description": "A set of processes blocked forever, each waiting on a resource held by another.",
      "importance": 1.0,
      "prerequisites": ["resource", "wait_for_graph"]
    },
    {
      "id": "coffman_conditions",
      "label": "Coffman conditions",
      "description": "Four necessary conditions for deadlock: mutual exclusion, hold and wait, no preemption, circular wait.",
      "importance": 0.95,
      "prerequisites": ["deadlock"]
    },
    {
      "id": "resource",
      "label": "Resource allocation",
      "description": "How OS grants exclusive or shared access to devices, locks, and memory regions.",
      "importance": 0.8,
      "prerequisites": []
    },
    {
      "id": "wait_for_graph",
      "label": "Wait-for graph",
      "description": "Graph used to detect circular wait among processes and resources.",
      "importance": 0.85,
      "prerequisites": ["deadlock"]
    }
  ],
  "edges": [
    { "source": "resource", "target": "deadlock", "relation_type": "prerequisite" },
    { "source": "deadlock", "target": "coffman_conditions", "relation_type": "prerequisite" }
  ]
}
```

---

## LessonPlanSchema

High-level pedagogy output: objectives, misconceptions, and an ordered list of **sections** that the scene compiler expands. Stored primarily in `LessonPlan.plan_json` (and mirrored lists like `lesson_objectives_json` where populated).

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lesson_title` | string | required | Working title for the video |
| `target_audience` | string | `"undergraduate CS student"` | Level and background |
| `estimated_duration_sec` | number | `300.0` | Target runtime in seconds |
| `objectives` | string[] | `[]` | Measurable learning outcomes |
| `prerequisites` | string[] | `[]` | What the viewer should already know |
| `misconceptions` | string[] | `[]` | Common mistakes to address on-screen |
| `sections` | `LessonPlanSection[]` | `[]` | Ordered acts of the lesson |

**LessonPlanSection**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `title` | string | required | Section heading |
| `objective` | string | `""` | What this section achieves |
| `scene_type` | string | `"deterministic_animation"` | Hint for compiler (`deterministic_animation`, `veo_cinematic`, etc.) |
| `duration_sec` | number | `30.0` | Budget for this section |
| `key_points` | string[] | `[]` | Bullets the narration should cover |
| `visual_strategy` | string | `""` | How to visualize (timeline, graph, architecture diagram, …) |

### Example

```json
{
  "lesson_title": "Deadlock: conditions, detection, and prevention",
  "target_audience": "undergraduate CS student",
  "estimated_duration_sec": 420,
  "objectives": [
    "State the four Coffman conditions",
    "Explain wait-for graphs and detection",
    "Compare prevention, avoidance, and recovery"
  ],
  "prerequisites": ["Processes", "Locks", "Scheduling basics"],
  "misconceptions": [
    "Starvation is the same as deadlock",
    "Deadlock can always be fixed by killing one random process without analysis"
  ],
  "sections": [
    {
      "title": "Hook: traffic jam analogy",
      "objective": "Motivate circular wait without formalism",
      "scene_type": "veo_cinematic",
      "duration_sec": 25,
      "key_points": ["Circular dependency", "Everyone stuck"],
      "visual_strategy": "Short cinematic analogy; transition to diagram"
    },
    {
      "title": "Coffman's four conditions",
      "objective": "List necessary conditions with concise definitions",
      "scene_type": "deterministic_animation",
      "duration_sec": 90,
      "key_points": [
        "Mutual exclusion",
        "Hold and wait",
        "No preemption",
        "Circular wait"
      ],
      "visual_strategy": "Four-panel deterministic layout with icons"
    },
    {
      "title": "Wait-for graph",
      "objective": "Show how cycles imply deadlock",
      "scene_type": "system_design_graph",
      "duration_sec": 75,
      "key_points": ["Nodes are processes and resources", "Edge direction means waiting"],
      "visual_strategy": "Bipartite graph animation building edge by edge"
    }
  ]
}
```

---

## SceneSpecSchema

Per-scene **executable spec**: narration, on-screen text, animation beats, optional Veo/image prompts, and `asset_requests` consumed by the asset pipeline. Each `Scene` row stores a full object in `scene_spec_json`.

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `scene_id` | string | `""` | Logical id (may match UUID string after persistence) |
| `title` | string | `""` | Scene title |
| `learning_objective` | string | `""` | Micro-outcome |
| `source_refs` | string[] | `[]` | `ref_key` values into `SourceFragment` |
| `scene_type` | string | `"deterministic_animation"` | Drives renderer choice |
| `render_strategy` | string | `"default"` | Sub-strategy for deterministic renderers |
| `duration_sec` | number | `30.0` | Scene length |
| `narration_text` | string | `""` | Script (may be refined by `NarrationService`) |
| `on_screen_text` | string[] | `[]` | Bullets / labels |
| `visual_elements` | `VisualElement[]` | `[]` | Structured layout hints |
| `animation_beats` | `AnimationBeat[]` | `[]` | Time-coded actions |
| `asset_requests` | `AssetRequest[]` | `[]` | Image/video generation tasks |
| `veo_prompt` | string \| null | `null` | Cinematic text-to-video prompt |
| `image_prompt` | string \| null | `null` | Global still-image prompt (if not using only `asset_requests`) |
| `music_mood` | string | `"neutral"` | Feeds background music selection |
| `validation_notes` | string | `""` | Compiler self-checks / warnings |

**VisualElement**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | `""` | e.g. `box`, `arrow`, `timeline`, `code_block` |
| `description` | string | `""` | Semantic content |
| `position` | string | `""` | Layout hint (`left`, `grid`, …) |
| `style` | string | `""` | Visual variant |

**AnimationBeat**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `timestamp_sec` | number | `0.0` | Time in scene |
| `action` | string | `""` | e.g. `highlight`, `add_edge`, `fade_in` |
| `description` | string | `""` | Human-readable beat |

**AssetRequest**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | `""` | `image` or `video` (pipeline branches on these) |
| `prompt` | string | `""` | Provider prompt |
| `provider` | string | `""` | Optional override (`gemini`, `veo`, …) |

### Example

```json
{
  "scene_id": "scene-02",
  "title": "Wait-for graph walkthrough",
  "learning_objective": "Relate graph cycles to deadlock",
  "source_refs": ["page_04_body_0"],
  "scene_type": "system_design_graph",
  "render_strategy": "default",
  "duration_sec": 72.5,
  "narration_text": "We draw processes as circles and resources as squares. An edge from a process to a resource means the process is waiting for it.",
  "on_screen_text": [
    "Process → Resource : waiting",
    "Resource → Process : held"
  ],
  "visual_elements": [
    {
      "type": "graph",
      "description": "Bipartite wait-for graph with P1, P2, R1, R2",
      "position": "center",
      "style": "clean_academic"
    }
  ],
  "animation_beats": [
    { "timestamp_sec": 0.0, "action": "reveal", "description": "Show P1 and R1" },
    { "timestamp_sec": 4.0, "action": "add_edge", "description": "P1 waits for R1" },
    { "timestamp_sec": 10.0, "action": "add_edge", "description": "Close the cycle" },
    { "timestamp_sec": 18.0, "action": "highlight", "description": "Pulse the cycle" }
  ],
  "asset_requests": [
    {
      "type": "image",
      "prompt": "Minimal academic diagram: bipartite wait-for graph, dark text on white, no decorative clutter",
      "provider": ""
    }
  ],
  "veo_prompt": null,
  "image_prompt": null,
  "music_mood": "focused",
  "validation_notes": "Ensure graph stays readable at 1080p"
}
```

---

## EvaluationReportSchema

Rubric output from the evaluator LLM. Stored in `EvaluationReport.report_json`; `score_overall` and `flags_json` are denormalized at the ORM layer from this payload.

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `overall_score` | number | `0.0` | Aggregate 0–1 (convention; tune prompts for scale) |
| `content_accuracy` | `CategoryScore` | `{}` | Factual correctness |
| `pedagogical_quality` | `CategoryScore` | `{}` | Clarity, scaffolding, pacing |
| `visual_quality` | `CategoryScore` | `{}` | Layout, consistency, readability |
| `narration_quality` | `CategoryScore` | `{}` | Script and speech fit |
| `engagement` | `CategoryScore` | `{}` | Interest without sacrificing accuracy |
| `flags` | string[] | `[]` | Blocking or warning tags |
| `suggestions` | string[] | `[]` | Actionable improvements |

**CategoryScore**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `score` | number | `0.0` | Sub-score for the category |
| `feedback` | string | `""` | Short justification |

### Example

```json
{
  "overall_score": 0.84,
  "content_accuracy": {
    "score": 0.9,
    "feedback": "Coffman conditions are stated correctly; wait-for graph direction is consistent."
  },
  "pedagogical_quality": {
    "score": 0.85,
    "feedback": "Good progression from analogy to formalism; could explicitly link graph cycle to deadlock theorem."
  },
  "visual_quality": {
    "score": 0.78,
    "feedback": "Graph readable; consider larger labels for mobile playback."
  },
  "narration_quality": {
    "score": 0.82,
    "feedback": "Concise and neutral tone; minor repetition in scene 3."
  },
  "engagement": {
    "score": 0.8,
    "feedback": "Opening analogy helps; middle section is slightly dense."
  },
  "flags": [],
  "suggestions": [
    "Add a one-sentence recap before the summary scene",
    "Explicitly name the detection algorithm when showing the wait-for graph"
  ]
}
```

---

## Where these appear in the API

| Schema | Typical location |
|--------|------------------|
| Concept graph | `GET /api/lessons/{id}` → `lesson_plan` via `LessonPlanResponse.concept_graph_json`; or direct plan fetch after `/plan` |
| Lesson plan | `LessonPlanResponse.plan_json` |
| Scene spec | Each `SceneResponse.scene_spec_json` |
| Evaluation | `EvaluationResponse.report_json` |

---

## Implementation reference

Python definitions: `apps/api/app/schemas/common.py`.

Prompt templates that steer the LLM toward valid JSON: `packages/prompts/v1/*.md`.
