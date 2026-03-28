import logging

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class ExtractionService:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def extract(self, fragments: list[dict], domain: str) -> dict:
        """
        Combine fragments into source text, call LLM to extract concepts.

        Returns structured concept data with:
        - title, difficulty_level
        - concept_graph (nodes + edges)
        - prerequisites, misconceptions, key_examples
        """
        source_text = "\n\n".join(
            f"[{f.get('kind', 'text')}] {f['text']}" for f in fragments
        )

        logger.info(
            "ExtractionService: extracting concepts from %d fragments, domain=%s",
            len(fragments), domain,
        )

        raw = await self.llm.extract_concepts(source_text, domain)

        nodes = raw.get("nodes", raw.get("concepts", []))
        edges = raw.get("edges", [])

        return {
            "title": raw.get("title", domain),
            "difficulty_level": raw.get("difficulty_level", "intermediate"),
            "concept_graph": {"nodes": nodes, "edges": edges},
            "prerequisites": raw.get("prerequisites", []),
            "misconceptions": raw.get("misconceptions", []),
            "key_examples": raw.get("key_examples", []),
        }
