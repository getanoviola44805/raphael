import logging
from collections.abc import Iterator

import httpx
import ollama

from .provider import AIProvider


logger = logging.getLogger(__name__)

MESSAGGIO_OLLAMA_SPENTO = (
    "⚠️ Non riesco a contattare Ollama. Assicurati che sia in "
    "esecuzione (avvialo dall'icona nella system tray oppure "
    "con 'ollama serve') e riprova."
)
MESSAGGIO_RISPOSTA_VUOTA = (
    "⚠️ Non sono riuscito a generare una risposta. Prova a riformulare la domanda."
)


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

    def _prepara_messaggi(self, prompt: str, history: list | None) -> list:
        if history:
            messages = [
                {"role": messaggio["role"], "content": messaggio["content"]}
                for messaggio in history
            ]
        else:
            messages = [{"role": "user", "content": prompt}]

        if self.system_prompt:
            messages.insert(0, {"role": "system", "content": self.system_prompt})

        return messages

    def _registra_statistiche(self, risposta):
        logger.info(
            "Ollama: motivo fine=%s, token domanda=%s, token risposta=%s",
            risposta.get("done_reason"),
            risposta.get("prompt_eval_count"),
            risposta.get("eval_count"),
        )

    def generate_response(self, prompt: str, history: list | None = None) -> str:
        try:
            risposta = ollama.chat(
                model=self.model,
                messages=self._prepara_messaggi(prompt, history),
                think=False,
                options={"num_ctx": self.context_length},
            )
        except (ConnectionError, httpx.ConnectError):
            return MESSAGGIO_OLLAMA_SPENTO

        self._registra_statistiche(risposta)

        contenuto = risposta["message"]["content"].strip()

        if not contenuto:
            return MESSAGGIO_RISPOSTA_VUOTA

        return contenuto

    def generate_response_stream(
        self, prompt: str, history: list | None = None
    ) -> Iterator[str]:
        testo_generato = False

        try:
            pezzi = ollama.chat(
                model=self.model,
                messages=self._prepara_messaggi(prompt, history),
                think=False,
                options={"num_ctx": self.context_length},
                stream=True,
            )

            for pezzo in pezzi:
                testo = pezzo["message"]["content"]

                if testo:
                    testo_generato = True
                    yield testo

                if pezzo.get("done"):
                    self._registra_statistiche(pezzo)

        except (ConnectionError, httpx.ConnectError):
            yield MESSAGGIO_OLLAMA_SPENTO
            return
        except ollama.ResponseError as errore:
            yield f"⚠️ Ollama ha restituito un errore: {errore.error}"
            return

        if not testo_generato:
            yield MESSAGGIO_RISPOSTA_VUOTA