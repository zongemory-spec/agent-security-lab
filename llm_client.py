from __future__ import annotations

from openai import OpenAI

from config import ProviderConfig, require_api_key


class RealLLMClient:
    def __init__(self, cfg: ProviderConfig):
        require_api_key(cfg)
        self.cfg = cfg
        self.client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)

    def chat(self, messages: list[dict], tools: list[dict] | None = None):
        kwargs = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": 0,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # Keep Qwen tool-calling deterministic-ish and avoid thinking/tool-call compatibility surprises.
        if self.cfg.provider == "qwen":
            kwargs["extra_body"] = {"enable_thinking": False}

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message
