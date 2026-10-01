"""Le fondamenta di tutte le azioni con cui Raphael cambia qualcosa sul PC.

Ogni azione passa dal GestoreAzioni, che:

- chiede conferma all'utente prima delle azioni a rischio medio o alto
  (la conferma la dà l'interfaccia: pulsanti, terminale o, in futuro, la voce);
- blocca tutto se è attiva la modalità sola lettura;
- scrive ogni cosa nel registro delle azioni;
- ricorda come annullare le ultime azioni.

Il modello non può confermare da solo: la decisione arriva sempre dall'utente.
"""

import json
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


logger = logging.getLogger(__name__)

RISCHIO_BASSO = "basso"
RISCHIO_MEDIO = "medio"
RISCHIO_ALTO = "alto"

ESITO_ESEGUITA = "eseguita"
ESITO_RIFIUTATA = "rifiutata"
ESITO_BLOCCATA = "bloccata"
ESITO_ERRORE = "errore"
ESITO_ANNULLATA = "annullata"
ESITO_STRUMENTO = "strumento"

SIMBOLI_ESITO = {
    ESITO_ESEGUITA: "✅",
    ESITO_STRUMENTO: "✅",
    ESITO_ANNULLATA: "↩️",
    ESITO_RIFIUTATA: "✋",
    ESITO_BLOCCATA: "🔒",
    ESITO_ERRORE: "⚠️",
}

MAX_AZIONI_ANNULLABILI = 20
MAX_VOCI_RIEPILOGO = 50

MESI = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]


class AzioneNonRiuscita(Exception):
    """Errore da mostrare all'utente così com'è, senza dettagli tecnici."""


@dataclass
class Azione:
    descrizione: str
    esegui: Callable[[], str]
    rischio: str = RISCHIO_MEDIO
    annulla: Callable[[], str] | None = None
    dettagli: str = ""


def rifiuta_sempre(azione: Azione) -> bool:
    """Conferma predefinita: senza un'interfaccia che chieda, non si fa niente."""
    return False


# ------------------------------------------------------------------ registro


class RegistroAzioni:
    """Diario di tutto quello che Raphael ha fatto, una riga JSON per evento."""

    def __init__(self, percorso=None):
        self.percorso = Path(percorso) if percorso else None
        self._in_memoria = []
        self._lock = threading.Lock()

    def registra(self, descrizione: str, esito: str, messaggio: str = "",
                 rischio: str = RISCHIO_BASSO):
        voce = {
            "quando": datetime.now().isoformat(timespec="seconds"),
            "descrizione": descrizione,
            "rischio": rischio,
            "esito": esito,
            "messaggio": messaggio.splitlines()[0] if messaggio else "",
        }

        with self._lock:
            if self.percorso is None:
                self._in_memoria.append(voce)
                return

            try:
                self.percorso.parent.mkdir(parents=True, exist_ok=True)
                with self.percorso.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(voce, ensure_ascii=False) + "\n")
            except OSError as errore:
                logger.warning("Registro delle azioni non scrivibile: %s", errore)

    def voci(self, giorno: date | None = None) -> list[dict]:
        with self._lock:
            if self.percorso is None:
                tutte = list(self._in_memoria)
            else:
                tutte = self._leggi_file()

        if giorno is None:
            return tutte

        prefisso = giorno.isoformat()
        return [voce for voce in tutte if voce.get("quando", "").startswith(prefisso)]

    def _leggi_file(self) -> list[dict]:
        if not self.percorso.exists():
            return []

        voci = []
        for riga in self.percorso.read_text(encoding="utf-8").splitlines():
            try:
                voci.append(json.loads(riga))
            except json.JSONDecodeError:
                continue
        return voci

    def riepilogo(self, giorno: date | None = None) -> str:
        giorno = giorno or date.today()
        voci = self.voci(giorno)
        nome_giorno = _nome_giorno(giorno)

        if not voci:
            return f"{nome_giorno.capitalize()} non ho fatto nessuna azione sul PC."

        righe = []
        for voce in voci[-MAX_VOCI_RIEPILOGO:]:
            ora = voce.get("quando", "")[11:16]
            simbolo = SIMBOLI_ESITO.get(voce.get("esito"), "•")
            testo = voce.get("messaggio") or voce.get("descrizione", "")
            if voce.get("esito") == ESITO_RIFIUTATA:
                testo = f"Non confermata: {voce.get('descrizione', '')}"
            elif voce.get("esito") == ESITO_BLOCCATA:
                testo = f"Bloccata dalla sola lettura: {voce.get('descrizione', '')}"
            righe.append(f"- {ora} {simbolo} {testo}")

        intestazione = f"Ecco cosa ho fatto {nome_giorno} ({len(voci)} azioni):"
        if len(voci) > MAX_VOCI_RIEPILOGO:
            intestazione += f"\n(mostro solo le ultime {MAX_VOCI_RIEPILOGO})"

        return intestazione + "\n" + "\n".join(righe)


