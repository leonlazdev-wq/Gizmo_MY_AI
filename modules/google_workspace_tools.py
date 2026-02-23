import hashlib
 main
from typing import Optional

WIKIMEDIA_SEARCH_API = "https://commons.wikimedia.org/w/api.php"


def _missing_google_client_error() -> str:
    return (
        "Google Workspace dependencies are missing. Install with:\n"
        "pip install google-api-python-client google-auth google-auth-httplib2 google-auth-oauthlib requests"
    )


def _build_services(credentials_path: str):
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        return None, None, _missing_google_client_error()

    scopes = [
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/presentations",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = service_account.Credentials.from_service_account_file(credentials_path, scopes=scopes)
    docs_service = build("docs", "v1", credentials=credentials)
    slides_service = build("slides", "v1", credentials=credentials)
    return docs_service, slides_service, None


def _find_wikimedia_image(query: str) -> str:
    try:
        import requests
    except ImportError:
        return f"https://picsum.photos/seed/{hashlib.md5(query.encode('utf-8')).hexdigest()}/1280/720"

    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrlimit": 1,
        "prop": "imageinfo",
        "iiprop": "url",
    }

    response = requests.get(WIKIMEDIA_SEARCH_API, params=params, timeout=15)
    response.raise_for_status()
    payload = response.json()
    pages = payload.get("query", {}).get("pages", {})

    for page in pages.values():
        image_info = page.get("imageinfo", [])
        if image_info and image_info[0].get("url"):
            return image_info[0]["url"]

    return f"https://picsum.photos/seed/{hashlib.md5(query.encode('utf-8')).hexdigest()}/1280/720"


def _hex_to_rgb_fraction(hex_color: str):
    value = hex_color.lstrip("#")
    if len(value) != 6:
        return None

    return {
        "red": int(value[0:2], 16) / 255,
        "green": int(value[2:4], 16) / 255,
        "blue": int(value[4:6], 16) / 255,
    }


 main
def write_text_to_doc(credentials_path: str, document_id: str, text: str) -> str:
    docs_service, _, error = _build_services(credentials_path)
    if error:
        return error

    if not text.strip():
        return "Nothing to write. Please provide text."

    doc = docs_service.documents().get(documentId=document_id).execute()
    end_index = doc.get("body", {}).get("content", [{}])[-1].get("endIndex", 1)

    docs_service.documents().batchUpdate(
        documentId=document_id,
        body={"requests": [{"insertText": {"location": {"index": max(1, end_index - 1)}, "text": text + "\n"}}]},
    ).execute()

    return "✅ Text added to Google Doc successfully."


