from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

_CONFIG_DIR = Path(__file__).parent
_CONFIG_FILE = _CONFIG_DIR / "config.yaml"


def _resolve_env_refs(value: Any) -> Any:
    """递归遍历并替换所有字符串中的 ${ENV_VAR}"""
    if isinstance(value, str):
        def _replace(m: re.Match):
            var = m.group(1)
            return os.environ.get(var, "")
        return re.sub(r"\$\{(\w+)\}", _replace, value)
    if isinstance(value, dict):
        return {k: _resolve_env_refs(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_refs(v) for v in value]
    return value


def _load_yaml(path: Path) -> dict:
    """加载 YAML 配置文件"""
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config() -> dict:
    """加载配置并解析环境变量引用"""
    if not _CONFIG_FILE.exists():
        return {"llm": {"api_key": "", "model": "claude-sonnet-4-20250514", "base_url": None, "max_tokens": 1024}}

    raw = _load_yaml(_CONFIG_FILE)
    return _resolve_env_refs(raw)


def get_llm_config() -> dict:
    """获取 LLM 配置节"""
    cfg = load_config()
    return cfg.get("llm", {})


# 模块级缓存
_llm_config: dict | None = None


def get_llm_config_cached() -> dict:
    global _llm_config
    if _llm_config is None:
        _llm_config = get_llm_config()
    return _llm_config
