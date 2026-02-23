import json
import os
import re
import threading
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime

import gradio as gr

# ── Lazy imports ───────────────────────────────────────────────────────────────
_google_imported = False
_import_error    = ""

def _try_import_google():
    global _google_imported, _import_error
    if _google_imported:
        return True
    try:
        global Credentials, Request, InstalledAppFlow, build
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        _google_imported = True
        return True
    except ImportError as e:
        _import_error = str(e)
        return False

# ── Extension meta ────────────────────────────────────────────────────────────
params = {
    "display_name": "Google Workspace",
    "is_tab": True,
}

# ── Paths ─────────────────────────────────────────────────────────────────────
DRIVE_ROOT  = Path("/content/drive/MyDrive/MY-AI-Gizmo")
CREDS_DIR   = DRIVE_ROOT / "google_credentials"
CREDS_FILE  = CREDS_DIR / "credentials.json"
TOKEN_FILE  = CREDS_DIR / "token.json"
URL_FILE    = DRIVE_ROOT / "public_url.txt"

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive.file",
]

# ── Service state ─────────────────────────────────────────────────────────────
_lock        = threading.Lock()
_creds       = None
_docs_svc    = None
_slides_svc  = None
_pending_flow = [None]


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════════════════════

def _status() -> str:
    if not CREDS_FILE.exists():
        return "🔴 No credentials.json — see Setup tab"
    if _creds and _creds.valid:
        return "🟢 Connected to Google"
    if TOKEN_FILE.exists():
        return "🟡 Token found — click Connect to refresh"
    return "🟠 credentials.json uploaded — click Connect"


def _save_creds(file_obj) -> str:
    if file_obj is None:
        return "❌ No file uploaded."
    try:
        CREDS_DIR.mkdir(parents=True, exist_ok=True)
        content = Path(file_obj.name).read_bytes()
        parsed  = json.loads(content)
        if "installed" not in parsed and "web" not in parsed:
            return "❌ This doesn't look like a Google OAuth credentials.json.\n   Download from Google Cloud Console → APIs & Services → Credentials."
        CREDS_FILE.write_bytes(content)
        return "✅ credentials.json saved! Now click 'Connect to Google'."
    except Exception as e:
        return f"❌ Save failed: {e}"


def _connect() -> str:
    global _creds, _docs_svc, _slides_svc
    if not _try_import_google():
        return (f"❌ Google libraries not installed.\n"
                f"Run: !pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client\n"
                f"Error: {_import_error}")
    if not CREDS_FILE.exists():
        return "❌ Upload credentials.json first."
    try:
        creds = None
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CREDS_FILE), SCOPES,
                    redirect_uri="urn:ietf:wg:oauth:2.0:oob"
                )
                auth_url, _ = flow.authorization_url(prompt="consent")
                _pending_flow[0] = flow
                return (
                    f"🔗 **Step 1 — Open this URL in your browser:**\n\n{auth_url}\n\n"
                    f"Google will show you a code.  **Paste it in the 'Auth Code' box and click Finish.**"
                )
        _creds = creds
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        _build_services()
        return "✅ Connected to Google Docs & Slides!"
    except Exception as e:
        return f"❌ Auth failed: {e}"


def _finish_auth(code: str) -> str:
    global _creds
    if not _pending_flow[0]:
        return "❌ Click 'Connect to Google' first."
    if not code.strip():
        return "❌ Paste the auth code."
    try:
        _pending_flow[0].fetch_token(code=code.strip())
        _creds = _pending_flow[0].credentials
        TOKEN_FILE.write_text(_creds.to_json(), encoding="utf-8")
        _build_services()
        _pending_flow[0] = None
        return "✅ Authenticated! Google Docs & Slides ready."
    except Exception as e:
        return f"❌ Code rejected: {e}"


def _disconnect() -> str:
    global _creds, _docs_svc, _slides_svc
    _creds = None; _docs_svc = None; _slides_svc = None
    try:
        TOKEN_FILE.unlink()
    except Exception:
        pass
    return "🔴 Disconnected. Token deleted."


def _build_services():
    global _docs_svc, _slides_svc
    _docs_svc   = build("docs",   "v1", credentials=_creds)
    _slides_svc = build("slides", "v1", credentials=_creds)


