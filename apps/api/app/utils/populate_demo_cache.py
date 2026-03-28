"""
Export a completed lesson into the demo disk cache for fast reloads.

Usage (from apps/api with venv active):

  python -m app.utils.populate_demo_cache --lesson-id <uuid> --slug rate_limiter

Slugs: rate_limiter | os_deadlock | bottom_up_parsing

Requires: lesson has completed asset generation (scenes + images + audio) and
ideally a final render (optional — run render first for output/lesson.mp4).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import shutil
from pathlib import Path
from uuid import UUID
from urllib.parse import unquote

from sqlalchemy import select
from app.db.session import get_async_session_factory, init_db
from app.models.lesson import Lesson
from app.models.scene import Scene
from app.models.scene_asset import AssetType, SceneAsset
from app.services.demo_cache import demo_cache_root

logger = logging.getLogger(__name__)


def _file_url_to_path(url: str) -> Path | None:
    if not url or not url.startswith("file://"):
        return None
    return Path(unquote(url[7:]))


async def export_lesson_to_cache(lesson_id: str, slug: str) -> None:
    await init_db()
    factory = get_async_session_factory()
    async with factory() as db:
        result = await db.execute(select(Lesson).where(Lesson.id == UUID(lesson_id)))
        lesson = result.scalar_one_or_none()
        if not lesson:
            raise SystemExit(f"Lesson not found: {lesson_id}")

        scenes_result = await db.execute(
            select(Scene)
            .where(Scene.lesson_id == lesson.id)
            .order_by(Scene.scene_order)
        )
        scenes = list(scenes_result.scalars().all())

        assets_result = await db.execute(
            select(SceneAsset).where(SceneAsset.scene_id.in_([s.id for s in scenes]))
        )
        assets_by_scene: dict[str, list[SceneAsset]] = {}
        for a in assets_result.scalars().all():
            assets_by_scene.setdefault(str(a.scene_id), []).append(a)

        root = demo_cache_root() / slug
        (root / "scenes").mkdir(parents=True, exist_ok=True)
        (root / "output").mkdir(parents=True, exist_ok=True)

        narration_texts: list[str] = []
        for idx, scene in enumerate(scenes):
            narration_texts.append(scene.narration_text or "")
            scene_dir = root / "scenes" / str(idx)
            scene_dir.mkdir(parents=True, exist_ok=True)
            for a in assets_by_scene.get(str(scene.id), []):
                p = _file_url_to_path(a.storage_url)
                if not p or not p.is_file():
                    logger.warning("Missing file for asset %s", a.id)
                    continue
                if a.asset_type == AssetType.audio:
                    shutil.copy2(p, scene_dir / "narration.wav")
                elif a.asset_type == AssetType.image:
                    shutil.copy2(p, scene_dir / "image.png")
                elif a.asset_type == AssetType.video:
                    shutil.copy2(p, scene_dir / "video.mp4")

        manifest = {
            "version": 1,
            "slug": slug,
            "scene_count": len(scenes),
            "narration_texts": narration_texts,
            "lesson_title": lesson.title,
            "input_topic": lesson.input_topic,
        }
        (root / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        # Optional: final lesson output
        out_base = Path("storage") / "output" / str(lesson.id)
        mp4 = out_base / "lesson.mp4"
        srt = out_base / "subtitles.srt"
        if mp4.is_file():
            shutil.copy2(mp4, root / "output" / "lesson.mp4")
            logger.info("Copied final lesson.mp4")
        else:
            logger.warning(
                "No lesson.mp4 at %s — run render-preview first for cached final video",
                mp4,
            )
        if srt.is_file():
            shutil.copy2(srt, root / "output" / "subtitles.srt")

        logger.info(
            "Demo cache written to %s (%d scenes, manifest ok)",
            root,
            len(scenes),
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser(description="Export lesson to demo disk cache")
    p.add_argument("--lesson-id", required=True, help="Completed lesson UUID")
    p.add_argument(
        "--slug",
        required=True,
        choices=("rate_limiter", "os_deadlock", "bottom_up_parsing"),
        help="Cache directory name",
    )
    args = p.parse_args()
    asyncio.run(export_lesson_to_cache(args.lesson_id, args.slug))


if __name__ == "__main__":
    main()
