"""SSO/OIDC mock-friendly configuration and test helpers."""

from __future__ import annotations

from typing import Dict


def get_redirect_uri(base_url: str = "http://localhost:5005") -> str:
    return f"{base_url}/auth/oidc/callback"


def run_sso_test(provider: str, client_id: str, client_secret: str, mock_mode: bool = True) -> Dict[str, str]:
    if mock_mode:
        return {"ok": "true", "provider": provider, "message": "Mock SSO handshake succeeded."}
    try:
        import authlib  # type: ignore  # lazy optional import

        _ = authlib
        return {"ok": "true", "provider": provider, "message": "Authlib available; configure real provider metadata."}
    except Exception as exc:
        return {"ok": "false", "provider": provider, "message": f"SSO test failed: {exc}"}


# Backward-compatible alias
test_connection = run_sso_test
