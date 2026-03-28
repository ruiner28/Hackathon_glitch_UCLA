"""DiagramService — generates diagram specs via LLM with curated fallbacks."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.diagram.rate_limiter import get_curated_diagram

logger = logging.getLogger(__name__)


_DIAGRAM_SPEC_PROMPT = """\
You are an expert system-design instructor who creates clean, professional
technical architecture diagrams. Given a topic and concept graph, produce a
**structured diagram specification** (JSON) that renders into a polished,
interview-ready diagram with modern icons, soft shadows, rounded boxes,
directional arrows, and balanced spacing.

### Topic
{topic}

### Concept Graph (for reference)
{concepts_json}

### Lesson Plan Sections (for reference)
{sections_json}

### Required JSON Schema
{{
  "topic": "string",
  "layout": {{"width": 1400, "height": 750, "direction": "left-to-right", "background": "#FAFBFC"}},
  "components": [
    {{
      "id": "snake_case",
      "label": "Human-readable (1-3 words per line, \\n for line breaks)",
      "x": number, "y": number, "w": 120-170, "h": 100-200,
      "icon": "user | gateway | shield | database | server",
      "style": "rounded | box | cylinder",
      "fill": "#hex — use pastel tints: blue #E3F2FD, green #E8F5E9, orange #FFF3E0, purple #F3E5F5, white #FFFFFF",
      "stroke": "#hex — use strong accent matching the fill family"
    }}
  ],
  "connections": [
    {{
      "id": "c1",
      "from": "component_id",
      "to": "component_id",
      "label": "short description (1-2 lines max)",
      "path_group": "string or null — groups connections into named flow paths",
      "annotation": "optional badge text (e.g. '200 OK')",
      "annotation_color": "#hex",
      "curve": "top | bottom | null — use for return/feedback arcs"
    }}
  ],
  "annotations": [
    {{
      "id": "a1",
      "text": "short note (1-2 lines)",
      "anchor": "component_id",
      "position": "top | bottom | left | right"
    }}
  ],
  "flow_paths": {{
    "path_name": {{
      "color": "#hex — use green #43A047 for success, red #E53935 for failure",
      "label": "legend label with path letter prefix",
      "description": "one concrete example, e.g. 'User A: 45/100 → allowed'"
    }}
  }},
  "status_badges": [
    {{
      "text": "short condition\\n→ outcome",
      "color": "#hex",
      "anchor": "component_id",
      "position": "inner-top | inner-bottom"
    }}
  ],
  "side_panel": {{
    "title": "Internal Logic",
    "x": 1210,
    "y": 55,
    "w": 175,
    "items": ["1. Step one", "2. Step two", "..."]
  }},
  "example_labels": [
    {{"text": "User A: 45/100 → allowed", "color": "#43A047", "x": 50, "y": 720}},
    {{"text": "User A: 101/100 → blocked", "color": "#E53935", "x": 280, "y": 720}}
  ],
  "algorithm_overlays": {{
    "overlay_key": {{
      "label": "Algorithm Name",
      "description": "One-sentence description."
    }}
  }}
}}

### Design Rules
- Place components left-to-right with ~160-200px spacing, centered vertically.
- Use distinct pastel fill colors for each component type (blue for logic, green for servers, orange for data, purple for networking).
- Keep labels short (2-4 words per line, use \\n for wraps).
- Define at least two flow paths (success and failure) with green and red colors.
- Add a side panel listing 5-8 internal logic steps.
- Add 2-3 example labels at the bottom showing concrete pass/fail examples.
- Add status badges inside the main decision component.
- Use meaningful snake_case IDs.
- Return ONLY the JSON object — no markdown, no explanation.
"""

_WALKTHROUGH_PROMPT = """\
Given this diagram specification for **{topic}**, create walkthrough states
that narrate through the diagram step by step. Each state should create strong
visual contrast — dim everything not in focus, highlight active flow paths with
animated dashes, and use overlay cards for algorithm details.

### Diagram Spec
{diagram_spec_json}

### Required JSON Schema (array of 5-8 objects)
[
  {{
    "state_id": "snake_case",
    "title": "Short title (2-5 words)",
    "narration": "3-5 sentences of spoken narration. Reference specific components and labels the viewer sees. Use concrete examples (e.g. 'User A sends their 45th request').",
    "focus_regions": ["component_id", ...],
    "highlight_paths": ["path_group_name", ...],
    "dim_regions": ["component_id", ...],
    "overlay_mode": "algorithm_overlay_key or null",
    "duration_sec": 15-30,
    "user_question_hooks": ["optional question to prompt thinking"]
  }}
]

### Rules
- First state: overview showing all components (empty dim_regions, empty highlight_paths).
- Middle states: highlight ONE flow at a time. Actively dim components not part of the current explanation.
  For example, when explaining the blocked flow, dim redis and app_servers since requests never reach them.
