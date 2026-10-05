"""The original 16 tests run unchanged against the preserved original sources only."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

class LegacyBaseline(unittest.TestCase):
    def test_original_16_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            with zipfile.ZipFile(Path(__file__).parent/"fixtures"/"legacy_v2.zip") as archive:
                archive.extractall(td)
            env = {k:v for k,v in os.environ.items() if k != "PYTHONPATH"}
            result = subprocess.run([sys.executable,"-m","unittest","discover","-s","tests","-v"],
                                    cwd=td,env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn("Ran 16 tests",result.stderr)

