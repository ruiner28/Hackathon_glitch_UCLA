# VisualCS

> Transform complex CS concepts into visual, narrated explainer videos.

VisualCS is a **hybrid** lesson pipeline: large language models plan and write pedagogy, while **deterministic renderers** (in the target architecture) carry exact diagrams, graphs, and timelines. Generative video and stills fill gaps for intros, analogies, and texture—without letting flashy but unreliable output replace core technical truth.

---

## What is VisualCS?

VisualCS converts difficult computer science learning material into **structured, narrated, visually rich** explainer videos. It supports:

- **CS concepts** — Compilers, operating systems, networks, databases, data structures and algorithms, automata, and related theory
- **System design** — Load balancers, caches, rate limiters, queues, sharding, and architectural tradeoffs
- **Lecture materials** — Upload **PPT/PPTX** or **PDF** files from a course, or enter a **plain-text topic** when you have no slides

### How it works

1. **Enter a topic** or **upload** lecture slides; the backend records a `SourceDocument` and extracts text fragments.
2. **AI extracts** a **concept graph**, prerequisites, and misconceptions, then builds a **lesson plan** with ordered sections.
3. **Scenes are compiled** into detailed **scene specs** (narration, on-screen text, animation beats, optional image/video requests).
4. **Narration** is synthesized (**TTS**); **images** and **short video clips** are generated when the spec asks for them; **background music** follows the dominant mood across scenes.
5. **Rendering and assembly** produce preview and final outputs. *The current codebase uses stored manifests as an MVP stepping stone toward full FFmpeg + Remotion (or similar) composition.*

### Key design principle

> **Deterministic educational clarity** over flashy but unreliable generation.

Technical diagrams (parse trees, wait-for graphs, scheduling timelines) are meant to be **rendered from structured specs**, not hallucinated frame-by-frame. **Generative video** (e.g. Veo-class models) is reserved for **hooks, analogies, and transitions** where approximate visuals are acceptable.

---

## Tech stack

### Frontend