- Algorithm states: focus only on the decision component and use overlay_mode. Dim everything else.
- Last state: summary showing all components and both flow paths highlighted.
- Narration must reference visual elements ("notice the green arrows", "the shield icon represents").
- Include at least one user_question_hook per state to encourage active learning.
- Return ONLY the JSON array — no markdown, no explanation.
"""

_ANIMATION_CHUNK_PROMPT = """\
You plan **short cinematic animation clips** for Veo (Google video generation).
Each clip is at most **8 seconds**. Clips concatenate into one explainer for a
**CS / system-design** topic (e.g. rate limiting, deadlock, load balancing).

### Topic
{topic}

### Diagram spec (components, connections, flow_paths, side_panel — use exact labels)
{diagram_spec_json}

### Walkthrough beats (chunk order should follow this pedagogical arc)
{walkthrough_json}

### Required JSON object (return ONLY this object, no markdown)
{{
  "theme": "One sentence: unified visual theme for ALL clips (palette, 3D isometric vs flat, lighting).",
  "music_prompt": "Rich instrumental Lyria prompt: genre, BPM feel, instruments, mood; educational tech documentary; **no vocals**.",
  "chunks": [
    {{
      "title": "2-6 words",
      "duration_sec": 8,
      "narration_text": "2-4 short sentences of **spoken voiceover** for this clip only. Clear English. Name concrete concepts (e.g. token bucket, circular wait). Say what the viewer should notice on screen. No stage directions like 'camera zooms'.",
      "veo_prompt": "One dense paragraph for Veo: **1080p-quality** 16:9 cinematic technical animation. Repeat the SAME style anchors every time (palette, isometric/orthographic, lighting). Tie visuals to **this CS topic**: name components from the diagram spec by label, show **request/data flow** with arrows or light trails, optional short on-screen labels (not lip-sync). One story beat per clip; continuity with prior/next chunks."
    }}
  ]
}}

### Rules
- **4 to 6** chunks. Story arc: context → core mechanism → failure/alternate path → example numbers → summary.
- **duration_sec** integer **5–8**.
- **veo_prompt**: must reference **specific diagram elements** (component labels, flow path colors, side-panel steps) where relevant so video matches the topic.
- **narration_text**: will be read aloud; must match what **veo_prompt** shows for that segment.
- **music_prompt**: strong melodic presence (not barely audible pad) but still instrumental.
"""


def _fallback_animation_plan(
    topic: str,
    diagram_spec: dict,
    walkthrough_states: list[dict],
) -> dict:
    """Build a minimal animation plan without LLM."""
    comp_labels = ", ".join(
        str(c.get("label", c.get("id", "")))
        for c in diagram_spec.get("components", [])[:12]
    )
    theme = (
        f"Unified educational 3D isometric explainer for {topic}: "
        "cool blue and teal accents, soft white-gray background, crisp labels, smooth camera moves."
    )
    music_prompt = (
        f"Uplifting minimal electronic ambient for a computer science tutorial about {topic}; "
        "steady mid-tempo, gentle arpeggios, no vocals, inspiring and clear."
    )
    style_anchor = (
        "16:9 cinematic 3D isometric technical animation, cool blue/teal/gray palette, "
        "soft gradients, clean readable labels, professional educational motion graphics. "
    )
    chunks: list[dict] = []
    states = walkthrough_states[:6] if walkthrough_states else []
    if not states:
        states = [
            {
                "title": "Overview",
                "narration": f"Introduction to {topic}.",
            }
        ]
    for st in states:
        title = str(st.get("title", "Scene"))
        narr = str(st.get("narration", ""))[:500]
        narr_voice = narr[:900] if narr else (
            f"This segment covers {title} in the context of {topic}. "
            f"Watch how data and control flow between the main parts of the system."
        )
        chunks.append({
            "title": title,
            "duration_sec": 8,
            "narration_text": narr_voice,
            "veo_prompt": (
                f"{style_anchor}Topic: {topic}. Beat: {title}. "
                f"Narrative context: {narr[:320]}. "
                f"Visually emphasize these named parts when relevant: {comp_labels}. "
                "Show directed flow with arrows or glowing paths; crisp readable labels; "
                "one clear idea per clip matching a CS interview-style explanation."
            ),
        })
    while len(chunks) < 4:
        chunks.append({
            "title": f"Deep dive {len(chunks) + 1}",
            "duration_sec": 8,
            "narration_text": (
                f"Another angle on {topic}: reinforcing the core mechanism and how components interact."
            ),
            "veo_prompt": (
                f"{style_anchor}Continue explaining {topic}; reinforce the main mechanism "
                "with labeled nodes, queues, or counters and visible data flow."
            ),
        })
    return {"theme": theme, "music_prompt": music_prompt, "chunks": chunks[:6]}


async def _generate_via_llm(
    llm_provider: Any,
    prompt: str,
) -> Any:
    """Call the LLM provider's _generate and parse JSON."""
    raw = await llm_provider._generate(prompt)

    from app.providers.google_llm import _extract_json
    return _extract_json(raw)


