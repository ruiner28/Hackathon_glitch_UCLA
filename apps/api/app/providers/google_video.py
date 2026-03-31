"""Video provider using Veo via google-genai SDK.

Uses Veo 2 (veo-2.0-generate-001) by default for short clips. Gemini Developer API
(api_key) does not support generate_audio or compression_quality on GenerateVideosConfig.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import deque

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.providers.base import VideoProvider

logger = logging.getLogger(__name__)

_MAX_POLL_SECONDS = 300
_POLL_INTERVAL = 10

_NEGATIVE = (
    "blurry, low resolution, illegible text, watermark, "
    "shaky handheld, cartoon mascot, horror, gore, flicker"
)


def _veo_config_attempts(
    duration_seconds: int,
) -> list[types.GenerateVideosConfig]:
    """Ordered fallbacks: some model/API combos reject 1080p or optional fields."""
    base = dict(
        aspect_ratio="16:9",
        number_of_videos=1,
        duration_seconds=duration_seconds,
    )
    return [
        types.GenerateVideosConfig(
            **base,
            resolution="1080p",
            enhance_prompt=True,
            negative_prompt=_NEGATIVE,
        ),
        types.GenerateVideosConfig(
            **base,
            resolution="720p",
            enhance_prompt=True,
            negative_prompt=_NEGATIVE,
        ),
        types.GenerateVideosConfig(
            **base,
            resolution="720p",
        ),
        types.GenerateVideosConfig(
            aspect_ratio="16:9",
            number_of_videos=1,
            duration_seconds=duration_seconds,
        ),
    ]


class VeoVideoProvider(VideoProvider):
    """Generates short video clips using the Veo API (Gemini developer client)."""

    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.VEO_MODEL
        self.last_error: str = ""
        self._failure_log: deque[str] = deque(maxlen=24)
        self._failure_lock = threading.Lock()
        if not (settings.GEMINI_API_KEY or "").strip():
            logger.warning(
                "VeoVideoProvider: GEMINI_API_KEY is empty — Veo calls will fail until set."
            )
        logger.info("VeoVideoProvider: initialized model=%s", self.model)

    def clear_generation_trace(self) -> None:
        with self._failure_lock:
            self._failure_log.clear()

    def generation_trace_summary(self, max_items: int = 6) -> str:
        with self._failure_lock:
            items = list(self._failure_log)[-max_items:]
        return " | ".join(items) if items else ""

    def _log_failure(self, message: str) -> None:
        msg = (message or "unknown").strip()[:600]
        if not msg:
            return
        with self._failure_lock:
            self._failure_log.append(msg)

    def _extract_video_bytes(self, operation) -> bytes | None:
        if operation.error:
            self.last_error = f"Veo operation error: {operation.error}"
            logger.error(self.last_error)
            return None

        result = operation.result or operation.response
        if not result or not result.generated_videos:
            self.last_error = "Veo finished but result had no generated_videos"
            logger.warning(self.last_error)
            return None

        generated = result.generated_videos[0]
        video = generated.video if generated else None
        if not video:
            self.last_error = "Veo response missing video object"
            logger.warning(self.last_error)
            return None

        if video.video_bytes:
            return video.video_bytes

        try:
            data = self.client.files.download(file=video)
            if data:
                return data
        except Exception as e:
            self.last_error = f"Veo file download failed: {e}"
            logger.error(self.last_error, exc_info=True)
            return None

        self.last_error = "Veo video had no bytes after download"
        logger.warning(self.last_error)
        return None

    def _poll_until_done(self, operation):
        start = time.monotonic()
        while operation.done is not True:
            elapsed = time.monotonic() - start
            if elapsed > _MAX_POLL_SECONDS:
                self.last_error = f"Veo polling timed out after {_MAX_POLL_SECONDS}s"
                logger.warning(self.last_error)
                return None
            logger.info("Veo: waiting (%.0fs)...", elapsed)
            time.sleep(_POLL_INTERVAL)
            try:
                operation = self.client.operations.get(operation=operation)
            except Exception as e:
                logger.warning("Veo: poll error: %s", e)
                time.sleep(_POLL_INTERVAL)
        return operation

    def _generate_sync(
        self,
        prompt: str,
        clamped: int,
        start_image_bytes: bytes | None,
    ) -> bytes:
        self.last_error = ""
        if not (self._settings.GEMINI_API_KEY or "").strip():
            self.last_error = "GEMINI_API_KEY is not set"
            self._log_failure(self.last_error)
            return b""

        image_arg = None
        if start_image_bytes:
            image_arg = types.Image(
                image_bytes=start_image_bytes,
                mime_type="image/png",
            )

        for attempt_i, config in enumerate(_veo_config_attempts(clamped)):
            try:
                logger.info(
                    "Veo: generate_videos attempt %s model=%s dur=%ss",
                    attempt_i + 1,
                    self.model,
                    clamped,
                )
                operation = self.client.models.generate_videos(
                    model=self.model,
                    prompt=prompt,
                    image=image_arg,
                    config=config,
                )
                operation = self._poll_until_done(operation)
                if operation is None:
                    continue

                video_bytes = self._extract_video_bytes(operation)
                if video_bytes:
                    return video_bytes

            except Exception as e:
                self.last_error = f"Veo generate_videos failed: {e}"
                logger.warning(
                    "Veo attempt %s failed (will try fallback config): %s",
                    attempt_i + 1,
                    e,
                    exc_info=logger.isEnabledFor(logging.DEBUG),
                )
                continue

        if not self.last_error:
            self.last_error = "All Veo config attempts returned no video bytes"
        logger.warning("Veo: %s", self.last_error)
        self._log_failure(self.last_error)
        return b""

    async def generate_from_text(self, prompt: str, duration_sec: float) -> bytes:
        return await self._generate(prompt, duration_sec)

    async def generate_from_image(
        self, image_data: bytes, prompt: str, duration_sec: float
    ) -> bytes:
        return await self._generate(prompt, duration_sec, start_image_bytes=image_data)

    async def _generate(
        self,
        prompt: str,
        duration_sec: float,
        start_image_bytes: bytes | None = None,
    ) -> bytes:
        clamped = max(5, min(int(duration_sec), 8))
        logger.info(
            "Veo: chunk (%ds) prompt_preview=%r has_start_frame=%s",
            clamped,
            (prompt[:120] + "…") if len(prompt) > 120 else prompt,
            start_image_bytes is not None,
        )

        data = await asyncio.to_thread(
            self._generate_sync, prompt, clamped, start_image_bytes
        )
        if data:
            logger.info("Veo: chunk ok (%.1f KB)", len(data) / 1024)
        return data
