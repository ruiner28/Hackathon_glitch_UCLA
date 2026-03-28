import logging

from app.providers.base import VideoProvider

logger = logging.getLogger(__name__)

# Minimal valid MP4 (ftyp + moov with no tracks) — just enough bytes for
# tools to recognise the container format.  Real content will come from the
# actual video provider.
_MINIMAL_MP4 = (
    # ftyp box
    b"\x00\x00\x00\x1c"  # box size: 28
    b"ftyp"              # box type
    b"isom"              # major brand
    b"\x00\x00\x02\x00"  # minor version
    b"isomiso2mp41"      # compatible brands
    # moov box (empty but valid)
    b"\x00\x00\x00\x08"  # box size: 8
    b"moov"              # box type
)


class MockVideoProvider(VideoProvider):
    """Returns minimal placeholder video bytes and logs the request."""

    async def generate_from_text(self, prompt: str, duration_sec: float) -> bytes:
        logger.info(
            "MockVideo: generate_from_text duration=%.1fs prompt=%r",
            duration_sec,
            prompt[:120],
        )
        return _MINIMAL_MP4

    async def generate_from_image(self, image_data: bytes, prompt: str, duration_sec: float) -> bytes:
        logger.info(
            "MockVideo: generate_from_image duration=%.1fs image_size=%d prompt=%r",
            duration_sec,
            len(image_data),
            prompt[:120],
        )
        return _MINIMAL_MP4
