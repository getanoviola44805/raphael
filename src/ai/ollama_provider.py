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
MAX_GIRI_STRUMENTI = 5


class OllamaProvider(AIProvider):
    def __init__(
        self,
        model: str = "llama3.2",
        system_prompt: str | None = None,
        context_length: int = 4096,
        strumenti: list | None = None,
    ):
        self.model = model
        self.system_prompt = system_prompt
        self.context_length = context_length
        self.strumenti = list(strumenti or [])
        self._strumenti_per_nome = {
            strumento.__name__: strumento for strumento in self.strumenti
        }

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

    def _esegui_strumento(self, nome: str, argomenti: dict) -> str:
        strumento = self._strumenti_per_nome.get(nome)

        if strumento is None:
            return f"Lo strumento '{nome}' non esiste."

        logger.info("Strumento: %s %s", nome, argomenti)

        try:
            return str(strumento(**argomenti))
        except Exception as errore:
            return f"Errore durante '{nome}': {errore}"

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
        messaggi = self._prepara_messaggi(prompt, history)
        testo_generato = False

        try:
            for _ in range(MAX_GIRI_STRUMENTI + 1):
                chiamate = []
                testo_del_giro = []

                opzioni_extra = {"tools": self.strumenti} if self.strumenti else {}
                pezzi = ollama.chat(
                    model=self.model,
                    messages=messaggi,
                    think=False,
                    options={"num_ctx": self.context_length},
                    stream=True,
                    **opzioni_extra,
                )

                for pezzo in pezzi:
                    messaggio = pezzo["message"]
                    testo = messaggio.get("content") or ""

                    if testo:
                        testo_generato = True
                        testo_del_giro.append(testo)
                        yield testo

                    if messaggio.get("tool_calls"):
                        chiamate.extend(messaggio["tool_calls"])

                    if pezzo.get("done"):
                        self._registra_statistiche(pezzo)

                if not chiamate:
                    break

                # Il modello ha chiesto di usare uno o più strumenti: li eseguiamo
                # e gli rimandiamo i risultati, così può scrivere la risposta.
                messaggi.append(
                    {
                        "role": "assistant",
                        "content": "".join(testo_del_giro),
                        "tool_calls": chiamate,
                    }
                )

                for chiamata in chiamate:
                    nome = chiamata["function"]["name"]
                    argomenti = chiamata["function"]["arguments"] or {}
                    esito = self._esegui_strumento(nome, argomenti)

                    testo_generato = True
                    yield f"\n\n*⚙️ {esito.splitlines()[0]}*\n\n"

                    messaggi.append(
                        {"role": "tool", "content": esito, "tool_name": nome}
                    )

        except (ConnectionError, httpx.ConnectError):
            yield MESSAGGIO_OLLAMA_SPENTO
            return
        except ollama.ResponseError as errore:
            if self.strumenti and "does not support tools" in str(errore.error):
                logger.warning("Il modello %s non supporta gli strumenti", self.model)
                self.strumenti = []
                yield from self.generate_response_stream(prompt, history)
                return

            yield f"⚠️ Ollama ha restituito un errore: {errore.error}"
            return

        if not testo_generato:
            yield MESSAGGIO_RISPOSTA_VUOTA