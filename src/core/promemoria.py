"""Promemoria e timer di Raphael.

L'agenda salva i promemoria in un file JSON, così restano anche dopo un
riavvio. Il pianificatore controlla ogni pochi secondi se qualcuno è scaduto e
avvisa l'interfaccia, che mostra la notifica. Un timer è semplicemente un
promemoria "tra N minuti".
"""

import json
import logging
import re
import threading
import unicodedata
from datetime import date, datetime, time, timedelta
from pathlib import Path


logger = logging.getLogger(__name__)

ORA_PREDEFINITA = time(9, 0)
MASSIMO_ANTICIPO = timedelta(days=366)
MAX_PROMEMORIA = 200

GIORNI = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]
GIORNI_ACCENTATI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]
NUMERI_IN_PAROLE = {
    "un": 1, "uno": 1, "una": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5,
    "sei": 6, "sette": 7, "otto": 8, "nove": 9, "dieci": 10, "undici": 11,
    "dodici": 12, "quindici": 15, "venti": 20, "trenta": 30, "quaranta": 40,
    "quarantacinque": 45, "cinquanta": 50, "sessanta": 60, "novanta": 90,
}
SECONDI_PER_UNITA = [
    ("second", 1), ("minut", 60), ("min", 60), ("or", 3600),
    ("giorn", 86400), ("settiman", 604800),
]

_NUMERO = r"(\d+(?:[.,]\d+)?|" + "|".join(sorted(NUMERI_IN_PAROLE, key=len, reverse=True)) + r")"
_DURATA = re.compile(
    r"\b" + _NUMERO + r"\s*(secondi|secondo|sec|minuti|minuto|min|ore|ora|giorni|giorno|settimane|settimana)\b"
)


def _normalizza(testo: str) -> str:
    testo = unicodedata.normalize("NFKD", testo.lower())
    testo = "".join(c for c in testo if not unicodedata.combining(c))
    testo = testo.replace("’", "'")
    return " ".join(testo.split())


def _numero(parola: str) -> float:
    if parola in NUMERI_IN_PAROLE:
        return NUMERI_IN_PAROLE[parola]
    return float(parola.replace(",", "."))


def _secondi_unita(unita: str) -> int:
    for prefisso, secondi in SECONDI_PER_UNITA:
        if unita.startswith(prefisso):
            return secondi
    return 60


# ------------------------------------------------------------ capire "quando"


def _durata(testo: str) -> timedelta | None:
    """Capisce durate come "10 minuti", "un'ora e mezza", "1 ora e 20 minuti"."""
    testo = re.sub(r"\bun quarto d'?\s?ora\b", "15 minuti", testo)
    testo = re.sub(r"\bmezz'?\s?ora\b", "30 minuti", testo)
    testo = re.sub(r"\bun'ora\b", "un ora", testo)

    coppie = _DURATA.findall(testo)
    if not coppie:
        return None

    secondi = sum(_numero(numero) * _secondi_unita(unita) for numero, unita in coppie)
    if re.search(r"\be mezz[ao]\b", testo):
        secondi += 1800

    return timedelta(seconds=secondi) if secondi > 0 else None


def _ora(testo: str) -> time | None:
    """Trova l'orario: "alle 9", "alle 18:30", "ore 7.15", "mezzogiorno", "9 di sera"."""
    if "mezzogiorno" in testo:
        return time(12, 0)
    if "mezzanotte" in testo:
        return time(0, 0)

    trovato = re.search(r"(?:\balle\b|\bore\b|\ball'|\bverso le\b)\s*(\d{1,2})(?:[:.](\d{2}))?", testo)
    if not trovato:
        trovato = re.search(r"\b(\d{1,2})[:.](\d{2})\b", testo)
    if not trovato:
        return None

    ore = int(trovato.group(1))
    minuti = int(trovato.group(2) or 0)

    if ore < 12 and re.search(r"\b(sera|pomeriggio|stasera)\b", testo):
        ore += 12
    if ore > 23 or minuti > 59:
        return None
    return time(ore, minuti)


