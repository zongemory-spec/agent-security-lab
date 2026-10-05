from __future__ import annotations
import json
from dataclasses import dataclass
from uuid import uuid4
from approvals import ApprovalStore
from security import (ARGUMENTS, HIGH_RISK_TOOLS, can_access_user, can_call_tool,
                      can_write_memory, sanitize_output, validate_tool_args)

DESCRIPTIONS = {
    "get_own_profile": "Read a profile. Ordinary users may only read their own.",
    "get_salary": "Read a salary. Ordinary users may only read their own.",
    "search_policy": "Search synthetic public policies.",
    "create_support_ticket": "Create a synthetic local ticket.",
    "write_memory": "Store a preference as untrusted data; never identity or authority.",
    "admin_dump": "Request approval to export synthetic tenant records. Does not execute.",
    "delete_user": "Request approval to delete a synthetic user. Does not execute. No confirm argument.",
}
TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": name, "description": DESCRIPTIONS[name],
     "parameters": {"type": "object", "properties": {key: {"type": "string"} for key in sorted(fields)},
                    "required": sorted(fields), "additionalProperties": False}}}
    for name, fields in ARGUMENTS.items()
]

@dataclass
class ToolResult:
    ok: bool
    output: str
    audit: str
    action_id: str | None = None

class ToolRouter:
    def __init__(self, memory, mode="secure", *, approvals=None):
        if mode not in {"secure", "vulnerable"}:
            raise ValueError("Invalid mode")
        self.memory, self.mode, self.db = memory, mode, memory.db
        self.approvals = approvals or ApprovalStore(self.db)

    def execute(self, tool_name, args, ctx, session_id="default", request_id="local"):
        self.memory.namespace(ctx, session_id, self.mode)
        valid, reason = validate_tool_args(tool_name, args)
        if not valid:
            result = ToolResult(False, f"DENIED: {reason}", reason)
        elif self.mode == "secure" and not can_call_tool(ctx, tool_name):
            result = ToolResult(False, "DENIED: tool permission", "tool_permission_denied")
        elif self.mode == "secure" and tool_name in {"get_own_profile", "get_salary"} and not can_access_user(ctx, args["user_id"], ctx.tenant_id):
            result = ToolResult(False, "DENIED: object permission", "object_permission_denied")
        elif self.mode == "secure" and tool_name == "write_memory" and not can_write_memory(args["key"]):
            result = ToolResult(False, "MEMORY_DENIED: key is not allowed", "memory_key_denied")
        else:
            result = self._dispatch(tool_name, args, ctx, session_id)
        self.db.audit(ctx, request_id, tool_name if tool_name in ARGUMENTS else "unknown_tool", result.audit)
        return result

    def _dispatch(self, name, args, ctx, session):
        if name in {"get_own_profile", "get_salary", "delete_user"}:
            with self.db.connect() as conn:
                user = conn.execute("SELECT * FROM users WHERE tenant=? AND user_id=?", (ctx.tenant_id, args["user_id"])).fetchone()
            if user is None:
                return ToolResult(False, "DENIED: object not found", "object_not_found")
        if self.mode == "secure" and name in HIGH_RISK_TOOLS:
            action_id = self.approvals.propose(name, args, ctx, session)
            return ToolResult(True, f"PENDING_APPROVAL: action_id={action_id}; independent human approval required", "pending_approval", action_id)
        if name == "get_salary":
            output = f"{args['user_id']} salary={user['salary']}"
        elif name == "get_own_profile":
            output = f"name={user['name']}, email={user['email']}, salary={user['salary']}"
        elif name == "search_policy":
            output = "官方退款制度：普通订单退款上限为 500 元。" if "退款" in args["query"] or "refund" in args["query"].lower() else "安全制度：敏感操作必须经过服务端鉴权、独立审批与审计。"
        elif name == "create_support_ticket":
            ticket_id = uuid4().hex
            with self.db.connect() as conn:
                conn.execute("INSERT INTO tickets VALUES (?,?,?,?,?)", (ticket_id, ctx.tenant_id, ctx.user_id, args["summary"], args["priority"]))
            output = f"ticket_id={ticket_id}"
        elif name == "write_memory":
            output = self.memory.write(args["key"], args["value"], ctx, session, self.mode)
        elif name == "admin_dump":
            with self.db.connect() as conn:
                output = json.dumps([dict(r) for r in conn.execute("SELECT * FROM users WHERE tenant=?", (ctx.tenant_id,))])
        elif name == "delete_user":
            with self.db.connect() as conn:
                conn.execute("DELETE FROM users WHERE tenant=? AND user_id=?", (ctx.tenant_id, args["user_id"]))
            output = f"user={args['user_id']} deleted (local vulnerable demo)"
        else:
            return ToolResult(False, "DENIED: unknown tool", "unknown_tool")
        return ToolResult(True, sanitize_output(output) if self.mode == "secure" else output, "executed")

