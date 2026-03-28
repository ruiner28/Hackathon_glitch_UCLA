import pytest
from unittest.mock import AsyncMock

from app.services.ingestion.service import IngestionService


class TestIngestionService:
    def setup_method(self):
        self.storage = AsyncMock()
        self.service = IngestionService(self.storage)

    @pytest.mark.asyncio
    async def test_process_topic(self):
        fragments = await self.service.process_topic("Compiler Bottom-Up Parsing", "cs")
        assert len(fragments) >= 1
        assert fragments[0]["kind"] == "synthetic"
        assert (
            "Compiler" in fragments[0]["text"]
            or "parsing" in fragments[0]["text"].lower()
        )
        assert fragments[0]["ref_key"] == "synthetic_topic"

    @pytest.mark.asyncio
    async def test_extract_fragments_topic(self):
        fragments = await self.service.extract_fragments(
            source_type="topic",
            file_path=None,
            topic="Deadlock in OS",
            domain="cs",
            doc_id="test-doc-id",
        )
        assert len(fragments) >= 1
        assert any(f["kind"] == "synthetic" for f in fragments)

    @pytest.mark.asyncio
    async def test_extract_fragments_invalid_type(self):
        """Non-existent file for pdf/pptx should handle gracefully."""
        fragments = await self.service.extract_fragments(
            source_type="pdf",
            file_path="/nonexistent/file.pdf",
            topic=None,
            domain="cs",
            doc_id="test-doc-id",
        )
        assert isinstance(fragments, list)
        assert fragments == []
