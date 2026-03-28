# VisualCS Architecture

## Overview

VisualCS is a hybrid educational media pipeline that converts CS concepts, system design topics, and lecture materials into structured, narrated, visually rich explainer videos.

### Core Thesis

Unlike naive "upload → summarize → generate one video" pipelines, VisualCS uses a hybrid approach:

- **Gemini** (and other LLMs behind `LLMProvider`) for understanding, concept extraction, pedagogy planning, scene compilation, narration wording, quiz ideas, and evaluation
- **Deterministic rendering** (target architecture) for exact CS diagrams and algorithm visualizations; the current MVP emits **render manifests** as placeholders until Remotion/Manim/FFmpeg are fully wired
- **Image generation** (`ImageProvider`) for style-consistent illustrations and keyframes when scene specs request `asset_requests` of type `image`
- **Veo / video models** (`VideoProvider`) for selective cinematic scenes when specs request `asset_requests` of type `video`
- **Cloud TTS** (`TTSProvider`) for narration audio stored per scene
- **Lyria / music APIs** (`MusicProvider`) for background music aligned to scene `music_mood`
- **FFmpeg + Remotion** (planned) for final muxing; **AssemblyService** and **RenderingService** today produce structured manifests for hackathon/demo iteration

### System Architecture Diagram (text)

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│   Frontend   │────▶│   FastAPI     │────▶│   PostgreSQL   │
│   Next.js    │◀────│   Backend     │     │                │
└─────────────┘     └──────┬───────┘     └───────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
      ┌──────────┐  ┌──────────┐  ┌──────────┐
      │  Gemini  │  │   Veo    │  │  Cloud   │
      │  (LLM)   │  │ (Video)  │  │   TTS    │
      └──────────┘  └──────────┘  └──────────┘
              │            │            │
              ▼            ▼            ▼
         ┌─────────────────────────────────┐
         │     Storage (GCS / Local)       │
         └─────────────────────────────────┘
