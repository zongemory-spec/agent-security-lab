"""Explicit initialization. Does not load .env or migrate old JSON."""
import json
from pathlib import Path
import secrets
import os
from storage import Database

def main():
    path = Path(os.getenv("LAB_DB", "data/lab.sqlite3"))
    fresh = not path.exists()
    db = Database(path)
    if fresh:
        db.seed_demo()
    auth = Path(os.getenv("LAB_AUTH_FILE", "data/demo_auth.json"))
    auth.parent.mkdir(parents=True, exist_ok=True)
    if not auth.exists():
        records = [{"user_id": uid, "tenant_id": tenant, "role": role, "token": secrets.token_urlsafe(32)}
                   for uid, role, tenant in [("alice", "user", "demo"), ("bob", "user", "demo"),
                    ("operator", "admin", "demo"), ("reviewer", "approver", "demo"),
                    ("alice", "user", "other")]]
        with auth.open("x", encoding="utf-8") as handle:
            json.dump(records, handle, indent=2)
        try:
            auth.chmod(0o600)
        except OSError:
            pass
    print("Initialized local synthetic database and private demo credential file. Tokens are not printed.")

if __name__ == "__main__":
    main()

