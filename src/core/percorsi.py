import os
import sys
from pathlib import Path


NOME_APP = "Raphael"


def e_eseguibile() -> bool:
    """True quando Raphael gira come .exe creato con PyInstaller."""
    return getattr(sys, "frozen", False)


def cartella_progetto() -> Path:
    return Path(__file__).resolve().parents[2]


def cartella_dati() -> Path:
    """Cartella in cui Raphael salva cronologia e log.

    Durante lo sviluppo è la cartella del progetto, come sempre.
    Nell'eseguibile è %LOCALAPPDATA%\\Raphael, così i dati non si perdono
    quando l'eseguibile viene ricreato o spostato.
    """
    if not e_eseguibile():
        return cartella_progetto()

    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / NOME_APP

    return Path.home() / f".{NOME_APP.lower()}"


def percorso_risorsa(nome: str) -> Path:
    """Percorso di un file della cartella assets (icona, immagini...)."""
    if e_eseguibile():
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = cartella_progetto()

    return base / "assets" / nome