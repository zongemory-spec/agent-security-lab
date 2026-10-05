# Agent Security Mini Lab

这是一个**纯本地、无需 API Key、无需第三方依赖**的 Agent Security 入门实验。

你可以用它理解并亲手验证：

- Prompt Injection
- Indirect Prompt Injection
- Tool Calling 越权
- RAG Poisoning
- Memory Poisoning
- Data Leakage
- Jailbreak（简化模拟）

## 架构

```text
User
  |
  v
Agent
  |----> RAG
  |----> Memory
  |----> Mock LLM
  |----> Tool Router
             |
             v
       Backend Tools
```

## 最重要的安全原则

1. LLM 只能“建议”调用工具，不能决定最终权限。
2. Tool 层必须做服务端鉴权。
3. RAG 文档应视为不可信输入。
4. Memory 不能把任意文本直接写入长期权限状态。
5. 输出前要做敏感信息检查与脱敏。

## 运行

Windows PowerShell：

```powershell
cd agent_security_mini_lab_v1
python app.py
```

运行测试：

```powershell
python -m unittest discover -s tests -v
```

不需要安装 pytest。

## 推荐实验顺序

1. 先进入 `vulnerable` 模式，把 1~6 全跑一次。
2. 再进入 `secure` 模式，重复相同场景。
3. 对比输出，理解“为什么 Prompt 防护本身不够”。

## 项目亮点

- vulnerable / secure 双模式对照
- Tool Backend 服务端鉴权
- 对象级访问控制
- RAG 可信来源过滤
- Memory 写入白名单
- 输出 DLP
- unittest 自动安全回归

## 面试一句话介绍

> 我用 Python 搭建了一个本地 Agent Security Mini Lab，把 Agent 拆成 LLM、RAG、Memory、Tool Router 和 Backend Tool 几层，通过 vulnerable / secure 两套模式复现 Prompt Injection、Tool 越权、RAG/Memory Poisoning 与 Data Leakage，并把关键权限校验放在后端而不是交给 LLM。

## 后续升级

Level 2：把 Mock LLM 换成真实 Qwen / DeepSeek / OpenAI compatible API。

Level 3：增加 FastAPI + SQLite + JWT + RBAC。

Level 4：扩展成无人机 Agent Security：

```text
get_vehicle_state()
set_mission()
arm_vehicle()
```

再研究 Prompt Injection、Mission 越权、高风险操作二次确认和 MAVLink/PX4 安全。
