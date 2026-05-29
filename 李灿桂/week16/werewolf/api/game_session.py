"""游戏会话管理：支持单步执行的游戏运行器"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from engine.config import GameConfig, Role, GamePhase, ROLE_CN
from agents import AgentRegistry, AgentType
from agents.base import Agent
from runner import GameRunner


def _log(msg: str):
    """带时间戳的后台日志"""
    t = time.strftime("%H:%M:%S")
    print(f"[{t}] {msg}")


class StepRunner:
    """支持单步执行的游戏运行器"""

    def __init__(self, config: GameConfig, agent_type: AgentType = AgentType.LLM):
        self.config = config
        self.runner = GameRunner(config, agent_type=agent_type)
        self.state = None
        self.step_index = 0
        self.step_labels: list[str] = []
        self.current_step = "init"
        self.game_over = False
        self.round_count = 0

    def init_game(self, player_names: list[str] | None = None):
        """初始化游戏，返回初始状态"""
        self.state = self.runner.setup(player_names)

        roles_info = ' | '.join(
            f'{p.name}(#{p.player_id})={p.role.value}'
            for p in self.state.players
        )
        _log(f"游戏初始化 — {roles_info}")

        self.step_index = 0
        self.game_over = False
        self.round_count = 0
        self.current_step = "init"
        self._compute_steps()
        return self._build_snapshot()

    def _compute_steps(self):
        """根据当前状态计算剩余步骤列表"""
        steps = []
        if not self.game_over:
            steps.append("night")
            steps.append("discussion")
            steps.append("vote")
        self.step_labels = steps

    def step(self) -> dict:
        """执行一步，返回当前状态快照"""
        if self.game_over:
            return self._build_snapshot()

        t0 = time.time()

        if self.current_step == "init":
            self._begin_night()
            self.current_step = "night"
        elif self.current_step == "night":
            self._run_night()
            if self._check_game_over():
                _log(f"夜间结算完成，游戏结束 [{t0:.1f}s]")
                return self._build_snapshot()
            self.current_step = "discussion"
            _log(f"夜间结算完成，进入讨论 [{time.time()-t0:.1f}s]")
        elif self.current_step == "discussion":
            self._run_discussion()
            self.current_step = "vote"
            _log(f"讨论结束，进入投票 [{time.time()-t0:.1f}s]")
        elif self.current_step == "vote":
            self._run_vote()
            if self.game_over:
                self.step_labels = []
                self.current_step = "done"
                _log(f"投票结束，{self.state.winner} 获胜！[总耗时 {time.time()-t0:.1f}s]")
                return self._build_snapshot()
            self._reset_round()
            self._begin_night()
            self.current_step = "night"
            self.step_index += 1
            _log(f"投票结束，进入下一夜 [{time.time()-t0:.1f}s]")

        self._compute_steps()
        return self._build_snapshot()

    def run_to_end(self) -> dict:
        """运行到游戏结束，返回最终状态"""
        _log("开始连续运行至结束...")
        t0 = time.time()
        while not self.game_over:
            self.step()
        _log(f"游戏结束，总耗时 {time.time()-t0:.1f}s")
        return self._build_snapshot()

    def get_state(self) -> dict:
        """获取当前状态快照"""
        return self._build_snapshot()

    # ---- 内部方法 ----

    def _begin_night(self):
        self.round_count += 1
        self.state.round = self.round_count
        msg = f"=== 第 {self.round_count} 回合 - 夜晚 ==="
        self.state.add_log(GamePhase.NIGHT_GUARD, msg)
        _log(f"夜晚开始（第 {self.round_count} 回合）")

    def _run_night(self):
        """执行完整夜晚阶段（并发调用 LLM，逐步日志）"""
        state = self.state
        state.add_log(GamePhase.NIGHT_GUARD, "=== 夜晚来临 ===")
        _log(f"── 夜晚阶段 ──")

        NIGHT_ORDER = [
            (Role.GUARD, GamePhase.NIGHT_GUARD, "守卫"),
            (Role.WEREWOLF, GamePhase.NIGHT_WEREWOLF, "狼人"),
            (Role.SEER, GamePhase.NIGHT_SEER, "预言家"),
            (Role.WITCH, GamePhase.NIGHT_WITCH, "女巫"),
        ]

        for role, phase, label in NIGHT_ORDER:
            state.phase = phase
            players_with_role = state.get_alive_by_role(role)

            if not players_with_role:
                continue

            # 同角色玩家可并行（如多狼投票）
            def _night_action(player):
                agent = self.runner.agents.get(player.player_id)
                if not agent:
                    return []
                self.runner._sync_agents_alive(state)
                available = self.runner.engine.get_available_actions(player.player_id)
                if not available:
                    return []
                night_info = self.runner.engine.get_night_info(player.player_id)
                t0 = time.time()
                decisions = agent.on_night(state, available, night_info)
                elapsed = time.time() - t0
                for action_type, target_id in decisions:
                    target_name = state.get_player(target_id).name if state.get_player(target_id) else "?"
                    _log(f"  {label} #{player.player_id}({player.name}) {action_type.value}→#{target_id}({target_name}) [{elapsed:.1f}s]")
                return [(player.player_id, action_type, target_id) for action_type, target_id in decisions]

            if len(players_with_role) > 1:
                with ThreadPoolExecutor(max_workers=len(players_with_role)) as pool:
                    futures = {pool.submit(_night_action, p): p for p in players_with_role}
                    for fut in as_completed(futures):
                        for pid, at, tid in fut.result():
                            self.runner.engine.submit_night_action(pid, at, tid)
            else:
                for p in players_with_role:
                    for pid, at, tid in _night_action(p):
                        self.runner.engine.submit_night_action(pid, at, tid)

            if role == Role.WITCH:
                break

        # 结算
        deaths = self.runner.engine.resolve_night()
        self.runner._sync_agents_alive(state)

        if deaths:
            for dead_id in deaths:
                dead = state.get_player(dead_id)
                name = dead.name if dead else "?"
                role = ROLE_CN.get(dead.role, "?") if dead else "?"
                state.add_log(GamePhase.DAY_DISCUSSION, f"昨晚 {name}（玩家 {dead_id}[{role}]）死了")
            death_names = []
            for d in deaths:
                pl = state.get_player(d)
                death_names.append(f"#{d}({pl.name})" if pl else f"#{d}")
            _log(f"  夜间死亡: {', '.join(death_names)}")
        else:
            state.add_log(GamePhase.DAY_DISCUSSION, "昨晚是平安夜")
            _log(f"  平安夜")

    def _run_discussion(self):
        """执行白天讨论阶段（并发调用 LLM）"""
        self.state.phase = GamePhase.DAY_DISCUSSION
        self.state.add_log(GamePhase.DAY_DISCUSSION, "=== 白天讨论开始 ===")
        _log(f"── 讨论阶段（并发 {self.config.num_players} 人）──")

        discussion_order = self.runner._get_discussion_order(self.state)
        alive_agents = [
            (player_id, self.runner.agents.get(player_id))
            for player_id in discussion_order
        ]

        def _speak(pid, agent):
            if not agent or not agent.is_alive:
                return None
            t0 = time.time()
            speech = agent.on_discussion(self.state)
            elapsed = time.time() - t0
            _log(f"  玩家 {pid}({agent.name}/{agent.role.value}) 发言 [{elapsed:.1f}s]")
            return (pid, speech)

        results = []
        with ThreadPoolExecutor(max_workers=min(8, len(alive_agents))) as pool:
            futures = {pool.submit(_speak, pid, ag): pid for pid, ag in alive_agents}
            for fut in as_completed(futures):
                r = fut.result()
                if r:
                    results.append(r)

        # 按讨论顺序插入日志
        spoken = dict(results)
        for pid, agent in alive_agents:
            speech = spoken.get(pid)
            if speech:
                player = self.state.get_player(pid)
                role_str = f"[{ROLE_CN.get(player.role, '?')}]" if player else ""
                self.state.add_log(GamePhase.DAY_DISCUSSION, f"玩家 {pid}{role_str}: {speech}")

    def _run_vote(self):
        """执行投票和放逐（并发调用 LLM）"""
        self.state.phase = GamePhase.DAY_VOTE
        self.state.votes = {}
        self.state.add_log(GamePhase.DAY_VOTE, "=== 投票环节 ===")
        _log(f"── 投票阶段（并发 {self.config.num_players} 人）──")

        alive_agents = self.runner.registry.get_alive_agents(self.state)

        def _vote(agent):
            if not agent.is_alive:
                return None
            t0 = time.time()
            target = agent.on_vote(self.state)
            elapsed = time.time() - t0
            if target >= 0:
                target_name = self.state.get_player(target).name if self.state.get_player(target) else "?"
                _log(f"  玩家 {agent.player_id}({agent.name}/{agent.role.value}) 投票给 #{target}({target_name}) [{elapsed:.1f}s]")
            else:
                _log(f"  玩家 {agent.player_id}({agent.name}/{agent.role.value}) 弃票 [{elapsed:.1f}s]")
            return (agent.player_id, target, agent)

        votes = []
        with ThreadPoolExecutor(max_workers=min(8, len(alive_agents))) as pool:
            futures = [pool.submit(_vote, ag) for ag in alive_agents]
            for fut in as_completed(futures):
                r = fut.result()
                if r:
                    votes.append(r)

        # 提交投票
        for pid, target, _ in votes:
            if target >= 0:
                self.runner.engine.submit_vote(pid, target)

        eliminated = self.runner.engine.resolve_day()
        if eliminated is not None:
            player = self.state.get_player(eliminated)
            name = player.name if player else "?"
            role = ROLE_CN.get(player.role, "?") if player else "?"
            self.state.add_log(GamePhase.DAY_VOTE, f"玩家 {eliminated}（{name}）[{role}] 被放逐")
            _log(f"  放逐: #{eliminated}({name})")
            self.runner._sync_agents_alive(self.state)
            self._check_game_over()
        else:
            _log(f"  无人被放逐（平票或无人投票）")

    def _check_game_over(self) -> bool:
        winner = self.runner.engine.check_game_over()
        if winner:
            self.game_over = True
            self.current_step = "done"
            self.step_labels = []
            _log(f"  游戏结束 — {winner} 获胜！")
        return self.game_over

    def _reset_round(self):
        """重置回合状态"""
        self.state.eliminated_this_round = None
        self.state.votes = {}
        self.state.night_deaths = []
        self.state.night_kill_target = None
        for p in self.state.players:
            p.protected = False
            p.poisoned = False

    def _build_snapshot(self) -> dict:
        """构建返回给前端的游戏状态快照（始终显示真实角色）"""
        state = self.state
        alive_players = []
        dead_players = []
        for p in state.players:
            pinfo = {
                "id": p.player_id,
                "name": p.name,
                "role": p.role.value,   # 始终显示真实角色，不再隐藏
                "status": p.status.value,
            }
            if p.is_alive:
                alive_players.append(pinfo)
            else:
                dead_players.append(pinfo)

        logs = [
            {
                "round": log.round,
                "phase": log.phase.value,
                "message": log.message,
            }
            for log in state.logs
        ]

        return {
            "session_id": getattr(self, "_session_id", ""),
            "game_over": self.game_over,
            "winner": state.winner,
            "round": state.round,
            "round_count": self.round_count,
            "step_index": self.step_index,
            "current_step": self.current_step,
            "remaining_steps": self.step_labels,
            "alive_players": alive_players,
            "dead_players": dead_players,
            "player_count": len(state.players),
            "logs": logs,
            "log_count": len(logs),
        }


class GameSessionManager:
    """管理多个游戏会话"""

    def __init__(self):
        self.sessions: dict[str, StepRunner] = {}

    def create_session(
        self,
        num_players: int = 9,
        agent_type: AgentType = AgentType.LLM,
        player_names: list[str] | None = None,
    ) -> dict:
        session_id = uuid.uuid4().hex[:12]
        config = GameConfig(num_players=num_players)
        runner = StepRunner(config, agent_type=agent_type)
        runner._session_id = session_id
        snapshot = runner.init_game(player_names)
        self.sessions[session_id] = runner
        return snapshot

    def get_session(self, session_id: str) -> Optional[StepRunner]:
        return self.sessions.get(session_id)

    def step_session(self, session_id: str) -> Optional[dict]:
        runner = self.sessions.get(session_id)
        if not runner:
            return None
        return runner.step()

    def run_session_to_end(self, session_id: str) -> Optional[dict]:
        runner = self.sessions.get(session_id)
        if not runner:
            return None
        return runner.run_to_end()

    def get_session_state(self, session_id: str) -> Optional[dict]:
        runner = self.sessions.get(session_id)
        if not runner:
            return None
        return runner.get_state()
