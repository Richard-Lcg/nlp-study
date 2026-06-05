from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from llm_cache.redis_client import RedisClient


class EmbeddingCache:
    """嵌入缓存

    缓存文本到向量的转换结果，避免对相同内容重复进行嵌入计算。
    使用文本的 MD5 哈希作为缓存键。
    """

    def __init__(self, redis: RedisClient, prefix: str = "embed_cache", ttl: int = 7200):
        self.redis = redis
        self.prefix = prefix
        self.ttl = ttl

    def _make_key(self, text: str, model_name: str = "") -> str:
        raw = f"{model_name}:{text.strip().lower()}"
        digest = hashlib.md5(raw.encode()).hexdigest()
        return f"{self.prefix}:{digest}"

    def get(self, text: str, model_name: str = "") -> Optional[list[float]]:
        """获取缓存的嵌入向量"""
        key = self._make_key(text, model_name)
        val = self.redis.get(key)
        if val is None:
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return None

    def set(self, text: str, vector: list[float], model_name: str = "") -> bool:
        """缓存嵌入向量"""
        key = self._make_key(text, model_name)
        return self.redis.set(key, vector, ttl=self.ttl)

    def bulk_get(self, texts: list[str], model_name: str = "") -> list[Optional[list[float]]]:
        """批量获取缓存的嵌入向量"""
        keys = [self._make_key(t, model_name) for t in texts]
        pipe = self.redis.conn.pipeline(transaction=False)
        for k in keys:
            pipe.get(k)
        raw_values = pipe.execute()
        results: list[Optional[list[float]]] = []
        for val in raw_values:
            if val is None:
                results.append(None)
            else:
                try:
                    results.append(json.loads(val))
                except (json.JSONDecodeError, TypeError):
                    results.append(None)
        return results

    def bulk_set(self, pairs: list[tuple[str, list[float]]], model_name: str = "") -> int:
        """批量缓存嵌入向量"""
        pipe = self.redis.conn.pipeline(transaction=False)
        for text, vector in pairs:
            key = self._make_key(text, model_name)
            pipe.set(key, json.dumps(vector, ensure_ascii=False), ex=self.ttl)
        results = pipe.execute()
        return sum(1 for r in results if r)

    def clear(self) -> int:
        """清除所有嵌入缓存"""
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = self.redis.conn.scan(cursor, match=f"{self.prefix}:*", count=100)
            if keys:
                deleted += self.redis.delete(*keys)
            if cursor == 0:
                break
        return deleted

    def stats(self) -> dict[str, Any]:
        """缓存统计信息"""
        cursor = 0
        total = 0
        while True:
            cursor, keys = self.redis.conn.scan(cursor, match=f"{self.prefix}:*", count=1000)
            total += len(keys)
            if cursor == 0:
                break
        return {
            "prefix": self.prefix,
            "total_keys": total,
            "default_ttl": self.ttl,
        }
