"""Explicit deterministic simulator. It is not a model or an attack-success benchmark."""
import json
from types import SimpleNamespace

class DemoLLM:
    cfg = SimpleNamespace(model="offline-script-v1", provider="mock", api_key="")
    async def chat(self, messages, tools=None):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": messages[-1]["content"]}
        user = messages[1]["content"].split("\n\nUNTRUSTED_CONTEXT:", 1)[0].removeprefix("USER REQUEST:\n")
        words = user.split(maxsplit=2)
        command = words[0] if words else ""
        target = words[1] if len(words) > 1 else "alice"
        mapping = {"/salary": ("get_salary", {"user_id": target}),
                   "/profile": ("get_own_profile", {"user_id": target}),
                   "/delete": ("delete_user", {"user_id": target}),
                   "/dump": ("admin_dump", {}),
                   "/policy": ("search_policy", {"query": target})}
        if command == "/remember" and len(words) == 3:
            mapping[command] = ("write_memory", {"key": words[1], "value": words[2]})
        if command not in mapping:
            return {"role": "assistant", "content": "离线演示：/salary alice、/salary bob、/delete bob、/dump、/remember language zh-CN"}
        name, args = mapping[command]
        return {"role": "assistant", "content": None, "tool_calls": [
            {"id": "demo-call", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}

