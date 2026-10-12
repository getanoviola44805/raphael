"""Strumenti con cui Raphael può agire sul computer dell'utente.

Sono pensati per essere sicuri: aprono programmi, siti e file, cercano file
e leggono la data. Non cancellano, non spostano e non modificano niente, e non
eseguono comandi arbitrari.
"""

import json
import logging
import os
import subprocess
import sys
import threading
import unicodedata
import webbrowser
from datetime import datetime
from pathlib import Path


ESTENSIONI_ESEGUIBILI = {
    ".exe", ".bat", ".cmd", ".com", ".msi", ".ps1", ".vbs", ".vbe",
    ".js", ".jse", ".wsf", ".wsh", ".scr", ".pif", ".lnk", ".reg", ".hta",
}
CARTELLE_DA_SALTARE = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", "AppData",
}
MAX_FILE_ESAMINATI = 50_000
MAX_RISULTATI = 10

SINONIMI_PROGRAMMI = {
    "vs code": "visual studio code",
    "vscode": "visual studio code",
    "chrome": "google chrome",
    "edge": "microsoft edge",
    "esplora file": "esplora file",
    "esplora risorse": "esplora file",
    "blocco note": "blocco note",
    "notepad": "blocco note",
    "calcolatrice": "calcolatrice",
}

# Parole troppo comuni per riconoscere un programma da sole.
PAROLE_GENERICHE = {
    "microsoft", "google", "adobe", "autodesk", "apple", "windows", "app",
    "programma", "the", "per", "and", "pro", "studio", "editor",
}

GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]

logger = logging.getLogger(__name__)

_programmi_in_cache = None
_lucchetto_programmi = threading.Lock()


def _normalizza(testo: str) -> str:
    senza_accenti = unicodedata.normalize("NFKD", testo)
    senza_accenti = "".join(c for c in senza_accenti if not unicodedata.combining(c))
    return " ".join(senza_accenti.lower().split())


def _avvia(bersaglio: str) -> None:
    """Apre un programma, un file o un indirizzo con l'app predefinita di Windows."""
    os.startfile(bersaglio)


