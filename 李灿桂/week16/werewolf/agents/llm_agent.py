from __future__ import annotations

import json
import re
from typing import Optional

from engine.config import ActionType, GamePhase, Role, ROLE_CN
from engine.game_state import GameState
from llm.client import LLMClient
from llm.prompts import PromptBuilder
from .base import Agent


class LLMAgent(Agent):
    """LLM Agent：基于大语言模型的智能角色"""

    def __init__(self, player_id: int, name: str, role: Role, llm_client: LLMClient | None = None):
        super().__init__(player_id, name, role)
        self.llm = llm_client or LLMClient()
        self.prompt_builder = PromptBuilder()

    def on_night(self, state, available_actions, night_info) -> list[tuple[ActionType, int]]:
        if not available_actions:
            return []

        system_prompt = self.prompt_builder.build_system_prompt(self.role)
        observation = self.observe(state)
        night_prompt = self.prompt_builder.build_night_prompt(
            role=self.role,
            observation=observation,
            night_info=night_info,
            available_actions=available_actions,
            memory=self.get_memory(),
        )

        response = self.llm.chat(system_prompt, night_prompt)

        decisions = self._parse_night_actions(response, available_actions)
        for action_type, target in decisions:
            self.remember(f"夜晚行动: {action_type.value} → 玩家 {target}")
        return decisions

    def on_discussion(self, state) -> str:
        system_prompt = self.prompt_builder.build_system_prompt(self.role)
        observation = self.observe(state)
        discussion_prompt = self.prompt_builder.build_discussion_prompt(
            role=self.role,
            observation=observation,
            memory=self.get_memory(),
        )

        response = self.llm.chat(system_prompt, discussion_prompt)
        speech = self._clean_speech(response)
        self.remember(f"发言: {speech}")
        return speech

    def on_vote(self, state) -> int:
        system_prompt = self.prompt_builder.build_system_prompt(self.role)
        observation = self.observe(state)
        vote_prompt = self.prompt_builder.build_vote_prompt(
            role=self.role,
            observation=observation,
            memory=self.get_memory(),
        )

        response = self.llm.chat(system_prompt, vote_prompt)
        target = self._parse_vote(response, state)
        self.remember(f"投票给玩家 {target}")
        return target

    def on_hunter_shot(self, state) -> Optional[int]:
        system_prompt = self.prompt_builder.build_system_prompt(self.role)
        observation = self.observe(state)
        prompt = self.prompt_builder.build_hunter_prompt(observation)
        response = self.llm.chat(system_prompt, prompt)
        target = self._parse_vote(response, state)
        if target >= 0:
            self.remember(f"猎人开枪: → 玩家 {target}")
            return target
        return None

    def on_last_words(self, state) -> str:
        return f"我是{ROLE_CN.get(self.role, '?')}，大家保重。"

    def _parse_night_actions(self, response: str, available: list[tuple[ActionType, list[int]]]) -> list[tuple[ActionType, int]]:
        """解析 LLM 返回的夜晚行动，优先从回复中提取目标，失败则随机选择"""
        import random as _random
        decisions = []
        for action_type, targets in available:
            if not targets:
                continue
            target = None
            # 尝试从 LLM 回复中解析目标编号
            nums_in_response = re.findall(r'(\d+)\s*[号#]?', response)
            for n in nums_in_response:
                pid = int(n)
                if pid in targets:
                    target = pid
                    break
            if target is None:
                target = _random.choice(targets)
            decisions.append((action_type, target))
        return decisions

    def _parse_vote(self, response: str, state) -> int:
        """解析投票目标"""
        match = re.search(r'(?:vote|target|投票)[:\s]*(\d+)', response, re.IGNORECASE)
        if match:
            target_id = int(match.group(1))
            if state.get_player(target_id):
                return target_id

        # fallback: 找第一个数字
        nums = re.findall(r'\d+', response)
        if nums:
            return int(nums[0])
        return -1

    def _clean_speech(self, response: str) -> str:
        return response.strip().strip('"').strip("'")
