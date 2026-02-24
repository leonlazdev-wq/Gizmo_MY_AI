"""Analytics aggregation helpers."""

from __future__ import annotations

from statistics import mean


def compute_kpis(latencies_ms: list[int], failure_count: int, total_requests: int) -> dict[str, float]:
    """Compute KPI metrics."""
    avg_latency = mean(latencies_ms) if latencies_ms else 0.0
    failure_rate = (failure_count / total_requests * 100.0) if total_requests else 0.0
    return {
        "requests": float(total_requests),
        "avg_latency_ms": float(round(avg_latency, 2)),
        "failure_rate_pct": float(round(failure_rate, 2)),
    }


def synthetic_metrics(request_count: int = 50) -> dict[str, list[int]]:
    """Generate synthetic metric series for dashboard tests."""
    reqs = [max(1, request_count // 5 + i) for i in range(10)]
    lats = [220 + (i * 7) for i in range(10)]
    return {"requests": reqs, "latencies": lats}
