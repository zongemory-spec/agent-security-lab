"""Local demo credential mapping. Not production authentication."""
import json
from pathlib import Path
import secrets
from security import PolicyError, UserContext

class AuthRegistry:
    def __init__(self, credentials):
        if any(len(token) < 24 for token in credentials):
            raise ValueError("Demo credentials must contain at least 24 characters")
        self.credentials = dict(credentials)

    @classmethod
    def from_file(cls, path):
        file = Path(path)
        if not file.exists():
            raise RuntimeError("Demo credentials missing. Run python init_demo.py first.")
        records = json.loads(file.read_text(encoding="utf-8-sig"))
        return cls({r["token"]: UserContext(r["user_id"], r["role"], r["tenant_id"]) for r in records})

    def authenticate(self, header):
        if not header or not header.startswith("Bearer "):
            raise PolicyError("authentication_required", 401)
        token = header[7:]
        for expected, ctx in self.credentials.items():
            if secrets.compare_digest(token.encode(), expected.encode()):
                return ctx
        raise PolicyError("invalid_credentials", 401)

    def is_approver(self, user_id, tenant):
        return any((c.user_id, c.tenant_id, c.role) == (user_id, tenant, "approver") for c in self.credentials.values())

