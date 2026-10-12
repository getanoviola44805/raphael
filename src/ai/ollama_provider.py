import logging
import re
import time
from collections.abc import Callable, Iterator

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
TEMPERATURA = 0.2  # bassa apposta: con gli strumenti serve precisione, non fantasia

# Per quanto tempo Ollama tiene il modello in memoria dopo l'ultima domanda.
# Ricaricarlo da zero richiede parecchi secondi: è il motivo principale per cui
# a volte la prima risposta dopo una pausa è lenta.
MANTIENI_CARICATO = "30m"

# Esiti che indicano che uno strumento non è riuscito: in quel caso il modello
# deve rileggerli e decidere cosa fare, quindi il secondo giro serve.
INIZI_DI_FALLIMENTO = (
    "Non ", "Errore", "Per sicurezza", "Lo strumento", "Posso ", "Il percorso", "⚠",
)

INGRANAGGIO = "\u2699"  # ⚙
# Le righe "⚙️ ..." le scrive il programma quando uno strumento è stato usato
# davvero. Se il modello le rivede nella cronologia impara a scriverle da solo,
# fingendo di aver fatto un'azione: per questo non gliele mostriamo mai.
RIGA_STRUMENTO = re.compile(r"^[ \t]*\*?[ \t]*\u2699\ufe0f?.*(?:\n|$)", re.MULTILINE)


def pulisci_risposta_precedente(testo: str) -> str:
    """Toglie da una vecchia risposta le righe degli strumenti."""
    pulito = RIGA_STRUMENTO.sub("", testo)
    pulito = re.sub(r"\n{3,}", "\n\n", pulito).strip()
    return pulito or "Fatto."


def togli_ingranaggi(testo: str) -> str:
    """Il simbolo ⚙️ può comparire solo quando uno strumento è stato usato davvero."""
    return testo.replace(INGRANAGGIO + "\ufe0f", "").replace(INGRANAGGIO, "")


