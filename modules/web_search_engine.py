"""Web Search Engine backend – query web then ask the AI."""

from __future__ import annotations

from modules.logging_colors import logger
from modules.web_search import search_with_providers

_search_history: list[dict] = []


def search_and_ask(query: str, num_results: int = 5, engine: str = "duckduckgo") -> tuple[str, str, list[list[str]]]:
    """Search the web, build a prompt, query the AI, return answer + raw results + history."""
    query = (query or "").strip()
    if not query:
        return "⚠️ Please enter a search query.", "", get_search_history()

    # Perform search
    try:
        results = search_with_providers(query, provider=engine, max_results=int(num_results))
    except Exception as exc:
        logger.error(f"Web search error: {exc}")
        results = []

    if not results:
        return (
            "⚠️ No search results found. Check your internet connection or try a different query.",
            "",
            get_search_history()
        )

    # Format results for AI prompt
    formatted = ""
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        url = r.get("url", "")
        snippet = r.get("snippet", "")[:500]
        formatted += f"{i}. **{title}**\n   URL: {url}\n   {snippet}\n\n"

    prompt = (
        f"Based on the following web search results, please answer the user's question.\n\n"
        f"Search results:\n{formatted}\n"
        f"Question: {query}\n\n"
        f"Provide a comprehensive answer with source citations (mention the source number)."
    )

    ai_answer = _get_ai_response(prompt)

    # Build raw results display
    raw_md = ""
    for i, r in enumerate(results, 1):
        title = r.get("title", "No title")
        url = r.get("url", "")
        snippet = r.get("snippet", "")[:300]
        raw_md += f"**{i}. {title}**\n{url}\n{snippet}\n\n---\n\n"

    # Record history
    _search_history.append({"query": query, "answer": ai_answer[:200]})

    return ai_answer, raw_md, get_search_history()


def get_search_history() -> list[list[str]]:
    return [[h["query"], h["answer"]] for h in _search_history[-10:]]


def _get_ai_response(prompt: str) -> str:
    try:
        from modules import shared
        from modules.text_generation import generate_reply

        if shared.model is None:
            return "⚠️ No model is loaded. Please load a model first."

        state = {"max_new_tokens": 1024, "temperature": 0.7, "top_p": 0.9}
        generator = generate_reply(prompt, state)
        response = ""
        for chunk in generator:
            if isinstance(chunk, str):
                response = chunk
            elif isinstance(chunk, list):
                response = chunk[0] if chunk else response
        return response.strip() or "[No response]"
    except Exception as exc:
        logger.error(f"AI response error: {exc}")
        return f"[Error: {exc}]"
