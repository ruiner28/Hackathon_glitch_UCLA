"""LLM provider backed by the Google Gemini API (google-genai SDK)."""

import json
import logging
import re
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.core.config import get_settings
from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_MAX_OUTPUT_TOKENS = 16384

_SYSTEM_INSTRUCTION = (
    "You are an expert computer-science educator and instructional designer. "
    "Always respond with valid JSON matching the requested schema. "
    "Do not include any text outside the JSON object."
)

# Gemini SDK sometimes injects internal validator error messages into the
# response stream when using response_mime_type="application/json".
# These lines corrupt the JSON and must be stripped before parsing.
_GEMINI_ARTIFACT_RE = re.compile(
    r"[ \t]*Callback from tool [^\n]*\n?",
    re.MULTILINE,
)


def _clean_gemini_artifacts(text: str) -> str:
    """Remove known Gemini SDK artifact lines that corrupt JSON output."""
    return _GEMINI_ARTIFACT_RE.sub("", text)


def _strip_markdown_fences(text: str) -> str:
    """Remove ``` / ```json at the start; do not require a closing fence (truncated replies)."""
    t = text.strip()
    m = re.match(r"^```(?:json)?\s*\n?", t, re.IGNORECASE)
    if m:
        t = t[m.end() :].strip()
    if t.endswith("```"):
        t = t[: -3].rstrip()
    return t.strip()


def _strip_stray_prose_lines(text: str) -> str:
    """Remove lines that are clearly not JSON (models sometimes insert English sentences mid-object)."""
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        if stripped.startswith("//") or stripped.startswith("#"):
            continue
        if stripped in ("true", "false", "null"):
            out.append(line)
            continue
        if any(c in line for c in "\"{}[]"):
            out.append(line)
            continue
        if re.match(r"^-?\d", stripped):
            out.append(line)
            continue
        if stripped in (",", "{", "}", "[", "]"):
            out.append(line)
            continue
        # JSON keys always start with a double quote; prose often starts with a letter
        if re.match(r"^[A-Za-z_]", stripped):
            logger.info(
                "Stripping stray prose line from LLM JSON: %s",
                stripped[:120],
            )
            continue
        out.append(line)
    return "\n".join(out)


def _sanitize_json_text(text: str) -> str:
    """Best-effort cleanup before json.loads (prose, fences already handled elsewhere)."""
    return _strip_stray_prose_lines(text)


