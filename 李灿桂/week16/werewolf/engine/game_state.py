from __future__ import annotations

from dataclasses import dataclass, field
from enum import auto, StrEnum
from typing import Optional

from .config import Role, GamePhase, ActionType


class PlayerStatus(StrEnum):
    ALIVE = auto()
    DEAD = auto()
    DYING = auto()  # 被投票放逐待发表遗言


@dataclass
class Player:
    player_id: int
    name: str
    role: Role
    status: PlayerStatus = PlayerStatus.ALIVE
    is_sheriff: bool = False  # 警长
    protected: bool = False  # 当晚是否被守卫守护
    poisoned: bool = False   # 是否被女巫毒杀
    vote_record: list[int] = field(default_factory=list)  # 每轮投票的目标

    @property
    def is_alive(self) -> bool:
        return self.status == PlayerStatus.ALIVE

    @property
    def can_act(self) -> bool:
        return self.status in (PlayerStatus.ALIVE, PlayerStatus.DYING)


@dataclass
class NightAction:
    actor_id: int
    action_type: ActionType
    target_id: int
    round: int
    resolved: bool = False
    blocked: bool = False  # 是否因守护等被阻挡


@dataclass
class GameLog:
    round: int
    phase: GamePhase
    message: str
    data: dict = field(default_factory=dict)


class WitchState:
    """女巫状态：记录解药和毒药的使用情况"""
    def __init__(self):
        self.save_potion_used = False
        self.poison_potion_used = False
        self.night_save_target: Optional[int] = None  # 当晚被杀目标（女巫可见）
        self.night_poison_target: Optional[int] = None


class GameState:
    def __init__(self, players: list[Player], config):
        self.players = players
        self.config = config
        self.round = 0
        self.phase: GamePhase = GamePhase.NIGHT_WEREWOLF
        self.alive_players: list[Player] = [p for p in players if p.is_alive]
        self.night_actions: list[NightAction] = []
        self.logs: list[GameLog] = []
        self.witch_state = WitchState()
        self.seen_roles: dict[int, str] = {}  # 预言家查验结果: target_id -> "good" | "werewolf"
        self.votes: dict[int, int] = {}  # voter_id -> target_id
        self.consecutive_no_elim = 0
        self.eliminated_this_round: Optional[int] = None
        self.night_kill_target: Optional[int] = None
        self.night_deaths: list[int] = field(default_factory=list)  # 一夜可能多死（刀+毒）
        self.discussion_order: list[int] = []  # 发言顺序（从死者旁边开始）
        self.winner: Optional[str] = None  # "werewolf" or "village"

    def get_player(self, player_id: int) -> Optional[Player]:
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None

    def get_alive(self) -> list[Player]:
        return [p for p in self.players if p.is_alive]

    def get_alive_by_role(self, role: Role) -> list[Player]:
        return [p for p in self.players if p.is_alive and p.role == role]

    def get_visible_players(self, player_id: int) -> list[Player]:
        """返回某玩家可以看到的玩家列表（存活的匿名玩家）"""
        return self.get_alive()

    def add_log(self, phase: GamePhase, message: str, data: dict | None = None):
        self.logs.append(GameLog(
            round=self.round,
            phase=phase,
            message=message,
            data=data or {},
        ))

    @property
    def is_night(self) -> bool:
        return self.phase in (
            GamePhase.NIGHT_WEREWOLF,
            GamePhase.NIGHT_SEER,
            GamePhase.NIGHT_WITCH,
            GamePhase.NIGHT_GUARD,
        )
