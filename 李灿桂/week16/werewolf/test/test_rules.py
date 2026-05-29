import unittest

from engine.config import Role, GamePhase, ActionType, GameConfig
from engine.game_state import GameState, Player, PlayerStatus, NightAction
from engine.rules import Rules


def make_state(players: list[Player], config=None) -> GameState:
    from collections import Counter
    counter = Counter(p.role for p in players)
    cfg = config or GameConfig(
        num_players=len(players),
        role_setup=dict(counter),
    )
    state = GameState(players, cfg)
    state.round = 1
    return state


class TestCheckWinner(unittest.TestCase):
    def test_village_wins_no_wolves(self):
        players = [
            Player(0, "A", Role.VILLAGER),
            Player(1, "B", Role.VILLAGER),
            Player(2, "C", Role.SEER),
        ]
        state = make_state(players)
        self.assertEqual(Rules.check_winner(state), "village")

    def test_werewolf_wins_tubian_all_villagers_dead(self):
        """屠边：平民全灭 → 狼人胜"""
        players = [
            Player(0, "A", Role.WEREWOLF),
            Player(1, "B", Role.WEREWOLF),
            Player(2, "C", Role.SEER),  # 神职还在
            # 平民已全灭
        ]
        state = make_state(players)
        self.assertEqual(Rules.check_winner(state), "werewolf")

    def test_werewolf_wins_tubian_all_specials_dead(self):
        """屠边：神职全灭 → 狼人胜"""
        players = [
            Player(0, "A", Role.WEREWOLF),
            Player(1, "B", Role.WEREWOLF),
            Player(2, "C", Role.VILLAGER),
            Player(3, "D", Role.VILLAGER),
        ]
        state = make_state(players)
        self.assertEqual(Rules.check_winner(state), "werewolf")

    def test_no_winner_when_both_types_alive(self):
        """双方都有平民和神职存活 → 未结束"""
        players = [
            Player(0, "A", Role.WEREWOLF),
            Player(1, "B", Role.VILLAGER),
            Player(2, "C", Role.SEER),
        ]
        state = make_state(players)
        self.assertIsNone(Rules.check_winner(state))

    def test_no_winner_mid_game(self):
        """多人局中期：两类好人都在 → 未结束"""
        players = [
            Player(0, "A", Role.WEREWOLF),
            Player(1, "B", Role.WEREWOLF),
            Player(2, "C", Role.VILLAGER),
            Player(3, "D", Role.VILLAGER),
            Player(4, "E", Role.SEER),
            Player(5, "F", Role.WITCH),
        ]
        state = make_state(players)
        self.assertIsNone(Rules.check_winner(state))


