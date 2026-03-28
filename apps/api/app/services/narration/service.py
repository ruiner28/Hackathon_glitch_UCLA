import logging

from app.providers.base import LLMProvider, StorageProvider, TTSProvider

logger = logging.getLogger(__name__)

CHARS_PER_SECOND = 15  # ~150 WPM at ~5 chars/word


class NarrationService:
    def __init__(
        self,
        llm: LLMProvider,
        tts: TTSProvider,
        storage: StorageProvider,
    ):
        self.llm = llm
        self.tts = tts
        self.storage = storage

    async def generate_narration(self, scene_spec: dict) -> dict:
        """
        Generate narration for a single scene.

        If narration_text already exists in the scene spec, uses it directly.
        Otherwise, calls LLM to write narration from the scene spec.
        Then synthesises audio via TTS and stores it.

        Returns {narration_text, audio_url, duration_sec}.
        """
        narration_text = scene_spec.get("narration_text", "").strip()
        scene_id = scene_spec.get("scene_id", "unknown")

        if not narration_text:
            logger.info(
                "NarrationService: generating narration text for scene %s via LLM",
                scene_id,
            )
            narration_text = await self.llm.write_narration(scene_spec)

        audio_bytes = await self.tts.synthesize(narration_text)

        audio_path = f"audio/narrations/{scene_id}.wav"
        audio_url = await self.storage.put_file(
            audio_path, audio_bytes, "audio/wav"
        )

        duration_sec = max(1.0, len(narration_text) / CHARS_PER_SECOND)

        logger.info(
            "NarrationService: narration for scene %s — %d chars, ~%.1fs, stored at %s",
            scene_id, len(narration_text), duration_sec, audio_url,
        )

        return {
            "scene_id": scene_id,
            "narration_text": narration_text,
            "audio_url": audio_url,
            "duration_sec": round(duration_sec, 2),
        }

    async def generate_all_narrations(
        self, scenes: list[dict], lesson_id: str
    ) -> list[dict]:
        """Generate narrations for all scenes in order."""
        logger.info(
            "NarrationService: generating narrations for %d scenes, lesson=%s",
            len(scenes), lesson_id,
        )
        results: list[dict] = []
        for scene_spec in scenes:
            result = await self.generate_narration(scene_spec)
            results.append(result)
        return results

    async def generate_transcript(self, scenes: list[dict]) -> dict:
        """
        Generate full transcript from scene narrations.

        Returns {
            full_text: str,
            scenes: [{scene_id, text, start_sec, end_sec}]
        }
        """
        scene_entries: list[dict] = []
        full_text_parts: list[str] = []
        cumulative_sec = 0.0

        for scene_spec in scenes:
            text = scene_spec.get("narration_text", "")
            duration = scene_spec.get("duration_sec", 30.0)
            scene_id = scene_spec.get("scene_id", scene_spec.get("id", ""))

            full_text_parts.append(text)
            scene_entries.append({
                "scene_id": str(scene_id),
                "text": text,
                "start_sec": round(cumulative_sec, 2),
                "end_sec": round(cumulative_sec + duration, 2),
            })
            cumulative_sec += duration

        return {
            "full_text": "\n\n".join(full_text_parts),
            "scenes": scene_entries,
        }
