import logging
import struct
import zlib

from app.providers.base import ImageProvider

logger = logging.getLogger(__name__)


def _minimal_png(width: int = 1, height: int = 1, rgba: tuple[int, ...] = (100, 100, 255, 255)) -> bytes:
    """Generate a valid minimal PNG image programmatically."""
    r, g, b, a = rgba

    raw_row = bytes([0, r, g, b, a])  # filter byte + RGBA
    raw_data = raw_row * height

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        crc = zlib.crc32(c) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + c + struct.pack(">I", crc)

    signature = b"\x89PNG\r\n\x1a\n"

    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    ihdr = _chunk(b"IDAT"[:0] + b"IHDR", ihdr_data)

    compressed = zlib.compress(raw_data)
    idat = _chunk(b"IDAT", compressed)

    iend = _chunk(b"IEND", b"")

    return signature + ihdr + idat + iend


class MockImageProvider(ImageProvider):
    """Returns a minimal valid PNG placeholder for every request."""

    async def generate_image(self, prompt: str, style: str, width: int, height: int) -> bytes:
        logger.info("MockImage: generate_image prompt=%r style=%s %dx%d", prompt[:80], style, width, height)
        return _minimal_png(width=1, height=1, rgba=(100, 149, 237, 255))

    async def generate_keyframe(self, scene_spec: dict) -> bytes:
        title = scene_spec.get("title", "unknown")
        logger.info("MockImage: generate_keyframe for scene '%s'", title)
        return _minimal_png(width=1, height=1, rgba=(60, 179, 113, 255))
