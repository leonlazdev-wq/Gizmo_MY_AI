"""Google Sheets integration backend for Gizmo."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


def _missing_deps_error() -> str:
    return (
        "Google API dependencies not installed. Run:\n"
        "pip install google-api-python-client google-auth google-auth-httplib2 google-auth-oauthlib"
    )


def _extract_sheet_id(url_or_id: str) -> str:
    """Extract spreadsheet ID from a URL or return the ID directly."""
    url_or_id = (url_or_id or "").strip()
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url_or_id)
    if match:
        return match.group(1)
    return url_or_id


def _build_sheets_service(credentials_path: str):
    """Build and return a Google Sheets API v4 service client."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        return None, _missing_deps_error()

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=scopes
        )
        service = build("sheets", "v4", credentials=creds)
        return service, None
    except Exception as exc:
        return None, f"❌ Failed to build Sheets service: {exc}"


# Module-level state for the active spreadsheet
_state: Dict = {
    "credentials_path": "",
    "sheet_id": "",
    "sheet_title": "",
    "sheet_names": [],
}


def _call_ai(prompt: str):
    """Call the AI model with the given prompt. Returns (output, error)."""
    try:
        from modules import shared
        if shared.model is None:
            return None, "❌ No AI model loaded. Please load a model first."
        state = shared.settings.copy()
        state['max_new_tokens'] = 1024
        from modules.text_generation import generate_reply
        output = ""
        for chunk in generate_reply(prompt, state, stopping_strings=[], is_chat=False):
            if isinstance(chunk, str):
                output = chunk
            elif isinstance(chunk, (list, tuple)) and len(chunk) > 0:
                output = chunk[0] if isinstance(chunk[0], str) else str(chunk[0])
        return output.strip(), None
    except Exception as exc:
        return None, f"❌ AI error: {exc}"


def connect_spreadsheet(sheet_id_or_url: str, credentials_path: str) -> Tuple[str, Dict]:
    """Connect to a Google Spreadsheet, fetch title and sheet names."""
    sheet_id = _extract_sheet_id(sheet_id_or_url)
    if not sheet_id:
        return "❌ Please provide a valid spreadsheet URL or ID.", {}

    if not credentials_path or not credentials_path.strip():
        return "❌ Please provide the path to your service account credentials JSON file.", {}

    service, error = _build_sheets_service(credentials_path.strip())
    if error:
        return error, {}

    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    except Exception as exc:
        return f"❌ Could not access spreadsheet: {exc}", {}

    title = spreadsheet.get("properties", {}).get("title", "Untitled")
    sheets = spreadsheet.get("sheets", [])
    sheet_names = [s.get("properties", {}).get("title", "") for s in sheets]

    _state["credentials_path"] = credentials_path.strip()
    _state["sheet_id"] = sheet_id
    _state["sheet_title"] = title
    _state["sheet_names"] = sheet_names

    info = {
        "title": title,
        "sheet_names": sheet_names,
    }
    return f"✅ Connected to '{title}' ({len(sheet_names)} sheet(s)).", info


def get_sheet_names(
    sheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> Tuple[str, List[str]]:
    """Return the names of all sheets in the spreadsheet."""
    sheet_id = sheet_id or _state.get("sheet_id")
    if not sheet_id:
        return "❌ No spreadsheet connected. Call connect_spreadsheet first.", []

    credentials_path = credentials_path or _state.get("credentials_path", "")
    service, error = _build_sheets_service(credentials_path)
    if error:
        return error, []

    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        sheets = spreadsheet.get("sheets", [])
        names = [s.get("properties", {}).get("title", "") for s in sheets]
        return f"✅ Found {len(names)} sheet(s).", names
    except Exception as exc:
        return f"❌ Could not fetch sheet names: {exc}", []


def read_range(
    range_str: str,
    sheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> Tuple[str, List[List]]:
    """Read data from a range like 'Sheet1!A1:D10'."""
    sheet_id = sheet_id or _state.get("sheet_id")
    if not sheet_id:
        return "❌ No spreadsheet connected. Call connect_spreadsheet first.", []

    credentials_path = credentials_path or _state.get("credentials_path", "")
    service, error = _build_sheets_service(credentials_path)
    if error:
        return error, []

    try:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=sheet_id, range=range_str)
            .execute()
        )
        values = result.get("values", [])
        return f"✅ Read {len(values)} row(s) from '{range_str}'.", values
    except Exception as exc:
        return f"❌ Could not read range '{range_str}': {exc}", []


def write_range(
    range_str: str,
    values: List[List],
    sheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> str:
    """Write a 2D list of values to the specified range."""
    sheet_id = sheet_id or _state.get("sheet_id")
    if not sheet_id:
        return "❌ No spreadsheet connected. Call connect_spreadsheet first."

    credentials_path = credentials_path or _state.get("credentials_path", "")
    service, error = _build_sheets_service(credentials_path)
    if error:
        return error

    try:
        body = {"values": values}
        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=sheet_id,
                range=range_str,
                valueInputOption="USER_ENTERED",
                body=body,
            )
            .execute()
        )
        updated = result.get("updatedCells", 0)
        return f"✅ Wrote {updated} cell(s) to '{range_str}'."
    except Exception as exc:
        return f"❌ Could not write to range '{range_str}': {exc}"


def read_all_data(
    sheet_name: str,
    sheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> Tuple[str, List[List]]:
    """Read the entire contents of a sheet."""
    return read_range(sheet_name, sheet_id, credentials_path)


def analyze_data(
    sheet_name: str,
    sheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> Tuple[str, str]:
    """Use AI to analyze the data in a sheet."""
    msg, data = read_all_data(sheet_name, sheet_id, credentials_path)
    if not data:
        return msg, ""

    # Convert data to readable text
    rows_text = "\n".join(["\t".join([str(cell) for cell in row]) for row in data[:50]])
    prompt = (
        f"Analyze the following spreadsheet data from sheet '{sheet_name}'. "
        "Identify trends, patterns, anomalies, and provide key insights:\n\n"
        + rows_text
    )
    output, error = _call_ai(prompt)
    if error:
        return error, ""
    return f"✅ Data analysis complete for '{sheet_name}'.", output


def suggest_formula(
    description: str,
    sheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> Tuple[str, str]:
    """Use AI to suggest a Google Sheets formula from a natural language description."""
    prompt = (
        "Generate a Google Sheets formula for the following task. "
        "Return only the formula (starting with =) with no extra explanation:\n\n"
        + description
    )
    output, error = _call_ai(prompt)
    if error:
        return error, ""
    # Extract just the formula if surrounded by extra text
    lines = [line.strip() for line in output.splitlines() if line.strip().startswith("=")]
    formula = lines[0] if lines else output.strip()
    return f"✅ Suggested formula generated.", formula


def get_sheet_metadata(
    sheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> Tuple[str, Dict]:
    """Return metadata: title, sheet_count."""
    sheet_id = sheet_id or _state.get("sheet_id")
    if not sheet_id:
        return "❌ No spreadsheet connected. Call connect_spreadsheet first.", {}

    credentials_path = credentials_path or _state.get("credentials_path", "")
    service, error = _build_sheets_service(credentials_path)
    if error:
        return error, {}

    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        title = spreadsheet.get("properties", {}).get("title", "Unknown")
        sheets = spreadsheet.get("sheets", [])
        meta = {
            "title": title,
            "sheet_count": len(sheets),
        }
        return f"✅ Fetched metadata for '{title}'.", meta
    except Exception as exc:
        return f"❌ Could not fetch metadata: {exc}", {}


def get_current_state() -> Dict:
    """Return the current module state."""
    return dict(_state)
