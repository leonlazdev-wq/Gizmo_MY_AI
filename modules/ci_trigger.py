"""CI trigger client."""

from __future__ import annotations


def trigger_ci(endpoint: str, token: str) -> dict[str, str]:
    """Trigger CI in mock-safe mode.

    Lazy-imports requests so environments without requests still load module.
    """
    if not endpoint or not token:
        return {"status": "error", "message": "Missing endpoint/token"}

    try:
        import requests  # lazy import
    except Exception:
        return {"status": "error", "message": "requests not available"}

    try:
        response = requests.post(endpoint, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        return {"status": "ok" if response.ok else "error", "message": f"HTTP {response.status_code}"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
