"""Google Slides integration backend for Gizmo."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


def _missing_deps_error() -> str:
    return (
        "Google API dependencies not installed. Run:\n"
        "pip install google-api-python-client google-auth google-auth-httplib2 google-auth-oauthlib"
    )


def _extract_presentation_id(url_or_id: str) -> str:
    """Extract presentation ID from a URL or return the ID directly."""
    url_or_id = (url_or_id or "").strip()
    match = re.search(r'/presentation/d/([a-zA-Z0-9_-]+)', url_or_id)
    if match:
        return match.group(1)
    return url_or_id


def _build_slides_service(credentials_path: str):
    """Build and return a Google Slides service client."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        return None, _missing_deps_error()

    try:
        scopes = [
            "https://www.googleapis.com/auth/presentations",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=scopes
        )
        service = build("slides", "v1", credentials=creds)
        return service, None
    except Exception as exc:
        return None, f"❌ Failed to build Slides service: {exc}"


# Module-level state for the active presentation
_state: Dict = {
    "credentials_path": "",
    "presentation_id": "",
    "presentation_title": "",
    "slide_count": 0,
}


def connect_presentation(presentation_id_or_url: str, credentials_path: str) -> Tuple[str, Dict]:
    """Connect to a Google Slides presentation and return status + metadata."""
    pres_id = _extract_presentation_id(presentation_id_or_url)
    if not pres_id:
        return "❌ Please provide a valid presentation URL or ID.", {}

    if not credentials_path or not credentials_path.strip():
        return "❌ Please provide the path to your service account credentials JSON file.", {}

    service, error = _build_slides_service(credentials_path.strip())
    if error:
        return error, {}

    try:
        presentation = service.presentations().get(presentationId=pres_id).execute()
    except Exception as exc:
        return f"❌ Could not access presentation: {exc}", {}

    slides = presentation.get("slides", [])
    title = presentation.get("title", "Untitled")
    _state["credentials_path"] = credentials_path.strip()
    _state["presentation_id"] = pres_id
    _state["presentation_title"] = title
    _state["slide_count"] = len(slides)

    info = {
        "presentation_id": pres_id,
        "title": title,
        "slide_count": len(slides),
    }
    return f"✅ Connected to '{title}' ({len(slides)} slides).", info


def get_slides_info() -> Tuple[str, List[Dict]]:
    """Return metadata for all slides in the connected presentation."""
    if not _state["presentation_id"]:
        return "❌ Not connected. Connect to a presentation first.", []

    service, error = _build_slides_service(_state["credentials_path"])
    if error:
        return error, []

    try:
        presentation = service.presentations().get(
            presentationId=_state["presentation_id"]
        ).execute()
    except Exception as exc:
        return f"❌ Could not fetch slides: {exc}", []

    slides = presentation.get("slides", [])
    result = []
    for i, slide in enumerate(slides):
        element_count = len(slide.get("pageElements", []))
        result.append({
            "index": i,
            "slide_number": i + 1,
            "object_id": slide.get("objectId", ""),
            "element_count": element_count,
        })
    return f"✅ Found {len(result)} slides.", result


def get_slide_content(slide_index: int) -> Tuple[str, List[Dict]]:
    """Return text/element content of a specific slide (0-based index)."""
    if not _state["presentation_id"]:
        return "❌ Not connected.", []

    service, error = _build_slides_service(_state["credentials_path"])
    if error:
        return error, []

    try:
        presentation = service.presentations().get(
            presentationId=_state["presentation_id"]
        ).execute()
    except Exception as exc:
        return f"❌ Could not fetch slide content: {exc}", []

    slides = presentation.get("slides", [])
    if slide_index < 0 or slide_index >= len(slides):
        return f"❌ Slide index {slide_index} out of range (0-{len(slides)-1}).", []

    slide = slides[slide_index]
    elements = []
    for el in slide.get("pageElements", []):
        obj_id = el.get("objectId", "")
        shape = el.get("shape", {})
        text_content = ""
        if shape:
            text_elements = shape.get("text", {}).get("textElements", [])
            for te in text_elements:
                text_run = te.get("textRun", {})
                if text_run.get("content"):
                    text_content += text_run["content"]
        elements.append({"object_id": obj_id, "text": text_content.strip()})

    return f"✅ Slide {slide_index + 1}: {len(elements)} element(s).", elements


