import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import httpx
from llm_client import RealLLMClient, ModelError

class AdapterTests(unittest.TestCase):
    def run_response(self, handler):
        cfg = SimpleNamespace(api_key="test-key",base_url="https://model.invalid/v1",model="test",provider="deepseek")
        client_type = httpx.AsyncClient
        with patch("llm_client.httpx.AsyncClient",side_effect=lambda **kw:client_type(transport=httpx.MockTransport(handler),**kw)):
            return asyncio.run(RealLLMClient(cfg).chat([{"role":"user","content":"test"}]))

    def test_http_429_is_not_success(self):
        with self.assertRaises(ModelError) as caught:
            self.run_response(lambda request:httpx.Response(429,json={"error":"secret upstream detail"}))
        self.assertEqual(caught.exception.status,503)
        self.assertEqual(str(caught.exception),"model_rate_limited")

    def test_transport_timeout(self):
        def timeout(request):
            raise httpx.ReadTimeout("secret URL",request=request)
        with self.assertRaises(ModelError) as caught:
            self.run_response(timeout)
        self.assertEqual(caught.exception.status,504)

    def test_malformed_response(self):
        with self.assertRaises(ModelError):
            self.run_response(lambda r:httpx.Response(200,json={"unexpected":"value"}))

    def test_valid_wire_response(self):
        self.assertEqual(self.run_response(lambda r:httpx.Response(200,json={"choices":[{"message":{"role":"assistant","content":"ok"}}]}))["content"],"ok")

