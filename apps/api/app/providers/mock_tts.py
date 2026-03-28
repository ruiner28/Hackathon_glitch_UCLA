import logging
import struct

from app.providers.base import TTSProvider

logger = logging.getLogger(__name__)


def _silent_wav(duration_sec: float, sample_rate: int = 22050, channels: int = 1, bits_per_sample: int = 16) -> bytes:
    """Generate a valid WAV file containing silence."""
    num_samples = int(sample_rate * duration_sec)
    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)
    data_size = num_samples * block_align

    header = struct.pack(
        "<4sI4s"   # RIFF header
        "4sIHHIIHH"  # fmt chunk
        "4sI",       # data chunk header
        b"RIFF",
        36 + data_size,  # file size - 8
        b"WAVE",
        b"fmt ",
        16,                # fmt chunk size
        1,                 # PCM format
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )

    silence = b"\x00" * data_size
    return header + silence


class MockTTSProvider(TTSProvider):
    """Generates a silent WAV file of appropriate duration based on text length."""

    CHARS_PER_SECOND = 15  # ~150 WPM at ~5 chars/word

    async def synthesize(
        self, text: str, voice: str = "en-US-Neural2-D", speaking_rate: float = 1.0
    ) -> bytes:
        duration = max(1.0, len(text) / (self.CHARS_PER_SECOND * speaking_rate))
        logger.info(
            "MockTTS: synthesize voice=%s rate=%.1f duration=%.1fs text=%r",
            voice,
            speaking_rate,
            duration,
            text[:80],
        )
        return _silent_wav(duration)