class TestResolveNight(unittest.TestCase):
    def test_wolf_kill_majority(self):
        """2狼投票杀同一人 → 击杀成功"""
        state = make_state([
            Player(0, "A", Role.WEREWOLF),
            Player(1, "B", Role.WEREWOLF),
            Player(2, "C", Role.VILLAGER),
        ])
        state.night_actions = [
            NightAction(0, ActionType.KILL, 2, 1),
            NightAction(1, ActionType.KILL, 2, 1),
        ]
        deaths = Rules.resolve_night(state)
        self.assertEqual(deaths, [2])
        self.assertEqual(state.get_player(2).status, PlayerStatus.DEAD)

    def test_wolf_kill_divided(self):
        """2狼投票不同人 → 平票无击杀"""
        state = make_state([
            Player(0, "A", Role.WEREWOLF),
            Player(1, "B", Role.WEREWOLF),
            Player(2, "C", Role.VILLAGER),
            Player(3, "D", Role.VILLAGER),
        ])
        state.night_actions = [
            NightAction(0, ActionType.KILL, 2, 1),
            NightAction(1, ActionType.KILL, 3, 1),
        ]
        deaths = Rules.resolve_night(state)
        self.assertEqual(deaths, [])

    def test_guard_protects(self):
        """守卫守护目标与狼人击杀目标相同 → 守护成功"""
        state = make_state([
            Player(0, "A", Role.WEREWOLF),
            Player(1, "B", Role.GUARD),
            Player(2, "C", Role.VILLAGER),
        ])
        state.night_actions = [
            NightAction(0, ActionType.KILL, 2, 1),
            NightAction(1, ActionType.PROTECT, 2, 1),
        ]
        deaths = Rules.resolve_night(state)
        self.assertEqual(deaths, [])
        self.assertEqual(state.get_player(2).status, PlayerStatus.ALIVE)

    def test_witch_poison_kills(self):
        state = make_state([
            Player(0, "A", Role.WITCH),
            Player(1, "B", Role.VILLAGER),
        ])
        state.night_actions = [
            NightAction(0, ActionType.POISON, 1, 1),
        ]
        deaths = Rules.resolve_night(state)
        self.assertEqual(deaths, [1])

    def test_witch_poison_and_wolf_kill_separate(self):
        """女巫毒人和狼人刀不同目标 → 两人都死"""
        state = make_state([
            Player(0, "A", Role.WEREWOLF),
            Player(1, "B", Role.WITCH),
            Player(2, "C", Role.VILLAGER),
            Player(3, "D", Role.VILLAGER),
        ])
        state.night_actions = [
            NightAction(0, ActionType.KILL, 2, 1),
            NightAction(1, ActionType.POISON, 3, 1),
        ]
        deaths = Rules.resolve_night(state)
        self.assertCountEqual(deaths, [2, 3])

    def test_seer_investigate_werewolf(self):
        state = make_state([
            Player(0, "A", Role.SEER),
            Player(1, "B", Role.WEREWOLF),
        ])
        state.night_actions = [
            NightAction(0, ActionType.INVESTIGATE, 1, 1),
        ]
        Rules.resolve_night(state)
        self.assertIn(1, state.seen_roles)
        self.assertEqual(state.seen_roles[1], "werewolf")

    def test_seer_investigate_good(self):
        """预言家查好人 -> 得到 'good'"""
        state = make_state([
            Player(0, "A", Role.SEER),
            Player(1, "B", Role.VILLAGER),
        ])
        state.night_actions = [
            NightAction(0, ActionType.INVESTIGATE, 1, 1),
        ]
        Rules.resolve_night(state)
        self.assertEqual(state.seen_roles[1], "good")

    def test_witch_poison_overrides_wolf_save(self):
        """毒杀优先于刀杀：毒杀独立，刀杀可能也被挡"""
        state = make_state([
            Player(0, "A", Role.WEREWOLF),
            Player(1, "B", Role.WITCH),
            Player(2, "C", Role.VILLAGER),
            Player(3, "D", Role.VILLAGER),
        ])
        state.night_actions = [
            NightAction(0, ActionType.KILL, 2, 1),
            NightAction(1, ActionType.POISON, 2, 1),  # 毒和刀同目标 → 一次死亡
        ]
        deaths = Rules.resolve_night(state)
        self.assertEqual(deaths, [2])

    def test_three_wolves_two_same_one_different(self):
        """3狼，2票同1人，1票另一人 → 多数决击杀成功"""
        state = make_state([
            Player(0, "A", Role.WEREWOLF),
            Player(1, "B", Role.WEREWOLF),
            Player(2, "C", Role.WEREWOLF),
            Player(3, "D", Role.VILLAGER),
            Player(4, "E", Role.VILLAGER),
        ])
        state.night_actions = [
            NightAction(0, ActionType.KILL, 3, 1),
            NightAction(1, ActionType.KILL, 3, 1),
            NightAction(2, ActionType.KILL, 4, 1),
        ]
        deaths = Rules.resolve_night(state)
        self.assertEqual(deaths, [3])


