from __future__ import annotations

from collections import Counter
from typing import Optional

from .config import Role, GamePhase, ActionType
from .game_state import GameState, Player, NightAction, PlayerStatus


class Rules:
    """游戏规则：胜负判定、行动合法性校验"""

    SPECIAL_ROLES = {Role.SEER, Role.WITCH, Role.HUNTER, Role.GUARD}

    @staticmethod
    def check_winner(state: GameState) -> Optional[str]:
        alive = state.get_alive()
        werewolves = [p for p in alive if p.role == Role.WEREWOLF]

        if not werewolves:
            return "village"

        # 屠边规则：狼人只需杀光所有平民 或 所有神职
        alive_villagers = [p for p in alive if p.role == Role.VILLAGER]
        alive_specials = [p for p in alive if p.role in Rules.SPECIAL_ROLES]

        if not alive_villagers or not alive_specials:
            return "werewolf"
        return None

    @staticmethod
    def validate_night_action(state: GameState, actor: Player, action_type: ActionType, target_id: int) -> bool:
        target = state.get_player(target_id)
        if not target or not target.is_alive:
            return False
        if not actor.is_alive:
            return False
        if action_type == ActionType.KILL:
            if actor.role != Role.WEREWOLF or target_id == actor.player_id:
                return False
        if action_type == ActionType.INVESTIGATE and actor.role != Role.SEER:
            return False
        if action_type == ActionType.SAVE:
            if actor.role != Role.WITCH or state.witch_state.save_potion_used:
                return False
        if action_type == ActionType.POISON:
            if actor.role != Role.WITCH or state.witch_state.poison_potion_used:
                return False
        if action_type == ActionType.PROTECT and actor.role != Role.GUARD:
            return False
        if action_type == ActionType.SHOOT and actor.role != Role.HUNTER:
            return False
        return True

    @staticmethod
    def resolve_night(state: GameState) -> list[int]:
        """结算整晚行动，返回所有死亡玩家 ID 列表"""
        round_actions = [a for a in state.night_actions if a.round == state.round and not a.resolved]

        resolved = []
        kill_votes: list[NightAction] = []
        protect_action: Optional[NightAction] = None
        poison_action: Optional[NightAction] = None

        # 分类行动
        for action in round_actions:
            if action.action_type == ActionType.PROTECT:
                protect_action = action
            elif action.action_type == ActionType.KILL:
                kill_votes.append(action)
            elif action.action_type == ActionType.POISON:
                poison_action = action
            elif action.action_type == ActionType.INVESTIGATE:
                action.resolved = True
                resolved.append(action)
                target = state.get_player(action.target_id)
                if target:
                    # 预言家只知好/坏（大拇指向上/向下），不知精确身份
                    state.seen_roles[action.target_id] = "werewolf" if target.role == Role.WEREWOLF else "good"

        # 守卫守护
        protected_id: Optional[int] = None
        if protect_action:
            protect_action.resolved = True
            resolved.append(protect_action)
            target = state.get_player(protect_action.target_id)
            if target:
                target.protected = True
                protected_id = protect_action.target_id

        # 狼人击杀：多数决
        kill_target: Optional[int] = None
        if kill_votes:
            tally = Counter(a.target_id for a in kill_votes)
            most_common = tally.most_common(2)
            if len(most_common) == 1 or most_common[0][1] > most_common[1][1]:
                kill_target = most_common[0][0]
                for a in kill_votes:
                    a.resolved = a.target_id == kill_target
                resolved.extend(a for a in kill_votes if a.resolved)

        if kill_target == protected_id:
            kill_target = None  # 守护成功

        # 女巫毒杀（独立于刀杀）
        poison_target: Optional[int] = None
        if poison_action:
            poison_action.resolved = True
            resolved.append(poison_action)
            poison_target = poison_action.target_id

        # 计算死亡列表
        deaths = set()
        if kill_target is not None:
            deaths.add(kill_target)
        if poison_target is not None:
            deaths.add(poison_target)

        for pid in deaths:
            player = state.get_player(pid)
            if player and player.is_alive:
                player.status = PlayerStatus.DEAD

        state.night_deaths = list(deaths)
        state.night_kill_target = kill_target
        return list(deaths)

    @staticmethod
    def resolve_day_vote(state: GameState) -> Optional[int]:
        votes = state.votes
        if not votes:
            state.consecutive_no_elim += 1
            return None

        tally: dict[int, int] = {}
        for target_id in votes.values():
            tally[target_id] = tally.get(target_id, 0) + 1

        max_votes = max(tally.values())
        candidates = [pid for pid, count in tally.items() if count == max_votes]

        if len(candidates) > 1 or max_votes == 0:
            state.consecutive_no_elim += 1
            return None

        eliminated = candidates[0]
        player = state.get_player(eliminated)
        if player:
            if player.role == Role.HUNTER:
                player.status = PlayerStatus.DYING
            else:
                player.status = PlayerStatus.DEAD

        state.consecutive_no_elim = 0
        state.eliminated_this_round = eliminated
        return eliminated

    @staticmethod
    def can_witch_save(state: GameState) -> bool:
        return (
            not state.witch_state.save_potion_used
            and state.night_kill_target is not None
        )

    @staticmethod
    def can_witch_poison(state: GameState) -> bool:
        return not state.witch_state.poison_potion_used
