import json
import logging
import re
from typing import Any

import google.generativeai as genai

from app.core.config import get_settings
from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2


def _extract_json(text: str) -> Any:
    """Extract JSON from an LLM response that may include markdown fences."""
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Last resort: find first { or [ and parse from there
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
    """LLM provider backed by the Google Gemini API (google-generativeai SDK)."""

    def __init__(self) -> None:
        settings = get_settings()
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model_name = settings.GEMINI_MODEL
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=(
                "You are an expert computer-science educator and instructional designer. "
                "Always respond with valid JSON matching the requested schema. "
                "Do not include any text outside the JSON object."
            ),
        )
        logger.info("GeminiLLM: initialised with model=%s", self.model_name)

    async def _generate(self, prompt: str) -> str:
        last_err: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 2):
            try:
                response = await self.model.generate_content_async(prompt)
                return response.text
            except Exception as exc:
                last_err = exc
                logger.warning("GeminiLLM: attempt %d failed: %s", attempt, exc)
        raise RuntimeError(f"Gemini API failed after {_MAX_RETRIES + 1} attempts") from last_err

    # ------------------------------------------------------------------

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
      "visual_strategy": "string describing visuals"
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
    "render_strategy": "remotion | image_to_video | veo | default",
    "duration_sec": number,
    "narration_text": "Full narration script for this scene (2-4 sentences, pedagogically clear)",
    "on_screen_text": ["bullet points shown on screen"],
    "visual_elements": [
      {{"type": "string", "description": "string", "position": "string", "style": "string"}}
    ],
    "animation_beats": [
      {{"timestamp_sec": number, "action": "fade_in | reveal | highlight | fade_out", "description": "string"}}
    ],
    "asset_requests": [
      {{"type": "image | video", "prompt": "string", "provider": "string"}}
    ],
    "veo_prompt": "string or null",
    "image_prompt": "string or null",
    "music_mood": "focused | dramatic | curious | uplifting | neutral",
    "validation_notes": ""
  }}
]

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
