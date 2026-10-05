"""OpenAI-compatible HTTP wire protocol, with bounded timeout and no retries."""
from __future__ import annotations
import httpx
from config import require_api_key

class ModelError(Exception):
    def __init__(self, reason, status=502):
        self.reason, self.status = reason, status
        super().__init__(reason)

class RealLLMClient:
    def __init__(self, cfg, timeout=15):
        require_api_key(cfg)
        self.cfg, self.timeout = cfg, timeout

    async def chat(self, messages, tools=None):
        payload = {"model": self.cfg.model, "messages": messages, "temperature": 0}
        if tools:
            payload.update(tools=tools, tool_choice="auto")
        if self.cfg.provider == "qwen":
            payload["enable_thinking"] = False
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.cfg.base_url.rstrip("/") + "/chat/completions",
                    headers={"Authorization": "Bearer " + self.cfg.api_key}, json=payload)
            if response.status_code == 429:
                raise ModelError("model_rate_limited", 503)
            if response.status_code >= 400:
                raise ModelError("model_upstream_error")
            message = response.json()["choices"][0]["message"]
            if not isinstance(message, dict):
                raise ValueError()
            return message
        except httpx.TimeoutException:
            raise ModelError("model_timeout", 504) from None
        except (httpx.HTTPError, ValueError, KeyError, IndexError):
            raise ModelError("model_invalid_response") from None

