from __future__ import annotations

import json
import time
from typing import Any, Optional

from llm_cache.redis_client import RedisClient


class ConversationManager:
    """对话历史管理器

    基于 session id 分开存储对话历史，
    支持自动过期、截断和格式化输出。
    """

    def __init__(
        self,
        redis: RedisClient,
        prefix: str = "conversation",
        ttl: int = 86400,
        max_turns: int = 50,
    ):
        self.redis = redis
        self.prefix = prefix
        self.ttl = ttl
        self.max_turns = max_turns

    def _session_key(self, session_id: str) -> str:
        return f"{self.prefix}:{session_id}"

    def add_message(self, session_id: str, role: str, content: str) -> int:
        """添加一条消息到对话历史"""
        key = self._session_key(session_id)
        msg = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }
        pipe = self.redis.conn.pipeline(transaction=False)
        pipe.rpush(key, json.dumps(msg, ensure_ascii=False))
        pipe.expire(key, self.ttl)
        pipe.llen(key)
        results = pipe.execute()

        total = results[2]
        if total > self.max_turns * 2:
            trim_start = total - self.max_turns * 2
            self.redis.ltrim(key, trim_start, -1)

        return total

    def get_history(self, session_id: str, limit: Optional[int] = None) -> list[dict[str, Any]]:
        """获取对话历史"""
        key = self._session_key(session_id)
        raw_messages = self.redis.lrange(key, 0, limit if limit else self.max_turns * 2)
        messages: list[dict[str, Any]] = []
        for raw in raw_messages:
            try:
                msg = json.loads(raw) if isinstance(raw, str) else raw
                messages.append(msg)
            except (json.JSONDecodeError, TypeError):
                continue
        return messages

    def clear_history(self, session_id: str) -> bool:
        """清除指定 session 的对话历史"""
        key = self._session_key(session_id)
        self.redis.delete(key)
        return True

    def get_all_sessions(self) -> list[str]:
        """获取所有活跃的 session ID"""
        cursor = 0
        sessions: set[str] = set()
        prefix_match = f"{self.prefix}:*"
        while True:
            cursor, keys = self.redis.conn.scan(cursor, match=prefix_match, count=100)
            for key in keys:
                session_id = key.replace(f"{self.prefix}:", "", 1)
                sessions.add(session_id)
            if cursor == 0:
                break
        return sorted(sessions)

    def format_for_llm(
        self,
        session_id: str,
        system_prompt: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[dict[str, str]]:
        """格式化为 LLM 可直接使用的消息列表"""
        history = self.get_history(session_id, limit=limit)
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for msg in history:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })
        return messages
