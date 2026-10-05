from dataclasses import dataclass
import re

@dataclass
class UserContext:
    user_id: str
    role: str = "user"

ALLOWED_TOOLS = {
    "user": {"get_own_profile", "get_salary"},
    "admin": {"get_own_profile", "get_salary", "admin_dump"},
}

SAFE_MEMORY_KEYS = {"language", "output_format", "timezone"}

def can_call_tool(ctx: UserContext, tool_name: str) -> bool:
    return tool_name in ALLOWED_TOOLS.get(ctx.role, set())

def can_access_user(ctx: UserContext, requested_user: str) -> bool:
    return ctx.role == "admin" or ctx.user_id == requested_user

def safe_memory_key(key: str) -> bool:
    return key in SAFE_MEMORY_KEYS

def sanitize_output(text: str) -> str:
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED_API_KEY]", text)

    def mask_email(match):
        local, domain = match.group(1), match.group(2)
        first = local[:1] if local else "*"
        return f"{first}***@{domain}"

    return re.sub(
        r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b",
        mask_email,
        text,
    )
