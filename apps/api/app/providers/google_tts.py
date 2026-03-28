"""TTS provider using Gemini 2.5 Flash TTS via google-genai SDK.

Uses the 'Charon' voice (Informative tone) for educational narration.
Outputs 24kHz mono 16-bit PCM wrapped in WAV format.
"""

import logging
import struct
import wave
import io

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.providers.base import TTSProvider

logger = logging.getLogger(__name__)

TTS_MODEL = "gemini-2.5-flash-preview-tts"
DEFAULT_VOICE = "Charon"
SAMPLE_RATE = 24000
SAMPLE_WIDTH = 2
CHANNELS = 1


class GeminiTTSProvider(TTSProvider):
    """Natural-sounding TTS using Gemini 2.5 Flash TTS (Charon voice)."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info("GeminiTTSProvider: initialized with voice=%s", DEFAULT_VOICE)

    async def synthesize(
        self, text: str, voice: str = "en-US-Neural2-D", speaking_rate: float = 1.0
    ) -> bytes:
        if not text or not text.strip():
            return _silent_wav(1.0)

        clean_text = text.strip()
        if len(clean_text) > 5000:
            clean_text = clean_text[:5000]

        style_instruction = (
            "Speak in a clear, warm, educational tone. "
            "Pace yourself naturally — slightly slower for key concepts, "
            "with brief pauses between sentences for clarity."
        )
        prompt = f"{style_instruction}\n\n{clean_text}"

        logger.info("GeminiTTS: synthesizing %d chars with voice=%s", len(clean_text), DEFAULT_VOICE)

        try:
            response = self.client.models.generate_content(
                model=TTS_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=DEFAULT_VOICE,
                            )
                        )
                    ),
                ),
            )

            if (
                not response.candidates
                or not response.candidates[0].content.parts
            ):
                logger.warning("GeminiTTS: empty response, returning silence")
                return _silent_wav(max(1.0, len(clean_text) / 15))

            pcm_data = response.candidates[0].content.parts[0].inline_data.data
            if not pcm_data:
                logger.warning("GeminiTTS: no audio data in response")
                return _silent_wav(max(1.0, len(clean_text) / 15))

            wav_bytes = _pcm_to_wav(pcm_data)
            duration = len(pcm_data) / (SAMPLE_RATE * SAMPLE_WIDTH)

            logger.info(
                "GeminiTTS: synthesized %.1fs audio (%.1f KB) for %d chars",
                duration, len(wav_bytes) / 1024, len(clean_text),
            )
            return wav_bytes

        except Exception as e:
            logger.error("GeminiTTS: synthesis failed: %s", e)
            return _silent_wav(max(1.0, len(clean_text) / 15))


def _pcm_to_wav(pcm_data: bytes) -> bytes:
    """Wrap raw PCM data in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def _silent_wav(duration_sec: float) -> bytes:
    """Generate a silent WAV file of the given duration."""
    num_samples = int(SAMPLE_RATE * duration_sec)
    data_size = num_samples * SAMPLE_WIDTH
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, CHANNELS, SAMPLE_RATE,
        SAMPLE_RATE * SAMPLE_WIDTH, SAMPLE_WIDTH, 16,
        b"data", data_size,
    )
    return header + (b"\x00" * data_size)
