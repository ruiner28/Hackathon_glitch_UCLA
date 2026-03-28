from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def extract_concepts(self, source_text: str, domain: str) -> dict:
        """Extract structured concepts from source material."""

    @abstractmethod
    async def create_lesson_plan(self, concepts: dict, domain: str, style: str) -> dict:
        """Create pedagogical lesson plan."""

    @abstractmethod
    async def compile_scenes(self, lesson_plan: dict, domain: str) -> list[dict]:
        """Compile lesson plan into scene specifications."""

    @abstractmethod
    async def write_narration(self, scene_spec: dict) -> str:
        """Write narration script for a scene."""

    @abstractmethod
    async def generate_quiz(self, lesson_plan: dict, scenes: list[dict]) -> list[dict]:
        """Generate quiz questions."""

    @abstractmethod
    async def evaluate_lesson(self, lesson_data: dict) -> dict:
        """Evaluate lesson quality."""


class ImageProvider(ABC):
    @abstractmethod
    async def generate_image(self, prompt: str, style: str, width: int, height: int) -> bytes:
        """Generate an image from prompt."""

    @abstractmethod
    async def generate_keyframe(self, scene_spec: dict) -> bytes:
        """Generate a keyframe image for video generation."""


class VideoProvider(ABC):
    @abstractmethod
    async def generate_from_text(self, prompt: str, duration_sec: float) -> bytes:
        """Generate video from text prompt."""

    @abstractmethod
    async def generate_from_image(self, image_data: bytes, prompt: str, duration_sec: float) -> bytes:
        """Generate video from image + prompt."""


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(
        self, text: str, voice: str = "en-US-Neural2-D", speaking_rate: float = 1.0
    ) -> bytes:
        """Synthesize speech from text, return audio bytes."""


class MusicProvider(ABC):
    @abstractmethod
    async def generate_track(self, mood: str, duration_sec: float) -> bytes:
        """Generate background music track."""


class StorageProvider(ABC):
    @abstractmethod
    async def put_file(self, path: str, data: bytes, content_type: str) -> str:
        """Store file, return URL/path."""

    @abstractmethod
    async def get_file(self, path: str) -> bytes:
        """Retrieve file bytes."""

    @abstractmethod
    async def get_signed_url(self, path: str, expiry_sec: int = 3600) -> str:
        """Get signed/accessible URL."""

    @abstractmethod
    async def delete_file(self, path: str) -> None:
        """Delete file."""
