"""Reusable performance helpers."""

from __future__ import annotations

import functools
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)


def cache_result(ttl_seconds: int = 300):
    """Cache function results for a TTL in seconds."""

    cache: Dict[str, Tuple[Any, float]] = {}

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = str(args) + str(kwargs)
            now = time.time()
            if key in cache:
                result, timestamp = cache[key]
                if now - timestamp < ttl_seconds:
                    logger.debug("cache hit for %s", func.__name__)
                    return result

            result = func(*args, **kwargs)
            cache[key] = (result, now)
            return result

        return wrapper

    return decorator


def async_task(func: Callable):
    """Run a function in a daemon thread and return the thread."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        thread.start()
        return thread

    return wrapper


class PerformanceMonitor:
    """Collect execution-time metrics for wrapped functions."""

    def __init__(self) -> None:
        self.metrics: List[Dict[str, float | str]] = []

    def measure(self, func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start

            self.metrics.append(
                {
                    'function': func.__name__,
                    'duration': duration,
                    'timestamp': time.time(),
                }
            )
            if duration > 1.0:
                logger.warning("%s took %.2fs", func.__name__, duration)
            return result

        return wrapper

    def get_stats(self):
        if not self.metrics:
            return {}

        durations = [float(m['duration']) for m in self.metrics]
        return {
            'count': len(self.metrics),
            'total_time': sum(durations),
            'avg_time': sum(durations) / len(durations),
            'max_time': max(durations),
            'min_time': min(durations),
        }
