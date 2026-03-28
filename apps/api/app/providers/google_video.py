"""Video provider using Veo via google-genai SDK.

Uses Veo 2 (veo-2.0-generate-001) for generating short video clips.
Supports text-to-video and image-to-video (frame chaining for longer sequences).
"""

import asyncio
import logging
import time

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.providers.base import VideoProvider

logger = logging.getLogger(__name__)

_MAX_POLL_SECONDS = 300
_POLL_INTERVAL = 10


class VeoVideoProvider(VideoProvider):
    """Generates short video clips using the Veo API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info("VeoVideoProvider: initialized")

    async def generate_from_text(self, prompt: str, duration_sec: float) -> bytes:
        """Generate video from text prompt only."""
        return await self._generate(prompt, duration_sec)

    async def generate_from_image(
        self, image_data: bytes, prompt: str, duration_sec: float
    ) -> bytes:
        """Generate video using a reference image as the starting frame.

        This enables scene chaining: use the last frame of a previous clip
        as the starting frame for the next clip.
        """
        return await self._generate(prompt, duration_sec, start_image_bytes=image_data)

    async def _generate(
        self,
        prompt: str,
        duration_sec: float,
        start_image_bytes: bytes | None = None,
    ) -> bytes:
        clamped = max(5, min(int(duration_sec), 8))
        logger.info(
            "Veo: generating video (%ds), prompt=%s, has_start_frame=%s",
            clamped,
            prompt[:100],
            start_image_bytes is not None,
        )

        try:
            image_arg = None
            if start_image_bytes:
                image_arg = types.Image(
                    image_bytes=start_image_bytes,
                    mime_type="image/png",
                )

            operation = self.client.models.generate_videos(
                model="veo-2.0-generate-001",
                prompt=prompt,
                image=image_arg,
                config=types.GenerateVideosConfig(
                    aspect_ratio="16:9",
                    number_of_videos=1,
                ),
            )

            video_bytes = await self._poll_operation(operation)

            if video_bytes:
                logger.info("Veo: generated video (%.1f KB)", len(video_bytes) / 1024)
                return video_bytes

            logger.warning("Veo: no video produced, returning empty")
            return b""

        except Exception as e:
            logger.error("Veo: generation failed: %s", e)
            return b""

    async def _poll_operation(self, operation) -> bytes | None:
        """Poll the long-running operation until done or timeout."""
        start = time.monotonic()

        while not operation.done:
            elapsed = time.monotonic() - start
            if elapsed > _MAX_POLL_SECONDS:
                logger.warning("Veo: polling timed out after %ds", _MAX_POLL_SECONDS)
                return None

            logger.info("Veo: waiting for generation (%.0fs elapsed)...", elapsed)
            await asyncio.sleep(_POLL_INTERVAL)

            try:
                operation = self.client.operations.get(operation)
            except Exception as e:
                logger.warning("Veo: poll error: %s", e)
                await asyncio.sleep(_POLL_INTERVAL)
                continue

        if not operation.response or not operation.response.generated_videos:
            logger.warning("Veo: operation done but no videos in response")
            return None

        generated_video = operation.response.generated_videos[0]

        try:
            self.client.files.download(file=generated_video.video)
            video_bytes = generated_video.video.video_bytes
            if video_bytes:
                return video_bytes
        except Exception as e:
            logger.error("Veo: download failed: %s", e)

        return None
