"""Mock-friendly SSO/OAuth setup helpers."""

from __future__ import annotations


def test_connection(provider: str, client_id: str, client_secret: str, mock_mode: bool = True) -> dict[str, str]:
    """Test SSO configuration with mock or lightweight validation."""
    provider_name = (provider or "").strip().lower()
    if provider_name not in {"google", "microsoft", "okta"}:
        return {"status": "error", "message": "Unsupported provider"}
    if not client_id or not client_secret:
        return {"status": "error", "message": "Missing client credentials"}
    if mock_mode:
        return {"status": "ok", "message": f"Mocked {provider.title()} OIDC test succeeded"}
    return {"status": "error", "message": "Real OIDC flow not enabled in this environment"}


# Prevent pytest from collecting helper as test
test_connection.__test__ = False
