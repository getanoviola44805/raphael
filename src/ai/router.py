from .provider import AIProvider


class AIRouter:
    def __init__(self, provider: AIProvider):
        self.provider = provider

    def generate_response(self, prompt: str) -> str:
        return self.provider.generate_response(prompt)