"""Whitelist export: no .env, credentials, runtime data, logs, notes or virtualenv."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = ["agent.py","api.py","app.py","approvals.py","auth.py","config.py","init_demo.py",
         "llm_client.py","memory.py","mock_llm.py","rag.py","scenarios.py","security.py",
         "storage.py","tools.py","ui.html","deterministic_security_demo.py","deterministic_memory_demo.py",
         "requirements.txt","requirements.lock",".env.example",".gitignore",".dockerignore",
         "Dockerfile","compose.yaml","README.md","package_source.py","start.ps1",
         ".github/workflows/tests.yml"]
if __name__ == "__main__":
    dest = ROOT/"dist"/"agent-security-engineering.zip"
    dest.parent.mkdir(exist_ok=True)
    paths = [ROOT/f for f in FILES] + list((ROOT/"tests").glob("test_*.py")) + [ROOT/"tests/fixtures/legacy_v2.zip"] + list((ROOT/"docs").glob("*.md"))
    with zipfile.ZipFile(dest,"w",zipfile.ZIP_DEFLATED) as archive:
        for p in paths:
            archive.write(p,p.relative_to(ROOT))
    print("Created source-only archive:",dest.name)

