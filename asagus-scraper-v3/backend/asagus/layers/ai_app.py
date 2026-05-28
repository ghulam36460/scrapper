from __future__ import annotations

from asagus.llm.providers import LLMClient
from asagus.models import SearchResult


class AIApplicationLayer:
    """RAG/ReAct facade for natural language business intelligence."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client

    async def summarize_results(self, query: str, results: list[SearchResult]) -> str:
        if not results:
            return "No matching businesses were found."
        if not self.llm_client:
            top = results[0].record
            return f"Top match: {top.name or top.email or top.phone} with score {results[0].score}."
        compact = [
            {
                "name": item.record.name,
                "city": item.record.city,
                "category": item.record.category,
                "email": item.record.email,
                "whatsapp": item.record.whatsapp,
                "score": item.score,
            }
            for item in results[:10]
        ]
        return await self.llm_client.summarize(query, compact)
