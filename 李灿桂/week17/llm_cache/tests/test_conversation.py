import pytest
from llm_cache import CacheConfig, RedisClient, ConversationManager


@pytest.fixture
def redis():
    config = CacheConfig(redis_db=1)
    client = RedisClient(config)
    yield client
    client.conn.flushdb()
    client.close()


@pytest.fixture
def conv_mgr(redis):
    return ConversationManager(redis, ttl=300, max_turns=5)


class TestConversationManager:
    def test_add_and_get_messages(self, conv_mgr):
        conv_mgr.add_message("s1", "user", "你好")
        conv_mgr.add_message("s1", "assistant", "你好！")
        history = conv_mgr.get_history("s1")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "你好"

    def test_empty_session(self, conv_mgr):
        history = conv_mgr.get_history("nonexistent")
        assert history == []

    def test_session_isolation(self, conv_mgr):
        conv_mgr.add_message("s1", "user", "msg1")
        conv_mgr.add_message("s2", "user", "msg2")
        assert len(conv_mgr.get_history("s1")) == 1
        assert len(conv_mgr.get_history("s2")) == 1

    def test_clear_history(self, conv_mgr):
        conv_mgr.add_message("s1", "user", "hello")
        assert conv_mgr.clear_history("s1")
        assert conv_mgr.get_history("s1") == []

    def test_max_turns_enforced(self, conv_mgr):
        for i in range(12):
            conv_mgr.add_message("s1", "user", f"msg{i}")
            conv_mgr.add_message("s1", "assistant", f"ans{i}")
        history = conv_mgr.get_history("s1")
        assert len(history) <= conv_mgr.max_turns * 2

    def test_format_for_llm(self, conv_mgr):
        conv_mgr.add_message("s1", "user", "hi")
        conv_mgr.add_message("s1", "assistant", "hello")
        messages = conv_mgr.format_for_llm("s1", system_prompt="助手")
        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"

    def test_get_all_sessions(self, conv_mgr):
        conv_mgr.add_message("s1", "user", "a")
        conv_mgr.add_message("s2", "user", "b")
        sessions = conv_mgr.get_all_sessions()
        assert "s1" in sessions
        assert "s2" in sessions