class OllamaProvider(AIProvider):
    def __init__(
        self,
        model: str = "llama3.2",
        system_prompt: str | Callable[[], str] | None = None,
        context_length: int = 4096,
        strumenti: list | None = None,
        osservatore_strumenti: Callable[[str, dict, str], None] | None = None,
        strumenti_conclusivi: set[str] | None = None,
        keep_alive: str = MANTIENI_CARICATO,
    ):
        self.model = model
        self.system_prompt = system_prompt
        self.context_length = context_length
        self.strumenti = list(strumenti or [])
        self.osservatore_strumenti = osservatore_strumenti
        # Strumenti il cui esito basta come risposta ("Ho aperto Discord."):
        # se riescono, non serve un secondo giro del modello per commentarli.
        self.strumenti_conclusivi = set(strumenti_conclusivi or ())
        self.keep_alive = keep_alive
        self._strumenti_per_nome = {
            strumento.__name__: strumento for strumento in self.strumenti
        }

    def _prompt_di_sistema(self) -> str | None:
        # Il prompt può essere una funzione: così viene ricostruito a ogni
        # domanda e include sempre i ricordi aggiornati.
        if callable(self.system_prompt):
            return self.system_prompt()

        return self.system_prompt

    def _prepara_messaggi(self, prompt: str, history: list | None) -> list:
        if history:
            messages = [
                {
                    "role": messaggio["role"],
                    "content": (
                        pulisci_risposta_precedente(messaggio["content"])
                        if messaggio["role"] == "assistant"
                        else messaggio["content"]
                    ),
                }
                for messaggio in history
            ]
        else:
            messages = [{"role": "user", "content": prompt}]

        prompt_di_sistema = self._prompt_di_sistema()
        if prompt_di_sistema:
            messages.insert(0, {"role": "system", "content": prompt_di_sistema})

        return messages

    def _registra_statistiche(self, risposta):
        def secondi(chiave):
            return (risposta.get(chiave) or 0) / 1e9

        logger.info(
            "Ollama: motivo fine=%s, token domanda=%s, token risposta=%s, "
            "durata=%.1fs (caricamento %.1fs, lettura %.1fs, scrittura %.1fs)",
            risposta.get("done_reason"),
            risposta.get("prompt_eval_count"),
            risposta.get("eval_count"),
            secondi("total_duration"),
            secondi("load_duration"),
            secondi("prompt_eval_duration"),
            secondi("eval_duration"),
        )

    def prepara(self) -> bool:
        """Carica il modello e legge in anticipo le istruzioni fisse.

        Ollama conserva quello che ha già letto: così alla prima domanda vera
        il modello è già in memoria e le ~4.000 parole di istruzioni e
        strumenti non vanno rilette da capo.
        """
        inizio = time.perf_counter()
        opzioni_extra = {"tools": self.strumenti} if self.strumenti else {}
        try:
            ollama.chat(
                model=self.model,
                messages=self._prepara_messaggi("ciao", None),
                think=False,
                options={
                    "num_ctx": self.context_length,
                    "temperature": TEMPERATURA,
                    "num_predict": 1,
                },
                keep_alive=self.keep_alive,
                **opzioni_extra,
            )
        except Exception as errore:
            logger.warning("Preparazione del modello non riuscita: %s", errore)
            return False

        logger.info("Modello pronto in %.1f s", time.perf_counter() - inizio)
        return True

    def _giro_concluso(self, chiamate: list, esiti: list[str]) -> bool:
        """Vero se tutti gli strumenti usati sono conclusivi e sono riusciti."""
        if not self.strumenti_conclusivi or not chiamate:
            return False
        for chiamata, esito in zip(chiamate, esiti):
            if chiamata["function"]["name"] not in self.strumenti_conclusivi:
                return False
            if esito.strip().startswith(INIZI_DI_FALLIMENTO):
                return False
        return True

    def _esegui_strumento(self, nome: str, argomenti: dict) -> str:
        strumento = self._strumenti_per_nome.get(nome)

        if strumento is None:
            return f"Lo strumento '{nome}' non esiste."

        logger.info("Strumento: %s %s", nome, argomenti)

        try:
            esito = str(strumento(**argomenti))
        except Exception as errore:
            esito = f"Errore durante '{nome}': {errore}"

        if self.osservatore_strumenti is not None:
            try:
                self.osservatore_strumenti(nome, argomenti, esito)
            except Exception:
                logger.exception("Osservatore degli strumenti fallito")

        return esito

    def generate_response(self, prompt: str, history: list | None = None) -> str:
        try:
            risposta = ollama.chat(
                model=self.model,
                messages=self._prepara_messaggi(prompt, history),
                think=False,
                options={"num_ctx": self.context_length, "temperature": TEMPERATURA},
                keep_alive=self.keep_alive,
            )
        except (ConnectionError, httpx.ConnectError):
            return MESSAGGIO_OLLAMA_SPENTO

        self._registra_statistiche(risposta)

        contenuto = risposta["message"]["content"].strip()

        if not contenuto:
            return MESSAGGIO_RISPOSTA_VUOTA

        return contenuto

    def generate_response_stream(
        self,
        prompt: str,
        history: list | None = None,
        ragiona: bool = False,
        immagini: list | None = None,
    ) -> Iterator[str]:
        messaggi = self._prepara_messaggi(prompt, history)
        testo_generato = False

        if immagini:
            # Le immagini vanno allegate all'ultimo messaggio dell'utente.
            messaggi[-1]["images"] = [str(immagine) for immagine in immagini]

        try:
            for _ in range(MAX_GIRI_STRUMENTI + 1):
                chiamate = []
                testo_del_giro = []

                opzioni_extra = {"tools": self.strumenti} if self.strumenti else {}
                pezzi = ollama.chat(
                    model=self.model,
                    messages=messaggi,
                    think=ragiona,
                    options={"num_ctx": self.context_length, "temperature": TEMPERATURA},
                    keep_alive=self.keep_alive,
                    stream=True,
                    **opzioni_extra,
                )

                for pezzo in pezzi:
                    messaggio = pezzo["message"]
                    testo = togli_ingranaggi(messaggio.get("content") or "")

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

                esiti = []
                for chiamata in chiamate:
                    nome = chiamata["function"]["name"]
                    argomenti = chiamata["function"]["arguments"] or {}
                    esito = self._esegui_strumento(nome, argomenti)
                    esiti.append(esito)

                    testo_generato = True
                    yield f"\n\n*⚙️ {esito.splitlines()[0]}*\n\n"

                    messaggi.append(
                        {"role": "tool", "content": esito, "tool_name": nome}
                    )

                # "Ho aperto Discord." basta come risposta: niente secondo giro.
                if self._giro_concluso(chiamate, esiti):
                    break

        except (ConnectionError, httpx.ConnectError):
            yield MESSAGGIO_OLLAMA_SPENTO
            return
        except ollama.ResponseError as errore:
            if self.strumenti and "does not support tools" in str(errore.error):
                logger.warning("Il modello %s non supporta gli strumenti", self.model)
                self.strumenti = []
                yield from self.generate_response_stream(
                    prompt, history, ragiona=ragiona, immagini=immagini
                )
                return

            yield f"⚠️ Ollama ha restituito un errore: {errore.error}"
            return

        if not testo_generato:
            yield MESSAGGIO_RISPOSTA_VUOTA