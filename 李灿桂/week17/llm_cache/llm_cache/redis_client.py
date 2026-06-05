from __future__ import annotations

import json
from typing import Any, Optional

import redis as redis_py

from llm_cache.config import CacheConfig


class RedisClient:
    """Redis 连接管理器（线程安全的连接池）"""

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self._pool: Optional[redis_py.ConnectionPool] = None
        self._redis: Optional[redis_py.Redis] = None

    def _get_pool(self) -> redis_py.ConnectionPool:
        if self._pool is None:
            self._pool = redis_py.ConnectionPool(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password,
                decode_responses=self.config.redis_decode_responses,
                max_connections=self.config.redis_pool_max_connections,
                socket_timeout=self.config.redis_socket_timeout,
                socket_connect_timeout=self.config.redis_socket_connect_timeout,
            )
        return self._pool

    @property
    def conn(self) -> redis_py.Redis:
        if self._redis is None:
            self._redis = redis_py.Redis(connection_pool=self._get_pool())
        return self._redis

    # --- 通用操作 ---

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        kwargs: dict = {}
        if ttl is not None:
            kwargs["ex"] = ttl
        if not isinstance(value, (str, bytes)):
            value = json.dumps(value, ensure_ascii=False)
        return bool(self.conn.set(key, value, **kwargs))

    def get(self, key: str) -> Optional[Any]:
        val = self.conn.get(key)
        if val is None:
            return None
        return val

    def get_json(self, key: str) -> Optional[Any]:
        val = self.get(key)
        if val is None:
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val

    def delete(self, *keys: str) -> int:
        return self.conn.delete(*keys)

    def exists(self, key: str) -> bool:
        return bool(self.conn.exists(key))

    def expire(self, key: str, ttl: int) -> bool:
        return bool(self.conn.expire(key, ttl))

    def ttl(self, key: str) -> int:
        return self.conn.ttl(key)

    # --- 哈希操作 ---

    def hset(self, name: str, key: str, value: Any) -> int:
        if not isinstance(value, (str, bytes)):
            value = json.dumps(value, ensure_ascii=False)
        return self.conn.hset(name, key, value)

    def hget(self, name: str, key: str) -> Optional[Any]:
        return self.conn.hget(name, key)

    def hgetall(self, name: str) -> dict:
        return self.conn.hgetall(name) or {}

    def hdel(self, name: str, *keys: str) -> int:
        return self.conn.hdel(name, *keys)

    # --- 列表操作 ---

    def lpush(self, name: str, *values: Any) -> int:
        encoded = [
            json.dumps(v, ensure_ascii=False) if not isinstance(v, (str, bytes)) else v
            for v in values
        ]
        return self.conn.lpush(name, *encoded)

    def lrange(self, name: str, start: int = 0, end: int = -1) -> list[Any]:
        items = self.conn.lrange(name, start, end) or []
        return items

    def llen(self, name: str) -> int:
        return self.conn.llen(name)

    def ltrim(self, name: str, start: int, end: int) -> bool:
        return bool(self.conn.ltrim(name, start, end))

    # --- 集合操作 ---

    def sadd(self, name: str, *values: str) -> int:
        return self.conn.sadd(name, *values)

    def smembers(self, name: str) -> set:
        return self.conn.smembers(name) or set()

    def srem(self, name: str, *values: str) -> int:
        return self.conn.srem(name, *values)

    # --- 全文搜索（RediSearch 模块） ---

    def ft_create(self, index_name: str, schema: str) -> Optional[Any]:
        try:
            return self.conn.execute_command(f"FT.CREATE", index_name, "ON", "HASH", "PREFIX", "1", f"{index_name}:", "SCHEMA", *schema.split())
        except redis_py.ResponseError as e:
            if "already exists" in str(e).lower() or "index already" in str(e).lower():
                return None
            raise

    def ft_search(self, index_name: str, query: str) -> list:
        try:
            return self.conn.execute_command("FT.SEARCH", index_name, query)
        except redis_py.ResponseError:
            return []

    # --- 向量搜索（RedisStack） ---

    def _vector_similarity_command(self, key: str, vector_field: str, query_vector: list[float],
                                   k: int, score_field: str = "score") -> list:
        """构造并执行向量相似度搜索"""
        attr = f"{score_field}=$vec_score"
        cmd = [
            "FT.SEARCH", key,
            f"@{vector_field}:[VECTOR_RANGE $vec_radius $vec_blob]=>{{$yield_distance_as: ${score_field}}}",
            "RETURN", "1", score_field,
            "SORTBY", score_field,
            "DIALECT", "2",
            "PARAMS", "4", "vec_radius", str(1.0), "vec_blob",
            self._vector_to_bytes(query_vector).decode("latin-1"),
            "LIMIT", "0", str(k),
        ]
        return self.conn.execute_command(*cmd)

    def _vector_to_bytes(self, vector: list[float]) -> bytes:
        import struct
        return struct.pack(f"{len(vector)}f", *vector)

    def close(self):
        if self._redis:
            self._redis.close()
            self._redis = None
        if self._pool:
            self._pool.disconnect()
            self._pool = None
