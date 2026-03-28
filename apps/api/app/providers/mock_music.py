import logging
import struct

from app.providers.base import MusicProvider

logger = logging.getLogger(__name__)


def _silent_wav(duration_sec: float, sample_rate: int = 22050, channels: int = 2, bits_per_sample: int = 16) -> bytes:
    """Generate a valid stereo WAV file containing silence."""
    num_samples = int(sample_rate * duration_sec)
    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)
    data_size = num_samples * block_align

    header = struct.pack(
        "<4sI4s"
        "4sIHHIIHH"
        "4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
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


class MockMusicProvider(MusicProvider):
    """Generates a silent stereo WAV file of the requested duration."""

    async def generate_track(self, mood: str, duration_sec: float) -> bytes:
        logger.info("MockMusic: generate_track mood=%s duration=%.1fs", mood, duration_sec)
        return _silent_wav(max(1.0, duration_sec))
