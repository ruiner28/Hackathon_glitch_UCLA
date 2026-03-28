"""Image provider using Imagen 4 via google-genai SDK for high-quality diagram generation."""

import base64
import logging

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.providers.base import ImageProvider

logger = logging.getLogger(__name__)

IMAGE_MODEL = "imagen-4.0-generate-001"


class NanoBananaImageProvider(ImageProvider):
    """Generates images using Imagen 4 (Nano Banana Pro)."""

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
            f"Premium reference-grade technical diagram: clear hierarchy, labeled arrows, "
            f"consistent iconography, high contrast, generous whitespace, crisp vector-like edges, "
            f"readable typography, no blurry text, no watermarks, no photorealistic faces."
        )

        logger.info("Imagen4: generating image, prompt=%s", prompt[:100])

        try:
            response = self.client.models.generate_images(
                model=IMAGE_MODEL,
                prompt=enhanced_prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                ),
            )

            if response.generated_images and len(response.generated_images) > 0:
                image = response.generated_images[0].image
                image_bytes = image.image_bytes
                if isinstance(image_bytes, str):
                    image_bytes = base64.b64decode(image_bytes)
                logger.info(
                    "Imagen4: generated image (%.1f KB)",
                    len(image_bytes) / 1024,
                )
                return image_bytes

            logger.warning("Imagen4: no images in response, trying Gemini native fallback")
            return await self._gemini_native_fallback(enhanced_prompt)

        except Exception as e:
            logger.error("Imagen4: generation failed: %s, trying Gemini native fallback", e)
            try:
                return await self._gemini_native_fallback(enhanced_prompt)
            except Exception as e2:
                logger.error("Gemini native fallback also failed: %s", e2)
                return self._fallback_image()

    async def _gemini_native_fallback(self, prompt: str) -> bytes:
        """Fall back to Gemini native image generation if Imagen 4 fails."""
        response = self.client.models.generate_content(
            model="gemini-2.5-flash-preview-image-generation",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        if not response.candidates:
            return self._fallback_image()

        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type and part.inline_data.mime_type.startswith("image/"):
                image_bytes = part.inline_data.data
                if isinstance(image_bytes, str):
                    image_bytes = base64.b64decode(image_bytes)
                return image_bytes

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
