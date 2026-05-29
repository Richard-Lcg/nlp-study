from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum, auto
from typing import Optional

from engine.config import ActionType, GamePhase, Role
from engine.game_state import GameState, Player


class AgentType(StrEnum):
    RANDOM = auto()
    LLM = auto()


class Agent(ABC):
    """Agent 基类：所有角色 Agent 的通用接口"""

    def __init__(self, player_id: int, name: str, role: Role):
        self.player_id = player_id
        self.name = name
        self.role = role
        self.is_alive = True
        self.memory: list[str] = []  # 历史记忆（发言、行动等）

    @abstractmethod
    def on_night(self, state: GameState, available_actions: list[tuple[ActionType, list[int]]], night_info: dict) -> list[tuple[ActionType, int]]:
        """夜晚阶段决策，返回 (行动类型, 目标ID) 列表"""
        ...

    @abstractmethod
    def on_discussion(self, state: GameState) -> str:
        """白天讨论阶段发言"""
        ...

    @abstractmethod
    def on_vote(self, state: GameState) -> int:
        """白天投票阶段，返回要投票的玩家 ID（-1 表示弃票）"""
        ...

    @abstractmethod
    def on_hunter_shot(self, state: GameState) -> Optional[int]:
        """猎人被放逐时开枪，返回目标 ID 或 None"""
        ...

    @abstractmethod
    def on_last_words(self, state: GameState) -> str:
        """遗言"""
        ...

    def observe(self, state: GameState) -> dict:
        """获取该 Agent 视角的游戏状态（信息受限）"""
        player = state.get_player(self.player_id)
        alive = state.get_alive()
        public = {
            "round": state.round,
            "phase": state.phase.value,
            "alive_players": [{"id": p.player_id, "name": p.name, "is_sheriff": p.is_sheriff} for p in alive],
            "alive_count": len(alive),
            "total_players": len(state.players),
            "day_votes": dict(state.votes) if state.phase == GamePhase.DAY_VOTE else {},
            "eliminated_today": state.eliminated_this_round,
        }

        # 角色私有信息
        if player:
            public["my_role"] = player.role.value
            public["my_id"] = self.player_id

        # 狼人看到队友
        if self.role == Role.WEREWOLF:
            public["werewolf_teammates"] = [
                {"id": p.player_id, "name": p.name}
                for p in alive if p.role == Role.WEREWOLF and p.player_id != self.player_id
            ]

        # 预言家看到历史查验
        if self.role == Role.SEER:
            seen = {}
            for pid, result in state.seen_roles.items():
                label = "好人" if result == "good" else "狼人"
                seen[str(pid)] = label
            public["seen_results"] = seen

        # 女巫看到解药毒药状态
        if self.role == Role.WITCH:
            public["save_potion_used"] = state.witch_state.save_potion_used
            public["poison_potion_used"] = state.witch_state.poison_potion_used

        return public

    def remember(self, event: str):
        """记录事件到记忆"""
        self.memory.append(f"[第{len(self.memory) + 1}轮] {event}")

    def get_memory(self) -> str:
        """返回格式化的记忆文本"""
        return "\n".join(self.memory[-20:]) if self.memory else "暂无记录"
