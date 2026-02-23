"""Small knowledge graph utility."""

from __future__ import annotations

from typing import Dict, List


class KnowledgeGraph:
    def __init__(self):
        self.edges: List[Dict] = []

    def add_relation(self, source: str, relation: str, target: str) -> None:
        self.edges.append({"source": source, "relation": relation, "target": target})

    def query(self, entity: str) -> List[Dict]:
        e = (entity or "").lower()
        return [x for x in self.edges if e in x["source"].lower() or e in x["target"].lower()]


GLOBAL_GRAPH = KnowledgeGraph()
