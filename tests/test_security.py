import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from attacks import (
    scenario_prompt_injection,
    scenario_tool_overreach,
    scenario_rag_poisoning,
    scenario_memory_poisoning,
    scenario_data_leakage,
)

class AgentSecurityTests(unittest.TestCase):

    def test_prompt_injection_vulnerable_leaks(self):
        result = scenario_prompt_injection("vulnerable")
        self.assertIn("salary=", result["output"])

    def test_prompt_injection_secure_denied(self):
        result = scenario_prompt_injection("secure")
        self.assertIn("DENIED", result["output"])

    def test_tool_overreach_vulnerable(self):
        result = scenario_tool_overreach("vulnerable")
        self.assertIn("bob salary=", result["output"])

    def test_tool_overreach_secure(self):
        result = scenario_tool_overreach("secure")
        self.assertIn("DENIED", result["output"])

    def test_rag_poisoning_secure_filters_untrusted(self):
        result = scenario_rag_poisoning("secure")
        self.assertIn("500 元", result["output"])
        self.assertNotIn("50000 元", result["output"])

    def test_memory_poisoning_secure(self):
        result = scenario_memory_poisoning("secure")
        self.assertIn("MEMORY_DENIED", result["memory_write"])
        self.assertEqual({}, result["memory"])

    def test_data_leakage_vulnerable(self):
        result = scenario_data_leakage("vulnerable")
        self.assertIn("sk-demo-secret", result["output"])

    def test_data_leakage_secure_redacts(self):
        result = scenario_data_leakage("secure")
        self.assertIn("[REDACTED_API_KEY]", result["output"])
        self.assertNotIn("sk-demo-secret", result["output"])

if __name__ == "__main__":
    unittest.main()
