"""Offline evidence from disposable synthetic state; never calls a model provider."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from threading import Barrier

from approvals import ApprovalStore
from memory import MemoryStore
from security import PolicyError, UserContext
from storage import Database
from tools import ToolRouter


def collect_evidence(workers=8):
    if type(workers) is not int or not 2 <= workers <= 32:
        raise ValueError("workers must be an integer between 2 and 32")
    with tempfile.TemporaryDirectory(prefix="security-showcase-") as td:
        db = Database(Path(td) / "synthetic.sqlite3")
        db.seed_demo()
        memory = MemoryStore(db=db)
        router = ToolRouter(memory)
        store = ApprovalStore(db)
        alice = UserContext("alice")
        bob = UserContext("bob")
        operator = UserContext("operator", "admin")
        reviewer = UserContext("reviewer", "approver")
        cases = []

        def record(name, expected, actual, test):
            cases.append({"scenario": name, "expected": expected, "actual": actual,
                          "passed": expected == actual, "regression_test": test})

        def rejection(fn):
            try:
                fn()
            except PolicyError as exc:
                return exc.reason
            return "unexpectedly_allowed"

        def proposal(session):
            result = router.execute("delete_user", {"user_id": "bob"}, operator, session)
            return store.get(result.action_id, operator)

        current = lambda uid, tenant: (uid, tenant) == ("reviewer", "demo")
        record("own_record", True, router.execute("get_salary", {"user_id": "alice"}, alice).ok,
               "test_security.SecurityTests.test_own_profile_and_salary")
        record("horizontal_access", "object_permission_denied",
               router.execute("get_salary", {"user_id": "bob"}, alice).audit,
               "test_security.SecurityTests.test_horizontal_and_vertical_permissions")
        record("vertical_access", "tool_permission_denied", router.execute("admin_dump", {}, alice).audit,
               "test_security.SecurityTests.test_horizontal_and_vertical_permissions")
        record("forged_role_argument", "missing_or_extra_fields",
               router.execute("get_salary", {"user_id": "bob", "role": "admin"}, alice).audit,
               "test_security.SecurityTests.test_invalid_arguments_matrix")
        record("model_confirm_argument", "missing_or_extra_fields",
               router.execute("delete_user", {"user_id": "bob", "confirm": "true"}, operator).audit,
               "test_security.SecurityTests.test_invalid_arguments_matrix")

        action = proposal("self-approval")
        record("self_approval", "independent_approver_required",
               rejection(lambda: store.decide(action["id"], action["digest"],
                                               UserContext("operator", "approver"), True)),
               "test_security.SecurityTests.test_self_approval_and_wrong_reviewer_denied")
        action = proposal("digest")
        record("tampered_digest", "action_digest_mismatch",
               rejection(lambda: store.decide(action["id"], "0" * 64, reviewer, True)),
               "test_security.SecurityTests.test_digest_changes_rejected")

        action = proposal("expired")
        with db.connect() as conn:
            conn.execute("UPDATE actions SET expires=0 WHERE id=?", (action["id"],))
        record("expired_approval", "action_expired",
               rejection(lambda: store.decide(action["id"], action["digest"], reviewer, True)),
               "test_security.SecurityTests.test_expired_pending_and_approved")
        action = proposal("revoked")
        store.decide(action["id"], action["digest"], reviewer, True)
        record("reviewer_revoked", "approval_authority_revoked",
               rejection(lambda: store.execute(action["id"], action["digest"], operator, lambda *_: False)),
               "test_security.SecurityTests.test_revoked_reviewer")

        router.execute("write_memory", {"key": "language", "value": "zh-CN"}, alice, "memory")
        record("memory_isolation", {}, memory.snapshot(bob, "memory"),
               "test_security.SecurityTests.test_memory_namespace_and_restart")
        record("memory_authority_key", "memory_key_denied",
               router.execute("write_memory", {"key": "role", "value": "admin"}, alice, "memory").audit,
               "test_security.SecurityTests.test_memory_poison_isolation_and_whitelist")

        # Dedicated action, unchanged target and digest, independent approval.
        action = proposal("concurrent")
        snapshots = [{"stage": "proposal", "status": action["status"],
                      "target_exists": router.execute("get_salary", {"user_id": "bob"}, operator).ok}]
        store.decide(action["id"], action["digest"], reviewer, True)
        snapshots.append({"stage": "approval", "status": store.get(action["id"], operator)["status"],
                          "target_exists": router.execute("get_salary", {"user_id": "bob"}, operator).ok})
        barrier = Barrier(workers)

        def attempt(index):
            barrier.wait(timeout=15)
            try:
                result = store.execute(action["id"], action["digest"], operator, current,
                                       request_id=f"showcase-replay-{index}")
                return {"attempt": index, "status": result["status"], "reason": None}
            except PolicyError as exc:
                return {"attempt": index, "status": "denied", "reason": exc.reason}

        with ThreadPoolExecutor(max_workers=workers) as pool:
            attempts = list(pool.map(attempt, range(1, workers + 1)))
        counts = Counter(a["status"] for a in attempts)
        reasons = Counter(a["reason"] for a in attempts if a["reason"])
        final = store.get(action["id"], operator)["status"]
        target_exists = router.execute("get_salary", {"user_id": "bob"}, operator).ok
        snapshots.append({"stage": "execution", "status": final, "target_exists": target_exists})
        actual = {"consumed": counts["consumed"], "denied": counts["denied"],
                  "reasons": dict(reasons), "final_status": final, "target_exists": target_exists}
        record("concurrent_replay", {"consumed": 1, "denied": workers - 1,
               "reasons": {"action_not_approved": workers - 1}, "final_status": "consumed",
               "target_exists": False}, actual, "test_security.SecurityTests.test_consumed_once_even_concurrent")
        record("approval_does_not_execute", ["pending", "approved", "consumed"],
               [s["status"] for s in snapshots], "test_api.APITests.test_approval_http_flow")
        record("target_preserved_until_execution", [True, True, False],
               [s["target_exists"] for s in snapshots], "test_security.SecurityTests.test_model_cannot_execute_high_risk")
        return {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
                "scope": "Offline synthetic application-policy scenarios; no real model or production security claim.",
                "passed": all(c["passed"] for c in cases), "scenario_count": len(cases),
                "cases": cases, "approval_flow": snapshots,
                "concurrency": {"workers": workers, **actual, "attempts": attempts}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    # Reserve the destination before doing work; never overwrite earlier evidence.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.out.open("x", encoding="utf-8") as handle:
            report = collect_evidence(args.workers)
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except (FileExistsError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"passed": report["passed"], "scenario_count": report["scenario_count"],
                      "workers": args.workers, "consumed": report["concurrency"]["consumed"],
                      "denied": report["concurrency"]["denied"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
