# 安全实验结果与复现

本页由 `showcase_evidence.py` 的实际运行报告整理。所有资料、账号和删除对象均为临时合成数据，不连接真实模型。

运行日期：2026-10-31；14 个场景通过。测试基础为 GitHub v3.1 业务实现，新增证据脚本和 5 项测试。

| 场景 | 预期 | 实测 | 结果 |
| --- | --- | --- | --- |
| own_record | `true` | `true` | 通过 |
| horizontal_access | `"object_permission_denied"` | `"object_permission_denied"` | 通过 |
| vertical_access | `"tool_permission_denied"` | `"tool_permission_denied"` | 通过 |
| forged_role_argument | `"missing_or_extra_fields"` | `"missing_or_extra_fields"` | 通过 |
| model_confirm_argument | `"missing_or_extra_fields"` | `"missing_or_extra_fields"` | 通过 |
| self_approval | `"independent_approver_required"` | `"independent_approver_required"` | 通过 |
| tampered_digest | `"action_digest_mismatch"` | `"action_digest_mismatch"` | 通过 |
| expired_approval | `"action_expired"` | `"action_expired"` | 通过 |
| reviewer_revoked | `"approval_authority_revoked"` | `"approval_authority_revoked"` | 通过 |
| memory_isolation | `{}` | `{}` | 通过 |
| memory_authority_key | `"memory_key_denied"` | `"memory_key_denied"` | 通过 |
| concurrent_replay | `{"consumed":1,"denied":7,"reasons":{"action_not_approved":7},"final_status":"consumed","target_exists":false}` | `{"consumed":1,"denied":7,"reasons":{"action_not_approved":7},"final_status":"consumed","target_exists":false}` | 通过 |
| approval_does_not_execute | `["pending","approved","consumed"]` | `["pending","approved","consumed"]` | 通过 |
| target_preserved_until_execution | `[true,true,false]` | `[true,true,false]` | 通过 |

## 执行方法

```sh
python showcase_evidence.py --workers 8 --out reports/my-showcase.json
```

输出文件必须不存在，以免覆盖历史证据。任一场景不符合预期时返回非零状态；意外程序异常也会导致失败，不能将不完整报告视为通过。

脚本使用 Barrier 同步发起线程，再由 SQLite 事务串行处理写入。报告逐项记录 attempt、status、reason；最终状态及目标是否存在也被检查。它验证应用事务的单次消费，不是网络压测、分布式 exactly-once 或真实模型防御率。

## 对应测试入口

- `own_record` → `test_security.SecurityTests.test_own_profile_and_salary`
- `horizontal_access` → `test_security.SecurityTests.test_horizontal_and_vertical_permissions`
- `vertical_access` → `test_security.SecurityTests.test_horizontal_and_vertical_permissions`
- `forged_role_argument` → `test_security.SecurityTests.test_invalid_arguments_matrix`
- `model_confirm_argument` → `test_security.SecurityTests.test_invalid_arguments_matrix`
- `self_approval` → `test_security.SecurityTests.test_self_approval_and_wrong_reviewer_denied`
- `tampered_digest` → `test_security.SecurityTests.test_digest_changes_rejected`
- `expired_approval` → `test_security.SecurityTests.test_expired_pending_and_approved`
- `reviewer_revoked` → `test_security.SecurityTests.test_revoked_reviewer`
- `memory_isolation` → `test_security.SecurityTests.test_memory_namespace_and_restart`
- `memory_authority_key` → `test_security.SecurityTests.test_memory_poison_isolation_and_whitelist`
- `concurrent_replay` → `test_security.SecurityTests.test_consumed_once_even_concurrent`
- `approval_does_not_execute` → `test_api.APITests.test_approval_http_flow`
- `target_preserved_until_execution` → `test_security.SecurityTests.test_model_cannot_execute_high_risk`

## 更广的回归验证

本次本地执行 `python -m unittest discover -s tests -v`：48 项通过。包括原有 43 项和新增 5 项；其中一个旧版隔离入口另外运行原版 16 项测试，不将其重复算成新增测试。

新增验证包括：证据与 8 路执行结果一致、故意错误放行时报告失败、失败时 CLI 返回非零、拒绝覆盖旧报告、并发参数边界。

[JSON 完整记录](../reports/showcase-evidence.json) · [测试日志](../reports/showcase-tests.txt) · [审批演示](APPROVAL_DEMO.md)
