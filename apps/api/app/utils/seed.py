"""Seed script to create demo lessons in the database."""
import asyncio
import logging

from app.db.session import get_async_session_factory, init_db
from app.models.lesson import Lesson, LessonDomain, LessonStylePreset, LessonStatus
from app.models.source_document import (
    SourceDocument,
    SourceDocumentStatus,
    SourceDocumentType,
)

logger = logging.getLogger(__name__)

DEMO_TOPICS = [
    {
        "topic": "Compiler Bottom-Up Parsing",
        "domain": LessonDomain.cs,
        "title": "Compiler Bottom-Up Parsing",
        "summary": (
            "Learn how bottom-up parsers work: shift-reduce operations, LR parse "
            "tables, handle identification, and AST construction."
        ),
        "style": LessonStylePreset.clean_academic,
    },
    {
        "topic": "Deadlock in Operating Systems",
        "domain": LessonDomain.cs,
        "title": "Deadlock in Operating Systems",
        "summary": (
            "Understand deadlock conditions, resource allocation graphs, prevention "
            "strategies, and the Banker's Algorithm."
        ),
        "style": LessonStylePreset.modern_technical,
    },
    {
        "topic": "Rate Limiter System Design",
        "domain": LessonDomain.system_design,
        "title": "Rate Limiter System Design",
        "summary": (
            "Design a rate limiter: token bucket, leaky bucket, sliding window "
            "algorithms, and distributed rate limiting with Redis."
        ),
        "style": LessonStylePreset.cinematic_minimal,
    },
]


async def seed_demo_data() -> None:
    """Create demo source documents and lessons."""
    await init_db()

    factory = get_async_session_factory()
    async with factory() as db:
        for demo in DEMO_TOPICS:
            source_doc = SourceDocument(
                type=SourceDocumentType.topic,
                title=demo["title"],
                status=SourceDocumentStatus.ready,
            )
            db.add(source_doc)
            await db.flush()

            lesson = Lesson(
                source_document_id=source_doc.id,
                input_topic=demo["topic"],
                domain=demo["domain"],
                title=demo["title"],
                summary=demo["summary"],
                style_preset=demo["style"],
                status=LessonStatus.created,
            )
            db.add(lesson)

            logger.info(
                "Seeded demo lesson: %s (id=%s)", demo["title"], lesson.id
            )

        await db.commit()
        logger.info("Demo data seeded successfully!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_demo_data())
