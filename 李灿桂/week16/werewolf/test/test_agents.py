import unittest
from unittest.mock import patch

from engine.config import Role, ActionType, GamePhase, GameConfig
from engine.game_state import GameState, Player, PlayerStatus
from agents.base import Agent
from agents.random_agent import RandomAgent
from agents.registry import AgentRegistry
from agents import AgentType


class TestAgentBase(unittest.TestCase):
    def test_agent_creation(self):
        agent = RandomAgent(player_id=0, name="TestAgent", role=Role.SEER)
        self.assertEqual(agent.player_id, 0)
        self.assertEqual(agent.role, Role.SEER)
        self.assertTrue(agent.is_alive)
        self.assertEqual(agent.memory, [])

    def test_remember(self):
        agent = RandomAgent(player_id=0, name="TestAgent", role=Role.VILLAGER)
        agent.remember("测试事件")
        self.assertEqual(len(agent.memory), 1)
        self.assertIn("测试事件", agent.memory[0])

    def test_get_memory_empty(self):
        agent = RandomAgent(player_id=0, name="TestAgent", role=Role.VILLAGER)
        self.assertIsInstance(agent.get_memory(), str)

    def test_observe_public_info(self):
        players = [
            Player(0, "A", Role.VILLAGER),
            Player(1, "B", Role.WEREWOLF),
        ]
        config = GameConfig(num_players=2, role_setup={Role.VILLAGER: 1, Role.WEREWOLF: 1})
        state = GameState(players, config)
        state.round = 3
        state.phase = GamePhase.DAY_DISCUSSION

        agent = RandomAgent(player_id=0, name="A", role=Role.VILLAGER)
        obs = agent.observe(state)

        self.assertEqual(obs["round"], 3)
        self.assertEqual(obs["phase"], "day_discussion")
        self.assertEqual(obs["alive_count"], 2)
        self.assertEqual(obs["my_role"], "villager")

    def test_observe_wolf_sees_teammates(self):
        players = [
            Player(0, "A", Role.WEREWOLF),
            Player(1, "B", Role.WEREWOLF),
            Player(2, "C", Role.VILLAGER),
        ]
        config = GameConfig(num_players=3, role_setup={Role.WEREWOLF: 2, Role.VILLAGER: 1})
        state = GameState(players, config)

        agent = RandomAgent(player_id=0, name="A", role=Role.WEREWOLF)
        obs = agent.observe(state)
        self.assertIn("werewolf_teammates", obs)
        self.assertEqual(len(obs["werewolf_teammates"]), 1)
        self.assertEqual(obs["werewolf_teammates"][0]["id"], 1)

    def test_observe_seer_sees_results(self):
        players = [
            Player(0, "A", Role.SEER),
            Player(1, "B", Role.VILLAGER),
        ]
        config = GameConfig(num_players=2, role_setup={Role.SEER: 1, Role.VILLAGER: 1})
        state = GameState(players, config)
        state.seen_roles[1] = Role.VILLAGER

        agent = RandomAgent(player_id=0, name="A", role=Role.SEER)
        obs = agent.observe(state)
        self.assertIn("seen_results", obs)
        self.assertIn("1", obs["seen_results"])

    def test_observe_witch_potion_state(self):
        players = [
            Player(0, "A", Role.WITCH),
            Player(1, "B", Role.VILLAGER),
        ]
        config = GameConfig(num_players=2, role_setup={Role.WITCH: 1, Role.VILLAGER: 1})
        state = GameState(players, config)
        state.witch_state.save_potion_used = True

        agent = RandomAgent(player_id=0, name="A", role=Role.WITCH)
        obs = agent.observe(state)
        self.assertTrue(obs["save_potion_used"])


class TestRandomAgent(unittest.TestCase):
    def setUp(self):
        players = [
            Player(0, "A", Role.WEREWOLF),
            Player(1, "B", Role.SEER),
            Player(2, "C", Role.VILLAGER),
        ]
        config = GameConfig(num_players=3, role_setup={Role.WEREWOLF: 1, Role.SEER: 1, Role.VILLAGER: 1})
        self.state = GameState(players, config)
        self.state.round = 1

    def test_on_night_returns_actions(self):
        agent = RandomAgent(player_id=0, name="A", role=Role.WEREWOLF)
        available = [(ActionType.KILL, [1, 2])]
        decisions = agent.on_night(self.state, available, {})
        self.assertTrue(len(decisions) > 0)
        action_type, target = decisions[0]
        self.assertEqual(action_type, ActionType.KILL)
        self.assertIn(target, [1, 2])

    def test_on_night_no_available(self):
        agent = RandomAgent(player_id=2, name="C", role=Role.VILLAGER)
        decisions = agent.on_night(self.state, [], {})
        self.assertEqual(decisions, [])

    def test_on_discussion_returns_string(self):
        agent = RandomAgent(player_id=2, name="C", role=Role.VILLAGER)
        speech = agent.on_discussion(self.state)
        self.assertIsInstance(speech, str)
        self.assertTrue(len(speech) > 0)

    def test_on_vote_returns_valid_target(self):
        agent = RandomAgent(player_id=2, name="C", role=Role.VILLAGER)
        target = agent.on_vote(self.state)
        self.assertIn(target, [0, 1])

    def test_on_hunter_shot(self):
        agent = RandomAgent(player_id=0, name="A", role=Role.HUNTER)
        target = agent.on_hunter_shot(self.state)
        self.assertIsNotNone(target)

    def test_on_last_words(self):
        agent = RandomAgent(player_id=0, name="A", role=Role.VILLAGER)
        words = agent.on_last_words(self.state)
        self.assertIsInstance(words, str)


class TestAgentRegistry(unittest.TestCase):
    def test_create_random_agent(self):
        registry = AgentRegistry()
        registry.set_agent_type(AgentType.RANDOM)
        agent = registry.create_agent(0, "Test", Role.VILLAGER)
        self.assertIsInstance(agent, RandomAgent)

    @patch("agents.registry.AgentRegistry.create_agent")
    def test_get_agent(self, mock_create):
        registry = AgentRegistry()
        registry._agents[0] = RandomAgent(0, "Test", Role.VILLAGER)
        agent = registry.get_agent(0)
        self.assertIsNotNone(agent)

    def test_get_agent_not_found(self):
        registry = AgentRegistry()
        self.assertIsNone(registry.get_agent(99))

    def test_get_all_agents(self):
        registry = AgentRegistry()
        registry._agents[0] = RandomAgent(0, "A", Role.VILLAGER)
        registry._agents[1] = RandomAgent(1, "B", Role.WEREWOLF)
        all_a = registry.get_all_agents()
        self.assertEqual(len(all_a), 2)


if __name__ == "__main__":
    unittest.main()
