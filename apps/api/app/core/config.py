from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/visualcs"
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_PATH: str = "./storage"

    LLM_PROVIDER: str = "mock"
    IMAGE_PROVIDER: str = "mock"
    VIDEO_PROVIDER: str = "mock"
    TTS_PROVIDER: str = "mock"
    MUSIC_PROVIDER: str = "mock"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    GCS_BUCKET_NAME: str = ""
    GOOGLE_PROJECT_ID: str = ""

    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "change-me-in-production"
    FRONTEND_URL: str = "http://localhost:3000"
    API_URL: str = "http://localhost:8000"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
