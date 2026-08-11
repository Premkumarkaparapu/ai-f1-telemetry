"""RAG service — retrieval-augmented generation for F1 knowledge.

Loads markdown documents from the knowledge/ directory, chunks them,
generates embeddings using the gemini-embedding-2 model, and performs
semantic cosine-similarity search.

Uses a local disk cache (knowledge_embeddings.pkl) to prevent repeated
API calls and token costs.
"""

import re
import pickle
import time
import numpy as np
from typing import Optional

from backend.app.core.ai_config import KNOWLEDGE_DIR, GEMINI_API_KEY
from backend.app.core.config import PROCESSED_DIR
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class KnowledgeChunk:
    """A single chunk of knowledge with metadata and embedding."""

    __slots__ = (
        "content", "source", "category", "section", "score", "embedding"
    )

    def __init__(
        self,
        content: str,
        source: str,
        category: str,
        section: str,
        embedding: Optional[list[float]] = None
    ):
        self.content = content
        self.source = source
        self.category = category
        self.section = section
        self.embedding = embedding
        self.score = 0.0


class RAGService:
    """Vector embedding-based semantic retrieval over the F1 knowledge base."""

    def __init__(self):
        self._chunks: list[KnowledgeChunk] = []
        self._loaded = False
        self._cache_path = PROCESSED_DIR / "knowledge_embeddings.pkl"

    def _get_gemini_client(self):
        """Initialize the Gemini client using the standard google-genai SDK."""
        from google import genai
        return genai.Client(api_key=GEMINI_API_KEY)

    def _load_knowledge(self) -> None:
        """Walk KNOWLEDGE_DIR, chunk all files, and generate/load embeddings."""
        if not KNOWLEDGE_DIR.exists():
            logger.warning("Knowledge dir not found: %s", KNOWLEDGE_DIR)
            self._loaded = True
            return

        md_files = list(KNOWLEDGE_DIR.rglob("*.md"))
        raw_chunks = []

        for fpath in md_files:
            try:
                text = fpath.read_text(encoding="utf-8")
            except Exception as exc:
                logger.warning("Cannot read %s: %s", fpath, exc)
                continue

            rel = fpath.relative_to(KNOWLEDGE_DIR)
            category = rel.parts[0] if len(rel.parts) > 1 else "general"

            chunks = self._chunk_markdown(
                text,
                source=fpath.name,
                category=category,
            )
            raw_chunks.extend(chunks)

        logger.info("RAG: identified %d document chunks", len(raw_chunks))

        # Check local vector cache
        cached_vectors = {}
        if self._cache_path.exists():
            try:
                logger.info("RAG: loading cached vectors from %s", self._cache_path)
                with open(self._cache_path, "rb") as f:
                    cached_vectors = pickle.load(f)
            except Exception as exc:
                logger.warning("Failed to load vector cache: %s", exc)

        # Build final chunks with embeddings
        self._chunks = []
        client = None
        needs_save = False

        for rc in raw_chunks:
            # Check cache using chunk content hash/string
            cache_key = f"{rc.source}:{rc.section}:{hash(rc.content)}"
            embedding = cached_vectors.get(cache_key)

            if embedding is None:
                # Generate embedding on the fly
                if client is None:
                    client = self._get_gemini_client()

                try:
                    logger.info(
                        "RAG: generating embedding for chunk '%s:%s'",
                        rc.source, rc.section
                    )
                    res = client.models.embed_content(
                        model="gemini-embedding-2",
                        contents=rc.content
                    )
                    embedding = res.embeddings[0].values
                    cached_vectors[cache_key] = embedding
                    needs_save = True
                    # Rate-limiting cooldown to respect 15 RPM free tier limits
                    time.sleep(0.3)
                except Exception as exc:
                    logger.error("Failed to generate embedding for %s: %s", rc.source, exc)
                    # Fallback to zero vector so the app doesn't crash
                    embedding = [0.0] * 3072

            self._chunks.append(
                KnowledgeChunk(
                    content=rc.content,
                    source=rc.source,
                    category=rc.category,
                    section=rc.section,
                    embedding=embedding
                )
            )

        # Save cache if we generated new embeddings
        if needs_save and cached_vectors:
            try:
                PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
                logger.info("RAG: saving vector cache to %s", self._cache_path)
                with open(self._cache_path, "wb") as f:
                    pickle.dump(cached_vectors, f)
            except Exception as exc:
                logger.warning("Failed to save vector cache: %s", exc)

        self._loaded = True

    def _chunk_markdown(
        self,
        text: str,
        source: str,
        category: str,
    ) -> list[KnowledgeChunk]:
        """Split markdown into chunks at ## headings."""
        sections = re.split(r"\n(?=##\s)", text)
        chunks = []

        for section in sections:
            section = section.strip()
            if not section or len(section) < 20:
                continue

            heading_match = re.match(r"^##\s*(.+?)(?:\n|$)", section)
            heading = heading_match.group(1).strip() if heading_match else "Introduction"

            chunks.append(
                KnowledgeChunk(
                    content=section,
                    source=source,
                    category=category,
                    section=heading,
                )
            )

        if not chunks and len(text.strip()) > 20:
            title = re.match(r"^#\s*(.+?)(?:\n|$)", text)
            chunks.append(
                KnowledgeChunk(
                    content=text.strip(),
                    source=source,
                    category=category,
                    section=title.group(1).strip() if title else "Document",
                )
            )

        return chunks

    def search(
        self,
        query: str,
        top_k: int = 3,
        category: Optional[str] = None,
    ) -> list[dict]:
        """Return the top-k most semantically relevant knowledge chunks."""
        if not self._loaded:
            self._load_knowledge()

        if not self._chunks:
            return []

        # Get query embedding
        try:
            client = self._get_gemini_client()
            q_res = client.models.embed_content(
                model="gemini-embedding-2",
                contents=query
            )
            q_vec = np.array(q_res.embeddings[0].values)
        except Exception as exc:
            logger.error("RAG search query embedding failed: %s", exc)
            return []

        # Filter chunks by category if requested
        valid_chunks = self._chunks
        if category:
            valid_chunks = [c for c in valid_chunks if c.category == category]

        if not valid_chunks:
            return []

        # Calculate cosine similarities using NumPy
        results = []
        for chunk in valid_chunks:
            c_vec = np.array(chunk.embedding)
            # Cosine similarity formula
            norm_q = np.linalg.norm(q_vec)
            norm_c = np.linalg.norm(c_vec)
            if norm_q > 0 and norm_c > 0:
                score = float(np.dot(q_vec, c_vec) / (norm_q * norm_c))
            else:
                score = 0.0

            results.append({
                "content": chunk.content,
                "source": chunk.source,
                "category": chunk.category,
                "section": chunk.section,
                "score": round(score, 4),
            })

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get_categories(self) -> list[str]:
        """Return all available knowledge categories."""
        if not self._loaded:
            self._load_knowledge()
        return list(set(c.category for c in self._chunks))


# ── Singleton ─────────────────────────────────────────────────────────

_rag_instance: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Return the singleton RAG service instance."""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGService()
    return _rag_instance
