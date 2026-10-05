import re

def propose_action(user_prompt: str, rag_text: str = "", memory: dict | None = None):
    memory = memory or {}
    combined = f"{user_prompt}\n{rag_text}\n{memory}"

    # Direct / Indirect Prompt Injection
    if "admin_dump" in combined or "读取全部用户数据" in combined:
        return {
            "type": "tool",
            "tool_name": "admin_dump",
            "args": {},
            "reason": "模型受提示词影响，尝试调用高权限工具",
        }

    # Tool Calling horizontal privilege escalation
    match = re.search(r"(?:user_id=|用户\s*)(alice|bob)", combined, re.I)
    if "工资" in combined or "salary" in combined.lower():
        target = match.group(1).lower() if match else "alice"
        return {
            "type": "tool",
            "tool_name": "get_salary",
            "args": {"user_id": target},
            "reason": "模型选择工资查询工具",
        }

    if "profile" in combined.lower() or "资料" in combined:
        target = match.group(1).lower() if match else "alice"
        return {
            "type": "tool",
            "tool_name": "get_own_profile",
            "args": {"user_id": target},
            "reason": "模型选择资料查询工具",
        }

    if "退款" in combined:
        return {
            "type": "answer",
            "text": f"根据检索资料：{rag_text or '未找到资料'}",
        }

    if "jailbreak" in combined.lower() or "绕过安全限制" in combined:
        return {
            "type": "answer",
            "text": "模型被诱导尝试绕过既定安全策略（实验模拟）。",
        }

    return {
        "type": "answer",
        "text": "我会按照当前权限和可用资料处理该请求。",
    }
