"""Deterministic policy. Contexts are trusted only when constructed by the server."""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class UserContext:
    user_id: str
    role: str = "user"
    tenant_id: str = "demo"

TOOL_PERMISSIONS = {
    "user": {"get_own_profile", "get_salary", "search_policy", "create_support_ticket", "write_memory"},
    "admin": {"get_own_profile", "get_salary", "search_policy", "create_support_ticket", "write_memory", "admin_dump", "delete_user"},
    "approver": set(),
}
HIGH_RISK_TOOLS = {"admin_dump", "delete_user"}
SAFE_MEMORY_KEYS = {"language", "output_format", "timezone"}
ARGUMENTS = {
    "get_own_profile": {"user_id"}, "get_salary": {"user_id"},
    "search_policy": {"query"}, "create_support_ticket": {"summary", "priority"},
    "write_memory": {"key", "value"}, "admin_dump": set(), "delete_user": {"user_id"},
}

class PolicyError(Exception):
    def __init__(self, reason: str, status: int = 403):
        self.reason, self.status = reason, status
        super().__init__(reason)

def can_call_tool(ctx, tool_name):
    return tool_name in TOOL_PERMISSIONS.get(ctx.role, set())

def can_access_user(ctx, requested_user, tenant_id):
    return ctx.tenant_id == tenant_id and (ctx.role == "admin" or ctx.user_id == requested_user)

def can_write_memory(key):
    return key in SAFE_MEMORY_KEYS

def requires_confirmation(tool_name):
    return tool_name in HIGH_RISK_TOOLS

def sanitize_output(text):
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED_API_KEY]", text)
    text = re.sub(r"(?i)bearer\s+[^\s\"']+", "Bearer [REDACTED]", text)
    text = re.sub(r"(?i)((?:api[_-]?key|password|secret|token)\s*[=:]\s*)[^\s,;]+", r"\1[REDACTED]", text)
    return re.sub(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b",
                  lambda m: f"{m[1][:1]}***@{m[2]}", text)

def redact(value: Any, secrets=()):
    if isinstance(value, dict):
        return {k: "[REDACTED]" if any(s in k.lower() for s in ("secret", "token", "password", "api_key", "authorization"))
                else redact(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in sorted((s for s in secrets if s), key=len, reverse=True):
            value = value.replace(secret, "[REDACTED]")
        return sanitize_output(value)
    return value

def validate_tool_args(tool_name, args):
    if tool_name not in ARGUMENTS:
        return False, "unknown_tool"
    if not isinstance(args, dict) or set(args) != ARGUMENTS[tool_name]:
        return False, "missing_or_extra_fields"
    for key, value in args.items():
        if type(value) is not str or not 1 <= len(value) <= (300 if key == "summary" else 200):
            return False, "invalid_argument_type_or_length"
    if "user_id" in args and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args["user_id"]):
        return False, "invalid_user_id"
    if "priority" in args and args["priority"] not in {"low", "medium", "high"}:
        return False, "invalid_priority"
    return True, "ok"

