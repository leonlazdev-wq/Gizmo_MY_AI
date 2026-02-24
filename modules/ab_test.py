"""Prompt A/B test helper."""

from __future__ import annotations

import time


def run_ab_test(prompt_a: str, prompt_b: str, message: str) -> dict[str, str | float]:
    """Run simple side-by-side prompt variants with timing metrics."""
    t0 = time.perf_counter()
    out_a = f"[A] {prompt_a.strip()} :: {message.strip()}"
    ta = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    out_b = f"[B] {prompt_b.strip()} :: {message.strip()}"
    tb = (time.perf_counter() - t1) * 1000

    return {
        "output_a": out_a,
        "output_b": out_b,
        "ms_a": round(ta, 2),
        "ms_b": round(tb, 2),
    }
