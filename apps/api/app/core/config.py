from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# .../<repo>/apps/api/app/core/config.py → apps/api dir and monorepo root
_APPS_API_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Root .env (where developers usually keep secrets) then apps/api/.env overrides.
        env_file=(
            str(_REPO_ROOT / ".env"),
            str(_APPS_API_ROOT / ".env"),
        ),
        env_file_encoding="utf-8",
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

    GCS_BUCKET_NAME: str = ""
    GOOGLE_PROJECT_ID: str = ""
    # Vertex AI (Lyria music). Region for aiplatform.googleapis.com predict endpoints.
    GOOGLE_CLOUD_LOCATION: str = "us-central1"

    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "change-me-in-production"
    FRONTEND_URL: str = "http://localhost:3000"
    API_URL: str = "http://localhost:8000"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
