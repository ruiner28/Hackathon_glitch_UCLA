"""LLM provider backed by the Google Gemini API (google-genai SDK)."""

import json
import logging
import re
from typing import Any

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2

_SYSTEM_INSTRUCTION = (
    "You are an expert computer-science educator and instructional designer. "
    "Always respond with valid JSON matching the requested schema. "
    "Do not include any text outside the JSON object."
)


def _extract_json(text: str) -> Any:
    """Extract JSON from an LLM response that may include markdown fences."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start == -1:
            continue
        end = text.rfind(end_char)
        if end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}")


class GeminiLLMProvider(LLMProvider):
    """LLM provider backed by the Google Gemini API (new google-genai SDK)."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = settings.GEMINI_MODEL
        logger.info("GeminiLLM: initialised with model=%s", self.model_name)

    async def _generate(self, prompt: str) -> str:
        last_err: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 2):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=_SYSTEM_INSTRUCTION,
                    ),
                )
                return response.text
            except Exception as exc:
                last_err = exc
                logger.warning("GeminiLLM: attempt %d failed: %s", attempt, exc)
        raise RuntimeError(
            f"Gemini API failed after {_MAX_RETRIES + 1} attempts"
        ) from last_err

    async def extract_concepts(self, source_text: str, domain: str) -> dict:
        prompt = f"""Analyse the following source material about **{domain}** and extract a concept graph.

### Source Material
{source_text}

### Required JSON Schema
{{
  "nodes": [
    {{
      "id": "string (snake_case)",
      "label": "Human-readable name",
      "description": "One-sentence explanation",
      "importance": 0.0-1.0,
      "prerequisites": ["id", ...]
    }}
  ],
  "edges": [
    {{
      "source": "node id",
      "target": "node id",
      "relation_type": "prerequisite | specialisation | uses | produces | ..."
    }}
  ]
}}

Return ONLY the JSON object."""
        raw = await self._generate(prompt)
        return _extract_json(raw)

    async def create_lesson_plan(self, concepts: dict, domain: str, style: str) -> dict:
        prompt = f"""Create a detailed lesson plan for a visual CS lesson about **{domain}**.
Style preference: {style}.

### Concept Graph (for reference)
{json.dumps(concepts, indent=2)}

### Required JSON Schema
{{
  "lesson_title": "string",
  "target_audience": "string",
  "estimated_duration_sec": number,
  "objectives": ["string", ...],
  "prerequisites": ["string", ...],
  "misconceptions": ["string", ...],
  "sections": [
    {{
      "title": "string",
      "objective": "string",
      "scene_type": "deterministic_animation | generated_still_with_motion | veo_cinematic | code_trace | system_design_graph | summary_scene",
      "duration_sec": number (15-45),
      "key_points": ["string", ...],
      "visual_strategy": "string describing visuals",
      "narration": "Full narration for this section (2-4 sentences)",
      "teaching_note": "string — pedagogical note for this section"
    }}
  ]
}}

Create 6-8 sections with varied scene types. Return ONLY the JSON object."""
        raw = await self._generate(prompt)
        return _extract_json(raw)

    async def compile_scenes(self, lesson_plan: dict, domain: str) -> list[dict]:
        prompt = f"""Convert this lesson plan into detailed scene specifications for **{domain}**.

### Lesson Plan
{json.dumps(lesson_plan, indent=2)}

### Required JSON Schema (array of objects)
[
  {{
    "scene_id": "uuid string",
    "title": "string",
    "learning_objective": "string",
    "source_refs": [],
    "scene_type": "deterministic_animation | generated_still_with_motion | veo_cinematic | code_trace | system_design_graph | summary_scene",
    "style_preset": "clean_academic | modern_technical | cinematic_minimal (match lesson tone; repeat for visual identity)",
    "render_strategy": "remotion | image_to_video | veo | default",
    "render_mode": "auto | force_static | force_veo — auto uses motion only when it helps; force_static for recap/quiz-heavy stills; force_veo for strong dynamic hooks",
    "duration_sec": number,
    "narration_text": "Full narration script for this scene (2-4 sentences). Bridge from the previous idea: use phrases that connect sections into one lesson artifact.",
    "on_screen_text": ["bullet points shown on screen"],
    "continuity_anchor": "short phrase (e.g. color/motif) tying this scene to the lesson's recurring visual identity",
    "transition_note": "one line the editor shows before this scene — how it follows the prior section",
    "fallback_plan": "if video gen fails: what static image should still convey (one sentence)",
    "transition_metadata": {{"from_section": "string", "to_section": "string", "bridge_phrase": "string"}},
    "visual_elements": [
      {{"type": "string", "description": "string", "position": "string", "style": "string"}}
    ],
    "animation_beats": [
      {{"timestamp_sec": number, "action": "fade_in | reveal | highlight | fade_out", "description": "string"}}
    ],
    "asset_requests": [
      {{"type": "image | video", "prompt": "string", "provider": "string", "max_duration_sec": 5}}
    ],
    "veo_eligible": true/false,
    "veo_score": 0.0-1.0,
    "veo_prompt": "string or null — only when motion helps (flow, tokens draining, traffic). 3-5 second clip; camera, pacing, what moves.",
    "image_prompt": "string — Nano Banana still: explicit layout, whitespace, labeled regions, arrows, hierarchy, readable typography; no clutter.",
    "music_mood": "focused | dramatic | curious | uplifting | neutral",
    "teaching_note": "string",
    "validation_notes": ""
  }}
]

Rules:
- image_prompt: diagram-style clarity — grid, margins, callouts, consistent palette; educational first.
- veo_prompt: only for dynamic scenes (flows, counters, queues); keep duration implied short (3-5s); static recap/summary → veo_eligible false, render_mode force_static.
- Narration should reference on_screen_text and feel continuous across scenes.
Return ONLY the JSON array."""
        raw = await self._generate(prompt)
        return _extract_json(raw)

    async def write_narration(self, scene_spec: dict) -> str:
        prompt = f"""Write a clear, engaging narration script for this scene of a visual CS lesson.

### Scene Specification
{json.dumps(scene_spec, indent=2)}

Requirements:
- 2-4 sentences, spoken at a natural pace
- Pedagogically clear — guide the learner through the visual
- Reference what appears on screen
- Do NOT include stage directions or speaker tags

Return ONLY the narration text as a plain string (no JSON wrapping)."""
        return (await self._generate(prompt)).strip().strip('"')

    async def generate_quiz(self, lesson_plan: dict, scenes: list[dict]) -> list[dict]:
        prompt = f"""Generate quiz questions for this CS lesson.

### Lesson Plan
{json.dumps(lesson_plan, indent=2)}

### Scenes
{json.dumps(scenes[:3], indent=2)}

### Required JSON Schema (array of 3-5 questions)
[
  {{
    "question": "string",
    "options": ["string", "string", "string", "string"],
    "correct_answer": 0-3 (index),
    "explanation": "string explaining why the answer is correct"
  }}
]

Make questions test understanding, not recall. Return ONLY the JSON array."""
        raw = await self._generate(prompt)
        return _extract_json(raw)

    async def evaluate_lesson(self, lesson_data: dict) -> dict:
        prompt = f"""Evaluate the quality of this generated CS lesson.

### Lesson Data
{json.dumps(lesson_data, indent=2)}

### Required JSON Schema
{{
  "overall_score": 0.0-1.0,
  "content_accuracy": {{"score": 0.0-1.0, "feedback": "string"}},
  "pedagogical_quality": {{"score": 0.0-1.0, "feedback": "string"}},
  "visual_quality": {{"score": 0.0-1.0, "feedback": "string"}},
  "narration_quality": {{"score": 0.0-1.0, "feedback": "string"}},
  "engagement": {{"score": 0.0-1.0, "feedback": "string"}},
  "flags": ["string", ...],
  "suggestions": ["string", ...]
}}

Be constructive. Scores should be in the 0.7-0.95 range for a well-made lesson.
Return ONLY the JSON object."""
        raw = await self._generate(prompt)
        return _extract_json(raw)
