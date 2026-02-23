"""Analytics aggregation for admin dashboard."""

from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Dict, List


def compute_kpis(events: List[Dict[str, float]]) -> Dict[str, float]:
    if not events:
        return {"requests": 0, "avg_latency": 0.0, "failure_rate": 0.0}
    requests = len(events)
    avg_latency = mean(e.get("latency", 0.0) for e in events)
    failures = sum(1 for e in events if e.get("status") == "fail")
    return {
        "requests": requests,
        "avg_latency": round(avg_latency, 3),
        "failure_rate": round((failures / requests) * 100.0, 2),
    }


def top_integrations(events: List[Dict[str, str]]) -> Dict[str, int]:
    c = Counter(e.get("integration", "none") for e in events)
    return dict(c)
