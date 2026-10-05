from policy import safe_memory_key

class MemoryStore:
    def __init__(self):
        self.data = {}

    def reset(self):
        self.data = {}

    def vulnerable_write(self, key: str, value: str):
        self.data[key] = value
        return f"MEMORY_WRITTEN: {key}={value}"

    def secure_write(self, key: str, value: str):
        if not safe_memory_key(key):
            return f"MEMORY_DENIED: key={key} is not allowed"
        self.data[key] = value
        return f"MEMORY_WRITTEN: {key}={value}"

    def dump(self):
        return dict(self.data)

MEMORY = MemoryStore()
