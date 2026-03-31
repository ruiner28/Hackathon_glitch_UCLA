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
        parts = []
        for f in fragments:
            prefix = f"[{f.get('kind', 'text')}]"
            if f.get("academic_section"):
                prefix = f"[{f.get('kind', 'text')}:{f['academic_section']}]"
            parts.append(f"{prefix} {f['text']}")
        source_text = "\n\n".join(parts)

        logger.info(
            "ExtractionService: extracting concepts from %d fragments, domain=%s",
            len(fragments), domain,
        )

        raw = await self.llm.extract_concepts(source_text, domain)

        nodes = raw.get("nodes", raw.get("concepts", []))
        edges = raw.get("edges", [])

        title = raw.get("title", domain)
        if title == domain and "Topic:" in source_text:
            idx = source_text.index("Topic:") + 6
            rest = source_text[idx:].split(".")[0].strip()
            if rest:
                title = rest
        if title == domain and "about:" in source_text.lower():
            lower = source_text.lower()
            key = "about:"
            pos = lower.index(key) + len(key)
            tail = source_text[pos:].lstrip(" :\t")
            topic_part = tail.split(".")[0].strip()
            if topic_part:
                title = topic_part

        result = {
            "title": title,
            "difficulty_level": raw.get("difficulty_level", "intermediate"),
            "concept_graph": {"nodes": nodes, "edges": edges},
            "prerequisites": raw.get("prerequisites", []),
            "misconceptions": raw.get("misconceptions", []),
            "key_examples": raw.get("key_examples", []),
        }

        if raw.get("is_paper"):
            result["is_paper"] = True
            result["paper_sections"] = raw.get("paper_sections", {})

        return result