def add_text_to_slide(
    slide_index: int,
    text: str,
    position: Optional[Dict] = None,
) -> str:
    """Add a text box to a slide. position dict: {x, y, width, height} in PT."""
    if not _state["presentation_id"]:
        return "❌ Not connected."
    if not (text or "").strip():
        return "❌ Text cannot be empty."

    service, error = _build_slides_service(_state["credentials_path"])
    if error:
        return error

    try:
        presentation = service.presentations().get(
            presentationId=_state["presentation_id"]
        ).execute()
    except Exception as exc:
        return f"❌ Could not fetch presentation: {exc}"

    slides = presentation.get("slides", [])
    if slide_index < 0 or slide_index >= len(slides):
        return f"❌ Slide index {slide_index} out of range."

    slide_id = slides[slide_index]["objectId"]
    pos = position or {"x": 100, "y": 100, "width": 400, "height": 80}
    import uuid
    text_box_id = f"gizmo_text_{uuid.uuid4().hex[:10]}"

    requests = [
        {
            "createShape": {
                "objectId": text_box_id,
                "shapeType": "TEXT_BOX",
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": {
                        "height": {"magnitude": pos.get("height", 80), "unit": "PT"},
                        "width": {"magnitude": pos.get("width", 400), "unit": "PT"},
                    },
                    "transform": {
                        "scaleX": 1, "scaleY": 1,
                        "translateX": pos.get("x", 100),
                        "translateY": pos.get("y", 100),
                        "unit": "PT",
                    },
                },
            }
        },
        {
            "insertText": {
                "objectId": text_box_id,
                "insertionIndex": 0,
                "text": text.strip(),
            }
        },
    ]

    try:
        service.presentations().batchUpdate(
            presentationId=_state["presentation_id"],
            body={"requests": requests},
        ).execute()
    except Exception as exc:
        return f"❌ Failed to add text: {exc}"

    return f"✅ Text added to slide {slide_index + 1}."


def add_image_to_slide(
    slide_index: int,
    image_url: str,
    position: Optional[Dict] = None,
) -> str:
    """Add an image to a slide from a URL. position dict: {x, y, width, height} in PT."""
    if not _state["presentation_id"]:
        return "❌ Not connected."
    if not (image_url or "").strip():
        return "❌ Image URL cannot be empty."

    service, error = _build_slides_service(_state["credentials_path"])
    if error:
        return error

    try:
        presentation = service.presentations().get(
            presentationId=_state["presentation_id"]
        ).execute()
    except Exception as exc:
        return f"❌ Could not fetch presentation: {exc}"

    slides = presentation.get("slides", [])
    if slide_index < 0 or slide_index >= len(slides):
        return f"❌ Slide index {slide_index} out of range."

    slide_id = slides[slide_index]["objectId"]
    pos = position or {"x": 100, "y": 100, "width": 300, "height": 200}
    import uuid
    img_id = f"gizmo_img_{uuid.uuid4().hex[:10]}"

    requests = [
        {
            "createImage": {
                "objectId": img_id,
                "url": image_url.strip(),
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": {
                        "height": {"magnitude": pos.get("height", 200), "unit": "PT"},
                        "width": {"magnitude": pos.get("width", 300), "unit": "PT"},
                    },
                    "transform": {
                        "scaleX": 1, "scaleY": 1,
                        "translateX": pos.get("x", 100),
                        "translateY": pos.get("y", 100),
                        "unit": "PT",
                    },
                },
            }
        }
    ]

    try:
        service.presentations().batchUpdate(
            presentationId=_state["presentation_id"],
            body={"requests": requests},
        ).execute()
    except Exception as exc:
        return f"❌ Failed to add image: {exc}"

    return f"✅ Image added to slide {slide_index + 1}."


