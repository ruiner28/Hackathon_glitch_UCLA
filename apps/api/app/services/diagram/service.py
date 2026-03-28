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
