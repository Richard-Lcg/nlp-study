import pytest
import numpy as np
from llm_cache import CacheConfig, RedisClient, SemanticCache, EmbeddingCache


@pytest.fixture
def redis():
    config = CacheConfig(redis_db=1)
    client = RedisClient(config)
    yield client
    client.conn.flushdb()
    client.close()


@pytest.fixture
def sem_cache(redis):
    cache = SemanticCache(redis, ttl=60, similarity_threshold=0.9)
    yield cache


def mock_embedding(text: str, dim: int = 16) -> list[float]:
    """基于关键词的 mock 嵌入：共享关键词的文本产生高相似度向量"""
    vec = [0.0] * dim
    # 关键词 → 固定位置映射（确保语义相似的文本有高相似度）
    kw_positions = {
        "机器": 0, "学习": 0, "ML": 0,
        "天气": 2,
        "做菜": 3, "烹饪": 3,
    }
    for kw, pos in kw_positions.items():
        if kw in text:
            vec[pos] += 5.0
    # 字符级信号，保留文本差异性
    for i, char in enumerate(text):
        pos = (ord(char) + i * 7) % dim
        vec[pos] += 0.2
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


class TestEmbeddingCache:
    def test_set_and_get(self, redis):
        cache = EmbeddingCache(redis, ttl=60)
        vector = [0.1, 0.2, 0.3]
        assert cache.set("hello", vector)
        cached = cache.get("hello")
        assert cached == vector

    def test_cache_miss(self, redis):
        cache = EmbeddingCache(redis)
        assert cache.get("not_cached") is None

    def test_bulk_operations(self, redis):
        cache = EmbeddingCache(redis)
        pairs = [("a", [0.1, 0.2]), ("b", [0.3, 0.4])]
        assert cache.bulk_set(pairs) == 2
        results = cache.bulk_get(["a", "b", "c"])
        assert results[0] == [0.1, 0.2]
        assert results[1] == [0.3, 0.4]
        assert results[2] is None

    def test_clear(self, redis):
        cache = EmbeddingCache(redis)
        cache.set("x", [1.0, 2.0])
        assert cache.clear() > 0
        assert cache.get("x") is None


class TestSemanticCache:
    def test_exact_match(self, sem_cache):
        sem_cache.set("你好", "你好！有什么可以帮助你的？", embedding=[0.1] * 16)
        result = sem_cache.get("你好")
        assert result == "你好！有什么可以帮助你的？"

    def test_semantic_match(self, sem_cache):
        vec = mock_embedding("什么是机器学习", 16)
        sem_cache.set("什么是机器学习", "机器学习是AI的一个分支。", embedding=vec)

        result = sem_cache.get("能解释机器学习吗", embedding_fn=lambda x: mock_embedding(x, 16))
        assert result is not None
        assert "机器学习" in result

    def test_low_similarity_no_match(self, sem_cache):
        sem_cache.set("今天天气好", "是的，天气很好。", embedding=[1.0] * 16)
        result = sem_cache.get("如何做菜", embedding_fn=lambda x: [0.0] * 16)
        assert result is None

    def test_invalidate(self, sem_cache):
        sem_cache.set("test", "value")
        assert sem_cache.get("test") is not None
        sem_cache.invalidate("test")
        assert sem_cache.get("test") is None