def _extract_id(url_or_id: str) -> str:
    url_or_id = url_or_id.strip()
    m = re.search(r"/d/([a-zA-Z0-9_-]{20,})", url_or_id)
    return m.group(1) if m else url_or_id


# ══════════════════════════════════════════════════════════════════════════════
#  AI CALL
# ══════════════════════════════════════════════════════════════════════════════

def _call_ai(prompt: str, max_tokens: int = 1024, temperature: float = 0.7) -> str:
    try:
        payload = json.dumps({
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:5000/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[AI error: {e} — is the main model loaded?]"


# ══════════════════════════════════════════════════════════════════════════════
#  IMAGE SEARCH
# ══════════════════════════════════════════════════════════════════════════════

def _search_image_url(query: str) -> str | None:
    """
    Find a public image URL for the given query.
    Strategy:
      1. Unsplash Source URL (free, follow redirect for direct URL)
      2. DuckDuckGo image scraper fallback
    Returns a direct image URL or None.
    """
    clean_query = urllib.parse.quote_plus(query.replace(" ", "+"))

    # ── Try Unsplash Source ───────────────────────────────────────────────────
    try:
        unsplash_url = f"https://source.unsplash.com/800x600/?{clean_query}"
        req = urllib.request.Request(unsplash_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            final_url = r.geturl()
            # Make sure it redirected to an actual image
            if "images.unsplash.com" in final_url:
                # Strip query params that might expire
                base = final_url.split("?")[0]
                return base + "?w=800&q=80"
    except Exception:
        pass

    # ── Try DuckDuckGo image scrape ───────────────────────────────────────────
    try:
        ddg_url = f"https://duckduckgo.com/?q={clean_query}&iax=images&ia=images"
        req = urllib.request.Request(
            ddg_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="ignore")
        # DDG embeds image data in a script tag
        m = re.search(r'"image":"(https?://[^"]+\.(jpg|jpeg|png|webp))"', html)
        if m:
            return m.group(1)
    except Exception:
        pass

    # ── Fallback: Lorem Picsum (always works but not query-specific) ──────────
    try:
        seed = abs(hash(query)) % 1000
        return f"https://picsum.photos/seed/{seed}/800/600"
    except Exception:
        pass

    return None


def _ai_suggest_image_query(slide_content: str) -> str:
    """Ask the AI what image would fit this slide content best."""
    prompt = (
        f"This is the content of a presentation slide:\n\n{slide_content}\n\n"
        f"Suggest a short, specific image search query (3-5 words) that would find "
        f"a relevant, professional photo for this slide. "
        f"Reply with ONLY the search query, nothing else."
    )
    return _call_ai(prompt, max_tokens=30, temperature=0.3)


# ══════════════════════════════════════════════════════════════════════════════
#  GOOGLE DOCS
# ══════════════════════════════════════════════════════════════════════════════

def _read_doc(doc_id_or_url: str) -> tuple[str, str]:
    if not _docs_svc:
        return "", "❌ Not connected — go to Setup tab."
    doc_id = _extract_id(doc_id_or_url)
    try:
        doc   = _docs_svc.documents().get(documentId=doc_id).execute()
        title = doc.get("title", "Untitled")
        parts = []
        for block in doc.get("body", {}).get("content", []):
            for elem in block.get("paragraph", {}).get("elements", []):
                t = elem.get("textRun", {}).get("content", "")
                if t:
                    parts.append(t)
        return title, "".join(parts).strip()
    except Exception as e:
        return "", f"❌ {e}\n   Make sure the doc is in your Drive or shared with you."


def _append_to_doc(doc_id: str, text: str) -> str:
    try:
        doc       = _docs_svc.documents().get(documentId=doc_id).execute()
        end_index = doc["body"]["content"][-1]["endIndex"] - 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        insert    = f"\n\n{'─'*50}\n[AI — {timestamp}]\n\n{text}\n"
        _docs_svc.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [{"insertText": {"location": {"index": end_index}, "text": insert}}]}
        ).execute()
        return f"✅ Written into doc  →  https://docs.google.com/document/d/{doc_id}/edit"
    except Exception as e:
        return f"❌ Write failed: {e}"


def _create_doc(title: str, content: str) -> str:
    try:
        doc    = _docs_svc.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]
        _docs_svc.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]}
        ).execute()
        return f"✅ Created!  →  https://docs.google.com/document/d/{doc_id}/edit"
    except Exception as e:
        return f"❌ {e}"


