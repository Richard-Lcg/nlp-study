import pytest
import struct
import numpy as np
from llm_cache import CacheConfig, RedisClient, VectorIndex


@pytest.fixture
def redis():
    config = CacheConfig(redis_db=1)
    client = RedisClient(config)
    yield client
    try:
        client.conn.execute_command("FT.DROPINDEX", "test_idx")
    except Exception:
        pass
    client.conn.flushdb()
    client.close()


class TestVectorIndex:
    def test_create_index(self, redis):
        index = VectorIndex(redis, "test_idx", dimension=4, metric="COSINE", algorithm="FLAT")
        assert index.create_index() is True
        # 重复创建不报错
        assert index.create_index() is False

    def test_add_and_search(self, redis):
        index = VectorIndex(redis, "test_idx", dimension=4, metric="COSINE", algorithm="FLAT")
        index.create_index()

        index.add_vector("a", [0.1, 0.2, 0.3, 0.4], {"title": "doc_a"})
        index.add_vector("b", [0.9, 0.8, 0.7, 0.6], {"title": "doc_b"})

        import time
        time.sleep(0.5)

        results = index.search([0.1, 0.2, 0.3, 0.4], top_k=5)
        assert len(results) >= 1

    def test_batch_add(self, redis):
        index = VectorIndex(redis, "test_idx", dimension=4, metric="COSINE", algorithm="FLAT")
        index.create_index()

        vectors = [
            ("a", [0.1, 0.2, 0.3, 0.4], {"cat": "tech"}),
            ("b", [0.5, 0.6, 0.7, 0.8], {"cat": "food"}),
        ]
        assert index.add_vectors_batch(vectors) == 2

    def test_delete_index(self, redis):
        index = VectorIndex(redis, "test_idx", dimension=4)
        index.create_index()
        assert index.delete_index() is True

    def test_unsupported_metric(self, redis):
        with pytest.raises(ValueError):
            VectorIndex(redis, "bad_idx", metric="EUCLIDEAN")

    def test_unsupported_algorithm(self, redis):
        with pytest.raises(ValueError):
            VectorIndex(redis, "bad_idx", algorithm="ANNOY")
