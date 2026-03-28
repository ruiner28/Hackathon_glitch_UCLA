import logging

from app.providers.base import MusicProvider, StorageProvider

logger = logging.getLogger(__name__)


class MusicService:
    def __init__(self, music: MusicProvider, storage: StorageProvider):
        self.music = music
        self.storage = storage

    async def generate_background_track(
        self, mood: str, duration_sec: float, lesson_id: str
    ) -> str:
        """
        Generate and store background music.

        Calls the MusicProvider to generate a track with the given mood and
        duration, then stores it via StorageProvider.

        Returns the storage URL of the generated audio file.
        """
        logger.info(
            "MusicService: generating track mood=%s duration=%.1fs lesson=%s",
            mood, duration_sec, lesson_id,
        )

        audio_bytes = await self.music.generate_track(mood, duration_sec)

        path = f"audio/music/{lesson_id}/{mood}.wav"
        url = await self.storage.put_file(path, audio_bytes, "audio/wav")

        logger.info("MusicService: stored background track at %s", url)
        return url
