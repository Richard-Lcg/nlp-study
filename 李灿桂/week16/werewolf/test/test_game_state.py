import unittest

from engine.config import Role, GamePhase, GameConfig
from engine.game_state import GameState, Player, PlayerStatus, NightAction, GameLog, WitchState


class TestPlayer(unittest.TestCase):
    def test_create_player(self):
        p = Player(player_id=0, name="Alice", role=Role.SEER)
        self.assertEqual(p.name, "Alice")
        self.assertEqual(p.role, Role.SEER)
        self.assertTrue(p.is_alive)
        self.assertTrue(p.can_act)

    def test_player_dead(self):
        p = Player(player_id=1, name="Bob", role=Role.VILLAGER, status=PlayerStatus.DEAD)
        self.assertFalse(p.is_alive)
        self.assertFalse(p.can_act)

    def test_player_dying(self):
        p = Player(player_id=2, name="Charlie", role=Role.HUNTER, status=PlayerStatus.DYING)
        self.assertFalse(p.is_alive)
        self.assertTrue(p.can_act)  # 遗言/开枪阶段可以行动

    def test_sheriff_flag(self):
        p = Player(player_id=3, name="Diana", role=Role.VILLAGER, is_sheriff=True)
        self.assertTrue(p.is_sheriff)

    def test_default_vote_record(self):
        p = Player(player_id=4, name="Eve", role=Role.VILLAGER)
        self.assertEqual(p.vote_record, [])


class TestNightAction(unittest.TestCase):
    def test_create_night_action(self):
        action = NightAction(actor_id=0, action_type="kill", target_id=3, round=1)
        self.assertEqual(action.actor_id, 0)
        self.assertEqual(action.target_id, 3)
        self.assertEqual(action.round, 1)
        self.assertFalse(action.resolved)
        self.assertFalse(action.blocked)


class TestGameLog(unittest.TestCase):
    def test_create_log(self):
        log = GameLog(round=1, phase=GamePhase.NIGHT_WEREWOLF, message="test", data={"key": "val"})
        self.assertEqual(log.round, 1)
        self.assertEqual(log.data["key"], "val")


class TestWitchState(unittest.TestCase):
    def test_initial_state(self):
        ws = WitchState()
        self.assertFalse(ws.save_potion_used)
        self.assertFalse(ws.poison_potion_used)
        self.assertIsNone(ws.night_save_target)

    def test_use_save_potion(self):
        ws = WitchState()
        ws.save_potion_used = True
        self.assertTrue(ws.save_potion_used)

    def test_use_poison_potion(self):
        ws = WitchState()
        ws.poison_potion_used = True
        self.assertTrue(ws.poison_potion_used)


class TestGameState(unittest.TestCase):
    def setUp(self):
        self.config = GameConfig(num_players=9)
        self.players = [
            Player(player_id=i, name=f"P{i}", role=list(self.config.role_setup.keys())[0])
            for i in range(9)
        ]
        self.state = GameState(self.players, self.config)

    def test_get_player_found(self):
        p = self.state.get_player(0)
        self.assertIsNotNone(p)
        self.assertEqual(p.player_id, 0)

    def test_get_player_not_found(self):
        p = self.state.get_player(99)
        self.assertIsNone(p)

    def test_get_alive_all_alive(self):
        alive = self.state.get_alive()
        self.assertEqual(len(alive), 9)

    def test_get_alive_some_dead(self):
        self.players[0].status = PlayerStatus.DEAD
        alive = self.state.get_alive()
        self.assertEqual(len(alive), 8)

    def test_get_alive_by_role(self):
        """所有玩家角色相同（setUp 中），get_alive_by_role 应返回所有存活玩家"""
        wolves = self.state.get_alive_by_role(list(self.config.role_setup.keys())[0])
        self.assertEqual(len(wolves), 9)

    def test_get_alive_by_role_empty(self):
        """没有对应角色存活时返回空列表"""
        villagers = self.state.get_alive_by_role(Role.VILLAGER)
        self.assertEqual(villagers, [])

    def test_add_log(self):
        self.state.add_log(GamePhase.NIGHT_WEREWOLF, "测试日志")
        self.assertEqual(len(self.state.logs), 1)
        self.assertEqual(self.state.logs[0].message, "测试日志")

    def test_is_night(self):
        self.state.phase = GamePhase.NIGHT_WEREWOLF
        self.assertTrue(self.state.is_night)
        self.state.phase = GamePhase.DAY_DISCUSSION
        self.assertFalse(self.state.is_night)

    def test_initial_alive_players(self):
        self.assertEqual(len(self.state.alive_players), 9)

    def test_seen_roles(self):
        self.state.seen_roles[5] = Role.WEREWOLF
        self.assertEqual(self.state.seen_roles[5], Role.WEREWOLF)


if __name__ == "__main__":
    unittest.main()
