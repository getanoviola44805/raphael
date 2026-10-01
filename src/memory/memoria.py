"""Memoria a lungo termine di Raphael.

Raccoglie fatti duraturi sull'utente (nome, studi, preferenze, progetti) in un
file JSON sul computer, così Raphael se li ricorda anche nelle conversazioni
successive. Niente esce dal PC: il file sta nella cartella dei dati.
"""

import json
import logging
import re
import unicodedata
from datetime import date
from pathlib import Path


logger = logging.getLogger(__name__)

MAX_RICORDI = 100
MAX_LUNGHEZZA_RICORDO = 300
SOGLIA_SOMIGLIANZA = 0.5

# Dati che non devono mai finire in un file di testo, nemmeno in locale.
PAROLE_SENSIBILI = re.compile(
    r"\b(password|passwd|pin|puk|iban|cvv|carta di credito|codice segreto)\b",
    re.IGNORECASE,
)


def _normalizza(testo: str) -> str:
    senza_accenti = unicodedata.normalize("NFKD", testo)
    senza_accenti = "".join(c for c in senza_accenti if not unicodedata.combining(c))
    senza_punteggiatura = re.sub(r"[^\w\s]", " ", senza_accenti.lower())
    return " ".join(senza_punteggiatura.split())


def _parole_importanti(testo: str) -> set[str]:
    return {parola for parola in _normalizza(testo).split() if len(parola) > 3}


class MemoriaLungoTermine:
    def __init__(self, percorso=None):
        self.percorso = Path(percorso) if percorso else None
        self.ricordi = []

        if self.percorso:
            self.carica()

    # ------------------------------------------------------------ file

    def carica(self):
        if not self.percorso or not self.percorso.exists():
            return

        try:
            dati = json.loads(self.percorso.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as errore:
            logger.warning("Memoria illeggibile (%s): riparto da zero", errore)
            return

        self.ricordi = [
            {"testo": str(voce["testo"]), "data": str(voce.get("data", ""))}
            for voce in dati
            if isinstance(voce, dict) and voce.get("testo")
        ]

    def salva(self):
        if not self.percorso:
            return

        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        self.percorso.write_text(
            json.dumps(self.ricordi, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------- operazioni

    def elenca(self) -> list[str]:
        return [voce["testo"] for voce in self.ricordi]

    def aggiungi(self, testo: str) -> str:
        testo = " ".join(str(testo).split())

        if not testo:
            return "Non c'è niente da ricordare."

        if PAROLE_SENSIBILI.search(testo):
            return (
                "Non salvo in memoria password, PIN, codici o dati bancari: "
                "è più sicuro tenerli altrove."
            )

        if len(testo) > MAX_LUNGHEZZA_RICORDO:
            testo = testo[:MAX_LUNGHEZZA_RICORDO].rstrip() + "…"

        normalizzato = _normalizza(testo)
        if any(_normalizza(voce["testo"]) == normalizzato for voce in self.ricordi):
            return f"Lo sapevo già: {testo}"

        if len(self.ricordi) >= MAX_RICORDI:
            return (
                f"La memoria è piena ({MAX_RICORDI} ricordi). "
                "Fammi dimenticare qualcosa prima di aggiungere altro."
            )

        self.ricordi.append({"testo": testo, "data": date.today().isoformat()})
        self.salva()
        logger.info("Memoria: aggiunto un ricordo (%d totali)", len(self.ricordi))
        return f"Ho memorizzato: {testo}"

    def dimentica(self, riferimento) -> str:
        riferimento = str(riferimento).strip()

        if not riferimento:
            return "Dimmi cosa devo dimenticare."

        if not self.ricordi:
            return "Non ho niente in memoria."

        if riferimento.isdigit():
            return self._dimentica_numero(int(riferimento))

        trovati = self._cerca(riferimento)

        if not trovati:
            return f"Non ho trovato niente in memoria che corrisponda a: {riferimento}"

        if len(trovati) > 1:
            elenco = "\n".join(
                f"{indice + 1}. {self.ricordi[indice]['testo']}" for indice in trovati
            )
            return (
                "Ho trovato più ricordi simili, dimmi quale togliere "
                f"(puoi usare il numero):\n{elenco}"
            )

        return self._rimuovi(trovati[0])

    def svuota(self) -> str:
        quanti = len(self.ricordi)
        self.ricordi = []
        self.salva()
        return f"Ho dimenticato tutto ({quanti} ricordi)."

    # ------------------------------------------------------ per il modello

    def testo_per_prompt(self) -> str:
        if not self.ricordi:
            return ""

        righe = "\n".join(f"- {voce['testo']}" for voce in self.ricordi)
        return (
            "Ecco cosa sai dell'utente dalle conversazioni precedenti. "
            "Usalo con naturalezza solo quando è utile, senza elencarlo:\n"
            f"{righe}"
        )

    def formatta_elenco(self) -> str:
        if not self.ricordi:
            return (
                "Non ho ancora niente in memoria. Puoi dirmi cose come "
                "\"ricordati che studio Ingegneria\" oppure usare /ricorda."
            )

        righe = "\n".join(
            f"{numero}. {voce['testo']}"
            for numero, voce in enumerate(self.ricordi, start=1)
        )
        return f"Ecco cosa ricordo di te:\n\n{righe}"

    # ------------------------------------------------------------ interni

    def _dimentica_numero(self, numero: int) -> str:
        if not 1 <= numero <= len(self.ricordi):
            return f"Non esiste il ricordo numero {numero}."

        return self._rimuovi(numero - 1)

    def _rimuovi(self, indice: int) -> str:
        voce = self.ricordi.pop(indice)
        self.salva()
        logger.info("Memoria: rimosso un ricordo (%d rimasti)", len(self.ricordi))
        return f"Ho dimenticato: {voce['testo']}"

    def _cerca(self, riferimento: str) -> list[int]:
        cercato = _normalizza(riferimento)
        testi = [_normalizza(voce["testo"]) for voce in self.ricordi]

        uguali = [indice for indice, testo in enumerate(testi) if testo == cercato]
        if uguali:
            return uguali

        contenuti = [
            indice
            for indice, testo in enumerate(testi)
            if cercato in testo or testo in cercato
        ]
        if contenuti:
            return contenuti

        # Ultima possibilità: il modello ha riformulato il ricordo con parole
        # diverse, quindi confrontiamo le parole importanti.
        parole_cercate = _parole_importanti(riferimento)
        if not parole_cercate:
            return []

        punteggi = []
        for indice, voce in enumerate(self.ricordi):
            parole = _parole_importanti(voce["testo"])
            if parole:
                comuni = len(parole & parole_cercate)
                punteggi.append((comuni / len(parole | parole_cercate), indice))

        migliori = [voce for voce in punteggi if voce[0] >= SOGLIA_SOMIGLIANZA]
        if not migliori:
            return []

        massimo = max(punteggio for punteggio, _ in migliori)
        return [indice for punteggio, indice in migliori if punteggio == massimo]