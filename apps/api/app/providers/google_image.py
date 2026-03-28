"""Image provider using Nano Banana (gemini-2.5-flash-preview-image-generation) via google-genai SDK."""

import base64
import logging

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.providers.base import ImageProvider
from app.services.visual_system.nano_banana_prompt import enrich_image_prompt_from_scene_spec

logger = logging.getLogger(__name__)

IMAGE_MODEL = "gemini-2.5-flash-image"


class NanoBananaImageProvider(ImageProvider):
    """Generates images using Nano Banana image generation."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info("NanoBananaImageProvider: initialized with model=%s", IMAGE_MODEL)

    async def generate_image(
        self, prompt: str, style: str, width: int, height: int
    ) -> bytes:
        enhanced_prompt = (
            f"{prompt}. "
            f"Style: {style.replace('_', ' ')}. "
            f"Premium educational diagram: deep slate or soft white field, high contrast, "
            f"generous whitespace, crisp vector-like edges, no blurry text, no watermarks."
        )

        logger.info("NanoBanana: generating image, prompt=%s", prompt[:100])

        try:
            response = self.client.models.generate_content(
                model=IMAGE_MODEL,
                contents=enhanced_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )

            if not response.candidates:
                logger.warning("NanoBanana: empty candidates list")
                return self._fallback_image()

            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type and part.inline_data.mime_type.startswith("image/"):
                    image_bytes = part.inline_data.data
                    if isinstance(image_bytes, str):
                        image_bytes = base64.b64decode(image_bytes)
                    logger.info(
                        "NanoBanana: generated image (%.1f KB)",
                        len(image_bytes) / 1024,
                    )
                    return image_bytes

            logger.warning("NanoBanana: no image in response parts, falling back to placeholder")
            return self._fallback_image()

        except Exception as e:
            logger.error("NanoBanana: generation failed: %s", e)
            return self._fallback_image()

    async def generate_keyframe(self, scene_spec: dict) -> bytes:
        title = scene_spec.get("title", "")
        narration = scene_spec.get("narration_text", "")
        visual_elements = scene_spec.get("visual_elements", [])

        prompt_parts = [f"Educational diagram for: {title}"]
        if visual_elements:
            descs = [v.get("description", "") for v in visual_elements[:3]]
            prompt_parts.append(f"Elements: {', '.join(descs)}")
        if narration:
            prompt_parts.append(f"Context: {narration[:150]}")

        return await self.generate_image(
            ". ".join(prompt_parts),
            "clean_academic",
            1920,
            1080,
        )

    def _fallback_image(self) -> bytes:
        from app.providers.mock_image import _minimal_png
        return _minimal_png(width=1, height=1, rgba=(100, 149, 237, 255))
