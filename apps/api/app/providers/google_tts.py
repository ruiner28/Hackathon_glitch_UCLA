import logging

from google.cloud import texttospeech

from app.core.config import get_settings
from app.providers.base import TTSProvider

logger = logging.getLogger(__name__)


class GoogleTTSProvider(TTSProvider):
    """Text-to-speech provider using Google Cloud Text-to-Speech API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = texttospeech.TextToSpeechAsyncClient()
        self.project_id = settings.GOOGLE_PROJECT_ID
        logger.info("GoogleTTS: initialised (project=%s)", self.project_id)

    async def synthesize(
        self, text: str, voice: str = "en-US-Neural2-D", speaking_rate: float = 1.0
    ) -> bytes:
        # Detect SSML vs plain text
        if text.strip().startswith("<speak"):
            synthesis_input = texttospeech.SynthesisInput(ssml=text)
        else:
            synthesis_input = texttospeech.SynthesisInput(text=text)

        # Parse voice name into language code and name
        parts = voice.rsplit("-", 1)
        if len(parts) == 2 and len(parts[0]) >= 4:
            language_code = parts[0].rsplit("-", 1)[0]  # e.g. "en-US"
        else:
            language_code = "en-US"

        voice_params = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice,
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speaking_rate,
        )

        logger.info("GoogleTTS: synthesize voice=%s rate=%.1f len=%d", voice, speaking_rate, len(text))

        response = await self.client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
        )

        return response.audio_content
