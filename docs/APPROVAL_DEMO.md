# 独立审批：提案、批准与执行

截图来自本地 FastAPI 页面和离线 mock，使用新建的合成数据库。凭证输入框为密码类型，不展示实际 token；操作 ID、摘要与用户均为合成实验记录。截图对应一次人工顺序执行；8 路并发使用另一份临时数据单独验证。

## 三个阶段

| 阶段 | 动作 | 实际状态 | 合成 Bob 是否保留 |
| --- | --- | --- | --- |
| 提案 | operator 发送 `/delete bob` | pending | 是 |
| 批准 | reviewer 查看详情后批准 | approved | 是 |
| 执行 | 原 operator 执行一次 | consumed | 否 |

状态与目标存在性也由 [证据脚本](../showcase_evidence.py) 自动检查，避免仅依赖截图中的按钮。

### 1. 提案没有执行业务删除

![待审批提案](assets/approval-pending.png)

### 2. 独立批准仍没有执行业务删除

![独立审批已批准](assets/approval-approved.png)

### 3. 原请求者执行后才消费批准

![一次执行后状态为 consumed](assets/approval-consumed.png)

页面上方保留的是最初的提案响应；下方刷新后的审批详情与执行响应才是当前状态。模型回复不能覆盖数据库状态。

## 在自己的本地副本复现

先按 README 创建虚拟环境并安装依赖，然后运行：

```sh
python init_demo.py
python -m uvicorn api:create_app --factory --host 127.0.0.1 --port 8002 --no-access-log
```

打开 http://127.0.0.1:8002 。从本机 `data/demo_auth.json` 选择租户 demo 的 operator 和 reviewer 凭证。

1. 操作者填 operator，发送 `/delete bob`。
2. 审批人填 reviewer，点击“查看待审批详情”，核对工具、对象和摘要。
3. 点击“确认批准”；状态为 approved，不代表执行成功。
4. 使用原 operator 点击“由操作者执行一次”。
5. 再次查看详情，确认 consumed。服务端拒绝重复执行，不只依赖按钮禁用。

如需重做，请使用新建的演示数据库，不覆盖日常记录。`init_demo.py` 不会恢复旧库已删除的用户。审批默认 300 秒有效，过期后应重新发起提案。

此流程不需要真实模型 API。更完整的攻击、记忆对照与 HTTP 测试见 [DEMO](DEMO.md) 和 [结果表](SECURITY_RESULTS.md)。
