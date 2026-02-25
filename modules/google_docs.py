"""Google Docs integration backend for Gizmo."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


def _missing_deps_error() -> str:
    return (
        "Google API dependencies not installed. Run:\n"
        "pip install google-api-python-client google-auth google-auth-httplib2 google-auth-oauthlib"
    )


def _extract_doc_id(url_or_id: str) -> str:
    """Extract document ID from a URL or return the ID directly."""
    url_or_id = (url_or_id or "").strip()
    match = re.search(r'/document/d/([a-zA-Z0-9_-]+)', url_or_id)
    if match:
        return match.group(1)
    return url_or_id


def _build_docs_service(credentials_path: str):
    """Build and return a Google Docs API v1 service client."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        return None, _missing_deps_error()

    try:
        scopes = [
            "https://www.googleapis.com/auth/documents",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=scopes
        )
        service = build("docs", "v1", credentials=creds)
        return service, None
    except Exception as exc:
        return None, f"❌ Failed to build Docs service: {exc}"


def _build_drive_service(credentials_path: str):
    """Build and return a Google Drive API v3 service client."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        return None, _missing_deps_error()

    try:
        scopes = [
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=scopes
        )
        service = build("drive", "v3", credentials=creds)
        return service, None
    except Exception as exc:
        return None, f"❌ Failed to build Drive service: {exc}"


# Module-level state for the active document
_state: Dict = {
    "credentials_path": "",
    "doc_id": "",
    "doc_title": "",
    "word_count": 0,
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


def _extract_text_from_doc(document: Dict) -> str:
    """Extract plain text from a Google Docs document response."""
    text_parts: List[str] = []
    body = document.get("body", {})
    for element in body.get("content", []):
        _extract_text_from_element(element, text_parts)
    return "".join(text_parts)


def _extract_text_from_element(element: Dict, parts: List[str]) -> None:
    """Recursively extract text from a structural element."""
    if "paragraph" in element:
        for pe in element["paragraph"].get("elements", []):
            text_run = pe.get("textRun", {})
            parts.append(text_run.get("content", ""))
    elif "table" in element:
        for row in element["table"].get("tableRows", []):
            for cell in row.get("tableCells", []):
                for cell_elem in cell.get("content", []):
                    _extract_text_from_element(cell_elem, parts)
    elif "tableOfContents" in element:
        for toc_elem in element["tableOfContents"].get("content", []):
            _extract_text_from_element(toc_elem, parts)


def connect_document(doc_id_or_url: str, credentials_path: str) -> Tuple[str, Dict]:
    """Connect to a Google Doc, fetch title/word count, update _state."""
    doc_id = _extract_doc_id(doc_id_or_url)
    if not doc_id:
        return "❌ Please provide a valid document URL or ID.", {}

    if not credentials_path or not credentials_path.strip():
        return "❌ Please provide the path to your service account credentials JSON file.", {}

    service, error = _build_docs_service(credentials_path.strip())
    if error:
        return error, {}

    try:
        document = service.documents().get(documentId=doc_id).execute()
    except Exception as exc:
        return f"❌ Could not access document: {exc}", {}

    title = document.get("title", "Untitled")
    text = _extract_text_from_doc(document)
    word_count = len(text.split())

    _state["credentials_path"] = credentials_path.strip()
    _state["doc_id"] = doc_id
    _state["doc_title"] = title
    _state["word_count"] = word_count

    info = {
        "doc_id": doc_id,
        "title": title,
        "word_count": word_count,
    }
    return f"✅ Connected to '{title}' (~{word_count} words).", info


def get_document_content(doc_id: Optional[str] = None) -> Tuple[str, str]:
    """Fetch the full document text."""
    doc_id = doc_id or _state.get("doc_id")
    if not doc_id:
        return "❌ No document connected. Call connect_document first.", ""

    credentials_path = _state.get("credentials_path", "")
    service, error = _build_docs_service(credentials_path)
    if error:
        return error, ""

    try:
        document = service.documents().get(documentId=doc_id).execute()
    except Exception as exc:
        return f"❌ Could not fetch document: {exc}", ""

    text = _extract_text_from_doc(document)
    return f"✅ Fetched document content ({len(text)} characters).", text


def read_section(section_title: str, doc_id: Optional[str] = None) -> Tuple[str, str]:
    """Read a specific section by its heading text."""
    msg, full_text = get_document_content(doc_id)
    if not full_text:
        return msg, ""

    lines = full_text.splitlines()
    section_lines: List[str] = []
    in_section = False

    for line in lines:
        if line.strip().lower() == section_title.strip().lower():
            in_section = True
            continue
        elif in_section and line.strip() and line.strip() != line.lstrip():
            # Heuristic: a new heading-like line ends the section
            break
        if in_section:
            section_lines.append(line)

    if not in_section:
        return f"❌ Section '{section_title}' not found.", ""

    section_text = "\n".join(section_lines).strip()
    return f"✅ Read section '{section_title}'.", section_text


def insert_text(
    text: str,
    position: str = "end",
    doc_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> str:
    """Insert text into the document using batchUpdate."""
    doc_id = doc_id or _state.get("doc_id")
    if not doc_id:
        return "❌ No document connected. Call connect_document first."

    credentials_path = credentials_path or _state.get("credentials_path", "")
    service, error = _build_docs_service(credentials_path)
    if error:
        return error

    try:
        if position == "end":
            document = service.documents().get(documentId=doc_id).execute()
            body_content = document.get("body", {}).get("content", [])
            end_index = body_content[-1].get("endIndex", 1) - 1 if body_content else 1
            insert_index = max(1, end_index)
        else:
            insert_index = int(position)

        requests = [
            {
                "insertText": {
                    "location": {"index": insert_index},
                    "text": text,
                }
            }
        ]
        service.documents().batchUpdate(
            documentId=doc_id, body={"requests": requests}
        ).execute()
        return f"✅ Inserted {len(text)} characters at position '{position}'."
    except Exception as exc:
        return f"❌ Failed to insert text: {exc}"


def replace_text(
    old_text: str,
    new_text: str,
    doc_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> str:
    """Replace all occurrences of old_text with new_text using replaceAllText."""
    doc_id = doc_id or _state.get("doc_id")
    if not doc_id:
        return "❌ No document connected. Call connect_document first."

    credentials_path = credentials_path or _state.get("credentials_path", "")
    service, error = _build_docs_service(credentials_path)
    if error:
        return error

    try:
        requests = [
            {
                "replaceAllText": {
                    "containsText": {"text": old_text, "matchCase": True},
                    "replaceText": new_text,
                }
            }
        ]
        result = service.documents().batchUpdate(
            documentId=doc_id, body={"requests": requests}
        ).execute()
        replies = result.get("replies", [{}])
        occurrences = replies[0].get("replaceAllText", {}).get("occurrencesChanged", 0)
        return f"✅ Replaced {occurrences} occurrence(s) of '{old_text}'."
    except Exception as exc:
        return f"❌ Failed to replace text: {exc}"


def fix_grammar(
    section: Optional[str] = None,
    doc_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> str:
    """Use AI to fix grammar in the document or a specific section."""
    if section:
        text = section
    else:
        msg, text = get_document_content(doc_id)
        if not text:
            return msg

    prompt = (
        "Please fix any grammar, spelling, and punctuation errors in the following text. "
        "Return only the corrected text with no extra commentary:\n\n" + text[:4000]
    )
    output, error = _call_ai(prompt)
    if error:
        return error
    return f"✅ Grammar fix complete.\n\n{output}"


def summarize_document(
    doc_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> Tuple[str, str]:
    """Generate an AI summary of the document."""
    msg, text = get_document_content(doc_id)
    if not text:
        return msg, ""

    prompt = (
        "Please provide a concise summary of the following document. "
        "Highlight the main points and key takeaways:\n\n" + text[:6000]
    )
    output, error = _call_ai(prompt)
    if error:
        return error, ""
    return "✅ Document summarized.", output


def get_document_metadata(
    doc_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> Tuple[str, Dict]:
    """Return metadata: title, word_count, last_modified."""
    doc_id = doc_id or _state.get("doc_id")
    if not doc_id:
        return "❌ No document connected. Call connect_document first.", {}

    credentials_path = credentials_path or _state.get("credentials_path", "")

    drive_service, error = _build_drive_service(credentials_path)
    if error:
        return error, {}

    try:
        file_meta = drive_service.files().get(
            fileId=doc_id, fields="name,modifiedTime,wordCount"
        ).execute()
    except Exception as exc:
        return f"❌ Could not fetch metadata: {exc}", {}

    docs_service, error = _build_docs_service(credentials_path)
    word_count = _state.get("word_count", 0)
    if not error:
        try:
            document = docs_service.documents().get(documentId=doc_id).execute()
            text = _extract_text_from_doc(document)
            word_count = len(text.split())
        except Exception:
            pass

    meta = {
        "title": file_meta.get("name", "Unknown"),
        "word_count": word_count,
        "last_modified": file_meta.get("modifiedTime", "Unknown"),
    }
    return f"✅ Fetched metadata for '{meta['title']}'.", meta


def get_current_state() -> Dict:
    """Return the current module state."""
    return dict(_state)
