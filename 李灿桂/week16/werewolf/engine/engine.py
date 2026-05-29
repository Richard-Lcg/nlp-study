from __future__ import annotations

import random
from typing import Optional, Callable

from .config import GameConfig, Role, GamePhase, ActionType, ROLE_SETUPS, ROLE_CN
from .game_state import GameState, Player, PlayerStatus, NightAction, WitchState
from .rules import Rules


class GameEngine:
    """游戏引擎：控制回合流转、行动收集与结算"""

    def __init__(self, config: GameConfig):
        self.config = config
        self.state: Optional[GameState] = None
        self._on_phase_change: list[Callable] = []  # 阶段变化回调（用于日志/UI）

    def on_phase_change(self, callback: Callable):
        self._on_phase_change.append(callback)

    def _trigger_phase_change(self):
        for cb in self._on_phase_change:
            cb(self.state)

    def init_game(self, player_names: list[str], random_seed: int | None = None):
        """初始化一局游戏"""
        if random_seed is not None:
            random.seed(random_seed)

        if len(player_names) != self.config.num_players:
            raise ValueError(f"Expected {self.config.num_players} players, got {len(player_names)}")

        # 分配角色
        roles = []
        for role, count in self.config.role_setup.items():
            roles.extend([role] * count)
        random.shuffle(roles)

        players = []
        for i, name in enumerate(player_names):
            players.append(Player(
                player_id=i,
                name=name,
                role=roles[i],
            ))

        self.state = GameState(players, self.config)
        self.state.round = 1
        self.state.phase = GamePhase.NIGHT_WEREWOLF
        self.state.add_log(GamePhase.NIGHT_WEREWOLF, "游戏开始")
        self._trigger_phase_change()
        return self.state

    def advance_phase(self):
        """进入下一阶段"""
        if self.state is None:
            return

        phase_order = [
            GamePhase.NIGHT_GUARD,
            GamePhase.NIGHT_WEREWOLF,
            GamePhase.NIGHT_SEER,
            GamePhase.NIGHT_WITCH,
            GamePhase.DAY_DISCUSSION,
            GamePhase.DAY_VOTE,
        ]

        current = self.state.phase

        if current == GamePhase.DAY_VOTE:
            # 白天投票结束 → 进入下一夜或游戏结束
            self.state.round += 1
            self.state.phase = GamePhase.NIGHT_GUARD
        elif current == GamePhase.NIGHT_WITCH:
            self.state.phase = GamePhase.DAY_DISCUSSION
            # 夜晚死亡结算
            Rules.resolve_night(self.state)
        elif current in (GamePhase.NIGHT_GUARD, GamePhase.NIGHT_SEER, GamePhase.NIGHT_WEREWOLF):
            idx = phase_order.index(current)
            self.state.phase = phase_order[idx + 1]
        elif current == GamePhase.DAY_DISCUSSION:
            self.state.phase = GamePhase.DAY_VOTE
        elif current == GamePhase.GAME_OVER:
            return

        self._trigger_phase_change()

    def get_available_actions(self, player_id: int) -> list[tuple[ActionType, list[int]]]:
        """获取某玩家在当前阶段可执行的动作"""
        state = self.state
        if state is None:
            return []

        player = state.get_player(player_id)
        if not player or not player.can_act:
            return []

        actions = []
        alive = state.get_alive()
        alive_ids = [p.player_id for p in alive]

        if state.phase == GamePhase.NIGHT_WEREWOLF and player.role == Role.WEREWOLF:
            targets = [pid for pid in alive_ids if pid != player_id and state.get_player(pid).role != Role.WEREWOLF]
            actions.append((ActionType.KILL, targets))

        if state.phase == GamePhase.NIGHT_SEER and player.role == Role.SEER:
            actions.append((ActionType.INVESTIGATE, alive_ids))

        if state.phase == GamePhase.NIGHT_WITCH and player.role == Role.WITCH:
            if Rules.can_witch_save(state):
                actions.append((ActionType.SAVE, [state.night_kill_target]))
            if Rules.can_witch_poison(state):
                alive_except_self = [pid for pid in alive_ids if pid != player_id]
                actions.append((ActionType.POISON, alive_except_self))

        if state.phase == GamePhase.NIGHT_GUARD and player.role == Role.GUARD:
            alive_except_self = [pid for pid in alive_ids if pid != player_id]
            actions.append((ActionType.PROTECT, alive_except_self))

        return actions

    def submit_night_action(self, actor_id: int, action_type: ActionType, target_id: int) -> bool:
        """提交夜间行动"""
        state = self.state
        if state is None:
            return False

        actor = state.get_player(actor_id)
        if not actor:
            return False

        if not Rules.validate_night_action(state, actor, action_type, target_id):
            return False

        # 检查该玩家本轮是否已提交过同类行动
        for existing in state.night_actions:
            if existing.round == state.round and existing.actor_id == actor_id and existing.action_type == action_type:
                return False

        action = NightAction(
            actor_id=actor_id,
            action_type=action_type,
            target_id=target_id,
            round=state.round,
        )
        state.night_actions.append(action)

        action_cn = {
            ActionType.KILL: "投票杀死",
            ActionType.INVESTIGATE: "查验身份",
            ActionType.SAVE: "用解药救活",
            ActionType.POISON: "用毒药毒杀",
            ActionType.PROTECT: "守护",
            ActionType.SHOOT: "开枪射击",
        }.get(action_type, action_type.value)
        actor_role = ROLE_CN.get(actor.role, "?") if actor else "?"
        target = state.get_player(target_id)
        target_role = ROLE_CN.get(target.role, "?") if target else "?"
        state.add_log(state.phase, f"玩家 {actor_id}[{actor_role}] {action_cn} 玩家 {target_id}[{target_role}]")

        # 女巫救人和女巫毒人不是互斥的，但女巫救了之后当晚不再能问毒人
        if action_type == ActionType.SAVE:
            state.witch_state.save_potion_used = True
        elif action_type == ActionType.POISON:
            state.witch_state.poison_potion_used = True

        return True

    def submit_vote(self, voter_id: int, target_id: int) -> bool:
        """提交白天投票"""
        state = self.state
        if state is None or state.phase != GamePhase.DAY_VOTE:
            return False

        voter = state.get_player(voter_id)
        if not voter or not voter.is_alive:
            return False

        target = state.get_player(target_id)
        if not target:
            return False

        # 允许弃票（target_id == voter_id 或 target 已死）
        state.votes[voter_id] = target_id
        voter_role = ROLE_CN.get(voter.role, "?") if voter else "?"
        target_role = ROLE_CN.get(target.role, "?") if target else "?"
        state.add_log(GamePhase.DAY_VOTE, f"玩家 {voter_id}[{voter_role}] 投票给玩家 {target_id}[{target_role}]")
        return True

    def resolve_night(self) -> list[int]:
        """结算夜晚：处理所有夜晚行动并返回死亡列表"""
        state = self.state
        if state is None:
            return []
        return Rules.resolve_night(state)

    def resolve_day(self) -> Optional[int]:
        """结算白天投票，返回被放逐的玩家 ID"""
        state = self.state
        if state is None:
            return None
        return Rules.resolve_day_vote(state)

    def check_game_over(self) -> Optional[str]:
        """检查游戏是否结束"""
        if self.state is None:
            return None
        winner = Rules.check_winner(self.state)
        if winner:
            self.state.phase = GamePhase.GAME_OVER
            self.state.winner = winner
            winner_cn = "狼人" if winner == "werewolf" else "好人" if winner == "village" else winner
            self.state.add_log(GamePhase.GAME_OVER, f"游戏结束，{winner_cn} 获胜！")
            self._trigger_phase_change()
        return winner

    def get_night_info(self, player_id: int) -> dict:
        """返回某玩家在夜晚能看到的信息"""
        state = self.state
        if state is None:
            return {}

        info = {"round": state.round}

        player = state.get_player(player_id)
        if not player:
            return info

        # 狼人：看到其他狼人
        if player.role == Role.WEREWOLF:
            info["teammates"] = [p.player_id for p in state.get_alive_by_role(Role.WEREWOLF) if p.player_id != player_id]

        # 女巫：看到今晚被杀的人
        if player.role == Role.WITCH and state.night_kill_target is not None:
            info["night_kill_target"] = state.night_kill_target

        # 预言家：历史查验结果
        if player.role == Role.SEER and state.seen_roles:
            info["seen_roles"] = {str(k): ("好人" if v == "good" else "狼人") for k, v in state.seen_roles.items()}

        return info
