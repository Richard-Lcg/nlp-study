from __future__ import annotations

import struct
from typing import Any, Optional

from llm_cache.redis_client import RedisClient


class HybridQuery:
    """混合查询引擎

    支持将向量相似性搜索与业务元数据过滤、关键词全文搜索灵活组合。
    """

    def __init__(
        self,
        redis: RedisClient,
        index_name: str,
        vector_field: str = "embedding",
    ):
        self.redis = redis
        self.index_name = index_name
        self.vector_field = vector_field

    def vector_search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filter_expr: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """向量相似性搜索 + 元数据过滤"""
        blob = struct.pack(f"{len(query_vector)}f", *query_vector)
        score_field = "score"

        base = f"@{self.vector_field}:[VECTOR_RANGE $vec_radius $vec_blob]=>{{$yield_distance_as: ${score_field}}}"
        query = f"({base} {filter_expr})" if filter_expr else base

        cmd = [
            "FT.SEARCH", self.index_name, query,
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

        return self._parse(raw, score_field)

    def fulltext_search(
        self,
        query_text: str,
        top_k: int = 10,
        filter_expr: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """全文关键词搜索 + 元数据过滤"""
        search_expr = query_text
        if filter_expr:
            search_expr = f"({search_expr} {filter_expr})"

        cmd = [
            "FT.SEARCH", self.index_name, search_expr,
            "LIMIT", "0", str(top_k),
            "DIALECT", "2",
        ]
        try:
            raw = self.redis.conn.execute_command(*cmd)
        except Exception:
            return []

        return self._parse(raw, "score")

    def hybrid_search(
        self,
        query_vector: list[float],
        query_text: str,
        top_k: int = 10,
        vector_weight: float = 0.7,
        filter_expr: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """混合搜索：向量 + 全文 + 元数据过滤

        Args:
            query_vector: 查询向量
            query_text: 查询文本
            top_k: 返回数量
            vector_weight: 向量搜索权重（0~1），文本搜索权重为 1 - vector_weight
            filter_expr: RediSearch 过滤表达式

        Returns:
            融合排序后的结果列表
        """
        # 分别执行向量搜索和全文搜索
        vec_results = self.vector_search(query_vector, top_k=top_k * 2, filter_expr=filter_expr)
        txt_results = self.fulltext_search(query_text, top_k=top_k * 2, filter_expr=filter_expr)

        # RRF（Reciprocal Rank Fusion）融合排序
        key_scores: dict[str, float] = {}

        for rank, r in enumerate(vec_results):
            key = r.get("key", "")
            key_scores[key] = key_scores.get(key, 0) + vector_weight * (1.0 / (rank + 1))

        for rank, r in enumerate(txt_results):
            key = r.get("key", "")
            key_scores[key] = key_scores.get(key, 0) + (1 - vector_weight) * (1.0 / (rank + 1))

        # 按融合分数降序排列
        ranked = sorted(key_scores.items(), key=lambda x: -x[1])

        # 收集结果
        seen = set()
        results: list[dict[str, Any]] = []
        for key, score in ranked[:top_k]:
            if key in seen:
                continue
            seen.add(key)
            results.append({
                "key": key,
                "hybrid_score": round(score, 4),
            })

        return results

    def _parse(self, raw: list, score_field: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not raw or len(raw) < 2:
            return results
        i = 1
        while i < len(raw):
            entry: dict[str, Any] = {"key": raw[i]}
            fields = raw[i + 1] if i + 1 < len(raw) else []
            for j in range(0, len(fields) - 1, 2):
                k = fields[j]
                v = fields[j + 1]
                if k == self.vector_field:
                    continue
                entry[k] = v
            results.append(entry)
            i += 2
        return results

    def create_index_with_fields(
        self,
        fields: list[dict[str, str]],
    ) -> bool:
        """创建同时包含向量字段和文本字段的复合索引

        Args:
            fields: 字段定义列表
                [{"name": "title", "type": "TEXT"},
                 {"name": "category", "type": "TAG"},
                 {"name": "price", "type": "NUMERIC"}]

        向量字段会自动加在最后。
        """
        cmd = ["FT.CREATE", self.index_name, "ON", "HASH", "PREFIX", "1", f"{self.index_name}:"]

        schema_parts = ["SCHEMA"]
        for f in fields:
            schema_parts.extend([f["name"], f["type"]])

        schema_parts.extend([
            self.vector_field, "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", "768",
            "DISTANCE_METRIC", "COSINE",
        ])
        cmd.append(" ".join(schema_parts))
        try:
            self.redis.conn.execute_command(*cmd)
            return True
        except Exception as e:
            if "already exists" in str(e).lower():
                return False
            raise
