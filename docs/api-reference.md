# VisualCS API Reference

Base URL (local): `http://localhost:8000`

Interactive OpenAPI: `GET /docs` (Swagger UI) and `GET /redoc` (ReDoc) when the FastAPI app is running.

**Path prefixes**

- Health and version routes are mounted at the **root** (no `/api` prefix).
- Upload and lesson routes are under **`/api`**.

All JSON request bodies use `Content-Type: application/json` unless noted. UUIDs are serialized as strings in JSON.

---

## Health

### `GET /health`

Liveness check.

**Response** `200 OK`

```json
{ "status": "ok" }
```

---

### `GET /version`

Application name and version.

**Response** `200 OK`

```json
{ "version": "0.1.0", "name": "VisualCS" }
```

---

## Uploads

### `POST /api/uploads`

Upload a lecture file. **Multipart form** (`multipart/form-data`) with a single field `file`.

**Allowed types**

| Content-Type | Stored as |
|--------------|-----------|
| `application/pdf` | `pdf` |
| `application/vnd.openxmlformats-officedocument.presentationml.presentation` | `pptx` |

**Limits**

- Maximum size: **50 MB**

**Response** `201 Created` — `SourceDocumentResponse`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "pdf",
  "title": "Lecture3",
  "original_filename": "Lecture3.pdf",
  "storage_url": "/path/or/url/to/storage/...",
  "normalized_pdf_url": null,
  "metadata_json": {
    "size_bytes": 1024000,
    "content_type": "application/pdf"
  },
  "status": "uploaded",
  "created_at": "2026-03-27T12:00:00Z",
  "updated_at": null
}
```

**Errors**

- `400` — Unsupported MIME type or file too large

---

### `POST /api/uploads/topic`

Create a **virtual** source document representing a free-text topic (no binary upload).

**Request body** — `TopicInput`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `topic` | string | yes | Main subject line |
| `domain` | string \| null | no | Hint for extraction (e.g. aligns with lesson domain) |
| `style_preset` | string \| null | no | Visual style hint |
| `target_duration_sec` | integer \| null | no | Desired lesson length |
| `music_enabled` | boolean | no | Default `true` |

**Example**

```json
{
  "topic": "Deadlock in operating systems",
  "domain": "cs",
  "style_preset": "clean_academic",
  "target_duration_sec": 600,
  "music_enabled": true
}
```

**Response** `201 Created` — `SourceDocumentResponse` with `type: "topic"` and `status: "ready"`.

---

## Lessons

### `POST /api/lessons`

Create a lesson row. Pipeline steps are invoked with separate endpoints below.

**Request body** — `LessonCreate`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_document_id` | UUID \| null | no | From upload or topic endpoint |
| `topic` | string \| null | no | Inline topic; also used as title when no document |
| `domain` | string \| null | no | `cs`, `system_design`, or `ppt_lesson` (see enums below) |
| `style_preset` | string \| null | no | `clean_academic`, `modern_technical`, `cinematic_minimal` |

**Example**

```json
{
  "source_document_id": "550e8400-e29b-41d4-a716-446655440000",
  "topic": "Compiler parsing",
  "domain": "cs",
  "style_preset": "clean_academic"
}
```

**Response** `201 Created` — `LessonResponse`

```json
{
  "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "source_document_id": "550e8400-e29b-41d4-a716-446655440000",
  "input_topic": "Compiler parsing",
  "domain": "cs",
  "title": "Compiler parsing",
  "summary": null,
  "target_audience": "undergraduate CS student",
  "style_preset": "clean_academic",
  "status": "created",
  "created_at": "2026-03-27T12:05:00Z",
  "updated_at": null
}
```

**Errors**

- `404` — `source_document_id` not found

---

### `GET /api/lessons/{lesson_id}`

Fetch lesson with **all scenes** (ordered).

**Response** `200 OK` — `LessonDetailResponse` (`LessonResponse` + `scenes: SceneResponse[]`)

**Scene object** (`SceneResponse`):

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Scene primary key |
| `lesson_id` | UUID | Parent lesson |
| `scene_order` | integer | 0-based order |
| `scene_type` | string | See scene types below |
| `title` | string | Short title |
| `duration_sec` | float | Planned duration |
| `render_strategy` | string | Renderer hint |
| `source_refs_json` | array \| null | Fragment keys |
| `narration_text` | string \| null | Spoken script |
| `on_screen_text_json` | array \| object \| null | Bullets / labels |
| `scene_spec_json` | object \| null | Full compiled spec |
| `status` | string | `pending`, `generating`, `rendered`, `error` |
| `created_at` | datetime | |
| `updated_at` | datetime \| null | |

**Errors**

- `404` — Lesson not found

---

### `POST /api/lessons/{lesson_id}/extract`

Run ingestion (if document-backed) and **semantic extraction**; updates `LessonPlan` concept fields and lesson title/summary when the LLM returns them.

**Response** `200 OK` — `LessonResponse`

---

### `POST /api/lessons/{lesson_id}/plan`

Run **pedagogy planning**; requires prior extraction (concept graph on `LessonPlan`).

**Response** `200 OK` — `LessonPlanResponse`

```json
{
  "id": "...",
  "lesson_id": "...",
  "concept_graph_json": { "nodes": [], "edges": [] },
  "prerequisites_json": [],
  "misconceptions_json": [],
  "lesson_objectives_json": [],
  "plan_json": { },
  "created_at": "2026-03-27T12:10:00Z"
}
```

---

### `POST /api/lessons/{lesson_id}/compile-scenes`

Replace all scenes for the lesson with newly compiled rows from `plan_json`.

**Response** `200 OK` — `SceneResponse[]`

---

### `POST /api/lessons/{lesson_id}/generate-assets`

