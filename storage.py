"""SQLite state. All mutations use short transactions and fresh connections."""
from __future__ import annotations
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
from uuid import uuid4
from security import PolicyError, redact

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 tenant TEXT NOT NULL, user_id TEXT NOT NULL, name TEXT NOT NULL,
 email TEXT NOT NULL, salary INTEGER NOT NULL, PRIMARY KEY(tenant,user_id));
CREATE TABLE IF NOT EXISTS memory (
 tenant TEXT NOT NULL, actor TEXT NOT NULL, session TEXT NOT NULL,
 mode TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
 PRIMARY KEY(tenant,actor,session,mode,key));
CREATE TABLE IF NOT EXISTS actions (
 id TEXT PRIMARY KEY, tenant TEXT NOT NULL, actor TEXT NOT NULL, role TEXT NOT NULL,
 session TEXT NOT NULL, tool TEXT NOT NULL, args TEXT NOT NULL, digest TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected','expired','consumed')),
 created REAL NOT NULL, expires REAL NOT NULL, approved_by TEXT,
 decided REAL, consumed REAL, reason TEXT);
CREATE TABLE IF NOT EXISTS tickets (
 id TEXT PRIMARY KEY, tenant TEXT NOT NULL, actor TEXT NOT NULL,
 summary TEXT NOT NULL, priority TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, tenant TEXT NOT NULL, actor TEXT NOT NULL, result TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS audit (
 id TEXT PRIMARY KEY, request_id TEXT NOT NULL, tenant TEXT, actor TEXT,
 event TEXT NOT NULL, reason TEXT NOT NULL, created REAL NOT NULL);
PRAGMA user_version=1;
"""

class Database:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.suffix.lower() == ".json":
            raise ValueError("Legacy JSON memory is untrusted. Use a new .sqlite3 path; no automatic import.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError("Unsupported database schema")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def seed_demo(self):
        # Explicit initialization only: service startup never resurrects deleted users.
        with self.connect() as conn:
            for tenant in ("demo", "other"):
                for uid, salary in (("alice", 30000), ("bob", 25000)):
                    conn.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?,?)",
                                 (tenant, uid, uid.title(), f"{uid}@example.com", salary))

    def audit(self, ctx, request_id, event, reason):
        with self.connect() as conn:
            self.audit_in(conn, ctx, request_id, event, reason)

    @staticmethod
    def audit_in(conn, ctx, request_id, event, reason):
        conn.execute("INSERT INTO audit VALUES (?,?,?,?,?,?,?)",
                     (uuid4().hex, request_id, ctx.tenant_id if ctx else None,
                      ctx.user_id if ctx else None, event, reason, time.time()))

    def save_run(self, run_id, ctx, result, secrets=()):
        with self.connect() as conn:
            conn.execute("INSERT INTO runs VALUES (?,?,?,?,?)",
                         (run_id, ctx.tenant_id, ctx.user_id, json.dumps(redact(result, secrets), ensure_ascii=False), time.time()))

    def get_run(self, run_id, ctx):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise PolicyError("run_not_found", 404)
        if (row["tenant"], row["actor"]) != (ctx.tenant_id, ctx.user_id):
            raise PolicyError("run_access_denied")
        return json.loads(row["result"])

