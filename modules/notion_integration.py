"""Backend logic for the Notion Integration feature."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path("user_data/notion_config.json")


def _blocks_to_markdown(blocks: list) -> str:
    """Convert a list of Notion block objects to Markdown text."""
    lines = []
    for block in blocks:
        btype = block.get("type", "")
        obj = block.get(btype, {})
        rich_texts = obj.get("rich_text", [])
        text = "".join(rt.get("plain_text", "") for rt in rich_texts)

        if btype == "heading_1":
            lines.append(f"# {text}")
        elif btype == "heading_2":
            lines.append(f"## {text}")
        elif btype == "heading_3":
            lines.append(f"### {text}")
        elif btype == "bulleted_list_item":
            lines.append(f"- {text}")
        elif btype == "numbered_list_item":
            lines.append(f"1. {text}")
        elif btype == "code":
            lang = obj.get("language", "")
            lines.append(f"```{lang}\n{text}\n```")
        elif btype == "quote":
            lines.append(f"> {text}")
        elif btype == "divider":
            lines.append("---")
        elif text:
            lines.append(text)
    return "\n".join(lines)


def _markdown_to_blocks(markdown: str) -> list:
    """Convert Markdown text to a list of Notion paragraph/heading blocks."""
    blocks = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("### "):
            btype = "heading_3"
            content = stripped[4:]
        elif stripped.startswith("## "):
            btype = "heading_2"
            content = stripped[3:]
        elif stripped.startswith("# "):
            btype = "heading_1"
            content = stripped[2:]
        elif stripped.startswith("- "):
            btype = "bulleted_list_item"
            content = stripped[2:]
        elif stripped == "---":
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            continue
        else:
            btype = "paragraph"
            content = stripped

        blocks.append({
            "object": "block",
            "type": btype,
            btype: {
                "rich_text": [{"type": "text", "text": {"content": content}}]
            },
        })
    return blocks


class NotionManager:
    """Manages connection and CRUD operations with the Notion API."""

    def __init__(self):
        self.client = None
        self.connected = False

    def connect(self, api_key: str) -> tuple[bool, str]:
        """Initialise Notion client and validate the token.

        Returns (success: bool, message: str).
        """
        try:
            from notion_client import Client  # type: ignore
        except ImportError:
            return False, "notion-client is not installed. Run: pip install notion-client"

        api_key = (api_key or "").strip()
        if not api_key:
            return False, "No API key provided."

        try:
            self.client = Client(auth=api_key)
            # Quick validation: fetch the bot user
            self.client.users.me()
            self.connected = True
            # Persist key (config only, never committed to git)
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(json.dumps({"api_key": api_key}))
            return True, "✅ Connected to Notion successfully."
        except Exception as exc:
            self.connected = False
            return False, f"❌ Connection failed: {exc}"

    def load_saved_key(self) -> Optional[str]:
        """Return the previously saved API key if it exists."""
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text())
                return data.get("api_key")
            except Exception:
                pass
        return None

    def list_pages(self) -> tuple[list, str]:
        """List all pages accessible to the integration.

        Returns (pages: list[dict], message: str).
        Each dict has keys: id, title.
        """
        if not self.connected or not self.client:
            return [], "Not connected."
        try:
            results = self.client.search(filter={"property": "object", "value": "page"}).get("results", [])
            pages = []
            for r in results:
                title_prop = r.get("properties", {}).get("title", {})
                title_texts = title_prop.get("title", [])
                title = "".join(t.get("plain_text", "") for t in title_texts) or "Untitled"
                pages.append({"id": r["id"], "title": title})
            return pages, f"Found {len(pages)} page(s)."
        except Exception as exc:
            return [], f"Error listing pages: {exc}"

    def fetch_page_content(self, page_id: str) -> tuple[str, str]:
        """Fetch the blocks of a page and return them as Markdown.

        Returns (markdown: str, message: str).
        """
        if not self.connected or not self.client:
            return "", "Not connected."
        try:
            blocks = self.client.blocks.children.list(block_id=page_id).get("results", [])
            markdown = _blocks_to_markdown(blocks)
            return markdown, "Page fetched successfully."
        except Exception as exc:
            return "", f"Error fetching page: {exc}"

    def create_page(self, title: str, content: str, parent_id: Optional[str] = None) -> tuple[str, str]:
        """Create a new Notion page with Markdown *content*.

        Returns (page_url: str, message: str).
        """
        if not self.connected or not self.client:
            return "", "Not connected."
        try:
            parent = {"type": "page_id", "page_id": parent_id} if parent_id else {"type": "workspace", "workspace": True}
            children = _markdown_to_blocks(content)
            response = self.client.pages.create(
                parent=parent,
                properties={
                    "title": {
                        "title": [{"type": "text", "text": {"content": title or "Untitled"}}]
                    }
                },
                children=children[:100],  # Notion API limit
            )
            url = response.get("url", "")
            return url, f"✅ Page created: {url}"
        except Exception as exc:
            return "", f"❌ Error creating page: {exc}"

    def append_to_page(self, page_id: str, content: str) -> tuple[bool, str]:
        """Append Markdown *content* to an existing page.

        Returns (success: bool, message: str).
        """
        if not self.connected or not self.client:
            return False, "Not connected."
        try:
            blocks = _markdown_to_blocks(content)
            self.client.blocks.children.append(block_id=page_id, children=blocks[:100])
            return True, "✅ Content appended successfully."
        except Exception as exc:
            return False, f"❌ Error appending to page: {exc}"
