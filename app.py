import json

from attacks import (
    scenario_prompt_injection,
    scenario_indirect_prompt_injection,
    scenario_tool_overreach,
    scenario_rag_poisoning,
    scenario_memory_poisoning,
    scenario_data_leakage,
)

SCENARIOS = {
    "1": ("Prompt Injection", scenario_prompt_injection),
    "2": ("Indirect Prompt Injection", scenario_indirect_prompt_injection),
    "3": ("Tool Calling 越权", scenario_tool_overreach),
    "4": ("RAG Poisoning", scenario_rag_poisoning),
    "5": ("Memory Poisoning", scenario_memory_poisoning),
    "6": ("Data Leakage", scenario_data_leakage),
}

def pretty(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))

def main():
    print("=" * 60)
    print("Agent Security Mini Lab")
    print("=" * 60)

    while True:
        print("\n选择模式：")
        print("1. vulnerable")
        print("2. secure")
        print("0. exit")

        mode_choice = input("> ").strip()

        if mode_choice == "0":
            break

        if mode_choice not in {"1", "2"}:
            print("输入无效")
            continue

        mode = "vulnerable" if mode_choice == "1" else "secure"

        while True:
            print(f"\n当前模式: {mode}")
            for key, (name, _) in SCENARIOS.items():
                print(f"{key}. {name}")
            print("b. 返回")

            choice = input("> ").strip().lower()

            if choice == "b":
                break

            if choice not in SCENARIOS:
                print("输入无效")
                continue

            name, func = SCENARIOS[choice]
            print(f"\n--- {name} / {mode} ---")
            pretty(func(mode))

if __name__ == "__main__":
    main()