# ── Docs UI actions ────────────────────────────────────────────────────────────

def doc_load(url, state):
    title, text = _read_doc(url)
    if not title:
        return text, state, ""
    state.update({"id": _extract_id(url), "title": title, "text": text})
    preview = f"📄 **{title}**\n\n{text[:3000]}{'…' if len(text)>3000 else ''}"
    return preview, state, f"✅ Loaded: {title} ({len(text)} chars)"


def doc_ask(question, state, mt, temp, write_back):
    if not state.get("text"):
        return "❌ Load a doc first.", ""
    reply = _call_ai(
        f"Google Doc — '{state['title']}':\n\n{state['text'][:4000]}\n\n"
        f"Instruction: {question}\n\nYour response:",
        mt, temp
    )
    result = ""
    if write_back and state.get("id"):
        result = _append_to_doc(state["id"], reply)
    return reply, result


def doc_create(title, prompt_text, mt, temp):
    if not _docs_svc:
        return "❌ Not connected.", ""
    if not title.strip():
        return "❌ Enter a title.", ""
    content = _call_ai(
        f"Write a complete, well-structured document about: {prompt_text}\n"
        f"Use clear headings and paragraphs. Be thorough and professional.", mt, temp
    )
    result = _create_doc(title, content)
    return content, result


# ══════════════════════════════════════════════════════════════════════════════
#  GOOGLE SLIDES
# ══════════════════════════════════════════════════════════════════════════════

def _read_slides(url: str) -> tuple[str, list[dict], str]:
    """Returns (title, [{slide_num, text, object_id}], status)"""
    if not _slides_svc:
        return "", [], "❌ Not connected."
    pres_id = _extract_id(url)
    try:
        pres   = _slides_svc.presentations().get(presentationId=pres_id).execute()
        title  = pres.get("title", "Untitled")
        slides_data = []
        for i, slide in enumerate(pres.get("slides", []), 1):
            texts = []
            for elem in slide.get("pageElements", []):
                for te in elem.get("shape", {}).get("text", {}).get("textElements", []):
                    t = te.get("textRun", {}).get("content", "").strip()
                    if t:
                        texts.append(t)
            slides_data.append({
                "num": i,
                "object_id": slide["objectId"],
                "text": " | ".join(texts[:5])
            })
        return title, slides_data, f"✅ Loaded '{title}' — {len(slides_data)} slides"
    except Exception as e:
        return "", [], f"❌ {e}"


def _get_slide_placeholders(pres_id: str, slide_object_id: str) -> dict:
    """Return {TITLE: id, BODY: id} placeholder IDs for a slide."""
    try:
        pres   = _slides_svc.presentations().get(presentationId=pres_id).execute()
        target = next((s for s in pres["slides"] if s["objectId"] == slide_object_id), None)
        if not target:
            return {}
        result = {}
        for elem in target.get("pageElements", []):
            ph = elem.get("shape", {}).get("placeholder", {})
            ph_type = ph.get("type", "")
            if ph_type in ("CENTERED_TITLE", "TITLE"):
                result["TITLE"] = elem["objectId"]
            elif ph_type == "BODY":
                result["BODY"] = elem["objectId"]
        return result
    except Exception:
        return {}


def _insert_image_into_slide(pres_id: str, slide_object_id: str,
                              image_url: str,
                              x_pt: float = 200, y_pt: float = 150,
                              w_pt: float = 350, h_pt: float = 250) -> str:
    """Insert an image from a URL into a slide at the given position (in points)."""
    def pt_to_emu(pt):
        return int(pt * 12700)

    try:
        import uuid
        element_id = "img_" + uuid.uuid4().hex[:8]
        requests = [{
            "createImage": {
                "objectId": element_id,
                "url": image_url,
                "elementProperties": {
                    "pageObjectId": slide_object_id,
                    "size": {
                        "width":  {"magnitude": pt_to_emu(w_pt), "unit": "EMU"},
                        "height": {"magnitude": pt_to_emu(h_pt), "unit": "EMU"},
                    },
                    "transform": {
                        "scaleX": 1, "scaleY": 1,
                        "translateX": pt_to_emu(x_pt),
                        "translateY": pt_to_emu(y_pt),
                        "unit": "EMU",
                    },
                }
            }
        }]
        _slides_svc.presentations().batchUpdate(
            presentationId=pres_id,
            body={"requests": requests}
        ).execute()
        return f"✅ Image inserted into slide!"
    except Exception as e:
        return f"❌ Image insert failed: {e}\n   The image URL might not be publicly accessible."