def _giorno(testo: str, oggi: date) -> date | None:
    """Trova il giorno: "domani", "venerdì", "5/10", "2026-10-05", "5 ottobre"."""
    if "dopodomani" in testo:
        return oggi + timedelta(days=2)
    if "domani" in testo:
        return oggi + timedelta(days=1)
    if "oggi" in testo or "stasera" in testo or "stamattina" in testo:
        return oggi

    iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", testo)
    if iso:
        return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))

    numerica = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", testo)
    if numerica:
        anno = int(numerica.group(3) or oggi.year)
        if anno < 100:
            anno += 2000
        giorno = date(anno, int(numerica.group(2)), int(numerica.group(1)))
        if numerica.group(3) is None and giorno < oggi:
            giorno = giorno.replace(year=oggi.year + 1)
        return giorno

    for indice, mese in enumerate(MESI, start=1):
        con_mese = re.search(rf"\b(\d{{1,2}})\s+{mese}(?:\s+(\d{{4}}))?\b", testo)
        if con_mese:
            anno = int(con_mese.group(2) or oggi.year)
            giorno = date(anno, indice, int(con_mese.group(1)))
            if con_mese.group(2) is None and giorno < oggi:
                giorno = giorno.replace(year=oggi.year + 1)
            return giorno

    for indice, nome in enumerate(GIORNI):
        if re.search(rf"\b{nome}\b", testo):
            avanti = (indice - oggi.weekday()) % 7
            return oggi + timedelta(days=avanti)

    return None


def interpreta_quando(testo: str, adesso: datetime | None = None) -> datetime | None:
    """Trasforma "tra 10 minuti", "domani alle 9", "venerdì alle 18:30"... in una data.

    Restituisce None se non capisce. Un orario senza giorno vale per oggi, o per
    domani se è già passato; un giorno senza orario vale alle 9:00.
    """
    adesso = adesso or datetime.now()
    testo = _normalizza(str(testo))

    if not testo:
        return None

    # Formato completo, come lo scrive spesso il modello: 2026-10-01T15:30
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}[t ]\d{1,2}:\d{2}(:\d{2})?.*", testo):
        try:
            return datetime.fromisoformat(testo.upper().replace(" ", "T", 1)).replace(tzinfo=None)
        except ValueError:
            pass

    try:
        giorno = _giorno(testo, adesso.date())
    except ValueError:  # una data impossibile, come il 31/02
        return None
    ora = _ora(testo)

    if giorno is None and ora is None:
        durata = _durata(testo)
        return adesso + durata if durata else None

    if giorno is None:
        quando = datetime.combine(adesso.date(), ora)
        if quando <= adesso:
            quando += timedelta(days=1)
        return quando

    quando = datetime.combine(giorno, ora or ORA_PREDEFINITA)

    # "venerdì alle 9" detto di venerdì alle 10 significa venerdì prossimo.
    nome_giorno = any(re.search(rf"\b{nome}\b", testo) for nome in GIORNI)
    if nome_giorno and quando <= adesso:
        quando += timedelta(days=7)

    return quando


def descrivi_quando(quando: datetime, adesso: datetime | None = None) -> str:
    """Scrive la data in modo naturale: "oggi alle 15:30", "domani alle 09:00"..."""
    adesso = adesso or datetime.now()
    giorni = (quando.date() - adesso.date()).days
    orario = f"{quando:%H:%M}"

    if giorni == 0:
        testo = f"oggi alle {orario}"
    elif giorni == 1:
        testo = f"domani alle {orario}"
    elif 1 < giorni < 7:
        testo = f"{GIORNI_ACCENTATI[quando.weekday()]} alle {orario}"
    else:
        testo = (
            f"{GIORNI_ACCENTATI[quando.weekday()]} {quando.day} "
            f"{MESI[quando.month - 1]} {quando.year} alle {orario}"
        )

    mancano = quando - adesso
    if timedelta(0) < mancano < timedelta(hours=3):
        minuti = round(mancano.total_seconds() / 60)
        if minuti < 1:
            testo += " (tra meno di un minuto)"
        elif minuti < 60:
            testo += f" (tra {minuti} minut{'o' if minuti == 1 else 'i'})"
        else:
            ore, resto = divmod(minuti, 60)
            testo += f" (tra {ore} or{'a' if ore == 1 else 'e'}"
            testo += f" e {resto} minuti)" if resto else ")"

    return testo


# -------------------------------------------------------------------- agenda