def _elenca_programmi_installati() -> list[dict]:
    """Chiede a Windows l'elenco delle app del menu Start (anche quelle dello Store)."""
    comando = (
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
        "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress"
    )
    risultato = subprocess.run(
        ["powershell", "-NoProfile", "-Command", comando],
        capture_output=True,
        timeout=20,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    dati = json.loads(risultato.stdout.decode("utf-8") or "[]")

    if isinstance(dati, dict):
        dati = [dati]

    return [{"nome": app["Name"], "id": app["AppID"]} for app in dati]


def _programmi_installati() -> list[dict]:
    global _programmi_in_cache

    # Il lucchetto evita due PowerShell insieme se l'utente chiede di aprire
    # qualcosa mentre l'elenco si sta ancora preparando all'avvio.
    with _lucchetto_programmi:
        if _programmi_in_cache is None:
            _programmi_in_cache = _elenca_programmi_installati()

    return _programmi_in_cache


def prepara_elenco_programmi() -> None:
    """Legge subito l'elenco dei programmi, così il primo "apri ..." è istantaneo."""
    try:
        quanti = len(_programmi_installati())
        logger.info("Elenco dei programmi pronto: %s programmi", quanti)
    except Exception as errore:
        logger.warning("Non sono riuscito a leggere l'elenco dei programmi: %s", errore)


def cerca_programma_installato(nome: str) -> dict | None:
    """Il programma installato che corrisponde al nome, oppure None."""
    try:
        return trova_programma(nome, _programmi_installati())
    except Exception:
        return None


def trova_programma(nome: str, programmi: list[dict]) -> dict | None:
    """Sceglie il programma che corrisponde meglio al nome richiesto."""
    richiesto = _normalizza(nome)
    richiesto = SINONIMI_PROGRAMMI.get(richiesto, richiesto)

    esatti, iniziano, contengono = [], [], []

    for programma in programmi:
        candidato = _normalizza(programma["nome"])

        if candidato == richiesto:
            esatti.append(programma)
        elif candidato.startswith(richiesto):
            iniziano.append(programma)
        elif richiesto in candidato:
            contengono.append(programma)

    for gruppo in (esatti, iniziano, contengono):
        if gruppo:
            return min(gruppo, key=lambda programma: len(programma["nome"]))

    return _trova_per_parole(richiesto, programmi)


def _trova_per_parole(richiesto: str, programmi: list[dict]) -> dict | None:
    """Ultima possibilità: le parole in comune, per esempio "Fusion 360" → "Autodesk Fusion".

    Contano solo le parole che distinguono davvero un programma: numeri e nomi
    di aziende come "Microsoft" non bastano, altrimenti "Microsoft Word"
    aprirebbe Microsoft Teams.
    """
    parole_richieste = {
        parola for parola in richiesto.split()
        if len(parola) > 2 and not parola.isdigit() and parola not in PAROLE_GENERICHE
    }
    if not parole_richieste:
        return None

    candidati = []
    for programma in programmi:
        comuni = parole_richieste & set(_normalizza(programma["nome"]).split())
        if len(comuni) * 2 >= len(parole_richieste) and comuni:
            candidati.append((len(comuni), -len(programma["nome"]), programma))

    if not candidati:
        return None
    return max(candidati, key=lambda candidato: candidato[:2])[2]


def apri_programma(nome: str) -> str:
    """Apre un programma installato sul computer dell'utente.

    Args:
        nome: Il nome del programma da aprire, ad esempio "Chrome", "Discord", "Blocco note" o "Calcolatrice".

    Returns:
        L'esito dell'operazione.
    """
    try:
        programma = trova_programma(nome, _programmi_installati())
    except Exception as errore:
        return f"Non sono riuscito a leggere l'elenco dei programmi installati: {errore}"

    if programma is None:
        return f"Non ho trovato nessun programma installato che si chiami '{nome}'."

    try:
        _avvia(f"shell:AppsFolder\\{programma['id']}")
    except Exception as errore:
        return f"Ho trovato {programma['nome']}, ma non sono riuscito ad aprirlo: {errore}"

    return f"Ho aperto {programma['nome']}."


def apri_sito(indirizzo: str) -> str:
    """Apre un sito web nel browser predefinito dell'utente.

    Args:
        indirizzo: L'indirizzo del sito che l'utente ha chiesto, ad esempio "https://www.unict.it".

    Returns:
        L'esito dell'operazione.
    """
    indirizzo = indirizzo.strip()

    if "://" not in indirizzo:
        indirizzo = f"https://{indirizzo}"

    if not indirizzo.startswith(("http://", "https://")):
        return "Posso aprire solo indirizzi web che iniziano con http:// o https://."

    webbrowser.open(indirizzo)
    return f"Ho aperto {indirizzo} nel browser."


def _cartelle_utente() -> list[Path]:
    casa = Path.home()
    cartelle = [casa / "Desktop", casa / "Documents", casa / "Downloads"]

    for cartella_onedrive in casa.glob("OneDrive*"):
        cartelle += [cartella_onedrive / "Desktop", cartella_onedrive / "Documents"]

    return [cartella for cartella in cartelle if cartella.is_dir()]


def _elementi_nelle_cartelle_utente():
    for cartella in _cartelle_utente():
        for radice, sottocartelle, file in os.walk(cartella):
            sottocartelle[:] = [
                sottocartella
                for sottocartella in sottocartelle
                if sottocartella not in CARTELLE_DA_SALTARE
                and not sottocartella.startswith(".")
            ]

            for elemento in sottocartelle + file:
                yield Path(radice) / elemento


def cerca_file(nome: str) -> str:
    """Cerca file e cartelle nel Desktop, nei Documenti e nei Download dell'utente.

    Args:
        nome: Il nome, o una parte del nome, del file da cercare, ad esempio "tesi" o "fattura.pdf".

    Returns:
        L'elenco dei percorsi trovati, uno per riga.
    """
    richiesto = _normalizza(nome)
    trovati = []

    for esaminati, percorso in enumerate(_elementi_nelle_cartelle_utente(), start=1):
        if richiesto in _normalizza(percorso.name):
            trovati.append(str(percorso))

            if len(trovati) >= MAX_RISULTATI:
                break

        if esaminati >= MAX_FILE_ESAMINATI:
            break

    if not trovati:
        return (
            f"Non ho trovato file che contengano '{nome}' "
            "nel Desktop, nei Documenti o nei Download."
        )

    return f"Ho trovato {len(trovati)} risultati per '{nome}':\n" + "\n".join(trovati)


def apri_file(percorso: str) -> str:
    """Apre un file o una cartella con il programma predefinito di Windows.

    Args:
        percorso: Il percorso completo del file o della cartella, come restituito da cerca_file.

    Returns:
        L'esito dell'operazione.
    """
    elemento = Path(percorso.strip().strip('"'))

    if not elemento.exists():
        return f"Il percorso '{percorso}' non esiste."

    if elemento.is_file() and elemento.suffix.lower() in ESTENSIONI_ESEGUIBILI:
        return (
            "Per sicurezza non apro file eseguibili o script. "
            "Se vuoi avviare un programma, chiedimi di aprirlo per nome."
        )

    try:
        _avvia(str(elemento))
    except Exception as errore:
        return f"Non sono riuscito ad aprire '{elemento.name}': {errore}"

    return f"Ho aperto {elemento.name}."


def data_e_ora() -> str:
    """Restituisce la data e l'ora attuali del computer dell'utente.

    Returns:
        La data e l'ora attuali, in italiano.
    """
    adesso = datetime.now()
    giorno = GIORNI[adesso.weekday()]
    mese = MESI[adesso.month - 1]
    return f"Oggi è {giorno} {adesso.day} {mese} {adesso.year}, sono le {adesso:%H:%M}."


STRUMENTI_PC = [apri_programma, apri_sito, cerca_file, apri_file, data_e_ora]