def _create_slide(pres_id: str, slide_title: str, slide_body: str) -> tuple[str, str]:
    """Add a new TITLE_AND_BODY slide. Returns (slide_object_id, status)."""
    try:
        resp = _slides_svc.presentations().batchUpdate(
            presentationId=pres_id,
            body={"requests": [{"createSlide": {
                "slideLayoutReference": {"predefinedLayout": "TITLE_AND_BODY"}
            }}]}
        ).execute()
        slide_id = resp["replies"][0]["createSlide"]["objectId"]
        placeholders = _get_slide_placeholders(pres_id, slide_id)

        text_req = []
        if "TITLE" in placeholders and slide_title:
            text_req.append({"insertText": {"objectId": placeholders["TITLE"], "text": slide_title}})
        if "BODY" in placeholders and slide_body:
            text_req.append({"insertText": {"objectId": placeholders["BODY"], "text": slide_body}})
        if text_req:
            _slides_svc.presentations().batchUpdate(
                presentationId=pres_id, body={"requests": text_req}
            ).execute()

        link = f"https://docs.google.com/presentation/d/{pres_id}/edit"
        return slide_id, f"✅ Slide added  →  {link}"
    except Exception as e:
        return "", f"❌ {e}"


def _parse_outline(outline: str) -> list[dict]:
    slides = []
    current_title, current_body = "", []
    for line in outline.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^(#{1,3}|Slide\s*\d+[:.)]|\*\*Slide|\d+\.)", line, re.IGNORECASE):
            if current_title:
                slides.append({"title": current_title, "body": "\n".join(current_body)})
                current_body = []
            current_title = re.sub(r"^(#{1,3}|\d+\.\s*|Slide\s*\d+[:.)\s]+|\*\*)", "", line).strip("*:. ")
        else:
            current_body.append(re.sub(r"^[-•*]\s*", "• ", line))
    if current_title:
        slides.append({"title": current_title, "body": "\n".join(current_body)})
    if not slides:
        chunks = [c.strip() for c in re.split(r"\n{2,}", outline) if c.strip()]
        for chunk in chunks:
            lines = chunk.splitlines()
            slides.append({"title": lines[0][:80], "body": "\n".join(lines[1:])})
    return slides[:20]


# ── Slides UI actions ──────────────────────────────────────────────────────────

def slides_load(url, state):
    title, data, status = _read_slides(url)
    state.update({"id": _extract_id(url), "title": title, "slides": data})
    summary = f"📊 **{title}**\n\n"
    summary += "\n".join(f"**Slide {s['num']}:** {s['text']}" for s in data) if data else "(empty)"
    return summary, state, status


def slides_add_slide(instruction, state, mt, temp):
    if not state.get("id"):
        return "❌ Load a presentation first.", ""
    prompt = (
        f"Create a single presentation slide about: {instruction}\n"
        f"Reply in EXACTLY this format:\n"
        f"TITLE: <short slide title>\n"
        f"BODY:\n• bullet 1\n• bullet 2\n• bullet 3\n• bullet 4"
    )
    reply = _call_ai(prompt, min(mt, 512), temp)
    title_m = re.search(r"TITLE:\s*(.+)", reply)
    body_m  = re.search(r"BODY:\s*([\s\S]+)", reply)
    s_title = title_m.group(1).strip() if title_m else instruction[:60]
    s_body  = body_m.group(1).strip()  if body_m  else reply
    _, status = _create_slide(state["id"], s_title, s_body)
    return f"**{s_title}**\n\n{s_body}", status


def slides_find_and_insert_image(slide_num_str, instruction, state, mt, temp):
    """
    AI reads the slide content → picks best image search query →
    finds an image → inserts it into the slide.
    """
    if not state.get("id") or not state.get("slides"):
        return "❌ Load a presentation first.", "", ""

    # Find the target slide
    try:
        slide_num = int(slide_num_str)
    except Exception:
        return "❌ Enter a valid slide number.", "", ""

    slides_data = state.get("slides", [])
    target = next((s for s in slides_data if s["num"] == slide_num), None)
    if not target:
        return f"❌ Slide {slide_num} not found. The deck has {len(slides_data)} slides.", "", ""

    slide_content = target["text"]

    # Let AI decide the best image search query
    if instruction.strip():
        query = _call_ai(
            f"Slide content: {slide_content}\n"
            f"User instruction: {instruction}\n"
            f"Give a 3-5 word image search query for a professional photo that fits this slide. "
            f"Reply with ONLY the query.",
            max_tokens=20, temperature=0.3
        ).strip().strip('"\'')
    else:
        query = _ai_suggest_image_query(slide_content)
        query = query.strip().strip('"\'')

    status1 = f"🔍 Searching for image: **{query}**"

    # Search for image
    image_url = _search_image_url(query)
    if not image_url:
        return status1, "❌ Could not find an image. Try a different instruction.", ""

    status2 = f"🖼 Found image. Inserting into Slide {slide_num}…"

    # Insert into slide
    slide_object_id = target["object_id"]
    result = _insert_image_into_slide(state["id"], slide_object_id, image_url)

    return status1 + "\n" + status2, result, image_url


def slides_create_full(pres_title, topic, num_slides, mt, temp):
    if not _slides_svc:
        return "❌ Not connected.", ""
    if not pres_title.strip():
        return "❌ Enter a presentation title.", ""
    outline = _call_ai(
        f"Create a {num_slides}-slide presentation about: {topic}\n\n"
        f"Use EXACTLY this format for every slide:\n"
        f"## Slide 1: [Title]\n• bullet\n• bullet\n• bullet\n\n## Slide 2: [Title]\n(etc.)\n\n"
        f"Be professional and informative.",
        mt, temp
    )
    slides_data = _parse_outline(outline)
    if not slides_data:
        return outline, "❌ Could not parse outline into slides."
    try:
        pres    = _slides_svc.presentations().create(body={"title": pres_title}).execute()
        pres_id = pres["presentationId"]
        for slide in slides_data:
            _create_slide(pres_id, slide.get("title", ""), slide.get("body", ""))
        link = f"https://docs.google.com/presentation/d/{pres_id}/edit"
        return outline, f"✅ Created with {len(slides_data)} slides  →  {link}"
    except Exception as e:
        return outline, f"❌ {e}"


def slides_ai_coworker(command, state, mt, temp):
    """
    Free-form AI co-worker for slides.
    User types natural language like:
      'find an image for slide 3'
      'add a summary slide'
      'rewrite slide 2 title to be more engaging'
    """
    if not state.get("id"):
        return "❌ Load a presentation first.", ""

    slides_summary = "\n".join(
        f"Slide {s['num']}: {s['text']}" for s in state.get("slides", [])
    )
    prompt = (
        f"You are an expert presentation co-worker.\n"
        f"Current presentation: '{state.get('title', '')}'\n\n"
        f"Slides:\n{slides_summary}\n\n"
        f"User instruction: {command}\n\n"
        f"Describe what you will do, then provide the content.\n"
        f"If adding a slide, use format:\nTITLE: ...\nBODY:\n• ...\n• ...\n"
        f"If suggesting an image, use format:\nIMAGE QUERY: <3-5 word search query>"
    )
    reply = _call_ai(prompt, mt, temp)

    # Auto-detect and execute actions in the reply
    result = "*(reply shown above — no auto-action detected)*"

    # Auto-add slide if reply contains TITLE/BODY
    title_m = re.search(r"TITLE:\s*(.+)", reply)
    body_m  = re.search(r"BODY:\s*([\s\S]+?)(?:IMAGE QUERY:|$)", reply, re.DOTALL)
    if title_m and body_m:
        s_title = title_m.group(1).strip()
        s_body  = body_m.group(1).strip()
        _, result = _create_slide(state["id"], s_title, s_body)

    # Auto-insert image if reply contains IMAGE QUERY
    img_m = re.search(r"IMAGE QUERY:\s*(.+)", reply)
    if img_m and state.get("slides"):
        query = img_m.group(1).strip()
        img_url = _search_image_url(query)
        if img_url:
            # Insert into the last slide
            last_slide = state["slides"][-1]
            img_result = _insert_image_into_slide(state["id"], last_slide["object_id"], img_url)
            result = f"🔍 Query: {query}\n{img_result}"

    return reply, result


# ══════════════════════════════════════════════════════════════════════════════
#  GRADIO UI
# ══════════════════════════════════════════════════════════════════════════════

def ui():
    gr.Markdown("## 🔗 Google Workspace Connector")
    gr.Markdown("Connect your AI to **Google Docs** and **Google Slides** — read, write, and insert images.")

    status_box = gr.Textbox(value=_status(), label="Connection Status", interactive=False)
    gr.Button("🔄 Refresh", size="sm").click(fn=_status, outputs=status_box)

    # ── SETUP ──────────────────────────────────────────────────────────────────
    with gr.Tab("🔑 Setup"):
        gr.Markdown("""
### Connect in 3 steps

**Step 1 — Get credentials.json from Google (one time)**
1. [console.cloud.google.com](https://console.cloud.google.com) → Create project
2. **APIs & Services → Library** → Enable **Google Docs API** + **Google Slides API**
3. **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
4. Application type: **Desktop app** → Download `credentials.json`

**Step 2 — Upload below**

**Step 3 — Connect and follow the link**
""")
        creds_upload = gr.File(label="Upload credentials.json", file_types=[".json"])
        upload_result = gr.Textbox(label="", interactive=False)
        gr.Button("💾 Save Credentials", variant="primary").click(
            fn=_save_creds, inputs=creds_upload, outputs=upload_result
        )
        gr.Markdown("---")
        connect_result = gr.Textbox(label="Auth instructions / result", interactive=False, lines=6)
        gr.Button("🔗 Connect to Google", variant="primary").click(
            fn=_connect, outputs=connect_result
        ).then(fn=_status, outputs=status_box)

        gr.Markdown("**Paste the auth code Google gives you:**")
        with gr.Row():
            code_box = gr.Textbox(label="Auth code")
            gr.Button("✅ Finish Auth", variant="primary").click(
                fn=_finish_auth, inputs=code_box, outputs=connect_result
            ).then(fn=_status, outputs=status_box)

        gr.Button("🔴 Disconnect", variant="stop").click(
            fn=_disconnect, outputs=connect_result
        ).then(fn=_status, outputs=status_box)

    # ── GOOGLE DOCS ────────────────────────────────────────────────────────────
    with gr.Tab("📄 Google Docs"):

        with gr.Tab("Read & Chat"):
            gr.Markdown("Load any Google Doc and ask your AI about it.")
            doc_url   = gr.Textbox(label="Google Doc URL or ID",
                                   placeholder="https://docs.google.com/document/d/YOUR_ID/edit")
            doc_state = gr.State({})
            doc_load_btn = gr.Button("📥 Load Doc", variant="primary")
            doc_preview  = gr.Markdown("*No doc loaded yet.*")
            doc_load_st  = gr.Textbox(label="", interactive=False)

            doc_load_btn.click(fn=doc_load, inputs=[doc_url, doc_state], outputs=[doc_preview, doc_state, doc_load_st])

            gr.Markdown("---")
            doc_q        = gr.Textbox(label="Instruction for AI",
                                      placeholder="Summarize / Fix grammar / Translate / Write a conclusion…", lines=2)
            with gr.Row():
                doc_mt   = gr.Slider(128, 2048, value=1024, step=128, label="Max tokens")
                doc_temp = gr.Slider(0.0, 1.5, value=0.5, step=0.05, label="Temperature")
            doc_wb       = gr.Checkbox(label="✍️ Write AI reply back into the Google Doc")
            doc_ask_btn  = gr.Button("🤖 Ask AI", variant="primary")
            doc_reply    = gr.Textbox(label="AI Reply", lines=10, interactive=False)
            doc_write_st = gr.Textbox(label="Write Status", interactive=False)

            doc_ask_btn.click(fn=doc_ask, inputs=[doc_q, doc_state, doc_mt, doc_temp, doc_wb],
                              outputs=[doc_reply, doc_write_st])

        with gr.Tab("Create New Doc"):
            gr.Markdown("AI writes and creates a brand-new Google Doc for you.")
            new_doc_title  = gr.Textbox(label="Document title", placeholder="My AI-written report")
            new_doc_prompt = gr.Textbox(label="What should it be about?",
                                        placeholder="A detailed Python asyncio guide with examples…", lines=3)
            with gr.Row():
                ndmt = gr.Slider(256, 4096, value=2048, step=256, label="Max tokens")
                ndt  = gr.Slider(0.0, 1.5, value=0.6, step=0.05, label="Temperature")
            gr.Button("✨ Create Doc", variant="primary").click(
                fn=doc_create, inputs=[new_doc_title, new_doc_prompt, ndmt, ndt],
                outputs=[gr.Textbox(label="Content preview", lines=12, interactive=False),
                         gr.Textbox(label="Result / Link", interactive=False)]
            )

    # ── GOOGLE SLIDES ──────────────────────────────────────────────────────────
    with gr.Tab("📊 Google Slides"):

        with gr.Tab("AI Co-Worker 🤝"):
            gr.Markdown(
                "**Tell the AI what to do with your presentation in plain language.**\n\n"
                "Examples:\n"
                "- *'Add a slide about climate change solutions'*\n"
                "- *'Find a fitting image for slide 3'*\n"
                "- *'Read slide 4 and add an image that matches the content'*\n"
                "- *'Add a summary slide at the end'*"
            )
            cw_url   = gr.Textbox(label="Presentation URL or ID",
                                  placeholder="https://docs.google.com/presentation/d/YOUR_ID/edit")
            cw_state = gr.State({})
            gr.Button("📥 Load Presentation", variant="primary").click(
                fn=slides_load, inputs=[cw_url, cw_state],
                outputs=[gr.Markdown(), cw_state, gr.Textbox(label="Status", interactive=False)]
            )
            cw_preview = gr.Markdown("*No presentation loaded yet.*")
            cw_status  = gr.Textbox(label="", interactive=False)

            # Re-link the load button properly
            cw_load_btn = gr.Button("📥 Load Presentation", variant="primary", visible=False)

            gr.Markdown("---")
            cw_command = gr.Textbox(label="Tell the AI what to do",
                                    placeholder="Find an image for slide 2 / Add a slide about X…", lines=2)
            with gr.Row():
                cw_mt   = gr.Slider(128, 2048, value=1024, step=128, label="Max tokens")
                cw_temp = gr.Slider(0.0, 1.5, value=0.6, step=0.05, label="Temperature")
            gr.Button("🤝 Do it!", variant="primary").click(
                fn=slides_ai_coworker, inputs=[cw_command, cw_state, cw_mt, cw_temp],
                outputs=[gr.Textbox(label="AI Reply", lines=8, interactive=False),
                         gr.Textbox(label="Action Result", interactive=False)]
            )

        with gr.Tab("Add a Slide"):
            gr.Markdown("Load a deck, describe a slide, and the AI adds it.")
            add_url   = gr.Textbox(label="Presentation URL or ID")
            add_state = gr.State({})
            add_load  = gr.Button("📥 Load", variant="primary")
            add_prev  = gr.Markdown("*Not loaded.*")
            add_st    = gr.Textbox(label="", interactive=False)
            add_load.click(fn=slides_load, inputs=[add_url, add_state],
                           outputs=[add_prev, add_state, add_st])
            gr.Markdown("---")
            add_instr  = gr.Textbox(label="What should the new slide be about?",
                                    placeholder="The benefits of AI in healthcare…")
            with gr.Row():
                add_mt   = gr.Slider(128, 1024, value=512, step=64, label="Max tokens")
                add_temp = gr.Slider(0.0, 1.5, value=0.6, step=0.05, label="Temperature")
            gr.Button("➕ Generate & Add Slide", variant="primary").click(
                fn=slides_add_slide, inputs=[add_instr, add_state, add_mt, add_temp],
                outputs=[gr.Textbox(label="Slide content", lines=8, interactive=False),
                         gr.Textbox(label="Result", interactive=False)]
            )

        with gr.Tab("🖼 Insert Image"):
            gr.Markdown(
                "AI reads a slide, finds the most fitting image online, and inserts it.\n\n"
                "You can also give a specific instruction like: *'use a photo of a sunset'*"
            )
            img_url   = gr.Textbox(label="Presentation URL or ID")
            img_state = gr.State({})
            img_load  = gr.Button("📥 Load", variant="primary")
            img_prev  = gr.Markdown("*Not loaded.*")
            img_st    = gr.Textbox(label="", interactive=False)
            img_load.click(fn=slides_load, inputs=[img_url, img_state],
                           outputs=[img_prev, img_state, img_st])
            gr.Markdown("---")
            img_slide_num = gr.Number(label="Slide number", value=1, minimum=1, precision=0)
            img_instr     = gr.Textbox(label="Optional: image instruction",
                                       placeholder="Use a photo of a city skyline at night… (leave blank = AI decides)")
            with gr.Row():
                img_mt   = gr.Slider(128, 512, value=256, step=64, label="Max tokens")
                img_temp = gr.Slider(0.0, 1.5, value=0.5, step=0.05, label="Temperature")
            gr.Button("🔍 Find & Insert Image", variant="primary").click(
                fn=slides_find_and_insert_image,
                inputs=[img_slide_num, img_instr, img_state, img_mt, img_temp],
                outputs=[gr.Textbox(label="Search status", lines=3, interactive=False),
                         gr.Textbox(label="Insert result", interactive=False),
                         gr.Textbox(label="Image URL used", interactive=False)]
            )

        with gr.Tab("Create Full Deck"):
            gr.Markdown("Give a topic — AI writes and creates a complete Google Slides deck.")
            full_title  = gr.Textbox(label="Presentation title", placeholder="Introduction to Machine Learning")
            full_topic  = gr.Textbox(label="Topic description",
                                     placeholder="Cover the basics: what ML is, types, real-world uses, future trends.",
                                     lines=3)
            full_slides = gr.Slider(3, 15, value=7, step=1, label="Number of slides")
            with gr.Row():
                full_mt   = gr.Slider(256, 4096, value=2048, step=256, label="Max tokens")
                full_temp = gr.Slider(0.0, 1.5, value=0.6, step=0.05, label="Temperature")
            gr.Button("🎨 Generate Presentation", variant="primary").click(
                fn=slides_create_full,
                inputs=[full_title, full_topic, full_slides, full_mt, full_temp],
                outputs=[gr.Textbox(label="AI outline", lines=20, interactive=False),
                         gr.Textbox(label="Result / Link", interactive=False)]
            )

    # ── TIPS ───────────────────────────────────────────────────────────────────
    with gr.Tab("ℹ️ Tips"):
        gr.Markdown("""
### Image Insertion

The AI uses **Unsplash** (free, no API key needed) to find images.
If that fails it falls back to **Lorem Picsum** (random photo).

For best results, give a specific instruction in the image box, e.g.:
- *"a photo of a team collaborating in an office"*
- *"abstract blue technology background"*
- *"a chart showing growth"*

Images are inserted at a default position (right side of slide).
You can drag/resize them in Google Slides after insertion.

### Co-Worker Mode Tips
Tell the AI in plain language. It will:
- Detect if you want a new slide → creates it automatically
- Detect if you want an image → searches and inserts it
- Otherwise just replies with advice

### Credentials location
```
/content/drive/MyDrive/MY-AI-Gizmo/google_credentials/
  credentials.json   ← OAuth client secrets (you upload this)
  token.json         ← auto-saved after first login
```
Delete `token.json` to force re-authentication.

### Common errors
| Error | Fix |
|-------|-----|
| `Access denied` | Enable Google Docs API and Slides API in Cloud Console |
| `Image insert failed` | Image URL not publicly accessible — try different instruction |
| `Slide not found` | Check slide number — slides are numbered from 1 |
| `API not enabled` | Go to Cloud Console → APIs & Library → enable both APIs |
        """)
