"""Backend logic for the Google Calendar Integration feature."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

TOKEN_PATH = Path("user_data/google_token.json")
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Detect Google Colab
_IN_COLAB = "COLAB_JUPYTER_TOKEN" in os.environ or "COLAB_RELEASE_TAG" in os.environ


def _creds_from_token() -> Optional[object]:
    """Load saved credentials from TOKEN_PATH, refresh if needed."""
    try:
        from google.oauth2.credentials import Credentials  # type: ignore
        from google.auth.transport.requests import Request  # type: ignore
    except ImportError:
        return None

    if not TOKEN_PATH.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    return creds if creds and creds.valid else None


class GoogleCalendarManager:
    """Manages Google Calendar API interactions."""

    def __init__(self):
        self.service = None
        self.connected = False

    def authorize(self, credentials_path: str) -> tuple[bool, str]:
        """Run the OAuth2 flow using *credentials_path* (downloaded JSON).

        In Colab, returns the auth URL for manual pasting.
        Otherwise launches a local server.
        Returns (success: bool, message: str).
        """
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
            from googleapiclient.discovery import build  # type: ignore
        except ImportError:
            return False, (
                "Required packages not installed. Run:\n"
                "pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            )

        credentials_path = (credentials_path or "").strip()
        if not credentials_path or not Path(credentials_path).exists():
            return False, "credentials.json file not found at the specified path."

        try:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            if _IN_COLAB:
                flow.run_console()
            else:
                flow.run_local_server(port=0)
            creds = flow.credentials
            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_PATH.write_text(creds.to_json())
            self.service = build("calendar", "v3", credentials=creds)
            self.connected = True
            return True, "✅ Authorization successful."
        except Exception as exc:
            return False, f"❌ Authorization failed: {exc}"

    def connect_from_saved(self) -> tuple[bool, str]:
        """Attempt to connect using a previously saved token."""
        try:
            from googleapiclient.discovery import build  # type: ignore
        except ImportError:
            return False, (
                "Required packages not installed. Run:\n"
                "pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            )

        creds = _creds_from_token()
        if not creds:
            return False, "No saved token found. Please authorize first."
        try:
            self.service = build("calendar", "v3", credentials=creds)
            self.connected = True
            return True, "✅ Reconnected using saved token."
        except Exception as exc:
            return False, f"❌ Failed to connect: {exc}"

    def get_events(self, start_date: str, end_date: str) -> tuple[list, str]:
        """Fetch events between *start_date* and *end_date* (YYYY-MM-DD).

        Returns (events: list[dict], message: str).
        """
        if not self.connected or not self.service:
            return [], "Not connected. Please authorize first."
        try:
            time_min = f"{start_date}T00:00:00Z"
            time_max = f"{end_date}T23:59:59Z"
            result = (
                self.service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=100,
                )
                .execute()
            )
            events = []
            for item in result.get("items", []):
                start = item["start"].get("dateTime", item["start"].get("date", ""))
                end_t = item["end"].get("dateTime", item["end"].get("date", ""))
                events.append({
                    "id": item["id"],
                    "title": item.get("summary", "(No title)"),
                    "start": start,
                    "end": end_t,
                    "calendar": item.get("organizer", {}).get("displayName", "primary"),
                    "description": item.get("description", ""),
                })
            return events, f"Found {len(events)} event(s)."
        except Exception as exc:
            return [], f"Error fetching events: {exc}"

    def create_event(
        self,
        title: str,
        start: str,
        end: str,
        description: str = "",
        reminder_minutes: int = 30,
    ) -> tuple[dict, str]:
        """Create a calendar event.

        *start* and *end* should be ISO 8601 strings (e.g. '2025-06-01T10:00:00').
        Returns (event: dict, message: str).
        """
        if not self.connected or not self.service:
            return {}, "Not connected. Please authorize first."
        try:
            body = {
                "summary": title,
                "description": description,
                "start": {"dateTime": start, "timeZone": "UTC"},
                "end": {"dateTime": end, "timeZone": "UTC"},
                "reminders": {
                    "useDefault": False,
                    "overrides": [{"method": "popup", "minutes": reminder_minutes}],
                },
            }
            event = self.service.events().insert(calendarId="primary", body=body).execute()
            return event, f"✅ Event created: {event.get('htmlLink', '')}"
        except Exception as exc:
            return {}, f"❌ Error creating event: {exc}"

    def delete_event(self, event_id: str) -> tuple[bool, str]:
        """Delete the event with *event_id* from the primary calendar."""
        if not self.connected or not self.service:
            return False, "Not connected. Please authorize first."
        try:
            self.service.events().delete(calendarId="primary", eventId=event_id).execute()
            return True, "✅ Event deleted."
        except Exception as exc:
            return False, f"❌ Error deleting event: {exc}"

    def find_free_slots(self, date: str, min_duration_hours: float = 1.0) -> tuple[list, str]:
        """Find free time slots on *date* (YYYY-MM-DD) of at least *min_duration_hours*.

        Returns (slots: list[dict], message: str).
        Each slot: {"start": str, "end": str, "duration_hours": float}.
        """
        events, msg = self.get_events(date, date)
        if not events:
            return [{"start": f"{date}T08:00:00", "end": f"{date}T22:00:00", "duration_hours": 14.0}], "No events found; whole day is free."

        # Build occupied intervals
        occupied = []
        for ev in events:
            try:
                s = datetime.fromisoformat(ev["start"].replace("Z", "+00:00"))
                e = datetime.fromisoformat(ev["end"].replace("Z", "+00:00"))
                occupied.append((s, e))
            except Exception:
                pass
        occupied.sort()

        # Check gaps in a 08:00–22:00 window
        day_start = datetime.fromisoformat(f"{date}T08:00:00")
        day_end = datetime.fromisoformat(f"{date}T22:00:00")
        free_slots = []
        cursor = day_start
        for s, e in occupied:
            if s > cursor:
                gap_hours = (s - cursor).total_seconds() / 3600
                if gap_hours >= min_duration_hours:
                    free_slots.append({
                        "start": cursor.isoformat(),
                        "end": s.isoformat(),
                        "duration_hours": round(gap_hours, 2),
                    })
            cursor = max(cursor, e)
        if cursor < day_end:
            gap_hours = (day_end - cursor).total_seconds() / 3600
            if gap_hours >= min_duration_hours:
                free_slots.append({
                    "start": cursor.isoformat(),
                    "end": day_end.isoformat(),
                    "duration_hours": round(gap_hours, 2),
                })

        return free_slots, f"Found {len(free_slots)} free slot(s) on {date}."
