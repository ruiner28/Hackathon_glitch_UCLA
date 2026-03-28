"""Background music via Lyria on Vertex AI (predict API), with silent WAV fallback."""

from __future__ import annotations

import asyncio
import base64
import logging

import httpx

from app.core.config import get_settings
from app.providers.base import MusicProvider
from app.providers.mock_music import _silent_wav

logger = logging.getLogger(__name__)

_LYRIA_MODEL = "lyria-002"


class LyriaMusicProvider(MusicProvider):
    """Instrumental music via Vertex Lyria; falls back to silence if Vertex unavailable."""

    def __init__(self) -> None:
        settings = get_settings()
        self._project = (settings.GOOGLE_PROJECT_ID or "").strip()
        self._location = (settings.GOOGLE_CLOUD_LOCATION or "us-central1").strip()
        logger.info(
            "LyriaMusicProvider: project=%s location=%s",
            self._project or "(none)",
            self._location,
        )

    async def generate_track(self, mood: str, duration_sec: float) -> bytes:
        prompt = (mood or "neutral ambient").strip()
        if not self._project:
            logger.warning("Lyria: GOOGLE_PROJECT_ID unset, using silent WAV")
            return _silent_wav(max(1.0, duration_sec))

        try:
            return await asyncio.to_thread(self._predict_sync, prompt)
        except Exception as exc:
            logger.warning("Lyria: generation failed (%s), using silent WAV", exc)
            return _silent_wav(max(1.0, duration_sec))

    def _predict_sync(self, prompt: str) -> bytes:
        from google.auth import default
        from google.auth.transport.requests import Request

        creds, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(Request())
        token = creds.token

        loc = self._location
        url = (
            f"https://{loc}-aiplatform.googleapis.com/v1/projects/{self._project}"
            f"/locations/{loc}/publishers/google/models/{_LYRIA_MODEL}:predict"
        )
        body = {
            "instances": [
                {
                    "prompt": prompt[:2000],
                    "negative_prompt": "harsh noise, distorted, chaotic, vocals, speech",
                }
            ],
            "parameters": {},
        }
        with httpx.Client(timeout=180.0) as client:
            r = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
        if r.status_code != 200:
            logger.warning(
                "Lyria: HTTP %s %s",
                r.status_code,
                (r.text or "")[:300],
            )
            raise RuntimeError(f"Lyria predict failed: {r.status_code}")

        data = r.json()
        preds = data.get("predictions") or []
        if not preds:
            raise RuntimeError("Lyria: empty predictions")
        audio_b64 = preds[0].get("audioContent")
        if not audio_b64:
            raise RuntimeError("Lyria: no audioContent")
        raw = base64.b64decode(audio_b64)
        if len(raw) < 100:
            raise RuntimeError("Lyria: audio too small")
        logger.info("Lyria: generated music (%.1f KB)", len(raw) / 1024)
        return raw
