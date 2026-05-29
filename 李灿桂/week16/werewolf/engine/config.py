from enum import Enum


class Role(Enum):
    VILLAGER = "villager"
    WEREWOLF = "werewolf"
    SEER = "seer"
    WITCH = "witch"
    HUNTER = "hunter"
    GUARD = "guard"


class GamePhase(Enum):
    NIGHT_WEREWOLF = "night_werewolf"       # 狼人杀人
    NIGHT_SEER = "night_seer"               # 预言家验人
    NIGHT_WITCH = "night_witch"             # 女巫救人/毒人
    NIGHT_GUARD = "night_guard"             # 守卫守护
    DAY_DISCUSSION = "day_discussion"       # 白天讨论
    DAY_VOTE = "day_vote"                   # 投票放逐
    DAY_LAST_WORDS = "day_last_words"       # 遗言
    GAME_OVER = "game_over"                 # 游戏结束


class ActionType(Enum):
    KILL = "kill"
    INVESTIGATE = "investigate"
    SAVE = "save"
    POISON = "poison"
    PROTECT = "protect"
    SHOOT = "shoot"
    VOTE = "vote"


# 标准板子配置
ROLE_SETUPS = {
    9: {
        Role.WEREWOLF: 3,
        Role.VILLAGER: 3,
        Role.SEER: 1,
        Role.WITCH: 1,
        Role.HUNTER: 1,
    },
    12: {
        Role.WEREWOLF: 4,
        Role.VILLAGER: 4,
        Role.SEER: 1,
        Role.WITCH: 1,
        Role.HUNTER: 1,
        Role.GUARD: 1,
    },
}


# 角色中文名映射
ROLE_CN = {
    Role.VILLAGER: "村民",
    Role.WEREWOLF: "狼人",
    Role.SEER: "预言家",
    Role.WITCH: "女巫",
    Role.HUNTER: "猎人",
    Role.GUARD: "守卫",
}


class GameConfig:
    def __init__(
        self,
        num_players: int = 9,
        role_setup: dict[Role, int] | None = None,
        discussion_timeout: int = 120,
        vote_timeout: int = 60,
        max_consecutive_no_elim: int = 3,
        last_words_enabled: bool = True,
    ):
        self.num_players = num_players
        self.role_setup = role_setup or ROLE_SETUPS.get(num_players)
        if self.role_setup is None:
            raise ValueError(f"Unsupported player count: {num_players}. Supported: {list(ROLE_SETUPS.keys())}")
        self.discussion_timeout = discussion_timeout
        self.vote_timeout = vote_timeout
        self.max_consecutive_no_elim = max_consecutive_no_elim
        self.last_words_enabled = last_words_enabled
        self.total_players = sum(self.role_setup.values())
        if self.total_players != num_players:
            raise ValueError(f"Role setup total ({self.total_players}) != num_players ({num_players})")
