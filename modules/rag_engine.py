"""Simple RAG engine for local document ingestion and retrieval."""

from __future__ import annotations

import json
import math
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

RAG_STORE_PATH = Path("user_data/rag_store.json")
_WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)


@dataclass
class Chunk:
    id: str
    doc_name: str
    text: str
    embedding: Dict[str, float]


def _tokenize(text: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "") if len(w) > 1]


def _embed(text: str) -> Dict[str, float]:
    counts: Dict[str, float] = {}
    for token in _tokenize(text):
        counts[token] = counts.get(token, 0.0) + 1.0

    norm = math.sqrt(sum(v * v for v in counts.values())) or 1.0
    return {k: v / norm for k, v in counts.items()}


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def _read_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".py", ".json", ".csv"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            return "\n".join([(p.extract_text() or "") for p in reader.pages])
        except Exception:
            return ""

    if suffix == ".docx":
        try:
            import docx
            doc = docx.Document(str(path))
            return "\n".join([p.text for p in doc.paragraphs])
        except Exception:
            return ""

    return path.read_text(encoding="utf-8", errors="ignore")


def _chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []

    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i + chunk_size])
        i += max(1, chunk_size - overlap)
    return chunks


def _load_chunks() -> List[Chunk]:
    if not RAG_STORE_PATH.exists():
        return []

    raw = json.loads(RAG_STORE_PATH.read_text(encoding="utf-8"))
    return [Chunk(**x) for x in raw]


def _save_chunks(chunks: List[Chunk]) -> None:
    RAG_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAG_STORE_PATH.write_text(json.dumps([c.__dict__ for c in chunks], ensure_ascii=False, indent=2), encoding="utf-8")


def ingest_file(file_path: str) -> int:
    path = Path(file_path)
    if not path.exists():
        return 0

    text = _read_file(path)
    chunk_texts = _chunk_text(text)
    if not chunk_texts:
        return 0

    chunks = _load_chunks()
    chunks = [c for c in chunks if c.doc_name != path.name]

    for chunk_text in chunk_texts:
        chunks.append(Chunk(id=str(uuid.uuid4()), doc_name=path.name, text=chunk_text, embedding=_embed(chunk_text)))

    _save_chunks(chunks)
    return len(chunk_texts)


def list_documents() -> List[str]:
    names = sorted({c.doc_name for c in _load_chunks()})
    return names


def delete_document(doc_name: str) -> int:
    chunks = _load_chunks()
    old_len = len(chunks)
    new = [c for c in chunks if c.doc_name != doc_name]
    _save_chunks(new)
    return old_len - len(new)


def reindex_all() -> int:
    chunks = _load_chunks()
    for c in chunks:
        c.embedding = _embed(c.text)
    _save_chunks(chunks)
    return len(chunks)


def retrieve_context(query: str, top_k: int = 4) -> List[Dict]:
    q = _embed(query)
    scored = []
    for c in _load_chunks():
        scored.append((_cosine(q, c.embedding), c))

    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for score, c in scored[:max(1, int(top_k))]:
        out.append({"doc_name": c.doc_name, "score": round(score, 4), "text": c.text})

    return out


def format_rag_context(query: str, top_k: int = 4) -> str:
    rows = retrieve_context(query, top_k)
    if not rows:
        return ""

    parts = ["Relevant documents:"]
    for r in rows:
        parts.append(f"[{r['doc_name']}] {r['text'][:420]}")
    return "\n\n".join(parts)
