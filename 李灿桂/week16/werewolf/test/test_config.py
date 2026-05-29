import unittest

from engine.config import GameConfig, Role, GamePhase, ActionType, ROLE_SETUPS


class TestRoleAndPhase(unittest.TestCase):
    def test_role_values(self):
        self.assertEqual(Role.VILLAGER.value, "villager")
        self.assertEqual(Role.WEREWOLF.value, "werewolf")
        self.assertEqual(Role.SEER.value, "seer")
        self.assertEqual(Role.WITCH.value, "witch")
        self.assertEqual(Role.HUNTER.value, "hunter")
        self.assertEqual(Role.GUARD.value, "guard")

    def test_game_phase_values(self):
        self.assertIn(GamePhase.NIGHT_WEREWOLF, GamePhase)
        self.assertIn(GamePhase.DAY_DISCUSSION, GamePhase)
        self.assertIn(GamePhase.GAME_OVER, GamePhase)

    def test_action_type_values(self):
        self.assertEqual(ActionType.KILL.value, "kill")
        self.assertEqual(ActionType.VOTE.value, "vote")


class TestROLE_SETUPS(unittest.TestCase):
    def test_9_player_setup(self):
        setup = ROLE_SETUPS[9]
        self.assertEqual(sum(setup.values()), 9)
        self.assertEqual(setup[Role.WEREWOLF], 3)
        self.assertEqual(setup[Role.VILLAGER], 3)

    def test_12_player_setup(self):
        setup = ROLE_SETUPS[12]
        self.assertEqual(sum(setup.values()), 12)
        self.assertEqual(setup[Role.WEREWOLF], 4)

    def test_unsupported_player_count(self):
        self.assertNotIn(8, ROLE_SETUPS)
        self.assertNotIn(10, ROLE_SETUPS)


class TestGameConfig(unittest.TestCase):
    def test_default_9_player(self):
        config = GameConfig(num_players=9)
        self.assertEqual(config.num_players, 9)
        self.assertEqual(sum(config.role_setup.values()), 9)

    def test_12_player(self):
        config = GameConfig(num_players=12)
        self.assertEqual(config.num_players, 12)

    def test_custom_role_setup(self):
        setup = {Role.WEREWOLF: 2, Role.VILLAGER: 2}
        config = GameConfig(num_players=4, role_setup=setup)
        self.assertEqual(config.num_players, 4)

    def test_role_setup_mismatch_raises(self):
        setup = {Role.WEREWOLF: 1, Role.VILLAGER: 1}
        with self.assertRaises(ValueError):
            GameConfig(num_players=4, role_setup=setup)

    def test_unsupported_player_count_raises(self):
        with self.assertRaises(ValueError):
            GameConfig(num_players=7)

    def test_custom_timeouts(self):
        config = GameConfig(num_players=9, discussion_timeout=300, vote_timeout=30)
        self.assertEqual(config.discussion_timeout, 300)
        self.assertEqual(config.vote_timeout, 30)


if __name__ == "__main__":
    unittest.main()
