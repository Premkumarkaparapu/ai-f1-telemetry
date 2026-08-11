"""Knowledge Agent — queries the RAG service for F1 knowledge.

Receives a user question, searches the knowledge base,
and returns relevant chunks with source citations.
"""

from backend.app.core.logging import get_logger
from backend.app.services.rag_service import get_rag_service

logger = get_logger(__name__)


class KnowledgeAgent:
    """Retrieves relevant F1 knowledge from the RAG index."""

    def __init__(self):
        self.rag = get_rag_service()

    def execute(
        self,
        query: str,
        top_k: int = 3,
        category: str | None = None,
    ) -> dict:
        """Search the knowledge base and return results.

        Returns:
            {
                "knowledge_found": bool,
                "chunks": [
                    {
                        "content": str,
                        "source": str,
                        "category": str,
                        "section": str,
                        "score": float,
                    },
                    ...
                ],
                "sources": ["file1.md", ...],
            }
        """
        results = self.rag.search(
            query, top_k=top_k, category=category,
        )

        sources = list(set(
            r["source"] for r in results
        ))

        logger.info(
            "KnowledgeAgent: %d chunks found for '%s'",
            len(results), query[:50],
        )

        return {
            "knowledge_found": len(results) > 0,
            "chunks": results,
            "sources": sources,
        }