Generate narration (TTS) and any image/video assets declared in each scene’s `asset_requests`.

**Response** `200 OK` — `LessonResponse`

---

### `POST /api/lessons/{lesson_id}/render-preview`

Create a **preview** render job (lower fidelity / manifest in MVP).

**Response** `200 OK` — `RenderJobResponse`

```json
{
  "id": "...",
  "lesson_id": "...",
  "job_type": "preview",
  "status": "completed",
  "progress": 100.0,
  "logs": null,
  "error_message": null,
  "started_at": "2026-03-27T12:15:00Z",
  "completed_at": "2026-03-27T12:15:05Z",
  "created_at": "2026-03-27T12:15:00Z"
}
```

---

### `POST /api/lessons/{lesson_id}/render-final`

Create a **final** render job, including stitched audio and background music when available.

**Response** `200 OK` — `RenderJobResponse` (`job_type`: `final`)

---

### `GET /api/lessons/{lesson_id}/scenes`

List scenes for a lesson (same shape as embedded in lesson detail).

**Response** `200 OK` — `SceneResponse[]`

---

### `PATCH /api/scenes/{scene_id}`

Partial update of editable scene fields.

**Request body** — `SceneUpdate`

| Field | Type | Description |
|-------|------|-------------|
| `narration_text` | string \| null | Replace narration |
| `on_screen_text` | string[] \| null | Replace on-screen lines |
| `duration_sec` | float \| null | Adjust duration |

**Example**

```json
{
  "narration_text": "Let us revisit deadlock prevention.",
  "on_screen_text": ["Mutual exclusion", "Hold and wait"],
  "duration_sec": 45.0
}
```

**Response** `200 OK` — `SceneResponse`

**Errors**

- `404` — Scene not found

---

### `POST /api/scenes/{scene_id}/regenerate`

Mark scene for regeneration (`status` reset to `pending`). Does not automatically re-run asset generation; use this to coordinate a future re-generation pass.

**Response** `200 OK` — `SceneResponse`

---

### `POST /api/lessons/{lesson_id}/evaluate`

Run LLM **quality evaluation** and persist `EvaluationReport`.

**Response** `200 OK` — `EvaluationResponse`

```json
{
  "id": "...",
  "lesson_id": "...",
  "report_json": {
    "overall_score": 0.82,
    "content_accuracy": { "score": 0.9, "feedback": "..." },
    "flags": [],
    "suggestions": []
  },
  "score_overall": 0.82,
  "flags_json": [],
  "created_at": "2026-03-27T12:20:00Z"
}
```

---

### `GET /api/lessons/{lesson_id}/evaluation`

Return the **latest** evaluation for the lesson.

**Response** `200 OK` — `EvaluationResponse`

**Errors**

- `404` — No report yet

---

### `GET /api/lessons/{lesson_id}/transcript`

Concatenate scene `narration_text` values with timestamps.

**Response** `200 OK` — `TranscriptResponse`

```json
{
  "full_text": "Scene one narration.\n\nScene two narration.",
  "scenes": [
    {
      "scene_id": "...",
      "text": "Scene one narration.",
      "timestamp": 0.0
    },
    {
      "scene_id": "...",
      "text": "Scene two narration.",
      "timestamp": 30.0
    }
  ]
}
```

---

### `GET /api/lessons/{lesson_id}/quiz`

Return quiz questions. *Current implementation returns a minimal placeholder* (one question derived from the lesson title). The pipeline also contains `generate_quiz` for LLM-backed quizzes when wired to an endpoint.

**Response** `200 OK` — `QuizResponse`

```json
{
  "questions": [
    {
      "question": "What is the main topic of 'Deadlock'?",
      "options": ["Deadlock", "Unrelated Topic A", "Unrelated Topic B", "Unrelated Topic C"],
      "correct_index": 0,
      "explanation": "The lesson is about Deadlock."
    }
  ]
}
```

---

### `GET /api/lessons/{lesson_id}/download`

**Placeholder.** Requires a completed **final** render job. Currently returns JSON with a message that full binary download is not yet implemented.

**Response** `200 OK` (when final render exists)

```json
{
  "lesson_id": "...",
  "status": "completed",
  "message": "Download endpoint placeholder — video assembly not yet implemented."
}
```

**Errors**

- `404` — No completed final render

---

## Enumerations (string values)

**`Lesson.domain`**

- `cs`
- `system_design`
- `ppt_lesson`

**`Lesson.style_preset`**

- `clean_academic`
- `modern_technical`
- `cinematic_minimal`

**`Lesson.status`**

- `created`, `extracting`, `planning`, `compiling`, `generating_assets`, `rendering`, `completed`, `error`

**`Scene.scene_type`**

- `deterministic_animation`
- `generated_still_with_motion`
- `veo_cinematic`
- `code_trace`
- `system_design_graph`
- `summary_scene`

**`RenderJob.status`**

- `queued`
- `running`
- `completed`
- `failed`

---

## CORS

The API allows origins from `FRONTEND_URL` and `http://localhost:3000` with credentials and all methods/headers for development.

---

## Recommended call sequence

1. `POST /api/uploads` or `POST /api/uploads/topic`
2. `POST /api/lessons`
3. `POST /api/lessons/{id}/extract`
4. `POST /api/lessons/{id}/plan`
5. `POST /api/lessons/{id}/compile-scenes`
6. `POST /api/lessons/{id}/generate-assets`
7. `POST /api/lessons/{id}/render-preview` or `render-final`
8. Optional: `POST /api/lessons/{id}/evaluate`, `GET .../transcript`, `GET .../quiz`

See [schemas.md](./schemas.md) for the JSON inside `concept_graph_json`, `plan_json`, and `scene_spec_json`.
