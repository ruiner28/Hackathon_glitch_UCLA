from unittest.mock import patch

from app.services.pipeline import LessonPipeline


class TestLessonPipeline:
    def test_pipeline_creates_all_services(self):
        """Verify pipeline initializes all service components."""
        with (
            patch("app.services.pipeline.get_storage_provider"),
            patch("app.services.pipeline.get_llm_provider"),
            patch("app.services.pipeline.get_tts_provider"),
            patch("app.services.pipeline.get_music_provider"),
            patch("app.services.pipeline.get_image_provider"),
            patch("app.services.pipeline.get_video_provider"),
        ):
            pipeline = LessonPipeline()

            assert pipeline.ingestion is not None
            assert pipeline.extraction is not None
            assert pipeline.planning is not None
            assert pipeline.compilation is not None
            assert pipeline.rendering is not None
            assert pipeline.narration is not None
            assert pipeline.music is not None
            assert pipeline.assembly is not None
            assert pipeline.evaluation is not None
