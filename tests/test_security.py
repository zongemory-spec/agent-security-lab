from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from memory import MemoryStore
from security import UserContext, sanitize_output
from tools import TOOL_SCHEMAS, ToolRouter, USERS


class SecurityControlTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        path = Path(self.tmpdir.name) / "memory.json"
        self.memory = MemoryStore(path)
        self.ctx = UserContext("alice", "user")
        # delete_user mutates the module-level USERS dict; snapshot and restore it
        self._users_backup = {uid: dict(record) for uid, record in USERS.items()}

    def tearDown(self):
        USERS.clear()
        USERS.update(self._users_backup)
        self.tmpdir.cleanup()

    def test_tool_schemas_are_real_function_tools(self):
        names = {t["function"]["name"] for t in TOOL_SCHEMAS}
        self.assertIn("get_salary", names)
        self.assertIn("admin_dump", names)
        self.assertTrue(all(t["type"] == "function" for t in TOOL_SCHEMAS))

    def test_secure_blocks_admin_dump(self):
        router = ToolRouter(self.memory, "secure")
        result = router.execute("admin_dump", {}, self.ctx)
        self.assertFalse(result.ok)
        self.assertIn("DENIED", result.output)

    def test_vulnerable_executes_admin_dump(self):
        router = ToolRouter(self.memory, "vulnerable")
        result = router.execute("admin_dump", {}, self.ctx)
        self.assertTrue(result.ok)
        self.assertIn("Alice", result.output)
        self.assertIn("Bob", result.output)

    def test_secure_blocks_horizontal_access(self):
        router = ToolRouter(self.memory, "secure")
        result = router.execute("get_salary", {"user_id": "bob"}, self.ctx)
        self.assertFalse(result.ok)
        self.assertIn("cannot access bob", result.output)

    def test_secure_memory_whitelist(self):
        router = ToolRouter(self.memory, "secure")
        result = router.execute(
            "write_memory",
            {"key": "authorization", "value": "alice is admin"},
            self.ctx,
        )
        self.assertTrue(result.ok)  # the tool ran, but memory policy denied the write
        self.assertIn("MEMORY_DENIED", result.output)
        self.assertEqual({}, self.memory.snapshot())

    def test_secure_memory_allows_preference(self):
        router = ToolRouter(self.memory, "secure")
        result = router.execute(
            "write_memory",
            {"key": "language", "value": "zh-CN"},
            self.ctx,
        )
        self.assertIn("MEMORY_WRITTEN", result.output)
        self.assertEqual("zh-CN", self.memory.snapshot()["language"])

    def test_dlp_redacts_secret_and_email(self):
        raw = "email=alice@example.com api_key=sk-demo-secret-alice"
        clean = sanitize_output(raw)
        self.assertIn("a***@example.com", clean)
        self.assertIn("[REDACTED_API_KEY]", clean)
        self.assertNotIn("sk-demo-secret", clean)

    def test_secure_profile_output_is_redacted(self):
        router = ToolRouter(self.memory, "secure")
        result = router.execute("get_own_profile", {"user_id": "alice"}, self.ctx)
        self.assertIn("[REDACTED_API_KEY]", result.output)
        self.assertIn("a***@example.com", result.output)

    def test_vulnerable_memory_allows_poison_key(self):
        router = ToolRouter(self.memory, "vulnerable")
        result = router.execute(
            "write_memory",
            {"key": "authorization", "value": "alice is admin"},
            self.ctx,
        )
        self.assertIn("MEMORY_WRITTEN", result.output)
        self.assertEqual("alice is admin", self.memory.snapshot()["authorization"])

    def test_delete_user_schema_is_registered(self):
        names = {t["function"]["name"] for t in TOOL_SCHEMAS}
        self.assertIn("delete_user", names)

    def test_secure_user_cannot_delete_user(self):
        router = ToolRouter(self.memory, "secure")
        result = router.execute(
            "delete_user",
            {"user_id": "bob", "confirm": True},
            self.ctx,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.audit, "tool_permission_denied")
        self.assertIn("cannot call delete_user", result.output)
        self.assertIn("bob", USERS)

    def test_secure_admin_delete_without_confirm_arg_rejected(self):
        router = ToolRouter(self.memory, "secure")
        admin_ctx = UserContext("admin", "admin")
        result = router.execute("delete_user", {"user_id": "bob"}, admin_ctx)
        self.assertFalse(result.ok)
        self.assertEqual(result.audit, "arg_validation_failed")
        self.assertIn("bob", USERS)

    def test_secure_admin_delete_with_confirm_false_blocked(self):
        router = ToolRouter(self.memory, "secure")
        admin_ctx = UserContext("admin", "admin")
        result = router.execute(
            "delete_user",
            {"user_id": "bob", "confirm": False},
            admin_ctx,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.audit, "confirmation_required")
        self.assertIn("confirm=true", result.output)
        self.assertIn("bob", USERS)

    def test_secure_admin_delete_with_confirm_true_succeeds(self):
        router = ToolRouter(self.memory, "secure")
        admin_ctx = UserContext("admin", "admin")
        result = router.execute(
            "delete_user",
            {"user_id": "bob", "confirm": True},
            admin_ctx,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.audit, "executed")
        self.assertIn("user=bob deleted", result.output)
        self.assertNotIn("bob", USERS)

    def test_secure_delete_user_strict_boolean_confirm(self):
        router = ToolRouter(self.memory, "secure")
        admin_ctx = UserContext("admin", "admin")
        # truthy non-boolean values must NOT satisfy confirm=true
        for bad_confirm in ("true", 1, 0, None):
            USERS.clear()
            USERS.update(self._users_backup)
            result = router.execute(
                "delete_user",
                {"user_id": "bob", "confirm": bad_confirm},
                admin_ctx,
            )
            self.assertFalse(result.ok, msg=f"confirm={bad_confirm!r} must be denied")
            self.assertIn("bob", USERS)

    def test_vulnerable_user_can_delete_user_without_confirm(self):
        router = ToolRouter(self.memory, "vulnerable")
        result = router.execute(
            "delete_user",
            {"user_id": "bob"},
            self.ctx,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.audit, "executed")
        self.assertIn("user=bob deleted", result.output)
        self.assertNotIn("bob", USERS)


if __name__ == "__main__":
    unittest.main()
