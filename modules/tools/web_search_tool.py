from __future__ import annotations

from typing import Any, Dict

from modules.tools.base import Tool
from modules.web_search import search_with_providers


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search web and return summarized snippets."

    def execute(self, **kwargs) -> Dict[str, Any]:
        query = str(kwargs.get("query", ""))
        provider = str(kwargs.get("provider", "duckduckgo"))
        k = int(kwargs.get("k", 5))
        return {"ok": True, "results": search_with_providers(query, provider=provider, max_results=k)}
