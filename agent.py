from policy import UserContext, sanitize_output
from tools import vulnerable_execute, secure_execute
from rag import retrieve
from memory import MEMORY
from mock_llm import propose_action

class MiniAgent:
    def __init__(self, mode: str = "vulnerable"):
        if mode not in {"vulnerable", "secure"}:
            raise ValueError("mode must be vulnerable or secure")
        self.mode = mode

    def _rag_context(self, query: str):
        docs = retrieve(query, secure=(self.mode == "secure"))
        chunks = []

        for d in docs:
            if self.mode == "secure":
                chunks.append(
                    f"[UNTRUSTED_DATA_BOUNDARY][source={d.doc_id}] {d.text}"
                )
            else:
                chunks.append(d.text)

        return "\n".join(chunks)

    def chat(self, user_prompt: str, ctx: UserContext):
        rag_text = self._rag_context(user_prompt)

        action = propose_action(
            user_prompt=user_prompt,
            rag_text=rag_text,
            memory=MEMORY.dump(),
        )

        if action["type"] == "answer":
            output = action["text"]
        else:
            executor = (
                vulnerable_execute
                if self.mode == "vulnerable"
                else secure_execute
            )
            output = executor(
                action["tool_name"],
                action.get("args", {}),
                ctx,
            )

        if self.mode == "secure":
            output = sanitize_output(output)

        return {
            "mode": self.mode,
            "rag_context": rag_text,
            "llm_action": action,
            "output": output,
        }

    def write_memory(self, key: str, value: str):
        if self.mode == "vulnerable":
            return MEMORY.vulnerable_write(key, value)
        return MEMORY.secure_write(key, value)
