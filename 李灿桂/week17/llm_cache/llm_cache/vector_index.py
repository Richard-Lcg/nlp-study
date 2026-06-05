from __future__ import annotations

import json
import struct
import time
from typing import Any, Optional

import numpy as np

from llm_cache.redis_client import RedisClient


class VectorIndex:
    """向量索引管理器

    支持多种距离度量：L2（欧氏距离）、IP（内积）、COSINE（余弦相似度）。
    优先使用 Redis Stack 的 RediSearch 模块，不可用时自动回退到纯 Python 实现。
    """

    SUPPORTED_METRICS = {"L2", "IP", "COSINE"}
    SUPPORTED_ALGORITHMS = {"FLAT", "HNSW"}

    def __init__(
        self,
        redis: RedisClient,
        index_name: str,
        dimension: int = 768,
        metric: str = "COSINE",
        algorithm: str = "HNSW",
    ):
        if metric.upper() not in self.SUPPORTED_METRICS:
            raise ValueError(f"不支持的度量: {metric}，支持: {self.SUPPORTED_METRICS}")
        if algorithm.upper() not in self.SUPPORTED_ALGORITHMS:
            raise ValueError(f"不支持的算法: {algorithm}，支持: {self.SUPPORTED_ALGORITHMS}")

        self.redis = redis
        self.index_name = index_name
        self.dimension = dimension
        self.metric = metric.upper()
        self.algorithm = algorithm.upper()
        self._prefix = f"{index_name}:"
        self._vector_field = "embedding"
        self._meta_key = f"{index_name}:__meta__"
        self._use_redisearch: Optional[bool] = None

    def _has_redisearch(self) -> bool:
        """检测 Redis 是否支持 RediSearch 模块"""
        if self._use_redisearch is not None:
            return self._use_redisearch
        try:
            self.redis.conn.execute_command("FT.INFO", "_dummy_check_")
            self._use_redisearch = True
        except Exception:
            self._use_redisearch = False
        return self._use_redisearch

    def create_index(self) -> bool:
        """创建向量索引"""
        if self._has_redisearch():
            cmd = [
                "FT.CREATE", self.index_name,
                "ON", "HASH",
                "PREFIX", "1", self._prefix,
                "SCHEMA",
                self._vector_field, "VECTOR", self.algorithm,
                "6",
                "TYPE", "FLOAT32",
                "DIM", str(self.dimension),
                "DISTANCE_METRIC", self.metric,
            ]
            try:
                self.redis.conn.execute_command(*cmd)
                return True
            except Exception as e:
                if "already exists" in str(e).lower():
                    return False
                raise
        # 纯 Python 回退：用 meta key 记录索引是否存在
        if self.redis.exists(self._meta_key):
            return False
        self.redis.set(self._meta_key, json.dumps({
            "type": "native_fallback",
            "dimension": self.dimension,
            "metric": self.metric,
            "algorithm": self.algorithm,
        }))
        return True

    def _native_add_vector(self, key: str, vector: list[float], metadata: Optional[dict[str, Any]] = None) -> None:
        """纯 Python 回退：将向量存为 hash 字段（JSON 编码避免 decode_responses 冲突）"""
        mapping: dict[str, Any] = {
            "__vector_json": json.dumps(vector, ensure_ascii=False),
        }
        if metadata:
            for k, v in metadata.items():
                mapping[k] = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        self.redis.conn.hset(key, mapping=mapping)

    def _native_search(
        self,
        query_vector: list[float],
        top_k: int,
        filter_expr: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """纯 Python 回退：扫描所有向量在客户端计算相似度"""
        query_arr = np.array(query_vector, dtype=np.float32)
        query_norm = np.linalg.norm(query_arr)
        if query_norm == 0:
            return []

        cursor = 0
        results: list[tuple[float, str]] = []
        score_field = "score"

        while True:
            cursor, keys = self.redis.conn.scan(cursor, match=f"{self._prefix}*", count=200)
            for key in keys:
                if key == self._meta_key:
                    continue
                vec_json = self.redis.conn.hget(key, "__vector_json")
                if vec_json is None:
                    continue
                try:
                    vec = json.loads(vec_json)
                except (json.JSONDecodeError, TypeError):
                    continue
                vec_arr = np.array(vec, dtype=np.float32)
                vec_norm = np.linalg.norm(vec_arr)
                if vec_norm == 0:
                    continue

                if self.metric == "COSINE":
                    score = float(np.dot(query_arr, vec_arr) / (query_norm * vec_norm))
                elif self.metric == "IP":
                    score = float(np.dot(query_arr, vec_arr))
                else:  # L2
                    dist = float(np.linalg.norm(query_arr - vec_arr))
                    score = 1.0 / (1.0 + dist)

                results.append((score, key))

            if cursor == 0:
                break

        results.sort(key=lambda x: -x[0])
        top = results[:top_k]

        out: list[dict[str, Any]] = []
        for score, key in top:
            entry: dict[str, Any] = {"key": key, score_field: round(score, 6)}
            raw_fields = self.redis.conn.hgetall(key)
            for fk, fv in raw_fields.items():
                if fk in (b"__vector_json", b"__dim") or fk in ("__vector_json", "__dim"):
                    continue
                if isinstance(fv, bytes):
                    entry[fk.decode() if isinstance(fk, bytes) else fk] = fv.decode()
                else:
                    entry[fk] = fv
            out.append(entry)
        return out

    def add_vector(
        self,
        doc_id: str,
        vector: list[float],
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """添加向量到索引"""
        key = f"{self._prefix}{doc_id}"
        if self._has_redisearch():
            blob = struct.pack(f"{len(vector)}f", *vector)
            mapping: dict[str, Any] = {self._vector_field: blob}
            if metadata:
                mapping.update(metadata)
            self.redis.conn.hset(key, mapping=mapping)
        else:
            self._native_add_vector(key, vector, metadata)
        return True

    def add_vectors_batch(
        self,
        vectors: list[tuple[str, list[float], Optional[dict[str, Any]]]],
    ) -> int:
        """批量添加向量"""
        pipe = self.redis.conn.pipeline(transaction=False)
        for doc_id, vector, metadata in vectors:
            key = f"{self._prefix}{doc_id}"
            if self._has_redisearch():
                blob = struct.pack(f"{len(vector)}f", *vector)
                mapping: dict[str, Any] = {self._vector_field: blob}
                if metadata:
                    mapping.update(metadata)
                pipe.hset(key, mapping=mapping)
            else:
                # 纯 Python 回退不支持 pipeline 中的 hset mapping，逐个处理
                self._native_add_vector(key, vector, metadata)
        if self._has_redisearch():
            results = pipe.execute()
            return sum(1 for r in results if r)
        return len(vectors)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filter_expr: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """执行向量搜索

        Args:
            query_vector: 查询向量
            top_k: 返回 top-k 结果
            filter_expr: 可选的过滤表达式，如 "@category:{tech}"

        Returns:
            按相似度降序排列的结果列表
        """
        if self._has_redisearch():
            blob = struct.pack(f"{len(query_vector)}f", *query_vector)
            score_field = "score"

            base_query = f"@{self._vector_field}:[VECTOR_RANGE $vec_radius $vec_blob]=>{{$yield_distance_as: ${score_field}}}"
            if filter_expr:
                full_query = f"({base_query} {filter_expr})"
            else:
                full_query = base_query

            cmd = [
                "FT.SEARCH", self.index_name, full_query,
                "RETURN", "2", score_field, "id",
                "SORTBY", score_field,
                "DIALECT", "2",
                "PARAMS", "4",
                "vec_radius", str(1.0),
                "vec_blob", blob.decode("latin-1"),
                "LIMIT", "0", str(top_k),
            ]
            try:
                raw = self.redis.conn.execute_command(*cmd)
            except Exception:
                return []

            return self._parse_search_results(raw, score_field)

        return self._native_search(query_vector, top_k, filter_expr)

    def _parse_search_results(self, raw: list, score_field: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not raw or len(raw) < 2:
            return results
        i = 1
        while i < len(raw):
            key = raw[i]
            fields = raw[i + 1] if i + 1 < len(raw) else []
            entry: dict[str, Any] = {"key": key, score_field: 1.0}
            for j in range(0, len(fields) - 1, 2):
                entry[fields[j]] = fields[j + 1]
            results.append(entry)
            i += 2
        results.sort(key=lambda x: float(x.get(score_field, 1.0)))
        return results

    def delete_index(self) -> bool:
        """删除索引"""
        if self._has_redisearch():
            try:
                self.redis.conn.execute_command("FT.DROPINDEX", self.index_name)
                return True
            except Exception:
                return False
        # Python 回退：删除所有关联键
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = self.redis.conn.scan(cursor, match=f"{self._prefix}*", count=200)
            if keys:
                deleted += self.redis.delete(*keys)
            if cursor == 0:
                break
        return deleted > 0

    def info(self) -> dict[str, Any]:
        """获取索引信息"""
        if self._has_redisearch():
            try:
                raw = self.redis.conn.execute_command("FT.INFO", self.index_name)
                info: dict[str, Any] = {}
                for i in range(0, len(raw), 2):
                    info[raw[i]] = raw[i + 1]
                return info
            except Exception:
                return {}
        # Python 回退
        meta = self.redis.get_json(self._meta_key)
        if not meta:
            return {}
        cursor = 0
        count = 0
        while True:
            cursor, keys = self.redis.conn.scan(cursor, match=f"{self._prefix}*", count=200)
            count += len(keys)
            if cursor == 0:
                break
        return {
            "index_name": self.index_name,
            "backend": "native_fallback",
            "num_docs": count,
            "dimension": meta.get("dimension", self.dimension),
            "metric": meta.get("metric", self.metric),
        }
