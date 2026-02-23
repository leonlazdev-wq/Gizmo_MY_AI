from __future__ import annotations

from modules.agents.core import CriticAgent, PlannerAgent, ToolAgent, WriterAgent
from modules.tools import default_tools


class AgentOrchestrator:
    def __init__(self):
        self.planner = PlannerAgent()
        self.tooler = ToolAgent(default_tools())
        self.writer = WriterAgent()
        self.critic = CriticAgent()

    def run(self, user_prompt: str) -> str:
        plan = self.planner.run(user_prompt)
        tool = self.tooler.run(user_prompt)
        draft = self.writer.run(user_prompt, plan.output, tool.notes)
        final = self.critic.run(draft.output)
        return final.output
