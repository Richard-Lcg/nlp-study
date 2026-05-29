import unittest
from collections import Counter

from engine.config import GameConfig, Role, GamePhase, ActionType
from agents import AgentType
from runner import GameRunner


class TestGameRunner(unittest.TestCase):
    def test_setup_9_players(self):
        config = GameConfig(num_players=9)
        runner = GameRunner(config)
        state = runner.setup([f"P{i}" for i in range(9)])
        self.assertEqual(len(state.players), 9)
        self.assertIsNotNone(runner.engine.state)

    def test_setup_default_names(self):
        config = GameConfig(num_players=9)
        runner = GameRunner(config)
        state = runner.setup()
        self.assertEqual(len(state.players), 9)

    def test_all_agents_created(self):
        config = GameConfig(num_players=9)
        runner = GameRunner(config)
        runner.setup()
        self.assertEqual(len(runner.agents), 9)

    def test_agent_roles_match_players(self):
        config = GameConfig(num_players=9)
        runner = GameRunner(config)
        state = runner.setup()
        for pid, agent in runner.agents.items():
            player = state.get_player(pid)
            self.assertEqual(agent.role, player.role)

    def test_full_game_completes(self):
        """完整的 9 人随机局可以正常结束"""
        config = GameConfig(num_players=9)
        runner = GameRunner(config, agent_type=AgentType.RANDOM)
        state = runner.run_game()
        self.assertIsNotNone(state.winner)
        self.assertIn(state.winner, ["werewolf", "village"])
        self.assertEqual(state.phase, GamePhase.GAME_OVER)

    def test_full_game_12_players(self):
        """完整的 12 人随机局可以正常结束"""
        config = GameConfig(num_players=12)
        runner = GameRunner(config, agent_type=AgentType.RANDOM)
        state = runner.run_game()
        self.assertIsNotNone(state.winner)
        self.assertEqual(state.phase, GamePhase.GAME_OVER)

    def test_game_has_logs(self):
        config = GameConfig(num_players=9)
        runner = GameRunner(config, agent_type=AgentType.RANDOM)
        state = runner.run_game()
        self.assertTrue(len(state.logs) > 0)

    def test_winner_is_consistent_with_state(self):
        """获胜方与游戏状态一致"""
        config = GameConfig(num_players=9)
        runner = GameRunner(config, agent_type=AgentType.RANDOM)
        state = runner.run_game()

        if state.winner == "village":
            wolves_alive = [p for p in state.get_alive() if p.role == Role.WEREWOLF]
            self.assertEqual(len(wolves_alive), 0)
        elif state.winner == "werewolf":
            alive = state.get_alive()
            wolves = [p for p in alive if p.role == Role.WEREWOLF]
            non_wolves = [p for p in alive if p.role != Role.WEREWOLF]
            self.assertTrue(len(wolves) >= len(non_wolves))

    def test_multiple_games_both_sides_can_win(self):
        """运行多局游戏，双方都有获胜机会（至少各赢1次）"""
        winners = []
        for seed in range(20):
            config = GameConfig(num_players=9)
            runner = GameRunner(config, agent_type=AgentType.RANDOM)
            state = runner.run_game()
            winners.append(state.winner)

        unique_winners = set(winners)
        self.assertIn("werewolf", unique_winners)
        self.assertIn("village", unique_winners)

    def test_no_game_hangs(self):
        """所有游戏都在回合上限内结束"""
        config = GameConfig(num_players=9)
        for seed in range(10):
            runner = GameRunner(config, agent_type=AgentType.RANDOM)
            state = runner.run_game()
            self.assertLessEqual(state.round, 99,
                                 f"Game with seed {seed} exceeded round limit")


class TestNightPhase(unittest.TestCase):
    def test_wolf_kill_majority_in_runner(self):
        """多狼在 runner 中能通过多数决击杀"""
        config = GameConfig(num_players=9)
        runner = GameRunner(config, agent_type=AgentType.RANDOM)
        state = runner.setup()

        # 手动控制：让所有狼投票杀同一人
        wolves = [p for p in state.players if p.role == Role.WEREWOLF]
        target = [p for p in state.players if p.role != Role.WEREWOLF][0]

        for w in wolves:
            runner.agents[w.player_id] = type('MockWolf', (), {
                'player_id': w.player_id,
                'role': Role.WEREWOLF,
                'is_alive': True,
                'on_night': lambda *a, **kw: [(ActionType.KILL, target.player_id)],
                'on_discussion': lambda *a: "pass",
                'on_vote': lambda *a: 0,
                'on_hunter_shot': lambda *a: None,
                'on_last_words': lambda *a: "bye",
                'observe': lambda *a: {},
                'remember': lambda *a: None,
                'get_memory': lambda *a: "",
            })()

        deaths = runner.run_night_phase(state)
        self.assertIn(target.player_id, deaths,
                       f"Wolf target {target.player_id} should be in deaths {deaths}")


if __name__ == "__main__":
    unittest.main()
