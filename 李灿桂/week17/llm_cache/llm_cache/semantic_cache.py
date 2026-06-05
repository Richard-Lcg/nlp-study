from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Optional

import numpy as np

from llm_cache.redis_client import RedisClient


class SemanticCache:
    """语义缓存

    针对 LLM 调用，基于语义相似度缓存请求-结果对。
    核心思路：将输入文本向量化，在缓存中查找语义相似的已缓存结果。
    """

    def __init__(
        self,
        redis: RedisClient,
        prefix: str = "sem_cache",
        ttl: int = 3600,
        similarity_threshold: float = 0.92,
    ):
        self.redis = redis
        self.prefix = prefix
        self.ttl = ttl
        self.similarity_threshold = similarity_threshold

    def _cache_key(self, text: str) -> str:
        digest = hashlib.md5(text.strip().encode()).hexdigest()
        return f"{self.prefix}:{digest}"

    def _vector_key(self, text: str) -> str:
        return f"{self.prefix}_vec:{hashlib.md5(text.strip().encode()).hexdigest()}"

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        arr_a = np.array(a, dtype=np.float32)
        arr_b = np.array(b, dtype=np.float32)
        norm_a = np.linalg.norm(arr_a)
        norm_b = np.linalg.norm(arr_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(arr_a, arr_b) / (norm_a * norm_b))

    def get(self, text: str, embedding_fn: Optional[callable] = None) -> Optional[str]:
        """获取语义匹配的缓存结果

        Args:
            text: 用户输入文本
            embedding_fn: 可选的嵌入函数，用于将输入文本向量化以进行语义匹配

        Returns:
            缓存的响应文本，如未命中返回 None
        """
        # 1. 尝试精确匹配
        exact_key = self._cache_key(text)
        exact = self.redis.get(exact_key)
        if exact is not None:
            return exact

        # 2. 尝试语义匹配（需要嵌入函数）
        if embedding_fn is None:
            return None

        input_vector = embedding_fn(text)
        if input_vector is None:
            return None

        # 扫描所有缓存的向量，计算相似度
        best_match = None
        best_score = 0.0
        cursor = 0
        while True:
            cursor, keys = self.redis.conn.scan(cursor, match=f"{self.prefix}_vec:*", count=100)
            if not keys:
                if cursor == 0:
                    break
                continue

            for vec_key in keys:
                cached_vec_json = self.redis.get(vec_key)
                if cached_vec_json is None:
                    continue
                try:
                    cached_vec = json.loads(cached_vec_json)
                except (json.JSONDecodeError, TypeError):
                    continue

                score = self._cosine_similarity(input_vector, cached_vec)
                if score > best_score:
                    best_score = score
                    best_match = vec_key

            if cursor == 0:
                break

        if best_match is None or best_score < self.similarity_threshold:
            return None

        # 从匹配的向量键反查缓存结果
        original_input = best_match.replace(f"{self.prefix}_vec:", "", 1)
        result_key = f"{self.prefix}:{original_input}"
        return self.redis.get(result_key)

    def set(self, text: str, response: str, embedding: Optional[list[float]] = None) -> bool:
        """缓存 LLM 请求-结果对

        Args:
            text: 用户输入文本
            response: LLM 输出
            embedding: 可选的嵌入向量，用于后续语义匹配
        """
        key = self._cache_key(text)
        ok = self.redis.set(key, response, ttl=self.ttl)

        if embedding is not None:
            vec_key = self._vector_key(text)
            self.redis.set(vec_key, embedding, ttl=self.ttl)

        return ok

    def invalidate(self, text: str) -> bool:
        """使指定文本的缓存失效"""
        key = self._cache_key(text)
        vec_key = self._vector_key(text)
        self.redis.delete(key, vec_key)
        return True

    def clear(self) -> int:
        """清除所有语义缓存"""
        deleted = 0
        cursor = 0
        while True:
            cursor, keys = self.redis.conn.scan(cursor, match=f"{self.prefix}:*", count=100)
            if keys:
                deleted += self.redis.delete(*keys)
            if cursor == 0:
                break
        cursor = 0
        while True:
            cursor, keys = self.redis.conn.scan(cursor, match=f"{self.prefix}_vec:*", count=100)
            if keys:
                deleted += self.redis.delete(*keys)
            if cursor == 0:
                break
        return deleted

    def stats(self) -> dict[str, Any]:
        """缓存统计"""
        result_count = 0
        vec_count = 0
        cursor = 0
        while True:
            cursor, keys = self.redis.conn.scan(cursor, match=f"{self.prefix}:*", count=1000)
            result_count += len(keys)
            if cursor == 0:
                break
        cursor = 0
        while True:
            cursor, keys = self.redis.conn.scan(cursor, match=f"{self.prefix}_vec:*", count=1000)
            vec_count += len(keys)
            if cursor == 0:
                break
        return {
            "prefix": self.prefix,
            "cached_responses": result_count,
            "cached_vectors": vec_count,
            "default_ttl": self.ttl,
            "similarity_threshold": self.similarity_threshold,
        }
