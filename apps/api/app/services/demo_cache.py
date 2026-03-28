"""
On-disk cache for showcase CS demo topics (images, audio, Veo clips, final MP4).

Layout under DEMO_CACHE_PATH (default: storage/demo_cache):

  {slug}/
    manifest.json
    scenes/{0..n-1}/image.png
    scenes/{0..n-1}/narration.wav
    scenes/{0..n-1}/video.mp4   (optional)
    output/lesson.mp4
    output/subtitles.srt

Populate with: python -m app.utils.populate_demo_cache --lesson-id <uuid> --slug rate_limiter
"""

from __future__ import annotations

import json
import logging
import re
import struct
from pathlib import Path
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Normalized substring -> cache slug (must match showcaseTopics on the homepage)
_TOPIC_SLUG_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"rate\s*limit", re.I), "rate_limiter"),
    (re.compile(r"deadlock", re.I), "os_deadlock"),
    (re.compile(r"bottom[-\s]?up\s*parsing|lr\s*parse", re.I), "bottom_up_parsing"),
]


def resolve_demo_cache_slug(input_topic: str | None) -> str | None:
    """Return cache directory slug if input_topic matches a showcase demo, else None."""
    if not input_topic or not input_topic.strip():
        return None
    for pattern, slug in _TOPIC_SLUG_PATTERNS:
        if pattern.search(input_topic.strip()):
            return slug
    return None


def demo_cache_root() -> Path:
    settings = get_settings()
    base = settings.DEMO_CACHE_PATH
    return Path(base).resolve()


def manifest_path(slug: str) -> Path:
    return demo_cache_root() / slug / "manifest.json"


def load_manifest(slug: str) -> dict[str, Any] | None:
    p = manifest_path(slug)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("demo_cache: failed to read manifest %s: %s", p, e)
        return None


def cache_is_ready_for_assets(slug: str, scene_count: int) -> bool:
    """True if per-scene cached files exist and match scene count."""
    m = load_manifest(slug)
    if not m:
        return False
    if m.get("scene_count") != scene_count:
        return False
    root = demo_cache_root() / slug
    for i in range(scene_count):
        scene_dir = root / "scenes" / str(i)
        if not (scene_dir / "image.png").is_file():
            return False
        if not (scene_dir / "narration.wav").is_file():
            return False
    return True


def cached_final_video_path(slug: str) -> Path | None:
    p = demo_cache_root() / slug / "output" / "lesson.mp4"
    return p if p.is_file() and p.stat().st_size > 1000 else None


def cached_subtitles_path(slug: str) -> Path | None:
    p = demo_cache_root() / slug / "output" / "subtitles.srt"
    return p if p.is_file() else None


def wav_duration_sec(wav_path: Path) -> float:
    try:
        data = wav_path.read_bytes()
        if len(data) < 44:
            return 1.0
        data_size = struct.unpack_from("<I", data, 40)[0]
        sample_rate = struct.unpack_from("<I", data, 24)[0]
        block_align = struct.unpack_from("<H", data, 32)[0]
        if sample_rate > 0 and block_align > 0:
            return data_size / (sample_rate * block_align)
    except Exception:
        pass
    return 1.0
