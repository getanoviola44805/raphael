from .provider import AIProvider


class MockAIProvider(AIProvider):
    def generate_response(self, prompt: str, history: list | None = None) -> str:
        return f"Risposta simulata a: {prompt}"