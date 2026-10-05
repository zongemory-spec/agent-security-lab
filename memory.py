from __future__ import annotations
import re
from security import can_write_memory
from storage import Database

class MemoryStore:
    def __init__(self, path="data/lab.sqlite3", *, db=None):
        self.db = db or Database(path)

    @staticmethod
    def namespace(ctx, session_id, mode):
        if mode not in {"secure", "vulnerable"}:
            raise ValueError("Invalid mode")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session_id):
            raise ValueError("Invalid session")
        return (ctx.tenant_id, ctx.user_id, session_id, mode)

    def snapshot(self, ctx, session_id, mode="secure"):
        with self.db.connect() as conn:
            rows = conn.execute("SELECT key,value FROM memory WHERE tenant=? AND actor=? AND session=? AND mode=?",
                                self.namespace(ctx, session_id, mode))
            return {r["key"]: r["value"] for r in rows if mode != "secure" or can_write_memory(r["key"])}

    def write(self, key, value, ctx, session_id, mode="secure"):
        ns = self.namespace(ctx, session_id, mode)
        if mode == "secure" and not can_write_memory(key):
            return "MEMORY_DENIED: key is not allowed"
        with self.db.connect() as conn:
            conn.execute("INSERT INTO memory VALUES (?,?,?,?,?,?) ON CONFLICT(tenant,actor,session,mode,key) DO UPDATE SET value=excluded.value", (*ns, key, value))
        return f"MEMORY_WRITTEN: {key}={value}"

    def reset(self, ctx, session_id, mode="secure"):
        with self.db.connect() as conn:
            conn.execute("DELETE FROM memory WHERE tenant=? AND actor=? AND session=? AND mode=?", self.namespace(ctx, session_id, mode))