def _nome_giorno(giorno: date) -> str:
    oggi = date.today()
    if giorno == oggi:
        return "oggi"
    if giorno == oggi - timedelta(days=1):
        return "ieri"
    return f"il {giorno.day} {MESI[giorno.month - 1]} {giorno.year}"


def interpreta_giorno(testo: str | None) -> date | None:
    """Capisce 'oggi', 'ieri', 'l'altro ieri' o una data come 2026-10-01 o 1/10/2026."""
    testo = (testo or "oggi").strip().lower()
    oggi = date.today()

    if testo in {"", "oggi"}:
        return oggi
    if testo == "ieri":
        return oggi - timedelta(days=1)
    if testo in {"l'altro ieri", "altro ieri", "avantieri"}:
        return oggi - timedelta(days=2)

    # Senza anno ("1/10") si intende l'anno in corso: lo aggiungiamo noi,
    # perché da Python 3.15 leggere una data senza anno non sarà più permesso.
    if testo.count("/") == 1:
        testo = f"{testo}/{oggi.year}"

    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(testo, formato).date()
        except ValueError:
            continue

    return None


# ------------------------------------------------------------------ gestore


class GestoreAzioni:
    def __init__(self, registro: RegistroAzioni | None = None, chiedi_conferma=None):
        self.registro = registro or RegistroAzioni()
        self.chiedi_conferma = chiedi_conferma or rifiuta_sempre
        self.sola_lettura = False
        self._da_annullare = []
        self._lock = threading.Lock()

    def esegui(self, azione: Azione) -> str:
        if azione.rischio != RISCHIO_BASSO:
            if self.sola_lettura:
                self.registro.registra(
                    azione.descrizione, ESITO_BLOCCATA, rischio=azione.rischio
                )
                return (
                    "La modalità sola lettura è attiva, quindi non ho fatto niente. "
                    "L'utente può disattivarla con /solalettura off."
                )

            try:
                confermata = bool(self.chiedi_conferma(azione))
            except Exception as errore:
                logger.warning("Richiesta di conferma fallita: %s", errore)
                confermata = False

            if not confermata:
                self.registro.registra(
                    azione.descrizione, ESITO_RIFIUTATA, rischio=azione.rischio
                )
                return (
                    "L'utente non ha confermato, quindi non ho fatto niente: "
                    f"{azione.descrizione}."
                )

        try:
            esito = azione.esegui()
        except AzioneNonRiuscita as errore:
            esito = str(errore)
            self.registro.registra(
                azione.descrizione, ESITO_ERRORE, esito, rischio=azione.rischio
            )
            return esito
        except Exception as errore:
            logger.exception("Azione fallita: %s", azione.descrizione)
            esito = f"Non ci sono riuscito ({azione.descrizione}): {errore}"
            self.registro.registra(
                azione.descrizione, ESITO_ERRORE, esito, rischio=azione.rischio
            )
            return esito

        self.registro.registra(
            azione.descrizione, ESITO_ESEGUITA, esito, rischio=azione.rischio
        )

        if azione.annulla is not None:
            with self._lock:
                self._da_annullare.append((azione.descrizione, azione.annulla))
                del self._da_annullare[:-MAX_AZIONI_ANNULLABILI]

        return esito

    def puo_annullare(self) -> bool:
        return bool(self._da_annullare)

    def annulla_ultima(self) -> str:
        with self._lock:
            if not self._da_annullare:
                return "Non c'è nessuna azione recente da annullare."
            descrizione, annulla = self._da_annullare.pop()

        try:
            esito = annulla()
        except AzioneNonRiuscita as errore:
            esito = str(errore)
            self.registro.registra(f"Annullare: {descrizione}", ESITO_ERRORE, esito)
            return esito
        except Exception as errore:
            logger.exception("Annullamento fallito: %s", descrizione)
            esito = f"Non sono riuscito ad annullare ({descrizione}): {errore}"
            self.registro.registra(f"Annullare: {descrizione}", ESITO_ERRORE, esito)
            return esito

        self.registro.registra(f"Annullare: {descrizione}", ESITO_ANNULLATA, esito)
        return esito

    def imposta_sola_lettura(self, attiva: bool) -> str:
        self.sola_lettura = bool(attiva)
        logger.info("Sola lettura: %s", self.sola_lettura)

        if self.sola_lettura:
            return (
                "🔒 Modalità sola lettura attivata: non farò nessuna azione che "
                "cambia qualcosa sul PC finché non scrivi /solalettura off."
            )
        return "🔓 Modalità sola lettura disattivata."