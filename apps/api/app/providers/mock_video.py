import logging
import os
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

from app.providers.base import VideoProvider

logger = logging.getLogger(__name__)

WIDTH, HEIGHT = 960, 540
FPS = 12
FRAME_COUNT_PER_SEC = FPS


def _get_font(size: int, bold: bool = False):
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _generate_motion_frames(prompt: str, duration_sec: float) -> list[Image.Image]:
    """Generate simple animated frames showing motion concept."""
    n_frames = max(6, int(duration_sec * FRAME_COUNT_PER_SEC))
    frames = []

    short_prompt = prompt[:60] if prompt else "Motion clip"

    font_label = _get_font(18, bold=True)
    font_badge = _get_font(12, bold=True)

    for i in range(n_frames):
        t = i / max(n_frames - 1, 1)
        img = Image.new("RGB", (WIDTH, HEIGHT))
        draw = ImageDraw.Draw(img)

        # Animated gradient background
        for y in range(HEIGHT):
            yt = y / HEIGHT
            phase = (t * 0.3 + yt * 0.7)
            r = int(20 + 15 * phase)
            g = int(25 + 20 * phase)
            b = int(45 + 30 * phase)
            draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

        # Moving particle dots
        import math
        for p in range(8):
            angle = t * math.pi * 2 + p * (math.pi / 4)
            cx = WIDTH // 2 + int(120 * math.cos(angle + p * 0.5))
            cy = HEIGHT // 2 + int(80 * math.sin(angle * 1.5 + p * 0.3))
            radius = 4 + int(3 * math.sin(t * math.pi * 2 + p))
            colors = [(56, 189, 248), (129, 140, 248), (244, 114, 182), (52, 211, 153)]
            pc = colors[p % len(colors)]
            faded = tuple(max(40, c - 30) for c in pc)
            draw.ellipse([(cx - radius, cy - radius), (cx + radius, cy + radius)], fill=faded)

        # Moving arrow showing flow direction
        arrow_x = int(80 + (WIDTH - 160) * t)
        arrow_y = HEIGHT // 2
        draw.line([(arrow_x - 30, arrow_y), (arrow_x, arrow_y)], fill=(56, 189, 248), width=3)
        draw.polygon([(arrow_x, arrow_y - 6), (arrow_x + 10, arrow_y), (arrow_x, arrow_y + 6)],
                     fill=(56, 189, 248))

        # Badge
        draw.rectangle([(10, 10), (120, 32)], fill=(56, 189, 248))
        draw.text((16, 14), "VEO MOTION", fill=(255, 255, 255), font=font_badge)

        # Label
        draw.text((10, HEIGHT - 40), short_prompt, fill=(200, 200, 210), font=font_label)

        frames.append(img)

    return frames


def _frames_to_mp4(frames: list[Image.Image], duration_sec: float) -> bytes:
    """Compose PIL frames into an MP4 using ffmpeg."""
    if not shutil.which("ffmpeg"):
        logger.warning("FFmpeg not found — returning empty video bytes")
        return b""

    tmpdir = tempfile.mkdtemp(prefix="veo_mock_")
    try:
        for i, frame in enumerate(frames):
            frame.save(os.path.join(tmpdir, f"f_{i:04d}.png"), "PNG")

        output = os.path.join(tmpdir, "clip.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(FPS),
            "-i", os.path.join(tmpdir, "f_%04d.png"),
            "-vf", f"scale={WIDTH}:{HEIGHT},format=yuv420p",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
            "-pix_fmt", "yuv420p",
            "-t", str(duration_sec),
            output,
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)

        if os.path.exists(output):
            with open(output, "rb") as f:
                return f.read()
        return b""
    except Exception as e:
        logger.error("Mock video generation failed: %s", e)
        return b""
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


class MockVideoProvider(VideoProvider):
    """Generates short animated placeholder clips to simulate Veo output."""

    async def generate_from_text(self, prompt: str, duration_sec: float) -> bytes:
        capped = min(duration_sec, 5.0)
        logger.info(
            "MockVideo: generate_from_text duration=%.1fs prompt=%r",
            capped, prompt[:100],
        )
        import asyncio
        loop = asyncio.get_event_loop()
        frames = await loop.run_in_executor(None, _generate_motion_frames, prompt, capped)
        video_bytes = await loop.run_in_executor(None, _frames_to_mp4, frames, capped)
        logger.info("MockVideo: produced %d bytes", len(video_bytes))
        return video_bytes

    async def generate_from_image(self, image_data: bytes, prompt: str, duration_sec: float) -> bytes:
        return await self.generate_from_text(prompt, duration_sec)
