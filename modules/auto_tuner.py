"""Auto tuning profiles for generation parameters."""

from __future__ import annotations

from typing import Dict


class ParameterAutoTuner:
    PROFILES: Dict[str, Dict] = {
        "creative_writing": {
            "name": "🎨 Creative Writing",
            "description": "Maximizes creativity and variety",
            "params": {"temperature": 1.2, "top_p": 0.95, "top_k": 50, "repetition_penalty": 1.15, "min_p": 0.05},
            "use_cases": ["story", "poetry", "creative", "brainstorm"],
        },
        "technical_accuracy": {
            "name": "🔬 Technical Accuracy",
            "description": "Prioritizes factual accuracy and coherence",
            "params": {"temperature": 0.3, "top_p": 0.85, "top_k": 20, "repetition_penalty": 1.05, "min_p": 0.1},
            "use_cases": ["coding", "technical", "analysis", "debug"],
        },
        "conversational": {
            "name": "💬 Conversational",
            "description": "Natural dialogue, balanced creativity",
            "params": {"temperature": 0.7, "top_p": 0.9, "top_k": 40, "repetition_penalty": 1.1, "min_p": 0.05},
            "use_cases": ["chat", "q&a", "conversation", "assistant"],
        },
        "speed_optimized": {
            "name": "⚡ Speed Optimized",
            "description": "Faster generation with concise outputs",
            "params": {"temperature": 0.5, "top_p": 0.9, "top_k": 20, "max_new_tokens": 256},
            "use_cases": ["quick", "summary", "speed", "fast"],
        },
    }

    def suggest_parameters(self, user_goal: str) -> Dict:
        goal = (user_goal or "").lower()
        best_key = "conversational"
        best_score = -1.0
        for key, profile in self.PROFILES.items():
            score = sum(1 for token in profile["use_cases"] if token in goal)
            if score > best_score:
                best_score = score
                best_key = key
        return self.PROFILES[best_key]

    def compare_profiles(self) -> str:
        rows = []
        for profile in self.PROFILES.values():
            p = profile["params"]
            rows.append(
                f"<tr><td><b>{profile['name']}</b><br/><small>{profile['description']}</small></td>"
                f"<td>{p.get('temperature', '-')}</td><td>{p.get('top_p', '-')}</td><td>{p.get('top_k', '-')}</td>"
                f"<td>{p.get('repetition_penalty', '-')}</td><td>{', '.join(profile['use_cases'])}</td></tr>"
            )
        return (
            "<table style='width:100%;border-collapse:collapse'>"
            "<thead><tr><th>Profile</th><th>Temp</th><th>Top-p</th><th>Top-k</th><th>Rep.</th><th>Use cases</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )


def format_profile(profile: Dict) -> str:
    params = profile.get("params", {})
    items = "\n".join([f"- **{k}**: `{v}`" for k, v in params.items()])
    return f"### {profile.get('name')}\n{profile.get('description')}\n\n{items}"