class DiagramService:
    """Orchestrates diagram-spec generation — curated fallback first, LLM second."""

    def __init__(self, llm_provider: Any | None = None) -> None:
        self.llm = llm_provider

    async def generate_diagram_spec(
        self,
        topic: str,
        concepts: dict | None = None,
        sections: list[dict] | None = None,
    ) -> dict:
        curated = get_curated_diagram(topic)
        if curated:
            logger.info("Using curated diagram spec for topic=%r", topic)
            return curated[0]

        if not self.llm:
            raise RuntimeError("No LLM provider and no curated spec for topic=%r" % topic)

        prompt = _DIAGRAM_SPEC_PROMPT.format(
            topic=topic,
            concepts_json=json.dumps(concepts or {}, indent=2),
            sections_json=json.dumps(sections or [], indent=2),
        )
        result = await _generate_via_llm(self.llm, prompt)
        if not isinstance(result, dict):
            raise ValueError(f"LLM returned {type(result).__name__}, expected dict for diagram spec")
        return result

    async def generate_walkthrough_states(
        self,
        topic: str,
        diagram_spec: dict,
    ) -> list[dict]:
        curated = get_curated_diagram(topic)
        if curated:
            logger.info("Using curated walkthrough states for topic=%r", topic)
            return curated[1]

        if not self.llm:
            raise RuntimeError("No LLM provider and no curated walkthrough for topic=%r" % topic)

        prompt = _WALKTHROUGH_PROMPT.format(
            topic=topic,
            diagram_spec_json=json.dumps(diagram_spec, indent=2),
        )
        result = await _generate_via_llm(self.llm, prompt)
        if not isinstance(result, list):
            raise ValueError(
                f"LLM returned {type(result).__name__}, expected list for walkthrough states"
            )
        return result

    async def generate_full(
        self,
        topic: str,
        concepts: dict | None = None,
        sections: list[dict] | None = None,
    ) -> tuple[dict, list[dict]]:
        """Generate both diagram spec and walkthrough states."""
        spec = await self.generate_diagram_spec(topic, concepts, sections)
        states = await self.generate_walkthrough_states(topic, spec)
        return spec, states

    async def plan_animation_chunks(
        self,
        topic: str,
        diagram_spec: dict,
        walkthrough_states: list[dict],
    ) -> dict:
        """Return theme, music_prompt, and chunks[] for Veo multi-clip generation."""
        if not self.llm or not callable(getattr(self.llm, "_generate", None)):
            logger.info("plan_animation_chunks: no LLM or no _generate, using fallback plan")
            return _fallback_animation_plan(topic, diagram_spec, walkthrough_states)

        prompt = _ANIMATION_CHUNK_PROMPT.format(
            topic=topic,
            diagram_spec_json=json.dumps(diagram_spec, indent=2)[:12000],
            walkthrough_json=json.dumps(walkthrough_states, indent=2)[:8000],
        )
        try:
            result = await _generate_via_llm(self.llm, prompt)
            if not isinstance(result, dict):
                raise ValueError("expected dict")
            chunks = result.get("chunks")
            if not isinstance(chunks, list) or len(chunks) < 1:
                raise ValueError("invalid chunks")
            cleaned: list[dict] = []
            for c in chunks[:8]:
                if not isinstance(c, dict):
                    continue
                dur = int(c.get("duration_sec", 8))
                dur = max(5, min(dur, 8))
                veo_p = str(c.get("veo_prompt", "")).strip()
                if not veo_p:
                    continue
                title_s = str(c.get("title", "Segment"))[:200]
                narr = str(c.get("narration_text", "")).strip()
                if not narr:
                    narr = (
                        f"In this part we focus on {title_s} for {topic}. "
                        f"Follow the flow and labels on screen as the concept unfolds."
                    )[:900]
                cleaned.append({
                    "title": title_s,
                    "duration_sec": dur,
                    "narration_text": narr[:1200],
                    "veo_prompt": veo_p[:4000],
                })
            if len(cleaned) < 2:
                raise ValueError("too few valid chunks")
            return {
                "theme": str(result.get("theme", ""))[:500] or "Educational technical animation",
                "music_prompt": str(result.get("music_prompt", ""))[:1500]
                or _fallback_animation_plan(topic, diagram_spec, walkthrough_states)[
                    "music_prompt"
                ],
                "chunks": cleaned[:6],
            }
        except Exception as exc:
            logger.warning("plan_animation_chunks LLM failed: %s, using fallback", exc)
            return _fallback_animation_plan(topic, diagram_spec, walkthrough_states)
