from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv



@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    api_key: str
    base_url: str
    model: str


def get_provider_config(provider: str | None = None) -> ProviderConfig:
    load_dotenv(os.getenv("LAB_PROVIDER_ENV_FILE") or None)
    provider = (provider or os.getenv("LLM_PROVIDER", "qwen")).strip().lower()

    if provider == "qwen":
        key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        return ProviderConfig(
            provider="qwen",
            api_key=key,
            base_url=os.getenv(
                "QWEN_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ).strip(),
            model=os.getenv("QWEN_MODEL", "qwen-plus").strip(),
        )

    if provider == "deepseek":
        key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        return ProviderConfig(
            provider="deepseek",
            api_key=key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip(),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro").strip(),
        )

    raise ValueError("LLM_PROVIDER must be 'qwen' or 'deepseek'")


def require_api_key(cfg: ProviderConfig) -> None:
    if not cfg.api_key or cfg.api_key == "replace_me":
        env_name = "DASHSCOPE_API_KEY" if cfg.provider == "qwen" else "DEEPSEEK_API_KEY"
        raise RuntimeError(
            f"Missing API key. Put {env_name}=... in .env (do not hard-code it in Python)."
        )


def get_agent_mode() -> str:
    mode = os.getenv("AGENT_MODE", "secure").strip().lower()
    if mode not in {"secure", "vulnerable"}:
        raise ValueError("AGENT_MODE must be 'secure' or 'vulnerable'")
    return mode


def get_max_tool_rounds() -> int:
    try:
        value = int(os.getenv("MAX_TOOL_ROUNDS", "4"))
    except ValueError:
        value = 4
    return max(1, min(value, 10))
