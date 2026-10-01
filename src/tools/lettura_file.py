"""Strumenti con cui Raphael legge i file dell'utente da solo.

Raphael può guardare cosa c'è in una cartella e leggere il contenuto di file di
testo, codice, PDF, Word e PowerPoint, trovandoli anche solo dal nome.
Legge soltanto: non modifica, non sposta e non cancella niente. Per sicurezza
lavora solo dentro la cartella dell'utente e non apre file di chiavi e
configurazioni segrete.
"""

import itertools
import logging
import math
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from .pc_control import (
    CARTELLE_DA_SALTARE,
    MAX_FILE_ESAMINATI,
    MAX_RISULTATI,
    _elementi_nelle_cartelle_utente,
    _normalizza,
)


logger = logging.getLogger(__name__)

MAX_CARATTERI_PER_PARTE = 10_000
MAX_DIMENSIONE_FILE = 50 * 1024 * 1024
MAX_PAGINE_PDF = 300
MAX_ELEMENTI_CARTELLA = 60

ESTENSIONI_TESTO = {
    ".txt", ".md", ".csv", ".tsv", ".log", ".json", ".xml", ".yaml", ".yml",
    ".ini", ".cfg", ".toml", ".html", ".htm", ".css", ".js", ".ts", ".jsx",
    ".tsx", ".py", ".java", ".c", ".h", ".cpp", ".hpp", ".cs", ".php", ".sql",
    ".sh", ".bat", ".ps1", ".tex", ".srt",
}
ESTENSIONI_DOCUMENTI = {".pdf", ".docx", ".pptx"}
ESTENSIONI_LEGGIBILI = ESTENSIONI_TESTO | ESTENSIONI_DOCUMENTI

# File che contengono chiavi, password o segreti: Raphael non li legge mai.
NOMI_PROTETTI = {".env", "id_rsa", "id_ed25519", "credentials.json"}
ESTENSIONI_PROTETTE = {".pem", ".key", ".pfx", ".p12", ".kdbx", ".ppk"}

# Nomi italiani delle cartelle di Windows, che sul disco hanno il nome inglese.
CARTELLE_ITALIANE = {
    "documenti": "Documents",
    "scrivania": "Desktop",
    "desktop": "Desktop",
    "download": "Downloads",
    "immagini": "Pictures",
    "musica": "Music",
    "video": "Videos",
}

SPAZIO_WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SPAZIO_SLIDE = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


# ------------------------------------------------------------- sicurezza


def _cartella_utente() -> Path:
    return Path.home().resolve()


def _controlla_cartella(cartella: Path) -> str | None:
    """Restituisce un messaggio d'errore se la cartella non si può guardare."""
    try:
        relativo = cartella.resolve().relative_to(_cartella_utente())
    except ValueError:
        return "Per sicurezza leggo solo i file che stanno nella tua cartella utente."

    for parte in relativo.parts:
        if parte in CARTELLE_DA_SALTARE or parte.startswith("."):
            return "Per sicurezza non leggo file di sistema o di cartelle nascoste."

    return None


def _controlla_percorso(percorso: Path) -> str | None:
    """Restituisce un messaggio d'errore se il file non si può leggere."""
    errore = _controlla_cartella(percorso.parent)
    if errore:
        return errore

    nome = percorso.name.lower()
    if nome in NOMI_PROTETTI or percorso.suffix.lower() in ESTENSIONI_PROTETTE:
        return "Per sicurezza non leggo file che contengono chiavi o password."

    return None


# --------------------------------------------------------- trovare i file


def _elementi_limitati():
    return itertools.islice(_elementi_nelle_cartelle_utente(), MAX_FILE_ESAMINATI)


def _trova_per_nome(nome: str) -> list[Path]:
    """Cerca un file dal nome, preferendo le corrispondenze più precise."""
    richiesto = _normalizza(nome)
    esatti, stesso_nome, contengono = [], [], []

    for percorso in _elementi_limitati():
        if not percorso.is_file():
            continue

        nome_file = _normalizza(percorso.name)
        if nome_file == richiesto:
            esatti.append(percorso)
        elif _normalizza(percorso.stem) == richiesto:
            stesso_nome.append(percorso)
        elif richiesto in nome_file:
            contengono.append(percorso)

        if len(esatti) >= MAX_RISULTATI:
            break

    for gruppo in (esatti, stesso_nome, contengono):
        if gruppo:
            # Prima i file che Raphael sa leggere.
            gruppo.sort(key=lambda p: p.suffix.lower() not in ESTENSIONI_LEGGIBILI)
            return gruppo[:MAX_RISULTATI]

    return []


