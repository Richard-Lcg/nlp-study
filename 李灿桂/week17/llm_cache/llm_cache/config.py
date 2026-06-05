from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CacheConfig:
    """全局缓存配置"""

    # Redis 连接配置（默认本地）
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_decode_responses: bool = True

    # 连接池
    redis_pool_max_connections: int = 20
    redis_socket_timeout: int = 5
    redis_socket_connect_timeout: int = 3

    # 语义缓存
    semantic_cache_ttl: int = 3600  # 默认缓存1小时
    semantic_similarity_threshold: float = 0.92

    # 嵌入缓存
    embedding_cache_ttl: int = 7200  # 默认缓存2小时

    # 对话管理
    conversation_ttl: int = 86400  # 默认保存1天
    max_conversation_turns: int = 50

    # 向量索引
    vector_dimension: int = 768
    index_timeout: int = 10
