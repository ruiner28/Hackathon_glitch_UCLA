import logging
import os
import shutil
import struct
import subprocess
import tempfile

from app.providers.base import TTSProvider

logger = logging.getLogger(__name__)


def _get_wav_duration(wav_bytes: bytes) -> float:
    """Extract duration from WAV header."""
    try:
        if len(wav_bytes) < 44:
            return 1.0
        data_size = struct.unpack_from("<I", wav_bytes, 40)[0]
        sample_rate = struct.unpack_from("<I", wav_bytes, 24)[0]
        block_align = struct.unpack_from("<H", wav_bytes, 32)[0]
        if sample_rate > 0 and block_align > 0:
            return data_size / (sample_rate * block_align)
    except Exception:
        pass
    return 1.0


class LocalTTSProvider(TTSProvider):
    """TTS provider using macOS `say` command for real speech synthesis."""

    VOICE = "Samantha"
    RATE = 175

    async def synthesize(
        self, text: str, voice: str = "en-US-Neural2-D", speaking_rate: float = 1.0
    ) -> bytes:
        if not shutil.which("say"):
            logger.warning("LocalTTS: 'say' command not found, returning silence")
            return _silent_wav_fallback(text, speaking_rate)

        tmpdir = tempfile.mkdtemp(prefix="tts_")
        aiff_path = os.path.join(tmpdir, "speech.aiff")
        wav_path = os.path.join(tmpdir, "speech.wav")

        try:
            rate = int(self.RATE * speaking_rate)
            clean_text = text.replace('"', '\\"').replace("'", "\\'")

            result = subprocess.run(
                ["say", "-v", self.VOICE, "-r", str(rate), "-o", aiff_path, clean_text],
                capture_output=True, text=True, timeout=60,
            )

            if result.returncode != 0 or not os.path.exists(aiff_path):
                logger.warning("LocalTTS: say failed: %s", result.stderr)
                return _silent_wav_fallback(text, speaking_rate)

            conv = subprocess.run(
                ["ffmpeg", "-y", "-i", aiff_path,
                 "-ar", "22050", "-ac", "1", "-sample_fmt", "s16",
                 wav_path],
                capture_output=True, text=True, timeout=30,
            )

            if conv.returncode != 0 or not os.path.exists(wav_path):
                logger.warning("LocalTTS: ffmpeg conversion failed: %s", conv.stderr[:200])
                return _silent_wav_fallback(text, speaking_rate)

            wav_bytes = open(wav_path, "rb").read()
            duration = _get_wav_duration(wav_bytes)
            logger.info(
                "LocalTTS: synthesized %.1fs of speech (%d bytes) for %d chars",
                duration, len(wav_bytes), len(text),
            )
            return wav_bytes

        except subprocess.TimeoutExpired:
            logger.warning("LocalTTS: timeout synthesizing %d chars", len(text))
            return _silent_wav_fallback(text, speaking_rate)
        except Exception as e:
            logger.error("LocalTTS: error: %s", e)
            return _silent_wav_fallback(text, speaking_rate)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


def _silent_wav_fallback(text: str, speaking_rate: float) -> bytes:
    chars_per_sec = 15
    duration = max(1.0, len(text) / (chars_per_sec * speaking_rate))
    sample_rate = 22050
    num_samples = int(sample_rate * duration)
    data_size = num_samples * 2

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, 1, sample_rate,
        sample_rate * 2, 2, 16,
        b"data", data_size,
    )
    return header + (b"\x00" * data_size)