def add_image_to_slide(credentials_path: str, presentation_id: str, slide_number: int, image_query: str, alt_text: Optional[str] = None) -> str:
    _, slides_service, error = _build_services(credentials_path)
    if error:
        return error

    if slide_number < 1:
        return "Slide number must be 1 or higher."

    presentation = slides_service.presentations().get(presentationId=presentation_id).execute()
    slides = presentation.get("slides", [])

    if slide_number > len(slides):
        return f"Presentation has {len(slides)} slides. Slide {slide_number} does not exist."

    slide_id = slides[slide_number - 1]["objectId"]
    image_url = _find_wikimedia_image(image_query)

    image_object_id = f"gizmo_img_{uuid.uuid4().hex[:10]}"
    requests = [{
        "createImage": {
            "objectId": image_object_id,
    requests = [{
        "createImage": {
          main
            "url": image_url,
            "elementProperties": {
                "pageObjectId": slide_id,
                "size": {
                    "height": {"magnitude": 220, "unit": "PT"},
                    "width": {"magnitude": 390, "unit": "PT"},
                },
                "transform": {
                    "scaleX": 1,
                    "scaleY": 1,
                    "translateX": 160,
                    "translateY": 120,
                    "unit": "PT",
                },
            },
        }
    }]

    if alt_text and alt_text.strip():
        requests.append(
            {
                "updatePageElementAltText": {
                    "objectId": "{{LAST_CREATED_OBJECT_ID}}",
         main
                    "title": alt_text.strip()[:300],
                    "description": image_query[:1000],
                }
            }
        )

    slides_service.presentations().batchUpdate(
        presentationId=presentation_id,
        body={"requests": requests},
    ).execute()

    return f"✅ Added image for '{image_query}' to slide {slide_number}. Source: {image_url}"


def apply_slide_designer_prompt(credentials_path: str, presentation_id: str, slide_number: int, designer_prompt: str, text_for_slide: str = "", image_query: str = "") -> str:
    _, slides_service, error = _build_services(credentials_path)
    if error:
        return error

    if slide_number < 1:
        return "Slide number must be 1 or higher."

    presentation = slides_service.presentations().get(presentationId=presentation_id).execute()
    slides = presentation.get("slides", [])
    if slide_number > len(slides):
        return f"Presentation has {len(slides)} slides. Slide {slide_number} does not exist."

    slide_id = slides[slide_number - 1]["objectId"]
    prompt = (designer_prompt or "").strip().lower()

    text_value = (text_for_slide or "").strip() or "AI generated lesson text"
    move_down_match = re.search(r"move\s+text\s+(\d+)\s*px\s+down", prompt)
    move_down_px = int(move_down_match.group(1)) if move_down_match else 0
    translate_y = 110 + int(move_down_px * 0.75)

    requests = []
    operations = []

    text_box_id = f"gizmo_text_{uuid.uuid4().hex[:10]}"
    requests.append({
        "createShape": {
            "objectId": text_box_id,
            "shapeType": "TEXT_BOX",
            "elementProperties": {
                "pageObjectId": slide_id,
                "size": {
                    "height": {"magnitude": 120, "unit": "PT"},
                    "width": {"magnitude": 440, "unit": "PT"},
                },
                "transform": {
                    "scaleX": 1,
                    "scaleY": 1,
                    "translateX": 80,
                    "translateY": translate_y,
                    "unit": "PT",
                },
            },
        }
    })
    requests.append({
        "insertText": {
            "objectId": text_box_id,
            "insertionIndex": 0,
            "text": text_value,
        }
    })
    operations.append("created text box")

    hex_color_match = re.search(r"#([0-9a-f]{6})", prompt)
    if "background" in prompt and hex_color_match:
        rgb = _hex_to_rgb_fraction(hex_color_match.group(0))
        if rgb:
            requests.append(
                {
                    "updatePageProperties": {
                        "objectId": slide_id,
                        "pageProperties": {
                            "pageBackgroundFill": {
                                "solidFill": {
                                    "color": {"rgbColor": rgb},
                                    "alpha": 1,
                                }
                            }
                        },
                        "fields": "pageBackgroundFill.solidFill",
                    }
                }
            )
            operations.append(f"set background color to {hex_color_match.group(0)}")

    if image_query.strip() or "add" in prompt and "image" in prompt:
        image_corner = "bottom-right"
        if "top left" in prompt:
            image_corner = "top-left"
        elif "top right" in prompt:
            image_corner = "top-right"
        elif "bottom left" in prompt:
            image_corner = "bottom-left"

        coord_map = {
            "top-left": (35, 35),
            "top-right": (500, 35),
            "bottom-left": (35, 315),
            "bottom-right": (500, 315),
        }
        x, y = coord_map[image_corner]
        image_url = _find_wikimedia_image(image_query.strip() or "presentation illustration")
        img_id = f"gizmo_img_{uuid.uuid4().hex[:10]}"
        requests.append(
            {
                "createImage": {
                    "objectId": img_id,
                    "url": image_url,
                    "elementProperties": {
                        "pageObjectId": slide_id,
                        "size": {
                            "height": {"magnitude": 150, "unit": "PT"},
                            "width": {"magnitude": 200, "unit": "PT"},
                        },
                        "transform": {
                            "scaleX": 1,
                            "scaleY": 1,
                            "translateX": x,
                            "translateY": y,
                            "unit": "PT",
                        },
                    },
                }
            }
        )
        operations.append(f"added image in {image_corner}")

    slides_service.presentations().batchUpdate(
        presentationId=presentation_id,
        body={"requests": requests},
    ).execute()

    return "✅ Slide designer applied: " + ", ".join(operations)
        body={"requests": requests[:1]},
    ).execute()

    return f"✅ Added image for '{image_query}' to slide {slide_number}. Source: {image_url}"
 main
