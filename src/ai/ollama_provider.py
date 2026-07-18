import ollama

from .provider import AIProvider


class OllamaProvider(AIProvider):
    def __init__(self, model: str = "llama3.2"):
        self.model = model

    def generate_response(self, prompt: str, history: list | None = None) -> str:
        if history:
            messages = [
                {"role": messaggio["role"], "content": messaggio["content"]}
                for messaggio in history
            ]
        else:
            messages = [{"role": "user", "content": prompt}]

        risposta = ollama.chat(
            model=self.model,
            messages=messages,
        )

        return risposta["message"]["content"]