from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_repo_root() -> Path:
    """Monorepo root (directory containing pnpm-workspace.yaml). Fallback: depth from this file."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pnpm-workspace.yaml").is_file():
            return parent
    return here.parents[4]


# Exposed for health/debug routes — must match env_file paths below.
REPO_ROOT = _resolve_repo_root()
APPS_API_ROOT = REPO_ROOT / "apps" / "api"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Root .env then apps/api/.env (later file wins for duplicate keys).
        env_file=(
            str(REPO_ROOT / ".env"),
            str(APPS_API_ROOT / ".env"),
        ),
        # utf-8-sig strips a leading BOM so the first line is read as GEMINI_API_KEY=...
        env_file_encoding="utf-8-sig",
        case_sensitive=True,
        extra="ignore",
    )

    # Default: file DB for local dev without Docker (run API from apps/api so ./visualcs.db resolves).
    DATABASE_URL: str = "sqlite+aiosqlite:///./visualcs.db"
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_PATH: str = "./storage"
    DEMO_CACHE_PATH: str = "./storage/demo_cache"

    LLM_PROVIDER: str = "mock"
    IMAGE_PROVIDER: str = "mock"
    VIDEO_PROVIDER: str = "mock"
    TTS_PROVIDER: str = "mock"
    MUSIC_PROVIDER: str = "mock"

    # Accept common alternate names (e.g. from other tools / manual .env typing).
    GEMINI_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("GEMINI_API_KEY", "Gemini_Api_Key"),
    )
    GEMINI_MODEL: str = "gemini-2.0-flash"
    # Veo text-to-video model id (Gemini API). Override if Google ships newer IDs.
    VEO_MODEL: str = "veo-2.0-generate-001"
    # Generate Animation: skip live Veo when offline assets exist (see demo_cache.py).
    VEO_OFFLINE_USE_DEMO_CACHE: bool = True
    # If true and storage/output/{lessonId}/lesson.mp4 already exists, reuse it (no Veo).
    VEO_REUSE_EXISTING_OUTPUT: bool = False
    # Stitch MP4s under LOCAL_STORAGE_PATH/VEO_VIDEOS_DIR (e.g. video 1.mp4 … video 3.mp4) for Generate Animation.
    VEO_USE_STITCHED_FOLDER: bool = True
    VEO_VIDEOS_DIR: str = "VeoVideos"

    GCS_BUCKET_NAME: str = ""
    GOOGLE_PROJECT_ID: str = ""
    # Vertex AI (Lyria music). Region for aiplatform.googleapis.com predict endpoints.
    GOOGLE_CLOUD_LOCATION: str = "us-central1"

    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "change-me-in-production"
    FRONTEND_URL: str = "http://localhost:3000"
    API_URL: str = "http://localhost:8000"

    # Google OAuth (Sign in with Google). Redirect URI must match Google Cloud Console
    # exactly (character-for-character) and use the Next origin + /api/auth/callback/google.
    # Aliases match common .env names from Next.js / other templates.
    GOOGLE_OAUTH_CLIENT_ID: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GOOGLE_OAUTH_CLIENT_ID",
            "NEXT_PUBLIC_GOOGLE_CLIENT_ID",
        ),
    )
    GOOGLE_OAUTH_CLIENT_SECRET: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GOOGLE_OAUTH_CLIENT_SECRET",
            "AUTH_GOOGLE_SECRET",
            "GOOGLE_CLIENT_SECRET",
        ),
    )
    GOOGLE_OAUTH_REDIRECT_URI: str = "http://localhost:3000/api/auth/callback/google"

    SESSION_COOKIE_NAME: str = "vc_session"
    SESSION_MAX_AGE_SEC: int = 60 * 60 * 24 * 7  # 7 days
    OAUTH_STATE_COOKIE_NAME: str = "oauth_state"
    OAUTH_STATE_MAX_AGE_SEC: int = 600
    OAUTH_NEXT_COOKIE_NAME: str = "oauth_next"

    @field_validator("GEMINI_API_KEY", mode="before")
    @classmethod
    def normalize_gemini_api_key(cls, v: object) -> str:
        """Strip whitespace and optional surrounding quotes from .env values."""
        if v is None:
            return ""
        s = str(v).strip()
        if len(s) >= 2 and (
            (s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")
        ):
            s = s[1:-1].strip()
        return s

    @field_validator("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", mode="before")
    @classmethod
    def strip_oauth_secrets(cls, v: object) -> str:
        if v is None:
            return ""
        s = str(v).strip()
        if len(s) >= 2 and (
            (s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")
        ):
            s = s[1:-1].strip()
        return s


def get_settings() -> Settings:
    """Fresh Settings each call so edits to `.env` apply after process restart (no stale lru_cache)."""
    return Settings()