class AgendaPromemoria:
    def __init__(self, percorso=None):
        self.percorso = Path(percorso) if percorso else None
        self.voci = []
        self._prossimo_id = 1
        self._lock = threading.Lock()
        self.carica()

    def carica(self):
        if not self.percorso or not self.percorso.exists():
            return
        try:
            dati = json.loads(self.percorso.read_text(encoding="utf-8"))
            self.voci = [
                voce for voce in dati
                if isinstance(voce, dict) and voce.get("testo") and voce.get("quando")
            ]
        except (OSError, json.JSONDecodeError, TypeError) as errore:
            logger.warning("Promemoria illeggibili (%s): riparto da zero", errore)
            self.voci = []
        self._prossimo_id = max((voce.get("id", 0) for voce in self.voci), default=0) + 1

    def _salva(self):
        if not self.percorso:
            return
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        self.percorso.write_text(
            json.dumps(self.voci, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def aggiungi(self, testo: str, quando: datetime) -> dict:
        with self._lock:
            if len(self.voci) >= MAX_PROMEMORIA:
                raise ValueError("ci sono già troppi promemoria in attesa")
            voce = {
                "id": self._prossimo_id,
                "testo": " ".join(str(testo).split()),
                "quando": quando.isoformat(timespec="seconds"),
                "creato": datetime.now().isoformat(timespec="seconds"),
            }
            self._prossimo_id += 1
            self.voci.append(voce)
            self._salva()
        logger.info("Promemoria aggiunto per %s", voce["quando"])
        return voce

    def in_attesa(self) -> list[dict]:
        with self._lock:
            return sorted(self.voci, key=lambda voce: voce["quando"])

    def scaduti(self, adesso: datetime | None = None) -> list[dict]:
        """Toglie dall'agenda e restituisce i promemoria arrivati all'ora giusta."""
        adesso = adesso or datetime.now()
        with self._lock:
            arrivati = [
                voce for voce in self.voci
                if datetime.fromisoformat(voce["quando"]) <= adesso
            ]
            if arrivati:
                self.voci = [voce for voce in self.voci if voce not in arrivati]
                self._salva()
        return sorted(arrivati, key=lambda voce: voce["quando"])

    def cancella(self, riferimento: str) -> str:
        riferimento = str(riferimento).strip()
        voci = self.in_attesa()

        if not voci:
            return "Non c'è nessun promemoria in attesa."

        if _normalizza(riferimento) in {"tutti", "tutto", "tutte"}:
            with self._lock:
                self.voci = []
                self._salva()
            return f"Ho cancellato tutti i promemoria ({len(voci)})."

        if riferimento.isdigit():
            numero = int(riferimento)
            if not 1 <= numero <= len(voci):
                return f"Non esiste il promemoria numero {numero}."
            da_togliere = voci[numero - 1]
        else:
            cercato = _normalizza(riferimento)
            trovati = [voce for voce in voci if cercato in _normalizza(voce["testo"])]
            if not trovati:
                return f"Non ho trovato promemoria che contengano '{riferimento}'."
            if len(trovati) > 1:
                return (
                    "Ci sono più promemoria simili, dimmi il numero:\n"
                    + self.formatta_elenco()
                )
            da_togliere = trovati[0]

        with self._lock:
            self.voci = [voce for voce in self.voci if voce["id"] != da_togliere["id"]]
            self._salva()
        return f"Ho cancellato il promemoria: {da_togliere['testo']}"

    def formatta_elenco(self, adesso: datetime | None = None) -> str:
        voci = self.in_attesa()
        if not voci:
            return "Non c'è nessun promemoria in attesa."

        righe = [
            f"{numero}. {voce['testo']}, "
            f"{descrivi_quando(datetime.fromisoformat(voce['quando']), adesso)}"
            for numero, voce in enumerate(voci, start=1)
        ]
        return "Promemoria in attesa:\n" + "\n".join(righe)


# -------------------------------------------------------------- pianificatore


class Pianificatore:
    """Controlla di continuo l'agenda e avvisa quando un promemoria è arrivato."""

    def __init__(self, agenda: AgendaPromemoria, notifica=None, intervallo_s: float = 5):
        self.agenda = agenda
        self.notifica = notifica or (lambda voce: logger.info("Promemoria: %s", voce["testo"]))
        self.intervallo_s = intervallo_s
        self._fermati = threading.Event()
        self._thread = None

    def controlla(self, adesso: datetime | None = None) -> int:
        arrivati = self.agenda.scaduti(adesso)
        for voce in arrivati:
            try:
                self.notifica(voce)
            except Exception:
                logger.exception("Notifica del promemoria fallita")
        return len(arrivati)

    def avvia(self):
        if self._thread and self._thread.is_alive():
            return
        self._fermati.clear()
        self._thread = threading.Thread(target=self._giro, daemon=True)
        self._thread.start()

    def _giro(self):
        while not self._fermati.is_set():
            self.controlla()
            self._fermati.wait(self.intervallo_s)

    def ferma(self):
        self._fermati.set()