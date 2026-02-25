"""Unified Memory Manager that delegates to both memory backends."""
from __future__ import annotations

from typing import Dict, List


class MemoryManager:
    """Unified interface for both semantic and factual memory systems."""

    def get_full_context(self, query: str = "", top_k_semantic: int = 5) -> str:
        """Get combined memory context from both systems for prompt injection."""
        from modules import chat_memory, memory

        factual = chat_memory.get_memory_context()
        semantic = memory.format_memory_context(query, top_k=top_k_semantic)

        parts = [p for p in (factual, semantic) if p]
        return "\n".join(parts)

    def search_all(self, query: str, top_k: int = 10) -> List[Dict]:
        """Search across both memory backends."""
        from modules import chat_memory, memory

        semantic_results = memory.retrieve_memory(query, top_k=top_k)

        factual_memories = chat_memory._load_memories()
        query_lower = query.lower()
        factual_results = [
            {
                "id": None,
                "text": m["fact"],
                "score": 1.0 if query_lower in m["fact"].lower() else 0.0,
                "source": "chat_memory",
                "importance": 0.0,
                "timestamp": m.get("created", ""),
                "memory_type": m.get("category", "other"),
            }
            for m in factual_memories
            if not query or query_lower in m["fact"].lower()
        ]

        combined = semantic_results + factual_results
        combined.sort(key=lambda x: x["score"], reverse=True)
        return combined[:top_k]

    def get_stats(self) -> Dict:
        """Get combined stats from both memory systems."""
        from modules import chat_memory, memory

        semantic_items = memory._load_all()
        factual_stats = chat_memory.get_memory_stats()

        return {
            "semantic_count": len(semantic_items),
            "factual_summary": factual_stats,
        }
