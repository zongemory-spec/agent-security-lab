# Agent Security Lab 工程版

当前入口与验证说明：[工程版启动与验收](docs/ENGINEERING.md)。

已替换模型自报 confirm、全局 USERS 和共享 JSON 记忆。默认离线、HTTP 固定 secure，支持独立双人审批与原子执行。

原版 16 项测试保存在隔离基线中；旧接口说明以下仅供对照，不适用于新版启动。

---

# Agent Security Real API Lab v2

这一版把上一版 Mock LLM 替换成了**真实 Qwen / DeepSeek API**，并使用模型原生 Function / Tool Calling。

> 目标：不是做“越狱攻击脚本”，而是学习企业 Agent 如何在模型不可信的前提下，仍通过 Tool Gateway、对象级鉴权、RAG 信任边界、Memory 白名单和 DLP 保住安全边界。

## 1. 你会看到的真实链路

```text
User
  ↓
Real Qwen / DeepSeek
  ↓  model returns tool_calls
Tool Router
  ↓  server-side auth / arg validation
Python Tool
  ↓
tool result
  ↓
Real Qwen / DeepSeek
  ↓
Final answer
```

模型真的会收到 `tools=[...]`，并可能返回：

```json
{
  "name": "get_salary",
  "arguments": {"user_id": "alice"}
}
```

Python 代码再真正执行对应函数，并把结果以 `role=tool` 回传给模型。

## 2. 安装

推荐 Python 3.11。

Windows PowerShell：

```powershell
cd agent_security_real_api_lab_v2
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

然后编辑 `.env`。

### Qwen

```env
LLM_PROVIDER=qwen
DASHSCOPE_API_KEY=你的Key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
```

新版阿里云 Model Studio 文档更推荐 workspace-specific base URL；本项目把 `QWEN_BASE_URL` 做成可配置项，所以你可以直接换成控制台显示的新地址。

### DeepSeek

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
```

**不要把 API Key 写进 Python，也不要提交 `.env` 到 Git。**

## 3. 运行真实 Agent

Qwen：

```powershell
python app.py --provider qwen --mode secure
```

DeepSeek：

```powershell
python app.py --provider deepseek --mode secure
```

漏洞对照模式：

```powershell
python app.py --provider qwen --mode vulnerable
```

## 4. 第一次建议这样跑

先 `secure`：

1. 选择 `1`：正常 Tool Calling，查询 Alice 工资。
2. 选择 `3`：让 Alice 查询 Bob 工资，看对象级鉴权。
3. 选择 `2`：提示词要求调用 `admin_dump`，看后端是否阻断。
4. 选择 `4`：profile 返回含敏感字段，看 DLP 脱敏。
5. 选择 `5`：尝试把权限写进 Memory，看白名单阻断。
6. 选择 `6`：加入 RAG Poisoning 文档。
7. 选择 `7`：加入带恶意指令的外部文档。

再切到 `vulnerable` 重跑，对比 Tool Trace。

注意：真实大模型具有概率性，它可能拒绝某些恶意提示，因此“攻击一定触发”不是实验目标。真正要验证的是：**即使模型已经被影响并发起危险 tool call，后端仍然必须能拒绝。**

## 5. 无 API Key 也能验证安全边界

```powershell
python deterministic_security_demo.py
```

这个脚本直接模拟“模型已经完全被攻击者控制”，强制请求：

- `admin_dump()`
- `get_salary(user_id="bob")`
- `write_memory(authorization=...)`

你会看到 vulnerable 与 secure 的确定性差异。

## 6. 自动测试

```powershell
python -m unittest discover -s tests -v
```

测试不调用 Qwen/DeepSeek，不消耗 API 额度。

## 7. 代码结构

```text
agent_security_real_api_lab_v2/
├── app.py                 # CLI
├── agent.py               # Agent + real tool-call loop
├── llm_client.py          # Qwen / DeepSeek OpenAI-compatible client
├── config.py              # env config
├── tools.py               # JSON Schema + real Python tools + router
├── security.py            # auth / validation / DLP
├── rag.py                 # local RAG + poisoning demo
├── memory.py              # persistent JSON memory
├── scenarios.py           # demo prompts
├── deterministic_security_demo.py
├── tests/
│   └── test_security.py
├── .env.example
├── .gitignore
└── requirements.txt
```

## 8. 这一版“真实”在哪里？

不是靠 `if "admin_dump" in prompt` 来模拟模型决定。

真正的决定来自 Qwen/DeepSeek：

```python
response = client.chat.completions.create(
    model=model,
    messages=messages,
    tools=TOOL_SCHEMAS,
    tool_choice="auto",
)
```

如果模型决定调用工具，API 返回 `message.tool_calls`。应用读取：

```python
call.function.name
call.function.arguments
```

经过 Tool Router 鉴权后执行真实 Python 函数，再：

```python
messages.append({
    "role": "tool",
    "tool_call_id": call.id,
    "content": result,
})
```

再次请求模型生成最终答案。

这就是标准的 Tool Calling 循环。

