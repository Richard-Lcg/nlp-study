import unittest

from engine.config import GameConfig, Role, GamePhase, ActionType
from engine.engine import GameEngine
from engine.game_state import PlayerStatus


class TestGameEngine(unittest.TestCase):
    def setUp(self):
        self.config = GameConfig(num_players=9)
        self.engine = GameEngine(self.config)

    def test_init_game(self):
        names = [f"P{i}" for i in range(9)]
        state = self.engine.init_game(names, random_seed=42)
        self.assertIsNotNone(state)
        self.assertEqual(len(state.players), 9)
        self.assertEqual(state.round, 1)
        self.assertEqual(state.phase, GamePhase.NIGHT_WEREWOLF)

    def test_init_game_wrong_player_count(self):
        with self.assertRaises(ValueError):
            self.engine.init_game(["P0", "P1"])  # 只需要 2 个但需要 9 个

    def test_all_roles_assigned(self):
        names = [f"P{i}" for i in range(9)]
        state = self.engine.init_game(names, random_seed=42)
        assigned = [p.role for p in state.players]
        from collections import Counter
        counts = Counter(assigned)
        self.assertEqual(counts[Role.WEREWOLF], 3)
        self.assertEqual(counts[Role.VILLAGER], 3)
        self.assertEqual(counts[Role.SEER], 1)
        self.assertEqual(counts[Role.WITCH], 1)
        self.assertEqual(counts[Role.HUNTER], 1)

    def test_get_available_actions_wolf_night(self):
        names = [f"P{i}" for i in range(9)]
        state = self.engine.init_game(names, random_seed=42)
        state.phase = GamePhase.NIGHT_WEREWOLF

        # 找一个狼人
        wolf = [p for p in state.players if p.role == Role.WEREWOLF][0]
        actions = self.engine.get_available_actions(wolf.player_id)
        self.assertTrue(len(actions) > 0)
        action_type, targets = actions[0]
        self.assertEqual(action_type, ActionType.KILL)
        # 不能杀狼队友
        for tid in targets:
            self.assertNotEqual(state.get_player(tid).role, Role.WEREWOLF)

    def test_get_available_actions_seer_night(self):
        names = [f"P{i}" for i in range(9)]
        state = self.engine.init_game(names, random_seed=42)
        state.phase = GamePhase.NIGHT_SEER

        seer = [p for p in state.players if p.role == Role.SEER][0]
        actions = self.engine.get_available_actions(seer.player_id)
        self.assertTrue(len(actions) > 0)
        self.assertEqual(actions[0][0], ActionType.INVESTIGATE)

    def test_get_available_actions_villager_no_action(self):
        names = [f"P{i}" for i in range(9)]
        state = self.engine.init_game(names, random_seed=42)
        state.phase = GamePhase.NIGHT_WEREWOLF

        villager = [p for p in state.players if p.role == Role.VILLAGER][0]
        actions = self.engine.get_available_actions(villager.player_id)
        self.assertEqual(actions, [])

    def test_submit_night_action_success(self):
        names = [f"P{i}" for i in range(9)]
        state = self.engine.init_game(names, random_seed=42)
        state.phase = GamePhase.NIGHT_WEREWOLF

        wolf = [p for p in state.players if p.role == Role.WEREWOLF][0]
        # 找一个非狼目标
        target = [p for p in state.players if p.role != Role.WEREWOLF][0]

        result = self.engine.submit_night_action(wolf.player_id, ActionType.KILL, target.player_id)
        self.assertTrue(result)
        self.assertEqual(len(state.night_actions), 1)

    def test_submit_night_action_invalid(self):
        names = [f"P{i}" for i in range(9)]
        state = self.engine.init_game(names, random_seed=42)
        state.phase = GamePhase.NIGHT_WEREWOLF

        villager = [p for p in state.players if p.role == Role.VILLAGER][0]
        result = self.engine.submit_night_action(villager.player_id, ActionType.KILL, 0)
        self.assertFalse(result)

    def test_submit_duplicate_action(self):
        names = [f"P{i}" for i in range(9)]
        state = self.engine.init_game(names, random_seed=42)
        state.phase = GamePhase.NIGHT_WEREWOLF

        wolf = [p for p in state.players if p.role == Role.WEREWOLF][0]
        target = [p for p in state.players if p.role != Role.WEREWOLF][0]

        self.engine.submit_night_action(wolf.player_id, ActionType.KILL, target.player_id)
        result = self.engine.submit_night_action(wolf.player_id, ActionType.KILL, target.player_id)
        self.assertFalse(result)  # 重复提交

    def test_night_resolve_correctly(self):
        names = [f"P{i}" for i in range(9)]
        state = self.engine.init_game(names, random_seed=42)

        # 模拟所有狼人杀同一个目标
        state.phase = GamePhase.NIGHT_WEREWOLF
        wolves = [p for p in state.players if p.role == Role.WEREWOLF]
        target = [p for p in state.players if p.role != Role.WEREWOLF][0].player_id

        for w in wolves:
            self.engine.submit_night_action(w.player_id, ActionType.KILL, target)

        deaths = self.engine.resolve_night()
        self.assertIn(target, deaths)
        self.assertEqual(state.get_player(target).status, PlayerStatus.DEAD)

    def test_check_game_over_village_wins(self):
        names = [f"P{i}" for i in range(9)]
        state = self.engine.init_game(names, random_seed=42)
        # 全杀光狼人
        wolves = [p for p in state.players if p.role == Role.WEREWOLF]
        for w in wolves:
            w.status = PlayerStatus.DEAD

        winner = self.engine.check_game_over()
        self.assertEqual(winner, "village")
        self.assertEqual(state.phase, GamePhase.GAME_OVER)

    def test_submit_vote(self):
        names = [f"P{i}" for i in range(9)]
        state = self.engine.init_game(names, random_seed=42)
        state.phase = GamePhase.DAY_VOTE

        result = self.engine.submit_vote(0, 3)
        self.assertTrue(result)
        self.assertIn(0, state.votes)

    def test_resolve_day(self):
        names = [f"P{i}" for i in range(9)]
        state = self.engine.init_game(names, random_seed=42)
        state.phase = GamePhase.DAY_VOTE
        state.votes = {0: 3, 1: 3, 2: 3, 4: 3, 5: 3, 6: 3}

        eliminated = self.engine.resolve_day()
        self.assertEqual(eliminated, 3)
        self.assertFalse(state.get_player(3).is_alive)

    def test_night_info_wolf(self):
        names = [f"P{i}" for i in range(9)]
        state = self.engine.init_game(names, random_seed=42)

        wolf = [p for p in state.players if p.role == Role.WEREWOLF][0]
        info = self.engine.get_night_info(wolf.player_id)
        self.assertIn("teammates", info)
        # 应该能看到其他狼队友
        other_wolves = [p.player_id for p in state.get_alive_by_role(Role.WEREWOLF) if p.player_id != wolf.player_id]
        self.assertEqual(info["teammates"], other_wolves)

    def test_night_info_seer(self):
        names = [f"P{i}" for i in range(9)]
        state = self.engine.init_game(names, random_seed=42)

        seer = [p for p in state.players if p.role == Role.SEER][0]
        target = [p for p in state.players if p.role != Role.SEER][0]
        state.seen_roles[target.player_id] = "good"

        info = self.engine.get_night_info(seer.player_id)
        self.assertIn("seen_roles", info)

    def test_night_info_witch(self):
        names = [f"P{i}" for i in range(9)]
        state = self.engine.init_game(names, random_seed=42)

        witch = [p for p in state.players if p.role == Role.WITCH][0]
        state.night_kill_target = 5
        info = self.engine.get_night_info(witch.player_id)
        self.assertEqual(info.get("night_kill_target"), 5)


