"""Comandi rapidi: le richieste semplici che Raphael esegue subito, senza il modello.

"apri Discord", "apri amazon, zalando e foot locker", "ricordami tra 20 secondi
di bere", "timer di 10 minuti", "che ore sono": per queste non serve ragionare.
Riconoscerle con delle regole è istantaneo e affidabile, mentre il modello
deve rileggere ogni volta più di 4.000 token di istruzioni e a volte
dimentica di usare lo strumento.

Le regole sono volutamente strette: se una frase non è chiarissima,
interpreta() restituisce None e la richiesta passa al modello come sempre.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

from .promemoria import interpreta_quando


MASSIMA_LUNGHEZZA = 140
MASSIME_COSE_DA_APRIRE = 5
MASSIME_PAROLE_PER_NOME = 4

SITI_NOTI = {
    "youtube": "https://www.youtube.com",
    "amazon": "https://www.amazon.it",
    "zalando": "https://www.zalando.it",
    "foot locker": "https://www.footlocker.it",
    "footlocker": "https://www.footlocker.it",
    "netflix": "https://www.netflix.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "wikipedia": "https://it.wikipedia.org",
    "reddit": "https://www.reddit.com",
    "twitch": "https://www.twitch.tv",
    "whatsapp web": "https://web.whatsapp.com",
    "studium": "https://studium.unict.it",
    "unict": "https://www.unict.it",
}

# Se dopo "apri" c'è una di queste parole, la richiesta non è un semplice nome
# ("apri il file della tesi", "apri la cartella ciao123"): ci pensa il modello.
PAROLE_NON_SEMPLICI = {
    "il", "lo", "la", "i", "gli", "le", "l", "un", "uno", "una",
    "file", "cartella", "documento", "foto", "immagine", "pdf", "sito", "pagina",
    "mio", "mia", "miei", "mie", "questo", "questa", "quel", "quello", "quella",
    "ultimo", "ultima", "di", "del", "della", "dei", "delle", "da", "dal", "dalla",
    "su", "sul", "sulla", "in", "nel", "nella", "con", "per", "che", "se",
    "poi", "dopo", "come", "dove", "perche", "non",
}

DOMINIO = re.compile(r"(?:https?://)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/\S*)?")

_GIORNI = (
    "lunedì|lunedi|martedì|martedi|mercoledì|mercoledi|giovedì|giovedi|"
    "venerdì|venerdi|sabato|domenica"
)
_INIZIO_TEMPO = (
    r"(?:tra|fra|alle|all'|verso\s+le|domani|dopodomani|oggi|stasera|stamattina|"
    r"stanotte|a\s+mezzogiorno|a\s+mezzanotte|mezzogiorno|mezzanotte|"
    rf"{_GIORNI}|il\s+\d|\d{{1,2}}[/:.]\d)"
)

_SALUTO = re.compile(r"^(?:ehi|ei|hey)?[\s,]*raphael\b[\s,:!.]*", re.IGNORECASE)
_PER_FAVORE = re.compile(r"^per\s+favore[\s,]+|[\s,]+per\s+favore$", re.IGNORECASE)
_APRI = re.compile(r"^(?:apri|avvia|lancia|aprimi)\s+(?P<cosa>.+)$", re.IGNORECASE)
_PROMEMORIA = re.compile(
    r"^(?P<verbo>(?:mi\s+)?(?:metti|imposta|crea|aggiungi)\s+un\s+promemoria|"
    r"promemoria|ricordami|avvisami|svegliami)\b[\s:,]*(?P<resto>.*)$",
    re.IGNORECASE,
)
_TIMER = re.compile(
    r"^(?:(?:mi\s+)?(?:metti|imposta|fai\s+partire|avvia|crea|fammi)\s+)?"
    r"(?:un\s+)?timer\s+(?:di\s+|da\s+|per\s+)?(?P<durata>.+)$",
    re.IGNORECASE,
)
_TEMPO_POI_TESTO = re.compile(
    rf"^(?P<quando>{_INIZIO_TEMPO}.*?)\s+(?:di|che|per)\s+(?P<testo>.+)$", re.IGNORECASE
)
_TESTO_POI_TEMPO = re.compile(
    rf"^(?:di|che)\s+(?P<testo>.+?)\s+(?P<quando>{_INIZIO_TEMPO}.*)$", re.IGNORECASE
)
_SOLO_TEMPO = re.compile(rf"^{_INIZIO_TEMPO}", re.IGNORECASE)
# "alle 9 di sera" non deve spezzarsi in "alle 9" + "sera...".
_MOMENTO_DEL_GIORNO = re.compile(
    r"\b(?:di|della|del|nel|nella)\s+(sera|mattina|pomeriggio|notte)\b", re.IGNORECASE
)

DOMANDE_SULL_ORA = {
    "che ore sono", "che ora e", "che ora e adesso", "che ore sono adesso",
    "che giorno e", "che giorno e oggi", "che data e", "che data e oggi",
    "quanti ne abbiamo", "quanti ne abbiamo oggi",
}


def _normalizza(testo: str) -> str:
    testo = unicodedata.normalize("NFKD", testo.lower())
    testo = "".join(c for c in testo if not unicodedata.combining(c))
    testo = testo.replace("’", "'")
    return " ".join(testo.split())


def _pulisci(testo: str) -> str:
    testo = " ".join(testo.replace("’", "'").split())
    testo = _SALUTO.sub("", testo)
    testo = _PER_FAVORE.sub("", testo)
    return testo.strip().rstrip(".!? ").strip()


def _con_maiuscola(testo: str) -> str:
    testo = testo.strip().rstrip(".!,;: ")
    return testo[:1].upper() + testo[1:]


@dataclass
class Chiamata:
    """Uno strumento da usare, con i suoi argomenti."""

    nome: str
    argomenti: dict = field(default_factory=dict)


class ComandiRapidi:
    def __init__(self, trova_programma=None, adesso=datetime.now):
        """trova_programma(nome) restituisce il programma installato o None."""
        self.trova_programma = trova_programma or (lambda nome: None)
        self.adesso = adesso

    def interpreta(self, testo: str) -> list[Chiamata] | None:
        """Le chiamate da fare per questa richiesta, oppure None se serve il modello."""
        if not testo or len(testo) > MASSIMA_LUNGHEZZA or "\n" in testo.strip():
            return None

        frase = _pulisci(testo)
        if not frase:
            return None

        for interprete in (self._ora, self._timer, self._promemoria, self._apri):
            chiamate = interprete(frase)
            if chiamate:
                return chiamate
        return None

    # ------------------------------------------------------------- ora

    def _ora(self, frase):
        if _normalizza(frase) in DOMANDE_SULL_ORA:
            return [Chiamata("data_e_ora")]
        return None

    # ------------------------------------------------------ promemoria

    def _promemoria_valido(self, quando, testo):
        try:
            momento = interpreta_quando(quando, self.adesso())
        except Exception:
            return None
        if momento is None or momento <= self.adesso():
            return None
        return [Chiamata("imposta_promemoria", {"quando": quando.strip(), "testo": testo})]

    def _timer(self, frase):
        trovato = _TIMER.match(frase)
        if not trovato:
            return None
        durata = trovato.group("durata").strip()
        return self._promemoria_valido(f"tra {durata}", f"Timer di {durata} finito")

    def _promemoria(self, frase):
        trovato = _PROMEMORIA.match(frase)
        if not trovato:
            return None

        resto = _MOMENTO_DEL_GIORNO.sub(r"\1", trovato.group("resto").strip())
        predefinito = "Sveglia!" if trovato.group("verbo").lower() == "svegliami" else "Promemoria"

        if not resto:
            return None

        for schema in (_TEMPO_POI_TESTO, _TESTO_POI_TEMPO):
            parti = schema.match(resto)
            if parti:
                testo = _con_maiuscola(parti.group("testo"))
                chiamate = self._promemoria_valido(parti.group("quando"), testo)
                if chiamate:
                    return chiamate

        # Solo il quando, senza testo: "svegliami alle 7", "avvisami tra 10 minuti".
        if _SOLO_TEMPO.match(resto):
            return self._promemoria_valido(resto, predefinito)
        return None

    # ------------------------------------------------------------ apri

    def _apri(self, frase):
        trovato = _APRI.match(frase)
        if not trovato:
            return None

        nomi = [
            nome.strip()
            for nome in re.split(r"\s*,\s*|\s+e\s+|\s+ed\s+", trovato.group("cosa"))
        ]
        if not nomi or len(nomi) > MASSIME_COSE_DA_APRIRE or not all(nomi):
            return None

        chiamate = []
        for nome in nomi:
            chiamata = self._cosa_aprire(nome)
            if chiamata is None:
                return None
            chiamate.append(chiamata)
        return chiamate

    def _cosa_aprire(self, nome):
        normalizzato = _normalizza(nome)
        parole = re.findall(r"[a-z0-9]+", normalizzato)

        if not parole or len(parole) > MASSIME_PAROLE_PER_NOME:
            return None

        try:
            programma = self.trova_programma(nome)
        except Exception:
            programma = None

        # Un programma con esattamente quel nome vince su tutto ("Esplora file").
        if programma and _normalizza(programma["nome"]) == normalizzato:
            return Chiamata("apri_programma", {"nome": nome})
        if any(parola in PAROLE_NON_SEMPLICI for parola in parole):
            return None
        if normalizzato in SITI_NOTI:
            return Chiamata("apri_sito", {"indirizzo": SITI_NOTI[normalizzato]})
        if DOMINIO.fullmatch(normalizzato):
            return Chiamata("apri_sito", {"indirizzo": nome.strip()})
        if programma:
            return Chiamata("apri_programma", {"nome": nome})
        return None