def _risolvi(percorso: str) -> tuple[Path | None, str | None]:
    """Trasforma ciò che ha scritto il modello in un file vero, o in un errore."""
    testo = percorso.strip().strip('"').strip("'")

    if not testo:
        return None, "Dimmi quale file devo leggere."

    candidato = Path(testo).expanduser()

    if not candidato.is_absolute() and ("/" in testo or "\\" in testo):
        # Un percorso relativo, come "Documents/appunti.txt": parte da casa.
        candidato = Path.home() / candidato

    if candidato.is_absolute():
        if not candidato.exists():
            return None, f"Il file '{testo}' non esiste."
        return candidato, None

    trovati = _trova_per_nome(testo)

    if not trovati:
        return None, (
            f"Non ho trovato nessun file chiamato '{testo}' "
            "nel Desktop, nei Documenti o nei Download."
        )

    if len(trovati) > 1:
        elenco = "\n".join(str(p) for p in trovati)
        return None, (
            f"Ho trovato più file per '{testo}', dimmi quale leggere:\n{elenco}"
        )

    return trovati[0], None


# ---------------------------------------------------- estrarre il testo


def _leggi_testo(percorso: Path) -> str:
    dati = percorso.read_bytes()

    for codifica in ("utf-8-sig", "cp1252"):
        try:
            return dati.decode(codifica)
        except UnicodeDecodeError:
            continue

    return dati.decode("utf-8", errors="replace")


def _leggi_pdf(percorso: Path) -> str:
    from pypdf import PdfReader

    lettore = PdfReader(str(percorso))

    if lettore.is_encrypted and not lettore.decrypt(""):
        raise ValueError("il PDF è protetto da password")

    pagine = []
    for numero, pagina in enumerate(lettore.pages[:MAX_PAGINE_PDF], start=1):
        testo = (pagina.extract_text() or "").strip()
        if testo:
            pagine.append(f"--- Pagina {numero} ---\n{testo}")

    if len(lettore.pages) > MAX_PAGINE_PDF:
        pagine.append(f"[Lette solo le prime {MAX_PAGINE_PDF} pagine.]")

    return "\n\n".join(pagine)


def _paragrafi(radice, spazio: str) -> list[str]:
    paragrafi = []

    for paragrafo in radice.iter(f"{spazio}p"):
        pezzi = []
        for elemento in paragrafo.iter():
            if elemento.tag == f"{spazio}t" and elemento.text:
                pezzi.append(elemento.text)
            elif elemento.tag == f"{spazio}tab":
                pezzi.append("\t")
        testo = "".join(pezzi).strip()
        if testo:
            paragrafi.append(testo)

    return paragrafi


def _leggi_docx(percorso: Path) -> str:
    with zipfile.ZipFile(percorso) as archivio:
        radice = ElementTree.fromstring(archivio.read("word/document.xml"))

    return "\n".join(_paragrafi(radice, SPAZIO_WORD))


def _leggi_pptx(percorso: Path) -> str:
    diapositive = []

    with zipfile.ZipFile(percorso) as archivio:
        nomi = [
            nome
            for nome in archivio.namelist()
            if re.fullmatch(r"ppt/slides/slide\d+\.xml", nome)
        ]
        nomi.sort(key=lambda nome: int(re.search(r"(\d+)", nome).group(1)))

        for numero, nome in enumerate(nomi, start=1):
            radice = ElementTree.fromstring(archivio.read(nome))
            testo = "\n".join(_paragrafi(radice, SPAZIO_SLIDE))
            if testo:
                diapositive.append(f"--- Diapositiva {numero} ---\n{testo}")

    return "\n\n".join(diapositive)


def estrai_testo(percorso: Path) -> str:
    estensione = percorso.suffix.lower()

    if estensione == ".pdf":
        return _leggi_pdf(percorso)
    if estensione == ".docx":
        return _leggi_docx(percorso)
    if estensione == ".pptx":
        return _leggi_pptx(percorso)

    return _leggi_testo(percorso)


# --------------------------------------------------------------- strumenti


