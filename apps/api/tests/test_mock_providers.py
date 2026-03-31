import pytest

from app.providers.mock_image import MockImageProvider
from app.providers.mock_llm import MockLLMProvider
from app.providers.mock_music import MockMusicProvider
from app.providers.mock_tts import MockTTSProvider


class TestMockLLMProvider:
    def setup_method(self):
        self.llm = MockLLMProvider()

    @pytest.mark.asyncio
    async def test_extract_concepts_parsing(self):
        result = await self.llm.extract_concepts("Compiler Bottom-Up Parsing", "cs")
        assert "nodes" in result
        assert "edges" in result
        assert len(result["nodes"]) >= 5

    @pytest.mark.asyncio
    async def test_extract_concepts_deadlock(self):
        result = await self.llm.extract_concepts("Deadlock in Operating Systems", "cs")
        assert "nodes" in result
        assert any(n["id"] == "deadlock" for n in result["nodes"])

    @pytest.mark.asyncio
    async def test_extract_concepts_rate_limiter(self):
        result = await self.llm.extract_concepts(
            "Rate Limiter System Design", "system_design"
        )
        assert "nodes" in result
        assert any(n["id"] == "token_bucket" for n in result["nodes"])

    @pytest.mark.asyncio
    async def test_extract_concepts_generic(self):
        result = await self.llm.extract_concepts("Some random unknown topic", "cs")
        assert "nodes" in result

    @pytest.mark.asyncio
    async def test_create_lesson_plan_parsing(self):
        concepts = await self.llm.extract_concepts("Bottom-Up Parsing", "cs")
        plan = await self.llm.create_lesson_plan(
            concepts, "bottom-up parsing", "clean_academic"
        )
        assert "lesson_title" in plan
        assert "sections" in plan
        assert len(plan["sections"]) >= 5

    @pytest.mark.asyncio
    async def test_create_lesson_plan_rate_limiter_when_domain_is_cs(self):
        """Homepage prefills topic but form often sends domain=cs; plan must still use curated rate-limit content."""
        source = (
            "Create a comprehensive educational lesson about: Rate Limiter. "
            "Domain: cs. Cover all key concepts."
        )
        raw = await self.llm.extract_concepts(source, "cs")
        concepts = {
            "title": "cs",
            "concept_graph": {"nodes": raw["nodes"], "edges": raw["edges"]},
        }
        plan = await self.llm.create_lesson_plan(concepts, "cs", "clean_academic")
        assert plan.get("lesson_title") == "Rate Limiter System Design"
        assert len(plan.get("sections", [])) >= 5

    @pytest.mark.asyncio
    async def test_compile_scenes(self):
        plan = await self.llm.create_lesson_plan({}, "deadlock", "clean_academic")
        scenes = await self.llm.compile_scenes(plan, "cs")
        assert len(scenes) >= 5
        for scene in scenes:
            assert "scene_id" in scene
            assert "title" in scene
            assert "narration_text" in scene
            assert "duration_sec" in scene

    @pytest.mark.asyncio
    async def test_generate_quiz_parsing(self):
        quiz = await self.llm.generate_quiz({"lesson_title": "Bottom-Up Parsing"}, [])
        assert len(quiz) >= 3
        for q in quiz:
            assert "question" in q
            assert "options" in q
            assert "correct_answer" in q

    @pytest.mark.asyncio
    async def test_evaluate_lesson(self):
        result = await self.llm.evaluate_lesson({"title": "Test"})
        assert "overall_score" in result
        assert result["overall_score"] > 0


class TestMockImageProvider:
    @pytest.mark.asyncio
    async def test_generate_image(self):
        provider = MockImageProvider()
        data = await provider.generate_image("test prompt", "clean_academic", 1920, 1080)
        assert isinstance(data, bytes)
        assert len(data) > 0
        assert data[:4] == b"\x89PNG"


class TestMockTTSProvider:
    @pytest.mark.asyncio
    async def test_synthesize(self):
        provider = MockTTSProvider()
        audio = await provider.synthesize("Hello world, this is a test narration.")
        assert isinstance(audio, bytes)
        assert len(audio) > 0
        assert audio[:4] == b"RIFF"


class TestMockMusicProvider:
    @pytest.mark.asyncio
    async def test_generate_track(self):
        provider = MockMusicProvider()
        audio = await provider.generate_track("focused", 30.0)
        assert isinstance(audio, bytes)
        assert audio[:4] == b"RIFF"
