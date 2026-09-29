from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UserContext:
    user_id: str
    role: str = "user"


TOOL_PERMISSIONS = {
    "user": {
        "get_own_profile",
        "get_salary",
        "search_policy",
        "create_support_ticket",
        "write_memory",
    },
    "admin": {
        "get_own_profile",
        "get_salary",
        "search_policy",
        "create_support_ticket",
        "write_memory",
        "admin_dump",
        "delete_user",
    },
}

SAFE_MEMORY_KEYS = {"language", "output_format", "timezone"}
HIGH_RISK_TOOLS = {"admin_dump", "delete_user"}


def can_call_tool(ctx: UserContext, tool_name: str) -> bool:
    return tool_name in TOOL_PERMISSIONS.get(ctx.role, set())


def can_access_user(ctx: UserContext, requested_user: str) -> bool:
    return ctx.role == "admin" or ctx.user_id == requested_user


def can_write_memory(key: str) -> bool:
    return key in SAFE_MEMORY_KEYS


def requires_confirmation(tool_name: str) -> bool:
    return tool_name in HIGH_RISK_TOOLS


def sanitize_output(text: str) -> str:
    """Very small demo DLP layer. Production DLP needs richer detectors/policies."""
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED_API_KEY]", text)

    def mask_email(match: re.Match[str]) -> str:
        local, domain = match.group(1), match.group(2)
        return f"{local[:1] or '*'}***@{domain}"

    text = re.sub(
        r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b",
        mask_email,
        text,
    )
    return text


def validate_tool_args(tool_name: str, args: dict[str, Any]) -> tuple[bool, str]:
    if tool_name in {"get_own_profile", "get_salary"}:
        user_id = args.get("user_id")
        if not isinstance(user_id, str) or user_id not in {"alice", "bob"}:
            return False, "invalid user_id"

    if tool_name == "create_support_ticket":
        summary = args.get("summary")
        priority = args.get("priority")
        if not isinstance(summary, str) or not 1 <= len(summary) <= 300:
            return False, "summary must be 1..300 chars"
        if priority not in {"low", "medium", "high"}:
            return False, "priority must be low|medium|high"

    if tool_name == "write_memory":
        key, value = args.get("key"), args.get("value")
        if not isinstance(key, str) or not isinstance(value, str):
            return False, "memory key/value must be strings"
        if len(value) > 200:
            return False, "memory value too long"

    if tool_name == "delete_user":
        user_id = args.get("user_id")
        if not isinstance(user_id, str) or user_id not in {"alice", "bob"}:
            return False, "invalid user_id"
        if not isinstance(args.get("confirm"), bool):
            return False, "confirm must be a boolean"

    return True, "ok"
