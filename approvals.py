"""Two-person approval for synthetic operations; model tools cannot approve or execute."""
from __future__ import annotations
import hashlib
import json
import time
from uuid import uuid4
from security import PolicyError, can_call_tool, validate_tool_args

def canonical(args):
    return json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def digest_for(tool, args):
    return hashlib.sha256((tool + "\n" + canonical(args)).encode()).hexdigest()

class ApprovalStore:
    def __init__(self, db, clock=time.time, ttl=300):
        self.db, self.clock, self.ttl = db, clock, ttl

    def propose(self, tool, args, ctx, session):
        valid, _ = validate_tool_args(tool, args)
        if not valid or not can_call_tool(ctx, tool) or tool not in {"delete_user", "admin_dump"}:
            raise PolicyError("proposal_denied")
        now, digest = self.clock(), digest_for(tool, args)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT id FROM actions WHERE tenant=? AND actor=? AND role=? AND session=? AND tool=? AND digest=? AND status IN ('pending','approved') AND expires>?",
                               (ctx.tenant_id, ctx.user_id, ctx.role, session, tool, digest, now)).fetchone()
            if row:
                return row["id"]
            action_id = uuid4().hex
            conn.execute("INSERT INTO actions(id,tenant,actor,role,session,tool,args,digest,status,created,expires) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (action_id, ctx.tenant_id, ctx.user_id, ctx.role, session, tool, canonical(args), digest, "pending", now, now+self.ttl))
        return action_id

    def _load(self, conn, action_id, ctx):
        row = conn.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
        if row is None:
            raise PolicyError("action_not_found", 404)
        if row["tenant"] != ctx.tenant_id or (row["actor"] != ctx.user_id and ctx.role != "approver"):
            raise PolicyError("action_access_denied")
        if row["status"] in {"pending", "approved"} and row["expires"] <= self.clock():
            conn.execute("UPDATE actions SET status='expired',reason='ttl_expired',decided=? WHERE id=?", (self.clock(), action_id))
            row = conn.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
        return row

    def get(self, action_id, ctx):
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._load(conn, action_id, ctx)
            result = dict(row)
            result["args"] = json.loads(result["args"])
            return result

    def decide(self, action_id, digest, ctx, approve, request_id="local"):
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._load(conn, action_id, ctx)
            if row["status"] == "expired":
                conn.commit()
                raise PolicyError("action_expired", 409)
            if ctx.role != "approver" or row["actor"] == ctx.user_id:
                raise PolicyError("independent_approver_required")
            if row["status"] != "pending":
                raise PolicyError("action_not_pending", 409)
            if digest != row["digest"] or digest_for(row["tool"], json.loads(row["args"])) != digest:
                raise PolicyError("action_digest_mismatch", 409)
            state = "approved" if approve else "rejected"
            conn.execute("UPDATE actions SET status=?,approved_by=?,decided=?,reason=? WHERE id=?",
                         (state, ctx.user_id, self.clock(), "human_" + state, action_id))
            self.db.audit_in(conn, ctx, request_id, "approval", state)
        return {"action_id": action_id, "status": state}

    def execute(self, action_id, digest, ctx, approver_is_current, request_id="local"):
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._load(conn, action_id, ctx)
            if row["status"] == "expired":
                conn.commit()
                raise PolicyError("action_expired", 409)
            if (row["actor"], row["role"]) != (ctx.user_id, ctx.role) or not can_call_tool(ctx, row["tool"]):
                raise PolicyError("execution_actor_denied")
            args = json.loads(row["args"])
            if digest != row["digest"] or digest_for(row["tool"], args) != digest or not validate_tool_args(row["tool"], args)[0]:
                raise PolicyError("action_digest_mismatch", 409)
            if row["status"] != "approved":
                raise PolicyError("action_not_approved", 409)
            if row["approved_by"] == ctx.user_id or not approver_is_current(row["approved_by"], ctx.tenant_id):
                raise PolicyError("approval_authority_revoked")
            if row["tool"] == "delete_user":
                cursor = conn.execute("DELETE FROM users WHERE tenant=? AND user_id=?", (ctx.tenant_id, args["user_id"]))
                if cursor.rowcount != 1:
                    raise PolicyError("object_not_found", 404)
                output = f"user={args['user_id']} deleted (synthetic)"
            elif row["tool"] == "admin_dump":
                rows = conn.execute("SELECT user_id,name,salary FROM users WHERE tenant=? ORDER BY user_id", (ctx.tenant_id,))
                output = json.dumps([dict(r) for r in rows])
            else:
                raise PolicyError("unknown_tool")
            # Business mutation and consumption commit or roll back together.
            conn.execute("UPDATE actions SET status='consumed',consumed=? WHERE id=?", (self.clock(), action_id))
            self.db.audit_in(conn, ctx, request_id, "action_execute", "consumed")
        return {"action_id": action_id, "status": "consumed", "output": output}

