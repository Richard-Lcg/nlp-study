from __future__ import annotations

from typing import Any, Callable, Optional


class SemanticRouter:
    """语义路由器

    根据用户输入的语义将其路由到不同的处理模块。
    通过预定义的"路由声明"（route declarations）和嵌入相似度匹配实现。
    """

    def __init__(
        self,
        embedding_fn: Callable[[str], list[float]],
        similarity_threshold: float = 0.85,
    ):
        self.embedding_fn = embedding_fn
        self.similarity_threshold = similarity_threshold
        self._routes: list[dict[str, Any]] = []

    def add_route(
        self,
        name: str,
        description: str,
        handler: Optional[Callable] = None,
        examples: Optional[list[str]] = None,
    ) -> None:
        """注册一个路由

        Args:
            name: 路由名称
            description: 路由描述
            handler: 可选的处理器函数
            examples: 可选的示例文本，用于丰富语义表示
        """
        texts = [description]
        if examples:
            texts.extend(examples)

        # 对所有描述文本取平均作为路由的嵌入向量
        vectors = [self.embedding_fn(t) for t in texts]
        dim = len(vectors[0])
        avg_vector = [sum(v[i] for v in vectors) / len(vectors) for i in range(dim)]

        self._routes.append({
            "name": name,
            "description": description,
            "handler": handler,
            "vector": avg_vector,
            "examples": examples or [],
        })

    def route(self, text: str) -> Optional[dict[str, Any]]:
        """将输入路由到最匹配的路由

        Returns:
            最匹配的路由信息，如无匹配返回 None
        """
        if not self._routes:
            return None

        input_vector = self.embedding_fn(text)
        if input_vector is None:
            return None

        best_route = None
        best_score = 0.0

        for route in self._routes:
            score = self._cosine_similarity(input_vector, route["vector"])
            if score > best_score:
                best_score = score
                best_route = route

        if best_score < self.similarity_threshold:
            return None

        return {
            "name": best_route["name"],
            "description": best_route["description"],
            "handler": best_route["handler"],
            "score": best_score,
        }

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        import numpy as np
        arr_a = np.array(a, dtype=np.float32)
        arr_b = np.array(b, dtype=np.float32)
        norm_a = np.linalg.norm(arr_a)
        norm_b = np.linalg.norm(arr_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(arr_a, arr_b) / (norm_a * norm_b))

    def list_routes(self) -> list[dict[str, Any]]:
        return [
            {"name": r["name"], "description": r["description"], "examples": r["examples"]}
            for r in self._routes
        ]

    def remove_route(self, name: str) -> bool:
        before = len(self._routes)
        self._routes = [r for r in self._routes if r["name"] != name]
        return len(self._routes) < before
