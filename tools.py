from policy import UserContext, can_call_tool, can_access_user

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

def _profile_text(user_id: str) -> str:
    u = USERS[user_id]
    return (
        f"name={u['name']}, email={u['email']}, "
        f"salary={u['salary']}, api_key={u['api_key']}"
    )

def vulnerable_execute(tool_name: str, args: dict, ctx: UserContext) -> str:
    # 漏洞版：直接信任 LLM 给出的工具和参数
    if tool_name == "get_own_profile":
        target = args.get("user_id", ctx.user_id)
        return _profile_text(target)

    if tool_name == "get_salary":
        target = args.get("user_id", ctx.user_id)
        return f"{target} salary={USERS[target]['salary']}"

    if tool_name == "admin_dump":
        return "\n".join(_profile_text(uid) for uid in USERS)

    return f"UNKNOWN_TOOL: {tool_name}"

def secure_execute(tool_name: str, args: dict, ctx: UserContext) -> str:
    # 安全版：后端做确定性鉴权
    if not can_call_tool(ctx, tool_name):
        return f"DENIED: role={ctx.role} cannot call {tool_name}"

    if tool_name == "get_own_profile":
        target = args.get("user_id", ctx.user_id)
        if not can_access_user(ctx, target):
            return f"DENIED: {ctx.user_id} cannot access {target}"
        return _profile_text(target)

    if tool_name == "get_salary":
        target = args.get("user_id", ctx.user_id)
        if not can_access_user(ctx, target):
            return f"DENIED: {ctx.user_id} cannot access {target}"
        return f"{target} salary={USERS[target]['salary']}"

    if tool_name == "admin_dump":
        return "\n".join(_profile_text(uid) for uid in USERS)

    return f"UNKNOWN_TOOL: {tool_name}"
