"""OpenAI-compatible HTTP wire protocol, with bounded timeout and no retries."""
from __future__ import annotations
import httpx
from config import require_api_key

class ModelError(Exception):
    def __init__(self, reason, status=502):
        self.reason, self.status = reason, status
        super().__init__(reason)

class RealLLMClient:
    def __init__(self, cfg, timeout=15, max_requests=None):
        require_api_key(cfg)
        self.cfg, self.timeout = cfg, timeout
        self.max_requests=max_requests
        self.request_count=0
        self.usage_records=[]

    async def chat(self, messages, tools=None):
        if self.max_requests is not None and self.request_count>=self.max_requests:
            raise ModelError("validation_budget_exhausted",429)
        self.request_count+=1
        payload = {"model": self.cfg.model, "messages": messages, "temperature": 0,"max_tokens":600}
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
            self.usage_records.append({"model":response.json().get("model",self.cfg.model),"usage":response.json().get("usage")})
            if not isinstance(message, dict):
                raise ValueError()
            return message
        except httpx.TimeoutException:
            raise ModelError("model_timeout", 504) from None
        except (httpx.HTTPError, ValueError, KeyError, IndexError):
            raise ModelError("model_invalid_response") from None

