from __future__ import annotations

import json
from pathlib import Path

from security import can_write_memory


class MemoryStore:
    def __init__(self, path: str | Path = "data/memory.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self.data = {str(k): str(v) for k, v in raw.items()}
        except Exception:
            self.data = {}

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def reset(self) -> None:
        self.data = {}
        self._save()

    def write(self, key: str, value: str, secure: bool) -> str:
        if secure and not can_write_memory(key):
            return f"MEMORY_DENIED: key={key} is not allowed"
        self.data[key] = value
        self._save()
        return f"MEMORY_WRITTEN: {key}={value}"

    def snapshot(self) -> dict[str, str]:
        return dict(self.data)
