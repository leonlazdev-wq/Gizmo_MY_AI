"""PDF reader backend for Gizmo."""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple


# Module-level state for the active PDF
_state: Dict = {
    "file_path": "",
    "page_count": 0,
    "title": "",
    "current_page": 0,
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


def _get_reader(file_path: Optional[str] = None):
    """Return a PyPDF2 PdfReader instance or (None, error_str)."""
    file_path = file_path or _state.get("file_path", "")
    if not file_path:
        return None, "❌ No PDF loaded. Call load_pdf first."
    if not os.path.isfile(file_path):
        return None, f"❌ File not found: {file_path}"
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(file_path)
        return reader, None
    except ImportError:
        return None, "❌ PyPDF2 not installed. Run: pip install PyPDF2"
    except Exception as exc:
        return None, f"❌ Failed to open PDF: {exc}"


def load_pdf(file_path: str) -> Tuple[str, Dict]:
    """Load a PDF file and update module state."""
    file_path = (file_path or "").strip()
    if not file_path:
        return "❌ Please provide a file path.", {}
    if not os.path.isfile(file_path):
        return f"❌ File not found: {file_path}", {}

    reader, error = _get_reader(file_path)
    if error:
        return error, {}

    page_count = len(reader.pages)
    meta = reader.metadata or {}
    title = meta.get("/Title", "") or os.path.splitext(os.path.basename(file_path))[0]
    file_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)

    _state["file_path"] = file_path
    _state["page_count"] = page_count
    _state["title"] = title
    _state["current_page"] = 0

    info = {
        "page_count": page_count,
        "title": title,
        "file_size": file_size_mb,
    }
    return f"✅ Loaded '{title}' ({page_count} pages, {file_size_mb} MB).", info


def get_pdf_info(file_path: Optional[str] = None) -> Tuple[str, Dict]:
    """Return PDF metadata: page_count, title, author, file_size_mb."""
    file_path = file_path or _state.get("file_path", "")
    reader, error = _get_reader(file_path)
    if error:
        return error, {}

    meta = reader.metadata or {}
    file_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
    info = {
        "page_count": len(reader.pages),
        "title": meta.get("/Title", "") or os.path.splitext(os.path.basename(file_path))[0],
        "author": meta.get("/Author", "Unknown"),
        "file_size_mb": file_size_mb,
    }
    return f"✅ PDF info retrieved.", info


def get_page_text(page_number: int, file_path: Optional[str] = None) -> Tuple[str, str]:
    """Get text from a specific page (0-indexed)."""
    reader, error = _get_reader(file_path)
    if error:
        return error, ""

    if page_number < 0 or page_number >= len(reader.pages):
        return f"❌ Page {page_number} out of range (0–{len(reader.pages) - 1}).", ""

    try:
        text = reader.pages[page_number].extract_text() or ""
        _state["current_page"] = page_number
        return f"✅ Extracted text from page {page_number}.", text
    except Exception as exc:
        return f"❌ Failed to extract page text: {exc}", ""


def get_all_text(file_path: Optional[str] = None) -> Tuple[str, str]:
    """Get all text concatenated from the PDF."""
    reader, error = _get_reader(file_path)
    if error:
        return error, ""

    try:
        parts = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            parts.append(f"--- Page {i} ---\n{page_text}")
        full_text = "\n\n".join(parts)
        return f"✅ Extracted text from {len(reader.pages)} pages.", full_text
    except Exception as exc:
        return f"❌ Failed to extract text: {exc}", ""


def search_pdf(query: str, file_path: Optional[str] = None) -> Tuple[str, List[Dict]]:
    """Search for text in the PDF. Returns list of dicts with page and context."""
    reader, error = _get_reader(file_path)
    if error:
        return error, []

    query_lower = query.lower()
    results: List[Dict] = []

    for i, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        if query_lower in page_text.lower():
            # Find context around the match
            idx = page_text.lower().find(query_lower)
            start = max(0, idx - 100)
            end = min(len(page_text), idx + len(query) + 100)
            context = page_text[start:end].strip()
            results.append({"page": i, "context": context})

    if results:
        return f"✅ Found '{query}' on {len(results)} page(s).", results
    return f"❌ '{query}' not found in PDF.", []


def summarize_pdf(file_path: Optional[str] = None) -> Tuple[str, str]:
    """Generate an AI summary of the entire PDF."""
    msg, text = get_all_text(file_path)
    if not text:
        return msg, ""

    prompt = (
        "Please provide a concise summary of the following PDF document. "
        "Highlight the main topics, arguments, and conclusions:\n\n"
        + text[:6000]
    )
    output, error = _call_ai(prompt)
    if error:
        return error, ""
    return "✅ PDF summarized.", output


def summarize_page(page_number: int, file_path: Optional[str] = None) -> Tuple[str, str]:
    """Generate an AI summary of a single page."""
    msg, text = get_page_text(page_number, file_path)
    if not text:
        return msg, ""

    prompt = (
        f"Please summarize the content of page {page_number} from this document:\n\n" + text
    )
    output, error = _call_ai(prompt)
    if error:
        return error, ""
    return f"✅ Page {page_number} summarized.", output


def answer_question(question: str, file_path: Optional[str] = None) -> Tuple[str, str]:
    """Answer a question using the PDF content as context (RAG-style)."""
    msg, text = get_all_text(file_path)
    if not text:
        return msg, ""

    # Use a simple keyword-based approach to find the most relevant section
    query_words = set(question.lower().split())
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    scored = []
    for para in paragraphs:
        para_words = set(para.lower().split())
        score = len(query_words & para_words)
        scored.append((score, para))
    scored.sort(key=lambda x: x[0], reverse=True)
    context = "\n\n".join([p for _, p in scored[:5]])

    prompt = (
        f"Using the following context from a PDF document, answer this question:\n"
        f"Question: {question}\n\n"
        f"Context:\n{context[:4000]}\n\n"
        "Answer:"
    )
    output, error = _call_ai(prompt)
    if error:
        return error, ""
    return "✅ Question answered.", output


def highlight_key_sections(file_path: Optional[str] = None) -> Tuple[str, str]:
    """Use AI to identify and return key passages from the PDF."""
    msg, text = get_all_text(file_path)
    if not text:
        return msg, ""

    prompt = (
        "Identify and list the most important key passages, definitions, and concepts "
        "from the following document. Format each as a numbered list:\n\n"
        + text[:6000]
    )
    output, error = _call_ai(prompt)
    if error:
        return error, ""
    return "✅ Key sections identified.", output


def get_current_state() -> Dict:
    """Return the current module state."""
    return dict(_state)
