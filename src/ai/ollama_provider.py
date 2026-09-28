import logging

import ollama

from .provider import AIProvider


logger = logging.getLogger(__name__)


class OllamaProvider(AIProvider):
    def __init__(
        self,
        model: str = "llama3.2",
        system_prompt: str | None = None,
        context_length: int = 4096,
    ):
        self.model = model
        self.system_prompt = system_prompt
        self.context_length = context_length

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
                think=False,
                options={"num_ctx": self.context_length},
            )
        except ConnectionError:
            return (
                "⚠️ Non riesco a contattare Ollama. Assicurati che sia in "
                "esecuzione (avvialo dall'icona nella system tray oppure "
                "con 'ollama serve') e riprova."
            )

        logger.info(
            "Ollama: motivo fine=%s, token domanda=%s, token risposta=%s",
            risposta.get("done_reason"),
            risposta.get("prompt_eval_count"),
            risposta.get("eval_count"),
        )

        contenuto = risposta["message"]["content"].strip()

        if not contenuto:
            return "⚠️ Non sono riuscito a generare una risposta. Prova a riformulare la domanda."

        return contenuto