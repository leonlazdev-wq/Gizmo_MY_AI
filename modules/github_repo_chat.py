"""Backend logic for the GitHub Repo Chat feature."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

# Maximum files/size guardrails
_MAX_FILES = 10_000
_MAX_SIZE_MB = 100

# File extensions to include in the index
_TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".sh",
    ".bash", ".zsh", ".fish", ".yaml", ".yml", ".toml", ".json", ".xml",
    ".html", ".css", ".scss", ".less", ".md", ".txt", ".rst", ".cfg", ".ini",
    ".env", ".dockerfile", "dockerfile", ".makefile", "makefile",
}


class RepoSession:
    """Holds state for a single loaded GitHub repository."""

    def __init__(self):
        self.repo_path: Optional[Path] = None
        self._temp_dir: Optional[str] = None
        self.repo_map: str = ""
        self.file_index: dict[str, str] = {}
        self.readme: str = ""
        self.stats: dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_repo(self, url: str, token: Optional[str] = None) -> dict:
        """Shallow-clone *url* and build an in-memory index.

        Returns a dict with keys: success (bool), message (str), stats (dict).
        """
        url = (url or "").strip()
        if not url:
            return {"success": False, "message": "No URL provided.", "stats": {}}

        # Inject token for private repos
        clone_url = url
        if token:
            # https://user:token@github.com/...
            clone_url = url.replace("https://", f"https://oauth2:{token.strip()}@")

        # Clean up any previous session
        self._cleanup()

        self._temp_dir = tempfile.mkdtemp(prefix="gizmo_repo_")
        dest = Path(self._temp_dir) / "repo"

        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--single-branch", clone_url, str(dest)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            self._cleanup()
            err = result.stderr or result.stdout
            return {"success": False, "message": f"Clone failed: {err.strip()}", "stats": {}}

        self.repo_path = dest
        self._build_index()
        return {"success": True, "message": "Repository loaded successfully.", "stats": self.stats}

    def get_file_content(self, filepath: str) -> str:
        """Return the content of *filepath* relative to the repo root."""
        if not self.repo_path:
            return ""
        full = self.repo_path / filepath
        try:
            return full.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return f"Error reading file: {exc}"

    def list_files(self) -> list[str]:
        """Return sorted list of indexed file paths (relative)."""
        return sorted(self.file_index.keys())

    def search_code(self, query: str) -> list[str]:
        """Very simple substring search across indexed files.

        Returns a list of relative file paths that contain *query*.
        """
        query_lower = query.lower()
        return [
            path for path, content in self.file_index.items()
            if query_lower in content.lower()
        ][:20]

    def build_context(self, user_question: str, selected_file: Optional[str] = None) -> str:
        """Build a context string combining repo map, README, and (optionally) a file."""
        parts = []
        if self.repo_map:
            parts.append(f"## Repository Map\n{self.repo_map}")
        if self.readme:
            parts.append(f"## README\n{self.readme[:3000]}")
        if selected_file and selected_file in self.file_index:
            content = self.file_index[selected_file][:8000]
            parts.append(f"## File: {selected_file}\n```\n{content}\n```")
        if user_question:
            parts.append(f"## Question\n{user_question}")
        return "\n\n".join(parts)

    def cleanup(self):
        """Remove temporary clone directory."""
        self._cleanup()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cleanup(self):
        if self._temp_dir and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        self._temp_dir = None
        self.repo_path = None
        self.repo_map = ""
        self.file_index = {}
        self.readme = ""
        self.stats = {}

    def _build_index(self):
        """Walk repo tree and populate file_index, repo_map, readme, stats."""
        if not self.repo_path:
            return

        file_count = 0
        language_counts: dict[str, int] = {}
        tree_lines: list[str] = []

        for root, dirs, files in os.walk(self.repo_path):
            # Skip hidden / venv / node_modules directories
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".") and d not in ("node_modules", "__pycache__", "venv", ".venv", "dist", "build")
            ]
            rel_root = Path(root).relative_to(self.repo_path)
            depth = len(rel_root.parts)
            indent = "  " * depth

            for filename in sorted(files):
                if file_count >= _MAX_FILES:
                    break
                full_path = Path(root) / filename
                rel_path = str(full_path.relative_to(self.repo_path))
                ext = Path(filename).suffix.lower()

                tree_lines.append(f"{indent}{filename}")
                language_counts[ext or "other"] = language_counts.get(ext or "other", 0) + 1
                file_count += 1

                if ext in _TEXT_EXTENSIONS or filename.lower() in ("dockerfile", "makefile"):
                    try:
                        text = full_path.read_text(encoding="utf-8", errors="replace")
                        self.file_index[rel_path] = text
                        if filename.lower() in ("readme.md", "readme.rst", "readme.txt"):
                            self.readme = text
                    except Exception:
                        pass

        total_size_mb = sum(
            f.stat().st_size for f in self.repo_path.rglob("*") if f.is_file()
        ) / (1024 * 1024)

        self.repo_map = "\n".join(tree_lines[:500])  # cap to 500 lines for prompt
        self.stats = {
            "files": file_count,
            "languages": language_counts,
            "size_mb": round(total_size_mb, 2),
        }
        if total_size_mb > _MAX_SIZE_MB:
            self.stats["warning"] = f"Repository is large ({total_size_mb:.0f} MB). Some files may have been skipped."