def change_slide_background(slide_index: int, color_or_image: str) -> str:
    """Change the background of a slide.

    color_or_image: hex color like '#ff0000' or an image URL starting with 'http'.
    """
    if not _state["presentation_id"]:
        return "❌ Not connected."

    service, error = _build_slides_service(_state["credentials_path"])
    if error:
        return error

    try:
        presentation = service.presentations().get(
            presentationId=_state["presentation_id"]
        ).execute()
    except Exception as exc:
        return f"❌ Could not fetch presentation: {exc}"

    slides = presentation.get("slides", [])
    if slide_index < 0 or slide_index >= len(slides):
        return f"❌ Slide index {slide_index} out of range."

    slide_id = slides[slide_index]["objectId"]
    value = (color_or_image or "").strip()

    if value.startswith("http"):
        bg_fill = {"stretchedPictureFill": {"contentUrl": value}}
        fields = "pageBackgroundFill.stretchedPictureFill"
    else:
        hex_val = value.lstrip("#")
        if len(hex_val) != 6:
            return "❌ Provide a valid hex color (e.g. #4285f4) or image URL."
        rgb = {
            "red": int(hex_val[0:2], 16) / 255,
            "green": int(hex_val[2:4], 16) / 255,
            "blue": int(hex_val[4:6], 16) / 255,
        }
        bg_fill = {"solidFill": {"color": {"rgbColor": rgb}, "alpha": 1}}
        fields = "pageBackgroundFill.solidFill"

    requests = [
        {
            "updatePageProperties": {
                "objectId": slide_id,
                "pageProperties": {"pageBackgroundFill": bg_fill},
                "fields": fields,
            }
        }
    ]

    try:
        service.presentations().batchUpdate(
            presentationId=_state["presentation_id"],
            body={"requests": requests},
        ).execute()
    except Exception as exc:
        return f"❌ Failed to change background: {exc}"

    return f"✅ Background updated on slide {slide_index + 1}."


def export_slide_as_image(slide_index: int) -> Tuple[str, Optional[str]]:
    """Export a slide as a PNG thumbnail using the Drive API export.

    Returns (status_message, image_path_or_none).
    """
    if not _state["presentation_id"]:
        return "❌ Not connected.", None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        return _missing_deps_error(), None

    try:
        scopes = [
            "https://www.googleapis.com/auth/presentations",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = service_account.Credentials.from_service_account_file(
            _state["credentials_path"], scopes=scopes
        )
        slides_service = build("slides", "v1", credentials=creds)
    except Exception as exc:
        return f"❌ Credentials error: {exc}", None

    try:
        presentation = slides_service.presentations().get(
            presentationId=_state["presentation_id"]
        ).execute()
    except Exception as exc:
        return f"❌ Could not fetch presentation: {exc}", None

    slides = presentation.get("slides", [])
    if slide_index < 0 or slide_index >= len(slides):
        return f"❌ Slide index {slide_index} out of range.", None

    slide_id = slides[slide_index]["objectId"]

    try:
        response = slides_service.presentations().pages().getThumbnail(
            presentationId=_state["presentation_id"],
            pageObjectId=slide_id,
            thumbnailProperties_mimeType="PNG",
            thumbnailProperties_thumbnailSize="LARGE",
        ).execute()
        thumbnail_url = response.get("contentUrl", "")
        if not thumbnail_url:
            return "❌ No thumbnail URL returned.", None

        import requests as _requests
        import tempfile
        import os
        resp = _requests.get(thumbnail_url, timeout=30)
        resp.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png", prefix=f"slide_{slide_index+1}_")
        tmp.write(resp.content)
        tmp.close()
        return f"✅ Slide {slide_index + 1} exported as PNG.", tmp.name
    except Exception as exc:
        return f"❌ Export failed: {exc}", None


def get_current_state() -> Dict:
    """Return current connection state."""
    return dict(_state)
