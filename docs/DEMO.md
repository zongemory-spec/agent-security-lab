# Reproduce the security boundaries

[README](../README.md) · [Threat model](THREAT_MODEL.md) · [Engineering guide](ENGINEERING.md)

Use the README's Python environment. All examples below use synthetic local users. Keep the HTTP server on `127.0.0.1`; no paid model configuration is needed.

## 1. Run the deterministic demonstration

```sh
python deterministic_security_demo.py
```

The script creates a temporary database, runs its cases and removes that disposable state when it exits. It does not use your HTTP demo database or require an access token.

| Output field | Expected result | Boundary illustrated |
| :--- | :--- | :--- |
| `own_salary.ok` | `true` | Reading your own synthetic record is allowed. |
| `cross_user_blocked.ok` / `.audit` | `false` / `object_permission_denied` | Changing a tool's target ID does not change caller authority. |
| `approval_concurrent_execution` | One `consumed`, one `action_not_approved` | One approved proposal cannot be consumed twice. Order is not fixed. |
| `alice_memory` | Contains `language: zh-CN` | Secure preferences belong to a scoped user / session. |
| `bob_memory` | Empty | Alice's preference is not Bob's memory. |

The concurrency example demonstrates approved execution; the browser exercise below separately shows the pending and approval steps. These local Python demonstrations construct trusted test contexts, while HTTP identities come from server-side token mapping.

## 2. Compare vulnerable and secure memory

```sh
python deterministic_memory_demo.py
```

Inspect the three labeled outputs:

- **Alice vulnerable** contains deliberately unsafe demonstration entries, including an authorization claim and an injected preference.
- **Alice secure** contains only the safe preference written to the separate secure namespace.
- **Bob secure** remains empty.

This illustrates namespace separation. It does not mean an allowlisted preference is trusted instructions, or that all prompt-injection attempts are prevented. The vulnerable comparison is not exposed as a public deployment recommendation.

## 3. Exercise the local browser UI

Initialize once and run the server as described in the README. Open http://127.0.0.1:8002 and inspect `data/demo_auth.json` locally.

| Identity in tenant `demo` | Role | Use in the exercise |
| :--- | :--- | :--- |
| `alice` | `user` | Own-record access and cross-user denial |
| `operator` | `admin` | Propose a high-risk operation, then execute after approval |
| `reviewer` | `approver` | Independently inspect and approve a proposal |

Do not copy tokens into issues, committed files or public screenshots.

### Read an own record and request another user's record

1. Put Alice's token in **操作者凭证**; leave the session as `demo`.
2. Send `/salary alice`. The trace should show permitted access to the synthetic record.
3. Send `/salary bob`. The trace should show `object_permission_denied`; no Bob salary should be returned.

### Request, review and execute a high-risk action

1. Replace the operator field with the **operator** token and send `/delete bob`.
2. Confirm the trace says `pending_approval`. The operation ID should be copied into **操作编号**. A proposal does not delete Bob.
3. Enter the **reviewer** token in **审批人凭证**, then click **查看待审批详情**. Check the tool, target, digest and pending status.
4. Click **确认批准**. The returned status is `approved`; approval alone still does not execute deletion.
5. Keep the original operator credential and click **由操作者执行一次**. The status should be `consumed`; the change affects only the local synthetic Bob record.
6. The UI disables repeat execution. The automated concurrency demo and tests verify server rejection of repeated calls; this protection does not depend only on the disabled button.

If no Bob record remains from an earlier run, use a new disposable demo database before repeating this deletion exercise. `init_demo.py` preserves an existing database; re-running it does not reset an already consumed action or restore deleted records.

## 4. Verify the boundaries with tests

```sh
python -m unittest discover -s tests -v
```

Tests cover object / role authorization, independent approval, expiration, digest changes, concurrent consumption, scoped memory and HTTP entry points. See the actual test files and current CI result for their precise scope.

A successful offline demonstration does not establish a real model's defense rate or production security. The [threat model](THREAT_MODEL.md) explains the trusted host, authentication and data boundaries.
