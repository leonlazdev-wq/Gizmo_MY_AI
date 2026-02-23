"""CI trigger helper."""

from __future__ import annotations

from typing import Dict


def trigger_ci(endpoint: str, token: str) -> Dict[str, str]:
    """Trigger CI endpoint with lazy requests import."""
    try:
        import requests  # lazy optional import

        r = requests.post(endpoint, headers={"Authorization": f"Bearer {token}"}, timeout=20)
        return {"ok": str(r.ok).lower(), "status": str(r.status_code), "body": r.text[:500]}
    except Exception as exc:
        return {"ok": "false", "status": "0", "body": str(exc)}
