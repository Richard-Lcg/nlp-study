from __future__ import annotations

from typing import Optional

from engine.config import GameConfig, Role, GamePhase, ActionType, ROLE_CN
from engine.engine import GameEngine
from engine.game_state import GameState
from agents import AgentRegistry, AgentType
from agents.base import Agent


class GameRunner:
    """游戏运行器：协调引擎和 Agent，驱动对局"""

    NIGHT_PHASES = [
        (Role.GUARD, GamePhase.NIGHT_GUARD),
        (Role.WEREWOLF, GamePhase.NIGHT_WEREWOLF),
        (Role.SEER, GamePhase.NIGHT_SEER),
        (Role.WITCH, GamePhase.NIGHT_WITCH),
    ]

    def __init__(self, config: GameConfig, agent_type: AgentType = AgentType.RANDOM):
        self.config = config
        self.engine = GameEngine(config)
        self.registry = AgentRegistry()
        self.registry.set_agent_type(agent_type)
        self.agents: dict[int, Agent] = {}
        self.game_over = False

    def setup(self, player_names: list[str] | None = None):
        if player_names is None:
            player_names = [f"Player{i}" for i in range(self.config.num_players)]

        state = self.engine.init_game(player_names)

        for player in state.players:
            agent = self.registry.create_agent(player.player_id, player.name, player.role)
            self.agents[player.player_id] = agent

        self.engine.on_phase_change(self._on_phase_change)
        return state

    def _on_phase_change(self, state: Optional[GameState]):
        if state and state.phase == GamePhase.GAME_OVER:
            self.game_over = True

    def _sync_agents_alive(self, state: GameState):
        """用游戏状态同步所有 Agent 的生死状态"""
        for pid, agent in self.agents.items():
            player = state.get_player(pid)
            agent.is_alive = player is not None and player.is_alive

    def run_night_phase(self, state: GameState):
        state.add_log(GamePhase.NIGHT_GUARD, "=== 夜晚来临 ===")

        for role, phase in self.NIGHT_PHASES:
            state.phase = phase
            players_with_role = state.get_alive_by_role(role)

            for player in players_with_role:
                agent = self.agents.get(player.player_id)
                if not agent:
                    continue

                self._sync_agents_alive(state)
                available = self.engine.get_available_actions(player.player_id)
                if not available:
                    continue

                night_info = self.engine.get_night_info(player.player_id)
                decisions = agent.on_night(state, available, night_info)

                for action_type, target_id in decisions:
                    self.engine.submit_night_action(player.player_id, action_type, target_id)

            if role == Role.WITCH:
                break

        # 一次性结算整个夜晚
        deaths = self.engine.resolve_night()
        self._sync_agents_alive(state)

        if deaths:
            for dead_id in deaths:
                dead = state.get_player(dead_id)
                name = dead.name if dead else "?"
                state.add_log(GamePhase.DAY_DISCUSSION, f"昨晚 {name}（玩家 {dead_id}[{ROLE_CN.get(dead.role, '?')}]）死了")
        else:
            state.add_log(GamePhase.DAY_DISCUSSION, "昨晚是平安夜")

        return deaths

    def run_day_phase(self, state: GameState):
        state.phase = GamePhase.DAY_DISCUSSION
        state.add_log(GamePhase.DAY_DISCUSSION, "=== 白天讨论开始 ===")

        discussion_order = self._get_discussion_order(state)

        for player_id in discussion_order:
            agent = self.agents.get(player_id)
            if not agent or not agent.is_alive:
                continue
            speech = agent.on_discussion(state)
            state.add_log(GamePhase.DAY_DISCUSSION, f"玩家 {player_id}[{ROLE_CN.get(agent.role, '?')}]: {speech}")

        state.phase = GamePhase.DAY_VOTE
        state.votes = {}
        state.add_log(GamePhase.DAY_VOTE, "=== 投票环节 ===")

        for agent in self.registry.get_alive_agents(state):
            if not agent.is_alive:
                continue
            target = agent.on_vote(state)
            if target >= 0:
                self.engine.submit_vote(agent.player_id, target)

        eliminated = self.engine.resolve_day()
        if eliminated is not None:
            player = state.get_player(eliminated)
            name = player.name if player else "?"
            role = ROLE_CN.get(player.role, "?") if player else "?"
            state.add_log(GamePhase.DAY_VOTE, f"玩家 {eliminated}（{name}）[{role}] 被放逐")
            self._sync_agents_alive(state)

    def run_game(self, player_names: list[str] | None = None) -> GameState:
        state = self.setup(player_names)
        self._print_game_start(state)

        round_count = 0
        while not self.game_over and round_count < 99:
            round_count += 1
            self._print_round_header(state)

            self.run_night_phase(state)
            if self._check_game_over():
                break

            self.run_day_phase(state)
            if self._check_game_over():
                break

            # 重置回合状态
            state.eliminated_this_round = None
            state.votes = {}
            state.night_deaths = []
            state.night_kill_target = None
            for p in state.players:
                p.protected = False
                p.poisoned = False

        return state

    def _check_game_over(self) -> bool:
        winner = self.engine.check_game_over()
        if winner:
            self._print_result()
            return True
        return False

    def _get_discussion_order(self, state: GameState) -> list[int]:
        import random
        alive = state.get_alive()
        order = [p.player_id for p in alive]
        random.shuffle(order)
        return order

    def _print_game_start(self, state: GameState):
        print("=" * 50)
        print("狼人杀游戏开始！")
        print(f"玩家人数: {self.config.num_players}")
        print("-" * 30)
        for p in state.players:
            print(f"玩家 {p.player_id}: {p.name} → {p.role.value}")
        print("=" * 50)

    def _print_round_header(self, state: GameState):
        print(f"\n{'=' * 50}")
        print(f"第 {state.round} 回合")
        alive = state.get_alive()
        print(f"存活: {[f'{p.player_id}({p.name})' for p in alive]}")
        print(f"{'=' * 50}")

    def _print_result(self):
        state = self.engine.state
        if not state:
            return
        print(f"\n{'=' * 50}")
        print(f"游戏结束！{state.winner} 获胜！")
        print(f"存活玩家:")
        for p in state.get_alive():
            print(f"  {p.name}（{p.role.value}）")
        print(f"{'=' * 50}")
