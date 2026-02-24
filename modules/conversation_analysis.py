"""Conversation intelligence helpers."""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List


def summarize_chat(messages: List[str], max_sentences: int = 5) -> str:
    text = " ".join(messages).strip()
    if not text:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:max(1, max_sentences)])


def extract_topics(messages: List[str], top_k: int = 8) -> List[str]:
    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_-]{3,}\b", " ".join(messages).lower())
    stop = {"this", "that", "with", "from", "have", "will", "your", "about", "please", "could", "should", "there"}
    freq = Counter([w for w in words if w not in stop])
    return [w for w, _ in freq.most_common(max(1, top_k))]


def extract_tasks(messages: List[str]) -> List[Dict]:
    tasks = []
    patterns = [r"\b(todo|task|next step|need to|must|deadline)\b"]
    for msg in messages:
        if any(re.search(p, msg.lower()) for p in patterns):
            tasks.append({"text": msg.strip(), "status": "open"})
    return tasks
