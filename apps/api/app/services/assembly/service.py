import json
import logging
import uuid

from app.providers.base import StorageProvider

logger = logging.getLogger(__name__)


class AssemblyService:
    def __init__(self, storage: StorageProvider):
        self.storage = storage

    async def assemble_video(
        self,
        lesson_id: str,
        scene_assets: list[dict],
        narration_urls: list[str],
        music_url: str | None,
        style: str,
    ) -> dict:
        """
        Assemble final video from scene assets and audio.

        For MVP, creates a manifest JSON describing the assembly. In production,
        this would call FFmpeg or a cloud video pipeline to stitch everything
        together.

        Returns {video_url, thumbnail_url, duration_sec}.
        """
        total_duration = sum(
            sa.get("duration_sec", 30) for sa in scene_assets
        )
        assembly_id = str(uuid.uuid4())

        manifest = {
            "assembly_id": assembly_id,
            "lesson_id": lesson_id,
            "style": style,
            "total_duration_sec": total_duration,
            "scene_count": len(scene_assets),
            "scenes": [
                {
                    "scene_id": sa.get("scene_id", ""),
                    "title": sa.get("title", ""),
                    "duration_sec": sa.get("duration_sec", 30),
                    "render_url": sa.get("render_url", ""),
                }
                for sa in scene_assets
            ],
            "narration_tracks": narration_urls,
            "music_url": music_url,
            "status": "assembled",
        }

        manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
        video_path = f"output/{lesson_id}/{assembly_id}/video_manifest.json"
        video_url = await self.storage.put_file(
            video_path, manifest_bytes, "application/json"
        )

        thumbnail_url = await self.generate_thumbnail(
            lesson_id,
            scene_assets[0].get("render_url", "") if scene_assets else "",
        )

        logger.info(
            "AssemblyService: assembled lesson %s — %d scenes, %.1fs total -> %s",
            lesson_id, len(scene_assets), total_duration, video_url,
        )

        return {
            "video_url": video_url,
            "thumbnail_url": thumbnail_url,
            "duration_sec": round(total_duration, 2),
        }

    async def generate_thumbnail(
        self, lesson_id: str, first_scene_asset: str
    ) -> str:
        """
        Generate thumbnail from first scene asset.

        For MVP, creates a placeholder JSON. In production, would extract a
        frame from the first scene video/image.
        """
        thumbnail_manifest = {
            "lesson_id": lesson_id,
            "source_asset": first_scene_asset,
            "status": "placeholder",
        }

        thumb_bytes = json.dumps(thumbnail_manifest, indent=2).encode("utf-8")
        path = f"output/{lesson_id}/thumbnail.json"
        url = await self.storage.put_file(path, thumb_bytes, "application/json")

        logger.info("AssemblyService: thumbnail for lesson %s -> %s", lesson_id, url)
        return url
