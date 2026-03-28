"""Provider factory — instantiates the right implementation based on settings."""

from app.core.config import get_settings
from app.providers.base import (
    ImageProvider,
    LLMProvider,
    MusicProvider,
    StorageProvider,
    TTSProvider,
    VideoProvider,
)


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.LLM_PROVIDER == "mock":
        from app.providers.mock_llm import MockLLMProvider

        return MockLLMProvider()
    from app.providers.google_llm import GeminiLLMProvider

    return GeminiLLMProvider()


def get_image_provider() -> ImageProvider:
    settings = get_settings()
    if settings.IMAGE_PROVIDER == "mock":
        from app.providers.mock_image import MockImageProvider

        return MockImageProvider()
    from app.providers.google_image import NanoBananaImageProvider

    return NanoBananaImageProvider()


def get_video_provider() -> VideoProvider:
    settings = get_settings()
    if settings.VIDEO_PROVIDER == "mock":
        from app.providers.mock_video import MockVideoProvider

        return MockVideoProvider()
    from app.providers.google_video import VeoVideoProvider

    return VeoVideoProvider()


def get_tts_provider() -> TTSProvider:
    settings = get_settings()
    if settings.TTS_PROVIDER == "mock":
        from app.providers.mock_tts import MockTTSProvider

        return MockTTSProvider()
    if settings.TTS_PROVIDER == "local":
        from app.providers.local_tts import LocalTTSProvider

        return LocalTTSProvider()
    from app.providers.google_tts import GeminiTTSProvider

    return GeminiTTSProvider()


def get_music_provider() -> MusicProvider:
    settings = get_settings()
    if settings.MUSIC_PROVIDER == "mock":
        from app.providers.mock_music import MockMusicProvider

        return MockMusicProvider()
    from app.providers.mock_music import MockMusicProvider

    return MockMusicProvider()


def get_storage_provider() -> StorageProvider:
    settings = get_settings()
    if settings.STORAGE_BACKEND == "local":
        from app.providers.mock_storage import LocalStorageProvider

        return LocalStorageProvider(settings.LOCAL_STORAGE_PATH)
    from app.providers.google_storage import GCSStorageProvider

    return GCSStorageProvider()
