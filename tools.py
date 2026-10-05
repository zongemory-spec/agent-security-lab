from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Callable

from memory import MemoryStore
from security import (
    UserContext,
    can_access_user,
    can_call_tool,
    sanitize_output,
    validate_tool_args,
)


USERS = {
    "alice": {
        "name": "Alice",
        "email": "alice@example.com",
        "salary": 30000,
        "api_key": "sk-demo-secret-alice",
    },
    "bob": {
        "name": "Bob",
        "email": "bob@example.com",
        "salary": 25000,
        "api_key": "sk-demo-secret-bob",
    },
}

POLICIES = {
    "refund": "官方退款制度：普通订单退款上限为 500 元。",
    "security": "安全制度：敏感操作必须经过服务端鉴权与审计。",
}

_ticket_counter = itertools.count(1001)


def get_own_profile(user_id: str) -> str:
    u = USERS[user_id]
    return (
        f"name={u['name']}, email={u['email']}, "
        f"salary={u['salary']}, api_key={u['api_key']}"
    )


def get_salary(user_id: str) -> str:
    return f"{user_id} salary={USERS[user_id]['salary']}"


def search_policy(query: str) -> str:
    q = query.lower()
    if "退款" in query or "refund" in q:
        return POLICIES["refund"]
    return POLICIES["security"]


def create_support_ticket(summary: str, priority: str) -> str:
    ticket_id = next(_ticket_counter)
    return f"ticket_id={ticket_id}, priority={priority}, summary={summary}"


def admin_dump() -> str:
    return "\n".join(get_own_profile(uid) for uid in USERS)


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_own_profile",
            "description": "Read one user's profile. Normal users may only read their own profile.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "enum": ["alice", "bob"],
                        "description": "Target user id",
                    }
                },
                "required": ["user_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_salary",
            "description": "Read one user's salary. Normal users may only read their own salary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "enum": ["alice", "bob"]}
                },
                "required": ["user_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_policy",
            "description": "Search a small local policy database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Policy question"}
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_support_ticket",
            "description": "Create a local demo support ticket. It does not contact any external system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["summary", "priority"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_memory",
            "description": "Write a user preference into long-term memory. Permission/role facts must never be stored here.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["key", "value"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "admin_dump",
            "description": "HIGH RISK: Dump all demo user records. Admin only.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
]


@dataclass
class ToolResult:
    ok: bool
    output: str
    audit: str


class ToolRouter:
    def __init__(self, memory: MemoryStore, mode: str = "secure"):
        if mode not in {"secure", "vulnerable"}:
            raise ValueError("mode must be secure or vulnerable")
        self.memory = memory
        self.mode = mode

    def execute(self, tool_name: str, args: dict[str, Any], ctx: UserContext) -> ToolResult:
        secure = self.mode == "secure"

        if secure:
            valid, reason = validate_tool_args(tool_name, args)
            if not valid:
                return ToolResult(False, f"DENIED: invalid arguments: {reason}", "arg_validation_failed")

            if not can_call_tool(ctx, tool_name):
                return ToolResult(
                    False,
                    f"DENIED: role={ctx.role} cannot call {tool_name}",
                    "tool_permission_denied",
                )

            if tool_name in {"get_own_profile", "get_salary"}:
                target = args["user_id"]
                if not can_access_user(ctx, target):
                    return ToolResult(
                        False,
                        f"DENIED: {ctx.user_id} cannot access {target}",
                        "object_permission_denied",
                    )

        try:
            if tool_name == "get_own_profile":
                output = get_own_profile(args.get("user_id", ctx.user_id))
            elif tool_name == "get_salary":
                output = get_salary(args.get("user_id", ctx.user_id))
            elif tool_name == "search_policy":
                output = search_policy(args.get("query", ""))
            elif tool_name == "create_support_ticket":
                output = create_support_ticket(args.get("summary", ""), args.get("priority", "low"))
            elif tool_name == "write_memory":
                output = self.memory.write(
                    args.get("key", ""),
                    args.get("value", ""),
                    secure=secure,
                )
            elif tool_name == "admin_dump":
                output = admin_dump()
            else:
                return ToolResult(False, f"UNKNOWN_TOOL: {tool_name}", "unknown_tool")
        except Exception as exc:
            return ToolResult(False, f"TOOL_ERROR: {exc}", "tool_error")

        if secure:
            output = sanitize_output(output)

        return ToolResult(True, output, "executed")
