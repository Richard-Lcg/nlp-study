from __future__ import annotations

from typing import Optional

from config import get_llm_config_cached


class LLMClient:
    """LLM API 客户端封装 — 支持 Anthropic SDK 和 OpenAI 兼容 API"""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        max_tokens: int | None = None,
    ):
        cfg = get_llm_config_cached()
        self.api_key = api_key or cfg.get("api_key", "") or ""
        self.model = model or cfg.get("model", "claude-sonnet-4-20250514")
        self.base_url = base_url or cfg.get("base_url") or ""
        self.max_tokens = max_tokens or cfg.get("max_tokens", 1024)
        self._client = None
        self._use_openai = self._detect_openai_compat()

    @staticmethod
    def _detect_openai_compat() -> bool:
        """检测是否为 OpenAI 兼容 API（非 Anthropic 原生 API）"""
        cfg = get_llm_config_cached()
        base_url = (cfg.get("base_url") or "").lower()
        # Anthropic 官方 API 使用 anthropic 域名
        if not base_url or "anthropic.com" in base_url:
            return False
        return True

    def _ensure_client(self):
        if self._client is not None:
            return

        if self._use_openai:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url or None,
                )
            except ImportError:
                raise ImportError(
                    "OpenAI-compatible LLM 需要 openai 包。运行: pip install openai"
                )
        else:
            try:
                from anthropic import Anthropic
                kwargs: dict = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = Anthropic(**kwargs)
            except ImportError:
                raise ImportError(
                    "anthropic 包未安装。运行: pip install anthropic"
                )

    def chat(self, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> str:
        self._ensure_client()
        mt = max_tokens or self.max_tokens

        if self._use_openai:
            response = self._client.chat.completions.create(
                model=self.model,
                max_tokens=mt,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content or ""
        else:
            response = self._client.messages.create(
                model=self.model,
                system=system_prompt,
                max_tokens=mt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