class TestValidateNightAction(unittest.TestCase):
    def setUp(self):
        self.state = make_state([
            Player(0, "A", Role.WEREWOLF),
            Player(1, "B", Role.SEER),
            Player(2, "C", Role.WITCH),
            Player(3, "D", Role.GUARD),
            Player(4, "E", Role.VILLAGER),
        ])

    def test_wolf_kill_valid(self):
        self.assertTrue(Rules.validate_night_action(self.state, self.state.get_player(0), ActionType.KILL, 4))

    def test_wolf_kill_invalid_target(self):
        self.assertFalse(Rules.validate_night_action(self.state, self.state.get_player(0), ActionType.KILL, 0))  # 不能自刀

    @unittest.skip("当前规则允许狼人自刀，跳过此测试")
    def test_wolf_cannot_self_kill(self):
        self.assertFalse(Rules.validate_night_action(self.state, self.state.get_player(0), ActionType.KILL, 0))

    def test_non_wolf_cannot_kill(self):
        self.assertFalse(Rules.validate_night_action(self.state, self.state.get_player(1), ActionType.KILL, 4))

    def test_seer_investigate_valid(self):
        self.assertTrue(Rules.validate_night_action(self.state, self.state.get_player(1), ActionType.INVESTIGATE, 4))

    def test_non_seer_cannot_investigate(self):
        self.assertFalse(Rules.validate_night_action(self.state, self.state.get_player(0), ActionType.INVESTIGATE, 4))

    def test_witch_save_valid(self):
        self.state.night_kill_target = 4
        self.assertTrue(Rules.validate_night_action(self.state, self.state.get_player(2), ActionType.SAVE, 4))

    def test_witch_save_already_used(self):
        self.state.witch_state.save_potion_used = True
        self.state.night_kill_target = 4
        self.assertFalse(Rules.validate_night_action(self.state, self.state.get_player(2), ActionType.SAVE, 4))

    def test_witch_poison_valid(self):
        self.assertTrue(Rules.validate_night_action(self.state, self.state.get_player(2), ActionType.POISON, 4))

    def test_witch_poison_already_used(self):
        self.state.witch_state.poison_potion_used = True
        self.assertFalse(Rules.validate_night_action(self.state, self.state.get_player(2), ActionType.POISON, 4))

    def test_guard_protect_valid(self):
        self.assertTrue(Rules.validate_night_action(self.state, self.state.get_player(3), ActionType.PROTECT, 0))

    def test_non_guard_cannot_protect(self):
        self.assertFalse(Rules.validate_night_action(self.state, self.state.get_player(0), ActionType.PROTECT, 4))


class TestResolveDayVote(unittest.TestCase):
    def test_majority_eliminates(self):
        players = [Player(i, f"P{i}", Role.VILLAGER) for i in range(5)]
        state = make_state(players)
        state.votes = {0: 3, 1: 3, 2: 3, 4: 3}  # 4票投3号
        eliminated = Rules.resolve_day_vote(state)
        self.assertEqual(eliminated, 3)
        self.assertEqual(state.get_player(3).status, PlayerStatus.DEAD)

    def test_tie_no_elimination(self):
        players = [Player(i, f"P{i}", Role.VILLAGER) for i in range(5)]
        state = make_state(players)
        state.votes = {0: 3, 1: 4, 2: 3, 4: 4}  # 平票
        eliminated = Rules.resolve_day_vote(state)
        self.assertIsNone(eliminated)

    def test_no_votes_no_elimination(self):
        players = [Player(i, f"P{i}", Role.VILLAGER) for i in range(5)]
        state = make_state(players)
        state.votes = {}
        eliminated = Rules.resolve_day_vote(state)
        self.assertIsNone(eliminated)

    def test_consecutive_no_elim(self):
        players = [Player(i, f"P{i}", Role.VILLAGER) for i in range(5)]
        state = make_state(players)
        state.votes = {}
        Rules.resolve_day_vote(state)
        self.assertEqual(state.consecutive_no_elim, 1)

    def test_hunter_dying_when_voted(self):
        players = [
            Player(0, "A", Role.VILLAGER),
            Player(1, "B", Role.HUNTER),
            Player(2, "C", Role.VILLAGER),
        ]
        state = make_state(players)
        state.votes = {0: 1, 2: 1}
        eliminated = Rules.resolve_day_vote(state)
        self.assertEqual(eliminated, 1)
        self.assertEqual(state.get_player(1).status, PlayerStatus.DYING)


class TestCanWitch(unittest.TestCase):
    def test_can_save_when_not_used_and_target_exists(self):
        state = make_state([Player(0, "A", Role.WITCH), Player(1, "B", Role.VILLAGER)])
        state.night_kill_target = 1
        self.assertTrue(Rules.can_witch_save(state))

    def test_cannot_save_when_already_used(self):
        state = make_state([Player(0, "A", Role.WITCH), Player(1, "B", Role.VILLAGER)])
        state.witch_state.save_potion_used = True
        state.night_kill_target = 1
        self.assertFalse(Rules.can_witch_save(state))

    def test_cannot_save_when_no_target(self):
        state = make_state([Player(0, "A", Role.WITCH)])
        state.night_kill_target = None
        self.assertFalse(Rules.can_witch_save(state))

    def test_can_poison_when_not_used(self):
        state = make_state([Player(0, "A", Role.WITCH)])
        self.assertTrue(Rules.can_witch_poison(state))

    def test_cannot_poison_when_already_used(self):
        state = make_state([Player(0, "A", Role.WITCH)])
        state.witch_state.poison_potion_used = True
        self.assertFalse(Rules.can_witch_poison(state))


if __name__ == "__main__":
    unittest.main()
