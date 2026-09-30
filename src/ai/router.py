from collections.abc import Iterator

from .provider import AIProvider


class AIRouter:
    def __init__(self, provider: AIProvider):
        self.provider = provider

    def generate_response(self, prompt: str, history: list | None = None) -> str:
        return self.provider.generate_response(prompt, history)

    def generate_response_stream(
        self, prompt: str, history: list | None = None
    ) -> Iterator[str]:
        return self.provider.generate_response_stream(prompt, history)