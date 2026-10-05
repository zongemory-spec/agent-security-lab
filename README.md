# Agent Security Lab

An educational, AI-assisted lab for testing security boundaries around LLM tool calls, retrieval, memory and high-risk actions.

面向 Agent 安全的可复现实验：原生工具调用、服务端对象权限校验、隔离记忆、独立双人审批、SQLite 事务与离线回归。

## Quick start (offline, no API key)

Python 3.12, from the repository root:

```sh
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -r requirements.lock
python init_demo.py
python -m uvicorn api:create_app --factory --host 127.0.0.1 --port 8002 --no-access-log
```

Open http://127.0.0.1:8002. Use a locally generated token from `data/demo_auth.json`; never commit this file. Default model behavior is a deterministic mock. Paid providers require explicit configuration; see [engineering guide](docs/ENGINEERING.md).

## What to inspect

- `agent.py`, `llm_client.py`: bounded tool loop and provider adapter.
- `auth.py`, `security.py`, `tools.py`: server-side identity and object authorization.
- `approvals.py`, `storage.py`: separate requester/reviewer, expiration, replay prevention and transactional execution.
- `memory.py`: tenant/user/session separation.
- `tests/`: current regression cases plus an isolated legacy vulnerable baseline.

```sh
python -m unittest discover -s tests -v
python deterministic_security_demo.py
```

Publication check: 43 tests passed locally. This is not a security certification or an attack-success-rate benchmark. The legacy fixture intentionally preserves old vulnerable behavior. Bind to localhost; demo authentication is not a production identity system.

## Versions

`snapshot/v1` → `snapshot/v2` → `snapshot/v2.1-engineering` → `snapshot/v3` → `snapshot/v3.1`. The earlier Git record is retained on an `archive/*` branch. Full historical project notes: [README.legacy.md](README.legacy.md).

## Development and provenance

This is an educational project developed with AI assistance. See [source history](docs/SOURCE_HISTORY.md) for the original records and local version snapshots. Imported commits are not backdated. Follow [CONTRIBUTING](CONTRIBUTING.md) for future changes.

本项目用于课程学习与求职作品展示，开发和本次仓库整理使用了 AI 辅助。可运行代码与验证记录不等于所有代码均由本人独立手写，也不代表生产系统经验。历史说明中的本机路径与旧验收记录仅供追溯。
