from __future__ import annotations

from typing import Optional
from engine.config import Role
from .base import Agent, AgentType
from .random_agent import RandomAgent


class AgentRegistry:
    """Agent 注册表：管理 Agent 创建和角色分配"""

    def __init__(self):
        self._agents: dict[int, Agent] = {}
        self._agent_type: AgentType = AgentType.RANDOM

    def set_agent_type(self, agent_type: AgentType):
        self._agent_type = agent_type

    def create_agent(self, player_id: int, name: str, role: Role) -> Agent:
        """根据当前类型创建 Agent"""
        if self._agent_type == AgentType.LLM:
            from .llm_agent import LLMAgent
            agent = LLMAgent(player_id, name, role)
        else:
            agent = RandomAgent(player_id, name, role)
        self._agents[player_id] = agent
        return agent

    def get_agent(self, player_id: int) -> Optional[Agent]:
        return self._agents.get(player_id)

    def get_all_agents(self) -> list[Agent]:
        return list(self._agents.values())

    def get_alive_agents(self, state) -> list[Agent]:
        return [a for a in self._agents.values() if a.is_alive]