def _balanced_json_slice(text: str, start: int, open_ch: str, close_ch: str) -> str | None:
    """Return substring from first balanced {…} or […] starting at *start*."""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _try_parse(text: str) -> Any | None:
    """Return parsed JSON or None."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_json(text: str) -> Any:
    """Extract JSON from an LLM response, tolerating fences, artifacts, and trailing junk."""
    cleaned = _sanitize_json_text(_clean_gemini_artifacts(text).strip())

    for variant in dict.fromkeys([cleaned, _strip_markdown_fences(cleaned)]):
        result = _try_parse(variant)
        if result is not None:
            return result
        # Second pass: strip prose again after fence removal (different line breaks)
        result = _try_parse(_sanitize_json_text(variant))
        if result is not None:
            return result

    # Full fenced block (both delimiters present)
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned, re.IGNORECASE)
    if match:
        inner = _sanitize_json_text(match.group(1).strip())
        result = _try_parse(inner)
        if result is not None:
            return result

    # Balanced {…} or […]
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = cleaned.find(open_ch)
        if start == -1:
            continue
        balanced = _balanced_json_slice(cleaned, start, open_ch, close_ch)
        if balanced:
            result = _try_parse(_sanitize_json_text(balanced))
            if result is not None:
                return result
        end = cleaned.rfind(close_ch)
        if end > start:
            result = _try_parse(
                _sanitize_json_text(cleaned[start : end + 1]),
            )
            if result is not None:
                return result

    raise ValueError(
        "Could not extract JSON from LLM response (truncated or invalid). "
        f"First 400 chars: {cleaned[:400]!r}"
    )


def _as_concept_dict(parsed: Any) -> dict:
    """Gemini sometimes returns a bare `[nodes]` array instead of `{{nodes, edges}}`."""
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        return {"nodes": parsed, "edges": []}
    raise ValueError(
        f"Gemini concept extraction returned {type(parsed).__name__}; expected object or array"
    )


def _as_lesson_plan_dict(parsed: Any) -> dict:
    """Normalize Gemini JSON: model sometimes returns a bare ``sections`` array or ``[{plan}]``."""
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        if (
            len(parsed) == 1
            and isinstance(parsed[0], dict)
            and (
                "sections" in parsed[0]
                or "lesson_title" in parsed[0]
                or "objectives" in parsed[0]
            )
        ):
            return parsed[0]
        # Bare array of section objects (matches schema for ``sections`` only).
        logger.info(
            "Gemini lesson plan returned a JSON array; normalized to plan['sections']."
        )
        return {"sections": parsed}
    raise ValueError(
        f"Gemini lesson plan returned {type(parsed).__name__}; expected a JSON object or array"
    )


def _as_scene_list(parsed: Any) -> list[dict]:
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        scenes = parsed.get("scenes")
        if isinstance(scenes, list):
            return scenes
        sections = parsed.get("sections")
        if isinstance(sections, list):
            return sections
    raise ValueError(
        f"Gemini scene compile returned {type(parsed).__name__}; expected a JSON array"
    )


def _is_gemini_api_key_rejected(exc: BaseException) -> bool:
    """True when Google returns invalid/missing API key (no point retrying)."""
    msg = str(exc).lower()
    if "api_key_invalid" in msg or "api key not valid" in msg:
        return True
    if isinstance(exc, genai_errors.ClientError):
        details = getattr(exc, "details", None)
        blob = json.dumps(details, default=str) if details is not None else ""
        if "API_KEY_INVALID" in blob or "api key not valid" in blob.lower():
            return True
    return False


_GEMINI_KEY_HELP = (
    "If the key is loaded but Google still says API_KEY_INVALID, open Google Cloud Console → "
    "APIs & Services → Credentials → your API key → set API restrictions to 'Don't restrict key' "
    "(for testing) or explicitly allow 'Generative Language API'. Enable the Generative Language API "
    "for the project. New key: https://aistudio.google.com/apikey — Shell env overrides .env: "
    "`unset GEMINI_API_KEY`. For local dev without Google: LLM_PROVIDER=mock."
)


class GeminiLLMProvider(LLMProvider):
    """LLM provider backed by the Google Gemini API (new google-genai SDK)."""

    def __init__(self) -> None:
        settings = get_settings()
        key = (settings.GEMINI_API_KEY or "").strip()
        if not key:
            raise ValueError(
                "GEMINI_API_KEY is empty. Set it in your root .env when LLM_PROVIDER=google."
            )
        self.client = genai.Client(api_key=key)
        self.model_name = settings.GEMINI_MODEL
        logger.info(
            "GeminiLLM: model=%s api_key_len=%s prefix=%s",
            self.model_name,
            len(key),
            key[:4] if len(key) >= 4 else "????",
        )

    def _response_text(self, response: Any) -> str:
        text = getattr(response, "text", None)
        if text and str(text).strip():
            return str(text)
        snippet = ""
        try:
            snippet = repr(response.model_dump())[:800]
        except Exception:
            snippet = repr(response)[:800]
        raise RuntimeError(
            "Gemini returned no text (blocked, empty candidates, or unsupported response). "
            f"Model={self.model_name!r}. Snippet: {snippet}"
        )

    async def _generate(self, prompt: str, *, json_response: bool = False) -> str:
        """When *json_response* is True, ask Gemini for strict JSON (reduces stray prose)."""
        config_kw: dict[str, Any] = {
            "system_instruction": _SYSTEM_INSTRUCTION,
            "max_output_tokens": _MAX_OUTPUT_TOKENS,
        }
        if json_response:
            config_kw["response_mime_type"] = "application/json"
        config = types.GenerateContentConfig(**config_kw)
        last_err: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 2):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )
                return self._response_text(response)
            except Exception as exc:
                if _is_gemini_api_key_rejected(exc):
                    raise RuntimeError(
                        f"Gemini API key was rejected by Google. {_GEMINI_KEY_HELP}"
                    ) from exc
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

Constraints:
- At most 12 nodes and 24 edges; keep each description under 120 characters.
- Never insert comments, notes, or English sentences inside the JSON. Every line must be valid JSON syntax.

Return ONLY the JSON object."""
        raw = await self._generate(prompt, json_response=True)
        return _as_concept_dict(_extract_json(raw))

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

Create 6-8 sections with varied scene types. Return ONLY one JSON object whose top-level keys include lesson_title and sections. Do not return a bare JSON array. Do not add comments or prose inside the JSON."""
        raw = await self._generate(prompt, json_response=True)
        return _as_lesson_plan_dict(_extract_json(raw))

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
Return ONLY the JSON array. Do not add comments or prose inside the JSON."""
        raw = await self._generate(prompt, json_response=True)
        return _as_scene_list(_extract_json(raw))

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

Make questions test understanding, not recall. Return ONLY the JSON array. Do not add comments or prose inside the JSON."""
        raw = await self._generate(prompt, json_response=True)
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
Return ONLY the JSON object. Do not add comments or prose inside the JSON."""
        raw = await self._generate(prompt, json_response=True)
        return _extract_json(raw)