def leggi_file(percorso: str, parte: int | None = None) -> str:
    """Legge il contenuto di un file dell'utente: testo, codice, PDF, Word (.docx) o PowerPoint (.pptx).

    Usalo quando l'utente ti chiede di leggere, riassumere, spiegare o controllare
    un suo file, anche se non te lo allega. Puoi passare il percorso completo
    restituito da cerca_file oppure solo il nome del file.
    I file lunghi vengono letti a parti: se il risultato dice che il file continua
    e ti serve il resto, chiedi la parte successiva.

    Args:
        percorso: Il percorso completo del file oppure solo il suo nome, ad esempio "appunti fisica.pdf".
        parte: Quale parte del file leggere, a partire da 1. Serve solo per i file lunghi.
    """
    file, errore = _risolvi(percorso)
    if errore:
        return errore

    if file.is_dir():
        return f"'{file.name}' è una cartella: usa elenca_cartella per vedere cosa contiene."

    errore = _controlla_percorso(file)
    if errore:
        return errore

    estensione = file.suffix.lower()
    if estensione not in ESTENSIONI_LEGGIBILI:
        return (
            f"Non so leggere i file {estensione or 'senza estensione'}. "
            "Leggo testo, codice, PDF, Word (.docx) e PowerPoint (.pptx)."
        )

    if file.stat().st_size > MAX_DIMENSIONE_FILE:
        return f"Il file '{file.name}' è troppo grande da leggere."

    try:
        testo = estrai_testo(file).strip()
    except Exception as errore:
        logger.warning("Lettura di %s fallita: %s", file, errore)
        return f"Non sono riuscito a leggere '{file.name}': {errore}"

    if not testo:
        if estensione == ".pdf":
            return (
                f"Il PDF '{file.name}' non contiene testo leggibile: probabilmente "
                "è una scansione fatta di immagini."
            )
        return f"Il file '{file.name}' è vuoto."

    try:
        parte = int(parte or 1)
    except (TypeError, ValueError):
        parte = 1

    totale_parti = math.ceil(len(testo) / MAX_CARATTERI_PER_PARTE)
    if not 1 <= parte <= totale_parti:
        return f"Il file '{file.name}' ha solo {totale_parti} parti."

    inizio = (parte - 1) * MAX_CARATTERI_PER_PARTE
    contenuto = testo[inizio:inizio + MAX_CARATTERI_PER_PARTE]

    logger.info("Letto %s (parte %d di %d)", file, parte, totale_parti)

    if totale_parti == 1:
        intestazione = f"Ho letto {file.name}."
    else:
        intestazione = f"Ho letto {file.name} (parte {parte} di {totale_parti})."

    risultato = f"{intestazione}\nPercorso: {file}\n\n{contenuto}"

    if parte < totale_parti:
        risultato += (
            f"\n\n[Il file continua: per leggere il resto usa leggi_file "
            f"con parte={parte + 1}.]"
        )

    return risultato


def _trova_cartella(testo: str) -> Path | None:
    if not testo:
        return None

    candidato = Path(testo).expanduser()
    if candidato.is_absolute():
        return candidato if candidato.is_dir() else None

    nome_su_disco = CARTELLE_ITALIANE.get(_normalizza(testo), testo)
    da_casa = Path.home() / nome_su_disco
    if da_casa.is_dir():
        return da_casa

    richiesto = _normalizza(testo)
    return next(
        (
            elemento
            for elemento in _elementi_limitati()
            if elemento.is_dir() and _normalizza(elemento.name) == richiesto
        ),
        None,
    )


def elenca_cartella(percorso: str) -> str:
    """Mostra i file e le sottocartelle contenuti in una cartella dell'utente.

    Usalo quando l'utente ti chiede cosa c'è in una cartella, o per trovare il
    file giusto prima di leggerlo. Puoi passare il percorso completo oppure solo
    il nome della cartella.

    Args:
        percorso: Il percorso completo della cartella oppure il suo nome, ad esempio "Documents" o "Fisica 2".
    """
    testo = percorso.strip().strip('"').strip("'")
    cartella = _trova_cartella(testo)

    if cartella is None:
        return f"Non ho trovato nessuna cartella chiamata '{testo}'."

    errore = _controlla_cartella(cartella)
    if errore:
        return errore

    try:
        elementi = sorted(
            (e for e in cartella.iterdir() if not e.name.startswith(".")),
            key=lambda e: (not e.is_dir(), e.name.lower()),
        )
    except OSError as errore:
        return f"Non riesco ad aprire la cartella '{cartella.name}': {errore}"

    if not elementi:
        return f"La cartella {cartella} è vuota."

    righe = [
        f"📁 {e.name}" if e.is_dir() else f"📄 {e.name}"
        for e in elementi[:MAX_ELEMENTI_CARTELLA]
    ]
    if len(elementi) > MAX_ELEMENTI_CARTELLA:
        righe.append(f"... e altri {len(elementi) - MAX_ELEMENTI_CARTELLA} elementi")

    return (
        f"La cartella {cartella} contiene {len(elementi)} elementi:\n"
        + "\n".join(righe)
    )


STRUMENTI_LETTURA = [leggi_file, elenca_cartella]