class TestGameEngine12Player(unittest.TestCase):
    def setUp(self):
        self.config = GameConfig(num_players=12)
        self.engine = GameEngine(self.config)

    def test_init_12_players(self):
        names = [f"P{i}" for i in range(12)]
        state = self.engine.init_game(names, random_seed=42)
        self.assertEqual(len(state.players), 12)
        from collections import Counter
        counts = Counter(p.role for p in state.players)
        self.assertEqual(counts[Role.GUARD], 1)

    def test_guard_action_available(self):
        names = [f"P{i}" for i in range(12)]
        state = self.engine.init_game(names, random_seed=42)
        state.phase = GamePhase.NIGHT_GUARD

        guard = [p for p in state.players if p.role == Role.GUARD]
        if guard:
            actions = self.engine.get_available_actions(guard[0].player_id)
            self.assertTrue(len(actions) > 0)
            self.assertEqual(actions[0][0], ActionType.PROTECT)

    def test_witch_save_action_shows(self):
        names = [f"P{i}" for i in range(12)]
        state = self.engine.init_game(names, random_seed=42)
        state.phase = GamePhase.NIGHT_WITCH
        state.night_kill_target = 5

        witch = [p for p in state.players if p.role == Role.WITCH][0]
        actions = self.engine.get_available_actions(witch.player_id)
        types = [a[0] for a in actions]
        self.assertIn(ActionType.SAVE, types)


class TestPhaseCallbacks(unittest.TestCase):
    def test_phase_change_callback(self):
        config = GameConfig(num_players=9)
        engine = GameEngine(config)
        calls = []

        def cb(state):
            calls.append(state.phase.value)

        engine.on_phase_change(cb)
        engine.init_game([f"P{i}" for i in range(9)], random_seed=42)

        self.assertTrue(len(calls) > 0)
        self.assertIn(GamePhase.NIGHT_WEREWOLF.value, calls)


if __name__ == "__main__":
    unittest.main()
