from anthropic import Anthropic

from .provider import AIProvider


class ClaudeProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def generate_response(self, prompt: str, history: list | None = None) -> str:
        if history:
            messages = [
                {"role": messaggio["role"], "content": messaggio["content"]}
                for messaggio in history
            ]
        else:
            messages = [{"role": "user", "content": prompt}]

        risposta = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=messages,
        )

        return risposta.content[0].text