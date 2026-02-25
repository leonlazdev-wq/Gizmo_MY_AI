"""Hugging Face model search and download helpers."""

from __future__ import annotations

import html
import subprocess
from typing import Dict, List

import requests


class ModelHub:
    def __init__(self) -> None:
        self.hf_api = "https://huggingface.co/api"

    def search_models(self, query: str, filters: Dict | None = None) -> List[Dict]:
        if not (query or "").strip():
            return []
        params = {"search": query.strip(), "sort": "downloads", "limit": 30, "filter": "text-generation"}
        try:
            response = requests.get(f"{self.hf_api}/models", params=params, timeout=20)
            response.raise_for_status()
            models = response.json()
        except Exception:
            return []

        size = (filters or {}).get("size", "All sizes")
        quant_filters = set((filters or {}).get("quantization", []))
        filtered = []
        for model in models:
            model_id = str(model.get("id", "")).lower()
            if quant_filters and not any(q.lower() in model_id for q in quant_filters):
                continue
            est = self.estimate_model_size(model)
            if size == "Small (<5GB)" and est >= 5:
                continue
            if size == "Medium (5-20GB)" and not (5 <= est <= 20):
                continue
            if size == "Large (>20GB)" and est <= 20:
                continue
            filtered.append(model)
        return filtered

    def format_model_results(self, models: List[Dict]) -> str:
        if not models:
            return "<p>No models found.</p>"
        blocks = []
        for model in models[:20]:
            model_id = str(model.get("id", ""))
            downloads = int(model.get("downloads", 0) or 0)
            likes = int(model.get("likes", 0) or 0)
            size_gb = self.estimate_model_size(model)
            blocks.append(
                "<div style='background:#2a2a2a;border:1px solid #444;border-radius:10px;padding:12px'>"
                f"<h4 style='margin:0;color:#4CAF50'>{html.escape(model_id)}</h4>"
                f"<p style='font-size:12px;color:#aaa'>~{size_gb:.1f}GB • ⬇️ {self.format_number(downloads)} • ❤️ {likes}</p>"
                "</div>"
            )
        return "<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px'>" + "".join(blocks) + "</div>"

    @staticmethod
    def estimate_model_size(model_info: Dict) -> float:
        model_id = str(model_info.get("id", "")).lower()
        if "70b" in model_id:
            return 40.0 if "q4" in model_id else 130.0
        if "30b" in model_id or "34b" in model_id:
            return 20.0 if "q4" in model_id else 60.0
        if "13b" in model_id:
            return 8.5 if "q4" in model_id else 26.0
        if "7b" in model_id:
            return 4.5 if "q4" in model_id else 14.0
        return 0.0

    @staticmethod
    def format_number(num: int) -> str:
        if num >= 1_000_000:
            return f"{num / 1_000_000:.1f}M"
        if num >= 1_000:
            return f"{num / 1_000:.1f}K"
        return str(num)

    def download_model(self, model_id: str) -> str:
        clean = (model_id or "").strip()
        if not clean:
            return "❌ Enter a model id like TheBloke/Mistral-7B-Instruct-v0.2-GGUF"
        try:
            proc = subprocess.run(["python", "download-model.py", clean], capture_output=True, text=True, timeout=1200)
            if proc.returncode == 0:
                return f"✅ Download finished for {clean}"
            return f"❌ Download failed for {clean}\n{proc.stderr[-800:]}"
        except Exception as exc:
            return f"❌ Download error: {exc}"

    def get_model_use_cases(self, model_id: str) -> Dict:
        """Return use-case tags for a model.

        First checks a local lookup table, then falls back to the Hugging Face
        model card tags when the model is not in the table.
        """
        # Local lookup: well-known models and their primary use cases
        _LOCAL: Dict[str, List[str]] = {
            # Coding
            "codellama": ["Coding"],
            "deepseek-coder": ["Coding"],
            "qwen2.5-coder": ["Coding"],
            "starcoder": ["Coding"],
            "wizardcoder": ["Coding"],
            # Instruction-following / chat
            "llama-3": ["Instruction following", "Chit-chat"],
            "llama-2": ["Instruction following", "Chit-chat"],
            "mistral": ["Instruction following", "Chit-chat"],
            "mixtral": ["Instruction following", "Chit-chat"],
            "phi-3": ["Instruction following", "Chit-chat"],
            "gemma": ["Instruction following", "Chit-chat"],
            "qwen2.5": ["Instruction following", "Chit-chat"],
            # Math / Science
            "deepseek-r1": ["Math/Science", "Research", "Instruction following"],
            "qwq": ["Math/Science", "Research"],
            "mathstral": ["Math/Science"],
            # Creative writing
            "creative": ["Creative writing"],
            "storywriter": ["Creative writing"],
            # Multilingual
            "bloom": ["Multilingual"],
            "aya": ["Multilingual"],
            # Research / reasoning
            "research": ["Research"],
        }

        model_lower = (model_id or "").lower()
        for key, tags in _LOCAL.items():
            if key in model_lower:
                return {"model_id": model_id, "use_cases": tags, "source": "local"}

        # Fallback: fetch tags from Hugging Face API
        try:
            response = requests.get(
                f"{self.hf_api}/models/{model_id}",
                params={"cardData": "true"},
                timeout=10,
            )
            if response.ok:
                data = response.json()
                tags = data.get("tags", []) + data.get("cardData", {}).get("tags", [])
                use_cases = []
                tag_map = {
                    "code": "Coding",
                    "math": "Math/Science",
                    "science": "Math/Science",
                    "instruct": "Instruction following",
                    "chat": "Chit-chat",
                    "creative": "Creative writing",
                    "multilingual": "Multilingual",
                    "research": "Research",
                }
                for tag in tags:
                    tag_l = tag.lower()
                    for kw, label in tag_map.items():
                        if kw in tag_l and label not in use_cases:
                            use_cases.append(label)
                if use_cases:
                    return {"model_id": model_id, "use_cases": use_cases, "source": "huggingface"}
        except Exception:
            pass

        return {"model_id": model_id, "use_cases": ["General purpose"], "source": "default"}
