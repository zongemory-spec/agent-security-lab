from __future__ import annotations

import argparse
import json

from agent import RealAgent
from config import get_agent_mode, get_provider_config
from llm_client import RealLLMClient
from scenarios import SCENARIOS
from security import UserContext


def print_result(result: dict) -> None:
    print("\n=== FINAL ANSWER ===")
    print(result["answer"])
    print("\n=== TOOL TRACE ===")
    print(json.dumps(result["trace"], ensure_ascii=False, indent=2))
    print("\n=== MEMORY BEFORE ===")
    print(json.dumps(result.get("memory_before", {}), ensure_ascii=False, indent=2))
    print("\n=== MEMORY AFTER ===")
    print(json.dumps(result.get("memory_after", {}), ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Real API Agent Security Lab")
    parser.add_argument("--provider", choices=["qwen", "deepseek"], default=None)
    parser.add_argument("--mode", choices=["secure", "vulnerable"], default=None)
    parser.add_argument("--user", default="alice")
    parser.add_argument("--role", choices=["user", "admin"], default="user")
    args = parser.parse_args()

    cfg = get_provider_config(args.provider)
    mode = args.mode or get_agent_mode()
    llm = RealLLMClient(cfg)
    agent = RealAgent(llm, mode=mode)
    ctx = UserContext(args.user, args.role)

    print("=" * 70)
    print("Agent Security Real API Lab")
    print(f"provider={cfg.provider} model={cfg.model} mode={mode} user={ctx.user_id} role={ctx.role}")
    print("=" * 70)

    while True:
        print("\nChoose:")
        print("c. custom prompt")
        for key, item in SCENARIOS.items():
            print(f"{key}. {item['name']}")
        print("r. reset memory/RAG")
        print("p. add poisoned RAG document")
        print("i. add indirect-injection RAG document")
        print("m. show long-term memory (not chat history)")
        print("0. exit")

        choice = input("> ").strip().lower()
        if choice == "0":
            return
        if choice == "r":
            agent.memory.reset()
            agent.rag.reset()
            print("reset done")
            continue
        if choice == "p":
            agent.rag.add_poison_doc()
            print("poisoned RAG document added")
            continue
        if choice == "i":
            agent.rag.add_indirect_prompt_doc()
            print("indirect-prompt document added")
            continue
        if choice == "m":
            print(json.dumps(agent.memory.snapshot(), ensure_ascii=False, indent=2))
            continue
        if choice == "c":
            prompt = input("User> ").strip()
        elif choice in SCENARIOS:
            prompt = SCENARIOS[choice]["prompt"]
            if choice == "6":
                agent.rag.add_poison_doc()
            if choice == "7":
                agent.rag.add_indirect_prompt_doc()
            print(f"User> {prompt}")
        else:
            print("invalid choice")
            continue

        try:
            result = agent.run(prompt, ctx)
            print_result(result)
        except Exception as exc:
            print(f"ERROR: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
