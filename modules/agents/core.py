from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class AgentResult:
    output: str
    notes: List[str]


class PlannerAgent:
    def run(self, user_prompt: str) -> AgentResult:
        steps = [
            "understand request",
            "collect context",
            "run tools if needed",
            "draft answer",
            "review answer",
        ]
        return AgentResult(output="\n".join([f"- {s}" for s in steps]), notes=["planner complete"])


class ToolAgent:
    def __init__(self, tools: Dict):
        self.tools = tools

    def run(self, user_prompt: str) -> AgentResult:
        notes = []
        if "calculate" in user_prompt.lower():
            expr = user_prompt.split("calculate", 1)[-1].strip()
            r = self.tools["calculator"].execute(expression=expr)
            notes.append(f"calculator: {r}")
        return AgentResult(output="Tool phase finished", notes=notes)


class WriterAgent:
    def run(self, user_prompt: str, plan: str, tool_notes: List[str]) -> AgentResult:
        body = f"Plan:\n{plan}\n\nAnswer draft for: {user_prompt}\n"
        if tool_notes:
            body += "\nTool notes:\n" + "\n".join(tool_notes)
        return AgentResult(output=body, notes=["writer complete"])


class CriticAgent:
    def run(self, draft: str) -> AgentResult:
        improved = draft + "\n\n[Critic] Added clarity and final checks."
        return AgentResult(output=improved, notes=["critic complete"])
