import json
from pathlib import Path


class ConversationHistory:
    def __init__(self):
        self.messages = []

    def add_message(self, role, content):
        self.messages.append(
            {
                "role": role,
                "content": content,
            }
        )

    def get_messages(self):
        return self.messages

    def save_to_file(self, path: str):
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_text(
            json.dumps(self.messages, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_from_file(self, path: str):
        file_path = Path(path)

        if not file_path.exists():
            return

        self.messages = json.loads(file_path.read_text(encoding="utf-8"))