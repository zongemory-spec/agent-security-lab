"""Four deterministic demonstrations, no credentials, no network, disposable state."""
import json
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from approvals import ApprovalStore
from memory import MemoryStore
from security import PolicyError, UserContext
from storage import Database
from tools import ToolRouter

def run():
    with tempfile.TemporaryDirectory() as td:
        db = Database(Path(td)/"demo.sqlite3")
        db.seed_demo()
        memory = MemoryStore(db=db)
        router = ToolRouter(memory)
        alice, bob = UserContext("alice"), UserContext("bob")
        actor, reviewer = UserContext("operator", "admin"), UserContext("reviewer", "approver")
        results = {}
        results["own_salary"] = router.execute("get_salary", {"user_id": "alice"}, alice).__dict__
        results["cross_user_blocked"] = router.execute("get_salary", {"user_id": "bob"}, alice).__dict__
        pending = router.execute("delete_user", {"user_id": "bob"}, actor)
        store = ApprovalStore(db)
        action = store.get(pending.action_id, actor)
        store.decide(action["id"], action["digest"], reviewer, True)
        def execute():
            try:
                return store.execute(action["id"], action["digest"], actor, lambda uid, tenant: uid == "reviewer")["status"]
            except PolicyError as exc:
                return exc.reason
        with ThreadPoolExecutor(2) as pool:
            results["approval_concurrent_execution"] = list(pool.map(lambda _: execute(), range(2)))
        memory.write("language", "zh-CN", alice, "s")
        results["alice_memory"] = memory.snapshot(alice, "s")
        results["bob_memory"] = memory.snapshot(bob, "s")
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return results

if __name__ == "__main__":
    run()

