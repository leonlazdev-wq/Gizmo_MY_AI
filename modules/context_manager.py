"""Token usage and pruning helpers for chat history."""

from __future__ import annotations

from typing import Any, Dict, List

try:
    import tiktoken
except Exception:  # pragma: no cover
    tiktoken = None


class ContextManager:
    """Analyze and prune chat context based on approximate token usage."""

    def __init__(self, model_name: str = "gpt-3.5-turbo", max_tokens: int = 4096) -> None:
        self.max_tokens = max_tokens
        self.pinned_messages: List[int] = []
        self._encoding = None
        if tiktoken is not None:
            try:
                self._encoding = tiktoken.encoding_for_model(model_name)
            except Exception:
                try:
                    self._encoding = tiktoken.get_encoding("cl100k_base")
                except Exception:
                    self._encoding = None

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        if self._encoding is not None:
            return len(self._encoding.encode(text))
        return max(1, len(text) // 4)

    def analyze_context(self, history: Dict[str, Any]) -> Dict[str, Any]:
        visible = history.get("visible", [])
        total_tokens = 0
        message_breakdown = []
        for message in visible:
            user = str(message[0] or "")
            assistant = str(message[1] or "")
            user_tokens = self.count_tokens(user)
            assistant_tokens = self.count_tokens(assistant)
            pair_total = user_tokens + assistant_tokens
            total_tokens += pair_total
            message_breakdown.append({"user": user_tokens, "assistant": assistant_tokens, "total": pair_total})

        context_pct = (total_tokens / self.max_tokens) * 100 if self.max_tokens else 0
        remaining = max(0, self.max_tokens - total_tokens)
        return {
            "total_tokens": total_tokens,
            "message_breakdown": message_breakdown,
            "context_percentage": context_pct,
            "remaining_tokens": remaining,
        }

    def pin_message(self, history: Dict[str, Any], msg_index: int) -> str:
        visible = history.get("visible", [])
        if msg_index < 0 or msg_index >= len(visible):
            return "❌ Invalid message index"
        if msg_index not in self.pinned_messages:
            self.pinned_messages.append(msg_index)
            return f"📌 Pinned message {msg_index + 1}"
        return f"ℹ️ Message {msg_index + 1} already pinned"

    def smart_prune(self, history: Dict[str, Any], target_tokens: int | None = None) -> tuple[Dict[str, Any], str]:
        target = target_tokens or int(self.max_tokens * 0.7)
        visible = history.get("visible", [])
        internal = history.get("internal", [])

        keep_indices = set(i for i in self.pinned_messages if 0 <= i < len(visible))
        current_tokens = sum(self.count_tokens(str(visible[i][0] or "") + str(visible[i][1] or "")) for i in keep_indices)

        for index in range(len(visible) - 1, -1, -1):
            if index in keep_indices:
                continue
            msg_tokens = self.count_tokens(str(visible[index][0] or "") + str(visible[index][1] or ""))
            if current_tokens + msg_tokens <= target:
                keep_indices.add(index)
                current_tokens += msg_tokens

        ordered = sorted(keep_indices)
        pruned = {
            "visible": [visible[i] for i in ordered],
            "internal": [internal[i] for i in ordered if i < len(internal)],
            "metadata": history.get("metadata", {}),
        }
        removed = len(visible) - len(pruned["visible"])
        return pruned, f"✂️ Pruned {removed} message(s); kept {len(pruned['visible'])}"

    def render_context_html(self, analysis: Dict[str, Any]) -> str:
        pct = min(100, max(0, analysis["context_percentage"]))
        color = "#4CAF50" if pct < 60 else "#FFC107" if pct < 85 else "#F44336"
        return (
            "<div style='text-align:center'>"
            f"<div style='font-size:24px;font-weight:bold'>{analysis['total_tokens']} / {self.max_tokens}</div>"
            "<div style='font-size:12px;color:#888'>tokens used</div>"
            "<div style='width:100%;height:10px;background:#ddd;border-radius:5px;margin-top:10px;'>"
            f"<div style='width:{pct:.1f}%;height:100%;background:{color};border-radius:5px;transition:width .3s'></div>"
            "</div></div>"
        )
