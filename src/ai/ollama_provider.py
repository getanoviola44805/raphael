import ollama

from .provider import AIProvider


class OllamaProvider(AIProvider):
    def __init__(self, model: str = "llama3.2", system_prompt: str | None = None):
        self.model = model
        self.system_prompt = system_prompt

    def generate_response(self, prompt: str, history: list | None = None) -> str:
        if history:
            messages = [
                {"role": messaggio["role"], "content": messaggio["content"]}
                for messaggio in history
            ]
        else:
            messages = [{"role": "user", "content": prompt}]

        if self.system_prompt:
            messages.insert(0, {"role": "system", "content": self.system_prompt})

        try:
            risposta = ollama.chat(
                model=self.model,
                messages=messages,
            )
        except ConnectionError:
            return (
                "⚠️ Non riesco a contattare Ollama. Assicurati che sia in "
                "esecuzione (avvialo dall'icona nella system tray oppure "
                "con 'ollama serve') e riprova."
            )

        return risposta["message"]["content"]