```

Redis is included in `docker-compose.yml` for future job queues; the synchronous pipeline in `LessonPipeline` does not require it for core lesson steps.

### Pipeline Flow

1. **Ingestion** — Accept topic or uploaded PDF/PPTX; normalize into `SourceDocument` and `SourceFragment` rows (`IngestionService`).
2. **Semantic extraction** — LLM consumes fragment text; produces concept graph, prerequisites, misconceptions (`ExtractionService` → `LessonPlan` JSON columns).
3. **Pedagogy planning** — LLM turns the concept graph into objectives and ordered sections (`PlanningService` → `plan_json`).
4. **Scene compilation** — LLM expands the plan into one `SceneSpec` per scene; persisted as `Scene` rows with `scene_spec_json` (`CompilationService`).
5. **Asset generation** — Narration via TTS; optional image/video bytes from providers; `SceneAsset` records (`NarrationService`, image/video branches in `LessonPipeline.run_asset_generation`).
6. **Video assembly** — Preview/final render jobs combine scene specs, audio URLs, and predominant `music_mood` into stored outputs (`RenderingService`, `MusicService`; `AssemblyService` for full stitch when implemented).
7. **Evaluation** — LLM scores pedagogical and content quality; `EvaluationReport` stores `report_json` and `score_overall` (`EvaluationService`).

Orchestration lives in `app/services/pipeline.py` (`LessonPipeline`), which wires services and providers and is invoked from FastAPI route handlers.

### Module Breakdown (A–K)

| Module | Name | Responsibility | Primary interfaces |
|--------|------|----------------|-------------------|
| **A** | **Web client** | Topic entry, uploads, lesson progress UI, quiz/transcript views | HTTP → `/api/*`; `NEXT_PUBLIC_API_URL` |
| **B** | **HTTP API** | REST endpoints, request/response schemas, errors | `app/api/routes/*.py`, Pydantic models in `app/schemas/` |
| **C** | **Persistence** | Lessons, plans, scenes, assets, render jobs, evaluation | SQLAlchemy models under `app/models/`, Alembic migrations |
| **D** | **Ingestion** | PDF (PyMuPDF), PPTX (python-pptx), synthetic topic fragments | `IngestionService.extract_fragments`, `StorageProvider` for uploads |
| **E** | **Semantic extraction** | Concept graph + pedagogy-relevant lists from source text | `LLMProvider.extract_concepts`, `ExtractionService` |
| **F** | **Pedagogy planning** | Lesson title, audience, duration, sections with scene hints | `LLMProvider.create_lesson_plan`, `PlanningService` |
| **G** | **Scene compilation** | Deterministic vs cinematic scene types, durations, asset requests | `LLMProvider.compile_scenes`, `CompilationService` |
| **H** | **Asset generation** | Narration script polish, TTS audio, image/video binary assets | `NarrationService`, `ImageProvider`, `VideoProvider`, `StorageProvider.put_file` |
| **I** | **Rendering & music** | Per-scene manifests, preview/final job records, background track | `RenderingService`, `MusicService`, `RenderJob` model |
| **J** | **Evaluation** | Rubric-style scores, flags, suggestions | `LLMProvider.evaluate_lesson`, `EvaluationService` |
| **K** | **Providers & storage** | Swappable mock vs cloud implementations | `app/providers/factory.py`, ABCs in `app/providers/base.py` |

Versioned prompt templates for LLM steps live under `packages/prompts/v1/` (concept extraction, lesson planner, scene compiler, narration, image/veo helpers, evaluator, quiz).

### Data Flow

Textual pipeline (simplified):

`SourceDocument` → **`SourceFragment`** (many rows: title, bullet, note, body, …) → **concept graph + lists** (stored on `LessonPlan`: `concept_graph_json`, `prerequisites_json`, `misconceptions_json`) → **`plan_json`** (objectives, sections, estimated duration) → **`Scene` rows** each with **`scene_spec_json`** (full `SceneSpec`-shaped dict) → **`SceneAsset`** (audio/image/video URLs) + **`RenderJob`** (preview/final) → **final video URL** (when assembly is complete) → **`EvaluationReport`**.

Correlation keys:

- `Lesson.source_document_id` links uploaded or topic-derived documents.
- `Scene.source_refs_json` ties narration back to fragment `ref_key` values when the compiler provides them.
- `Scene.scene_spec_json` is the canonical spec consumed by rendering and asset loops.

### Provider Abstraction

All external capabilities are hidden behind abstract base classes in `app/providers/base.py`:

- **`LLMProvider`** — `extract_concepts`, `create_lesson_plan`, `compile_scenes`, `write_narration`, `generate_quiz`, `evaluate_lesson`
- **`ImageProvider`** — `generate_image`, `generate_keyframe`
- **`VideoProvider`** — `generate_from_text`, `generate_from_image`
- **`TTSProvider`** — `synthesize`
- **`MusicProvider`** — `generate_track`
- **`StorageProvider`** — `put_file`, `get_file`, `get_signed_url`, `delete_file`

`app/providers/factory.py` selects implementations from settings:

- **`LLM_PROVIDER`**: `mock` → `MockLLMProvider`; otherwise **`GeminiLLMProvider`**
- **`TTS_PROVIDER`**: `mock` → `MockTTSProvider`; otherwise **`GoogleTTSProvider`**
- **`STORAGE_BACKEND`**: `local` → **`LocalStorageProvider`** (writes under `LOCAL_STORAGE_PATH`); otherwise **`GCSStorageProvider`**
- **`IMAGE_PROVIDER` / `VIDEO_PROVIDER` / `MUSIC_PROVIDER`**: `mock` uses mock providers; non-mock paths currently fall back to mock implementations until dedicated Google (or other) clients are added

This lets the full UI and API run **without API keys** while preserving identical call sites for production wiring.

### Related documentation

- [API reference](./api-reference.md) — HTTP endpoints and payloads
- [JSON schemas](./schemas.md) — `ConceptGraph`, `LessonPlan`, `SceneSpec`, `EvaluationReport` shapes
