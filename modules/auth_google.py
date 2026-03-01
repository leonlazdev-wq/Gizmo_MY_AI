"""
modules/auth_google.py — Google OAuth 2.0 middleware for Gizmo MY-AI.

Provides:
  • GoogleOAuthMiddleware  — WSGI middleware that intercepts requests,
    redirects unauthenticated visitors to Google Sign-In, verifies
    the returned token, and checks the email against the allow-list.
  • get_current_user()     — helper for reading the authenticated email
    from a signed session cookie.

Dependencies (lazy-imported, install instructions printed on first use):
    pip install authlib itsdangerous

No passwords are ever stored.  All secrets come from environment variables:
    GOOGLE_CLIENT_ID     — OAuth 2.0 client ID from Google Cloud Console
    GOOGLE_CLIENT_SECRET — OAuth 2.0 client secret
    GIZMO_SECRET_KEY     — random secret for signing session cookies
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# Lazy dependency imports — show helpful errors, never crash on import
# ---------------------------------------------------------------------------
def _require_authlib():
    try:
        from authlib.integrations.requests_client import OAuth2Session  # noqa: F401
        return True
    except ImportError:
        print(
            "[auth_google] authlib not installed.\n"
            "  Run: pip install authlib requests"
        )
        return False


def _require_itsdangerous():
    try:
        import itsdangerous  # noqa: F401
        return True
    except ImportError:
        print(
            "[auth_google] itsdangerous not installed.\n"
            "  Run: pip install itsdangerous"
        )
        return False


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------
def _load_config() -> dict:
    try:
        import yaml
        cfg_path = Path(__file__).resolve().parents[1] / "config.yaml"
        with open(cfg_path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _allowed_emails_path() -> Path:
    cfg = _load_config()
    rel = cfg.get("auth", {}).get("allowed_emails_file", "user_data/allowed_emails.txt")
    return (Path(__file__).resolve().parents[1] / rel).resolve()


def _session_timeout_seconds() -> int:
    cfg = _load_config()
    hours = cfg.get("auth", {}).get("session_timeout_hours", 24)
    return int(hours) * 3600


# ---------------------------------------------------------------------------
# Allow-list management
# ---------------------------------------------------------------------------
def load_allowed_emails() -> list[str]:
    """Return list of allowed Gmail addresses from the whitelist file."""
    path = _allowed_emails_path()
    if not path.exists():
        return []
    emails: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            emails.append(line.lower())
    return emails


def get_owner_email() -> str:
    """The first non-comment, non-blank line in the allow-list is the owner."""
    emails = load_allowed_emails()
    return emails[0] if emails else ""


def is_allowed(email: str) -> bool:
    return email.lower() in load_allowed_emails()


def is_owner(email: str) -> bool:
    return email.lower() == get_owner_email().lower()


# ---------------------------------------------------------------------------
# Session cookie helpers
# ---------------------------------------------------------------------------
def _get_signer():
    """Return an itsdangerous TimestampSigner (or None if unavailable)."""
    if not _require_itsdangerous():
        return None
    from itsdangerous import TimestampSigner
    secret = os.environ.get("GIZMO_SECRET_KEY", "change-me-in-production")
    return TimestampSigner(secret)


def make_session_cookie(email: str) -> str:
    """Create a signed, time-stamped session token for *email*."""
    signer = _get_signer()
    if signer is None:
        return ""
    payload = json.dumps({"email": email.lower()})
    return signer.sign(payload).decode()


def verify_session_cookie(cookie_value: str) -> Optional[str]:
    """
    Verify the cookie and return the email, or None if invalid/expired.
    """
    signer = _get_signer()
    if signer is None or not cookie_value:
        return None
    try:
        from itsdangerous import SignatureExpired, BadSignature
        raw = signer.unsign(cookie_value, max_age=_session_timeout_seconds())
        data = json.loads(raw)
        return data.get("email")
    except (SignatureExpired, BadSignature, Exception):
        return None


# ---------------------------------------------------------------------------
# Simple current-user helper (for use inside Gradio event handlers)
# ---------------------------------------------------------------------------
def get_current_user(request: Any) -> Optional[str]:
    """
    Extract the authenticated email from a Gradio Request object.

    Returns None if not authenticated (e.g. auth is disabled).
    """
    try:
        cookie_header = (request.headers or {}).get("cookie", "")
        cookies = dict(
            pair.split("=", 1) for pair in cookie_header.split("; ") if "=" in pair
        )
        cookie_value = cookies.get("gizmo_session", "")
        return verify_session_cookie(cookie_value)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Access-Denied HTML response
# ---------------------------------------------------------------------------
_ACCESS_DENIED_HTML = (
    b"<!DOCTYPE html>\n"
    b"<html lang=\"en\"><head><meta charset=\"UTF-8\">\n"
    b"<title>Access Denied - Gizmo MY-AI</title>\n"
    b"<style>\n"
    b"body{background:#0d0f12;color:#e0e0e0;font-family:sans-serif;"
    b"display:flex;align-items:center;justify-content:center;height:100vh;margin:0}\n"
    b".card{background:#1a1d23;border-radius:12px;padding:48px 40px;"
    b"text-align:center;max-width:440px;box-shadow:0 8px 32px rgba(0,0,0,.5)}\n"
    b"h1{color:#6C63FF;font-size:1.8rem;margin-bottom:.5rem}\n"
    b"p{color:#999;line-height:1.6}a{color:#6C63FF;text-decoration:none}\n"
    b"</style></head><body><div class=\"card\">\n"
    b"<h1>Access Denied</h1>\n"
    b"<p>Your Google account is not authorized to access <strong>Gizmo MY-AI</strong>.</p>\n"
    b"<p>Contact the owner to request access, then <a href=\"/logout\">try again</a>.</p>\n"
    b"</div></body></html>"
)


# ---------------------------------------------------------------------------
# WSGI middleware
# ---------------------------------------------------------------------------
GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO  = "https://www.googleapis.com/oauth2/v3/userinfo"
CALLBACK_PATH    = "/oauth/callback"
LOGOUT_PATH      = "/logout"
COOKIE_NAME      = "gizmo_session"


class GoogleOAuthMiddleware:
    """
    Wraps any WSGI app with Google OAuth 2.0 authentication.

    Skip authentication when:
      - GIZMO_AUTH_ENABLED env var is "false"
      - The request already carries a valid session cookie
    """

    def __init__(self, app: Callable, skip_auth: bool = False) -> None:
        self.app = app
        self.skip_auth = skip_auth
        self._client_id     = os.environ.get("GOOGLE_CLIENT_ID", "")
        self._client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        self._public_url    = self._get_public_url()

        if not self.skip_auth:
            if not _require_authlib():
                print("[auth_google] Disabling auth — authlib unavailable.")
                self.skip_auth = True
            if not _require_itsdangerous():
                print("[auth_google] Disabling auth — itsdangerous unavailable.")
                self.skip_auth = True

    @staticmethod
    def _get_public_url() -> str:
        try:
            import yaml
            cfg_path = Path(__file__).resolve().parents[1] / "config.yaml"
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f) or {}
            return cfg.get("server", {}).get("public_url", "https://gizmohub.ai")
        except Exception:
            return "https://gizmohub.ai"

    # ------------------------------------------------------------------
    # WSGI entry point
    # ------------------------------------------------------------------
    def __call__(self, environ: dict, start_response: Callable) -> Any:
        path = environ.get("PATH_INFO", "/")

        # Always allow logout
        if path == LOGOUT_PATH:
            return self._logout(environ, start_response)

        # Always allow OAuth callback
        if path == CALLBACK_PATH:
            return self._handle_callback(environ, start_response)

        # Skip auth if disabled
        if self.skip_auth:
            return self.app(environ, start_response)

        # Check session cookie
        cookie_header = environ.get("HTTP_COOKIE", "")
        cookies = dict(
            p.split("=", 1) for p in cookie_header.split("; ") if "=" in p
        )
        session_token = cookies.get(COOKIE_NAME, "")
        email = verify_session_cookie(session_token)

        if email and is_allowed(email):
            # Inject email into environ for downstream use
            environ["gizmo.user_email"] = email
            return self.app(environ, start_response)

        if email and not is_allowed(email):
            return self._access_denied(start_response)

        # Not authenticated — redirect to Google
        return self._redirect_to_google(start_response)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _redirect_to_google(self, start_response: Callable) -> list[bytes]:
        if not self._client_id:
            print("[auth_google] GOOGLE_CLIENT_ID not set — cannot redirect.")
            start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
            return [b"Auth misconfigured: GOOGLE_CLIENT_ID missing."]

        params = urllib.parse.urlencode({
            "client_id":     self._client_id,
            "redirect_uri":  f"{self._public_url}{CALLBACK_PATH}",
            "response_type": "code",
            "scope":         "openid email profile",
            "access_type":   "online",
            "prompt":        "select_account",
        })
        url = f"{GOOGLE_AUTH_URL}?{params}"
        start_response("302 Found", [
            ("Location", url),
            ("Content-Type", "text/html"),
        ])
        return [b"Redirecting to Google Sign-In..."]

    def _handle_callback(self, environ: dict, start_response: Callable) -> list[bytes]:
        """Exchange the OAuth code for an ID token and set a session cookie."""
        try:
            from authlib.integrations.requests_client import OAuth2Session

            qs = environ.get("QUERY_STRING", "")
            params = dict(urllib.parse.parse_qsl(qs))
            code = params.get("code", "")
            if not code:
                start_response("400 Bad Request", [("Content-Type", "text/plain")])
                return [b"Missing OAuth code."]

            redirect_uri = f"{self._public_url}{CALLBACK_PATH}"
            client = OAuth2Session(self._client_id, self._client_secret, redirect_uri=redirect_uri)
            token = client.fetch_token(GOOGLE_TOKEN_URL, code=code)

            # Get user info
            resp = client.get(GOOGLE_USERINFO)
            userinfo = resp.json()
            email = userinfo.get("email", "").lower()

            if not is_allowed(email):
                return self._access_denied(start_response)

            # Set signed session cookie
            cookie_val = make_session_cookie(email)
            headers = [
                ("Location", "/"),
                ("Set-Cookie",
                 f"{COOKIE_NAME}={cookie_val}; Path=/; HttpOnly; SameSite=Lax"),
            ]
            start_response("302 Found", headers)
            return [b"Login successful, redirecting..."]

        except Exception as exc:
            print(f"[auth_google] Callback error: {exc}")
            start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
            return [f"OAuth callback error: {exc}".encode()]

    @staticmethod
    def _access_denied(start_response: Callable) -> list[bytes]:
        start_response("403 Forbidden", [("Content-Type", "text/html; charset=utf-8")])
        return [_ACCESS_DENIED_HTML]

    @staticmethod
    def _logout(environ: dict, start_response: Callable) -> list[bytes]:
        start_response("302 Found", [
            ("Location", "/"),
            (
                "Set-Cookie",
                f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0",
            ),
        ])
        return [b"Logged out."]
