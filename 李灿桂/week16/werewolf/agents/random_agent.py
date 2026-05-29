from __future__ import annotations

import random
from typing import Optional

from engine.config import ActionType, Role
from engine.game_state import GameState
from .base import Agent


class RandomAgent(Agent):
    """随机 Agent：用于测试游戏引擎的基准实现"""

    def on_night(self, state, available_actions, night_info) -> list[tuple[ActionType, int]]:
        decisions = []
        for action_type, targets in available_actions:
            if targets:
                target = random.choice(targets)
                decisions.append((action_type, target))
                self.remember(f"夜晚行动: {action_type.value} → 玩家 {target}")
        return decisions

    def on_discussion(self, state) -> str:
        speech = f"我是好人，我觉得{random.choice(['1号', '2号', '3号', '4号', '5号'])}有点可疑。"
        self.remember(f"发言: {speech}")
        return speech

    def on_vote(self, state) -> int:
        alive = state.get_alive()
        candidates = [p.player_id for p in alive if p.player_id != self.player_id]
        if not candidates:
            return -1
        target = random.choice(candidates)
        self.remember(f"投票给玩家 {target}")
        return target

    def on_hunter_shot(self, state) -> Optional[int]:
        alive = state.get_alive()
        if not alive:
            return None
        target = random.choice(alive).player_id
        self.remember(f"猎人开枪: → 玩家 {target}")
        return target

    def on_last_words(self, state) -> str:
        words = f"我走了，大家加油。"
        self.remember(f"遗言: {words}")
        return words
