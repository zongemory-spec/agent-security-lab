"""Local CLI only. HTTP always uses server-authenticated contexts and secure mode."""
import argparse
import asyncio
import json
from pathlib import Path
from agent import RealAgent
from config import get_provider_config
from llm_client import RealLLMClient
from mock_llm import DemoLLM
from security import UserContext
from storage import Database

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--provider", choices=["qwen", "deepseek"])
    p.add_argument("--mode", choices=["secure", "vulnerable"], default="secure")
    p.add_argument("--allow-vulnerable", action="store_true")
    p.add_argument("--user", choices=["alice", "bob", "operator"], default="alice")
    a = p.parse_args()
    if a.mode == "vulnerable" and not a.allow_vulnerable:
        p.error("Local vulnerable experiments require --allow-vulnerable")
    path = Path(f"data/cli_{a.mode}.sqlite3")
    fresh = not path.exists()
    db = Database(path)
    if fresh:
        db.seed_demo()
    llm = RealLLMClient(get_provider_config(a.provider)) if a.provider else DemoLLM()
    agent = RealAgent(llm, a.mode, db=db)
    ctx = UserContext(a.user, "admin" if a.user == "operator" else "user")
    print("Local synthetic CLI. /quit to exit. Default backend is an offline simulator.")
    while True:
        prompt = input("User> ").strip()
        if prompt == "/quit":
            break
        try:
            print(json.dumps(asyncio.run(agent.run(prompt, ctx)), ensure_ascii=False, indent=2))
        except Exception as exc:
            print(type(exc).__name__ + ": request failed (details withheld)")

if __name__ == "__main__":
    main()