- [Next.js 15](https://nextjs.org/) (App Router)
- TypeScript
- [Tailwind CSS](https://tailwindcss.com/) + [shadcn/ui](https://ui.shadcn.com/) patterns (Radix primitives)
- [Zustand](https://zustand-demo.pmnd.rs/) for client state
- [Remotion](https://www.remotion.dev/) — **planned** for timeline-accurate composition alongside server-side tooling

### Backend

- [FastAPI](https://fastapi.tiangolo.com/) (Python 3.12+)
- [SQLAlchemy](https://www.sqlalchemy.org/) + [PostgreSQL](https://www.postgresql.org/)
- [Pydantic v2](https://docs.pydantic.dev/) for settings and API schemas
- [Alembic](https://alembic.sqlalchemy.org/) for migrations

### AI & media

- **Gemini** (via `GeminiLLMProvider`) — concept extraction, planning, scene compilation, narration assistance, evaluation
- **Veo-class video** — behind `VideoProvider` for selective cinematic scenes
- **Google Cloud Text-to-Speech** — behind `TTSProvider` for narration audio
- **Lyria / music generation** — behind `MusicProvider` for beds under narration
- **FFmpeg + Remotion** — **target** assembly path; MVP services emit **JSON manifests** and placeholder assets to unblock UI and API integration

---

## Quick start

### Prerequisites

- **Node.js** 20+
- **Python** 3.12+
- **pnpm**
- **PostgreSQL** 16+
- **FFmpeg** (for future/local assembly; optional for API-only demo)

### Clone and install

```bash
git clone <repository-url>
cd Hackathon   # or rename the folder to visualcs

# Frontend
cd apps/web
pnpm install

# Backend (new terminal)
cd apps/api
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

The repo includes `pnpm-workspace.yaml` with `apps/web` and `packages/*` (currently **versioned prompts** under `packages/prompts/`).

### Database

**Without Docker (recommended for local dev):** use **SQLite** so nothing listens on port 5432. Copy `.env.example` to the repo root `.env` and keep:

```bash
DATABASE_URL=sqlite+aiosqlite:///./visualcs.db
```

Run the API from `apps/api` (as `pnpm dev:api` does) so the database file is created at `apps/api/visualcs.db`. Tables are created on API startup (`init_db`).

**With PostgreSQL** (optional): start Postgres, then point `DATABASE_URL` at it:

```bash
docker compose up postgres -d
```

Configure the API:

```bash
cd apps/api
cp ../../.env.example .env
# Edit .env: DATABASE_URL, optional GEMINI_API_KEY, provider toggles
alembic upgrade head
```

### Run the backend

```bash
cd apps/api
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000/docs** for interactive OpenAPI.

### Run the frontend (or full stack from repo root)

From the **repository root**, one command starts **FastAPI (8000)** and **Next.js (3000)**:

```bash
pnpm install   # root — pulls web + tooling including concurrently
pnpm dev
```

Use **`pnpm dev:web`** if you only need the UI and will point it at another API URL.

```bash
cd apps/web
pnpm dev
```

The app calls `/api/*` on the same origin; Next.js proxies to FastAPI on port 8000 (see `apps/web/next.config.ts`). Set `NEXT_PUBLIC_API_URL` only if the API is hosted on a different origin.

Open **http://localhost:3000**.

If the browser or Next logs show **`Failed to proxy … 127.0.0.1:8000`** or **`ECONNRESET`**, either the API is not running on port 8000 (use **`pnpm dev`** from the root or **`pnpm dev:api`**), or a pipeline step ran longer than the old proxy limit — the app config raises the Next.js dev **proxy timeout** so **`compile-scenes`** and other LLM calls can finish.

If you still use **PostgreSQL in Docker** while the API runs on the host, ensure `DATABASE_URL` matches a reachable host (often `localhost`, not the Docker service name).

### Docker Compose (full stack)

```bash
docker compose up
```

Services: **postgres**, **redis**, **api** (port 8000), **web** (port 3000). The API container mounts `./apps/api` and persists storage under a Docker volume.

---

## Environment variables

Values below match `/.env.example` and `apps/api/app/core/config.py`. Variables present only in `.env.example` are noted as **reserved** for future use.

| Variable | Description |
|----------|-------------|
| `GOOGLE_PROJECT_ID` | GCP project for Gemini, TTS, GCS, and related APIs |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON (**reserved** / tooling; not read by `Settings` today) |
| `GCS_BUCKET_NAME` | Bucket for `GCSStorageProvider` when `STORAGE_BACKEND` is not `local` |
| `GEMINI_API_KEY` | API key for Gemini when `LLM_PROVIDER` is not `mock` |
| `GEMINI_MODEL` | Model id (e.g. `gemini-2.5-pro`, `gemini-2.0-flash`) |
| `DATABASE_URL` | Async SQLAlchemy URL (default driver `asyncpg`) |
| `DATABASE_URL_SYNC` | Sync URL for tools (**reserved** in app settings) |
| `REDIS_URL` | Redis connection string for future workers |
| `STORAGE_BACKEND` | `local` (default) or GCS-backed storage |
| `LOCAL_STORAGE_PATH` | Directory for uploads and generated assets when local |
| `LLM_PROVIDER` | `mock` or Google-backed (`mock` recommended for hackathon demos without keys) |
| `IMAGE_PROVIDER` | `mock` (non-mock path falls back to mock until wired) |
| `VIDEO_PROVIDER` | `mock` (same as above) |
| `TTS_PROVIDER` | `mock` or `google` |
| `MUSIC_PROVIDER` | `mock` (non-mock path falls back to mock until wired) |
| `APP_ENV` | e.g. `development`, `production` |
| `APP_SECRET_KEY` | Secret for signing (extend for sessions/JWT as needed) |
| `FRONTEND_URL` | Allowed CORS origin for the web app |
| `API_URL` | Public API base URL (for links and callbacks) |

### Using mock providers

Set `LLM_PROVIDER=mock`, `TTS_PROVIDER=mock`, `IMAGE_PROVIDER=mock`, `VIDEO_PROVIDER=mock`, and `MUSIC_PROVIDER=mock` to run the **full pipeline** without billing or quota. Mock providers return deterministic placeholder content suitable for UI and integration tests.

---

## Project structure

```
Hackathon/
├── apps/
│   ├── web/                 # Next.js frontend
│   └── api/                 # FastAPI backend, Alembic, providers
├── packages/
│   └── prompts/             # Versioned LLM prompt templates (v1)
├── docs/
│   ├── architecture.md      # System design and module map
│   ├── api-reference.md     # REST endpoints
│   └── schemas.md           # Concept graph, lesson plan, scene spec, evaluation
├── docker-compose.yml
├── pnpm-workspace.yaml
└── .env.example
```

Planned or team-scalable additions (not all present yet): `packages/shared-types`, `packages/renderers`, `packages/provider-clients`.

---

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/architecture.md](./docs/architecture.md) | Pipeline, data flow, modules A–K, provider abstraction |
| [docs/api-reference.md](./docs/api-reference.md) | Every route, schemas, errors, recommended call order |
| [docs/schemas.md](./docs/schemas.md) | `ConceptGraph`, `LessonPlan`, `SceneSpec`, `EvaluationReport` with examples |

---

## Demo topics

The product narrative fits three canonical demos (seed data may vary by environment):

1. **Compiler bottom-up parsing** — Shift/reduce stack, parse trees, AST
2. **OS deadlock** — Coffman conditions, resource allocation graphs, prevention vs avoidance
3. **Rate limiter system design** — Token bucket, sliding window, distributed considerations

Try: create a topic source with `POST /api/uploads/topic`, then `POST /api/lessons` and walk the pipeline endpoints documented in [docs/api-reference.md](./docs/api-reference.md).

---

## Future scope

- Research-paper → lesson for **non-CS** domains (biology, economics, humanities)
- **Multilingual** voiceovers and on-screen text
- **Real-time tutor** chat grounded in the concept graph
- **Teacher authoring studio** with slide-accurate scene editing
- **Classroom analytics** (completion, replay hotspots)
- **User progress** and **spaced repetition** tied to lesson objectives
- **Interactive quizzes** during playback (the pipeline already includes quiz generation hooks)
- **YouTube / LMS** export and share links
- **Collaborative editing** of lesson plans and scenes
- **Student personalization** (pace, depth, prerequisite bridging)
- **Visual simulation labs** (executable sandboxes paired with explanations)
- **Live whiteboard** mode co-generated with speech
- **Concept graph search** across a course library

---

## License

MIT

---

## Acknowledgments

Built for hackathon-style iteration: **mock-first providers**, **clear JSON contracts**, and **documented APIs** so judges and teammates can run the stack quickly and see the vision end-to-end.
