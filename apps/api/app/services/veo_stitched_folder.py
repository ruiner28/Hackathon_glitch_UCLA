"""Concatenate local clips under storage/VeoVideos into one MP4 (ffmpeg)."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_VIDEO_EXT = frozenset({".mp4", ".mov", ".webm", ".mkv"})


def _escape_concat_path(p: str) -> str:
    return p.replace("'", "'\\''")


def _natural_sort_key(path: Path) -> tuple:
    stem = path.stem.lower()
    nums = re.findall(r"\d+", stem)
    if nums:
        return (int(nums[0]), stem)
    return (9999, stem)


def list_stitchable_videos(veo_dir: Path) -> list[Path]:
    """All video files in `veo_dir` (non-recursive), ordered (e.g. video 1, 2, 3)."""
    if not veo_dir.is_dir():
        return []
    out: list[Path] = []
    for p in veo_dir.iterdir():
        if p.is_file() and p.suffix.lower() in _VIDEO_EXT and p.stat().st_size > 100:
            out.append(p)
    out.sort(key=_natural_sort_key)
    return out


def stitch_videos_to_path(sources: list[Path], dest: Path) -> bool:
    """
    Merge clips into `dest`. Tries stream copy first; re-encodes if codecs differ.
    Returns True if dest is a non-trivial MP4.
    """
    if not sources:
        return False
    if not shutil.which("ffmpeg"):
        logger.error("ffmpeg not on PATH; cannot stitch VeoVideos")
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)

    if len(sources) == 1:
        shutil.copy2(sources[0], dest)
        ok = dest.is_file() and dest.stat().st_size > 512
        if ok:
            logger.info("VeoVideos: single file copied to %s", dest)
        return ok

    list_lines: list[str] = []
    for sp in sources:
        ap = sp.resolve()
        list_lines.append(f"file '{_escape_concat_path(str(ap))}'")
    list_text = "\n".join(list_lines) + "\n"

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".txt",
        delete=False,
        encoding="utf-8",
    ) as tf:
        tf.write(list_text)
        list_path = tf.name

    try:
        cmd_copy = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_path,
            "-c",
            "copy",
            str(dest),
        ]
        r = subprocess.run(cmd_copy, capture_output=True, timeout=600)
        if r.returncode == 0 and dest.is_file() and dest.stat().st_size > 512:
            logger.info(
                "VeoVideos: stitched %d clips with -c copy -> %s",
                len(sources),
                dest,
            )
            return True

        logger.info(
            "VeoVideos: stream copy failed (%s), re-encoding for seamless concat",
            (r.stderr or b"")[:200].decode("utf-8", errors="replace"),
        )
        cmd_re = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_path,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(dest),
        ]
        r2 = subprocess.run(cmd_re, capture_output=True, timeout=900)
        if r2.returncode != 0:
            logger.warning(
                "VeoVideos ffmpeg re-encode failed: %s",
                (r2.stderr or b"")[:1200].decode("utf-8", errors="replace"),
            )
            return False
        ok = dest.is_file() and dest.stat().st_size > 512
        if ok:
            logger.info(
                "VeoVideos: stitched %d clips (re-encoded) -> %s",
                len(sources),
                dest,
            )
        return ok
    finally:
        try:
            Path(list_path).unlink(missing_ok=True)
        except OSError:
            pass
