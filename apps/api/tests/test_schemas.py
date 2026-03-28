import pytest

from app.schemas.common import (
    ConceptEdge,
    ConceptGraph,
    ConceptNode,
    EvaluationReportSchema,
    LessonPlanSchema,
    LessonPlanSection,
    SceneSpec,
)
from app.schemas.requests import LessonCreate, SceneUpdate, TopicInput
from app.schemas.responses import QuizQuestion, QuizResponse


class TestConceptGraph:
    def test_valid_concept_node(self):
        node = ConceptNode(
            id="parsing",
            label="Parsing",
            description="Process of analyzing symbols",
            importance=0.9,
            prerequisites=[],
        )
        assert node.id == "parsing"
        assert node.importance == 0.9

    def test_valid_concept_graph(self):
        graph = ConceptGraph(
            nodes=[
                ConceptNode(
                    id="a",
                    label="A",
                    description="Desc A",
                    importance=1.0,
                    prerequisites=[],
                ),
                ConceptNode(
                    id="b",
                    label="B",
                    description="Desc B",
                    importance=0.8,
                    prerequisites=["a"],
                ),
            ],
            edges=[ConceptEdge(source="a", target="b", relation_type="requires")],
        )
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1

    def test_importance_bounds(self):
        with pytest.raises(Exception):
            ConceptNode(
                id="x",
                label="X",
                description="D",
                importance=1.5,
                prerequisites=[],
            )


class TestSceneSpec:
    def test_valid_scene_spec(self):
        spec = SceneSpec(
            scene_id="s1",
            title="Test Scene",
            learning_objective="Test objective",
            source_refs=[],
            scene_type="deterministic_animation",
            render_strategy="remotion",
            duration_sec=30.0,
            narration_text="Test narration",
            on_screen_text=["Point 1"],
            visual_elements=[],
            animation_beats=[],
            asset_requests=[],
            music_mood="neutral",
            validation_notes="",
        )
        assert spec.scene_id == "s1"
        assert spec.duration_sec == 30.0

    def test_scene_spec_with_veo(self):
        spec = SceneSpec(
            scene_id="s2",
            title="Veo Scene",
            learning_objective="Visual hook",
            source_refs=[],
            scene_type="veo_cinematic",
            render_strategy="veo",
            duration_sec=15.0,
            narration_text="",
            on_screen_text=[],
            visual_elements=[],
            animation_beats=[],
            asset_requests=[],
            veo_prompt="Cinematic opening with code flowing",
            image_prompt="Dark background with glowing code",
            music_mood="dramatic",
            validation_notes="",
        )
        assert spec.veo_prompt is not None


class TestRequests:
    def test_topic_input(self):
        ti = TopicInput(topic="Compiler Bottom-Up Parsing")
        assert ti.topic == "Compiler Bottom-Up Parsing"
        assert ti.music_enabled is True

    def test_lesson_create(self):
        lc = LessonCreate(topic="TCP Handshake", domain="cs")
        assert lc.topic == "TCP Handshake"

    def test_scene_update(self):
        su = SceneUpdate(narration_text="Updated narration")
        assert su.narration_text == "Updated narration"
        assert su.on_screen_text is None


class TestQuiz:
    def test_quiz_question(self):
        q = QuizQuestion(
            question="What is parsing?",
            options=["A", "B", "C", "D"],
            correct_index=0,
            explanation="A is correct",
        )
        assert q.correct_index == 0

    def test_quiz_response(self):
        qr = QuizResponse(
            questions=[
                QuizQuestion(
                    question="Q1",
                    options=["A", "B"],
                    correct_index=0,
                    explanation="E1",
                ),
                QuizQuestion(
                    question="Q2",
                    options=["A", "B", "C"],
                    correct_index=2,
                    explanation="E2",
                ),
            ]
        )
        assert len(qr.questions) == 2
