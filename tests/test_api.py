import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from fastapi.testclient import TestClient
from api import create_app
from auth import AuthRegistry
from llm_client import ModelError
from mock_llm import DemoLLM
from security import UserContext
from storage import Database

class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Database(Path(self.tmp.name)/"api.sqlite3")
        self.db.seed_demo()
        self.auth = AuthRegistry({"test-credential-"+key+"-"*24:ctx for key,ctx in {
            "a":UserContext("alice"),"b":UserContext("bob"),
            "admin":UserContext("operator","admin"),"reviewer":UserContext("reviewer","approver")}.items()})
        self.app = create_app(self.db,self.auth,DemoLLM())
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def headers(self, token="a"):
        return {"Authorization":"Bearer test-credential-"+token+"-"*24}

    def chat(self, message, token="a", **extra):
        return self.client.post("/chat",headers=self.headers(token),json={"session_id":"s","message":message,**extra})

    def test_health_and_auth(self):
        self.assertEqual(self.client.get("/health").json(),{"status":"ok"})
        self.assertEqual(self.client.post("/chat",json={"session_id":"s","message":"x"}).status_code,401)
        self.assertEqual(self.chat("x","invalid").status_code,401)

    def test_forged_role_tenant_mode_rejected(self):
        for key,value in [("role","admin"),("user_id","bob"),("tenant_id","other"),("mode","vulnerable")]:
            self.assertEqual(self.chat("x",**{key:value}).status_code,422)

    def test_bad_input_no_echo(self):
        r = self.chat("secret=not-for-errors",session_id="../bad")
        self.assertEqual(r.status_code,422)
        self.assertNotIn("not-for-errors",r.text)

    def test_own_and_denied_model_tools(self):
        r = self.chat("/salary alice")
        self.assertEqual(r.status_code,200)
        self.assertIn("30000",r.json()["answer"])
        self.assertEqual(self.chat("/salary bob").json()["trace"][0]["audit"],"object_permission_denied")

    def test_runs_authorization_and_ids(self):
        r = self.chat("/salary alice")
        run = r.json()["run_id"]
        self.assertEqual(run,r.headers["X-Request-ID"])
        self.assertEqual(self.client.get("/runs/"+run,headers=self.headers()).status_code,200)
        self.assertEqual(self.client.get("/runs/"+run,headers=self.headers("b")).status_code,403)

    def test_approval_http_flow(self):
        result = self.chat("/delete bob","admin").json()
        action_id = result["trace"][0]["action_id"]
        url = "/actions/"+action_id
        a = self.client.get(url,headers=self.headers("admin")).json()
        body = {"digest":a["digest"]}
        self.assertEqual(self.client.get(url,headers=self.headers()).status_code,403)
        self.assertEqual(self.client.post(url+"/execute",headers=self.headers("admin"),json=body).status_code,409)
        self.assertEqual(self.client.post(url+"/approve",headers=self.headers("admin"),json=body).status_code,403)
        self.assertEqual(self.client.post(url+"/approve",headers=self.headers("reviewer"),json=body).status_code,200)
        self.assertEqual(self.client.post(url+"/execute",headers=self.headers("admin"),json={**body,"user_id":"alice"}).status_code,422)
        self.assertEqual(self.client.post(url+"/execute",headers=self.headers("admin"),json=body).status_code,200)
        self.assertEqual(self.client.post(url+"/execute",headers=self.headers("admin"),json=body).status_code,409)

    def test_upstream_429_and_error_without_secrets(self):
        class Broken(DemoLLM):
            async def chat(self,*args,**kwargs):
                raise ModelError("model_rate_limited",503)
        self.app.state.agent.llm = Broken()
        self.assertEqual(self.chat("x").status_code,503)

    def test_cancellable_timeout(self):
        class Slow(DemoLLM):
            async def chat(self,*args,**kwargs):
                await asyncio.sleep(1)
        self.app.state.agent.llm = Slow()
        self.app.state.agent.timeout = .01
        self.assertEqual(self.chat("x").status_code,504)
        with self.db.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM actions").fetchone()[0],0)

    def test_known_secret_redacted_from_response_and_saved_run(self):
        class Echo(DemoLLM):
            async def chat(self,*args,**kwargs):
                return {"role":"assistant","content":"Bearer abc sk-demo-key"}
        self.app.state.agent.llm = Echo()
        r = self.chat("x")
        self.assertNotIn("sk-demo-key",r.text)
        self.assertNotIn("Bearer abc",r.text)

    def test_invalid_json_and_unknown_tool(self):
        class Bad(DemoLLM):
            async def chat(self,*args,**kwargs):
                return {"role":"assistant","tool_calls":[{"id":"c","function":{"name":"delete_user","arguments":"{"}}]}
        self.app.state.agent.llm = Bad()
        self.assertEqual(self.chat("x").json()["status"],"invalid_tool_call")

    def test_repeat_calls_do_not_repeat_side_effects(self):
        class Repeat(DemoLLM):
            async def chat(self,*args,**kwargs):
                return {"role":"assistant","tool_calls":[{"id":"c","function":{"name":"create_support_ticket","arguments":'{"summary":"help","priority":"low"}'}}]}
        self.app.state.agent.llm = Repeat()
        self.assertEqual(self.chat("x").json()["status"],"duplicate_call")
        with self.db.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM tickets").fetchone()[0],1)

    def test_call_limit(self):
        class Many(DemoLLM):
            async def chat(self,*args,**kwargs):
                return {"role":"assistant","tool_calls":[{"id":str(i),"function":{"name":"search_policy","arguments":json.dumps({"query":str(i)})}} for i in range(20)]}
        self.app.state.agent.llm = Many()
        r = self.chat("x").json()
        self.assertEqual(r["status"],"call_limit")
        self.assertEqual(len(r["trace"]),3)

    def test_round_limit(self):
        self.app.state.agent.max_calls = 20
        class Rounds(DemoLLM):
            async def chat(self,messages,**kwargs):
                return {"role":"assistant","tool_calls":[{"id":str(len(messages)),"function":{"name":"search_policy","arguments":json.dumps({"query":str(len(messages))})}}]}
        self.app.state.agent.llm = Rounds()
        with patch("agent.get_max_tool_rounds",return_value=2):
            self.assertEqual(self.chat("x").json()["status"],"round_limit")

