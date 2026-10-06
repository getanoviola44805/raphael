"""Screenshot e "guarda lo schermo": Raphael cattura lo schermo e lo descrive.

La cattura usa la libreria mss (veloce, multi-monitor). La descrizione la
chiede a un piccolo motore Ollama dedicato, separato dal motore principale di
Raphael (quello con tutti gli altri strumenti collegati): così non c'è un
cane che si morde la coda — questo strumento serve a *costruire* la lista di
strumenti del motore principale, quindi non può dipendere da esso.
"""

import logging
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import mss
import mss.tools

from ai.ollama_provider import OllamaProvider


logger = logging.getLogger(__name__)

CARTELLA_PREDEFINITA = Path(tempfile.gettempdir()) / "raphael_schermate"
DOMANDA_PREDEFINITA = (
    "Descrivi brevemente e in modo chiaro cosa vedi in questo screenshot dello schermo."
)


def _cattura_schermo(cartella: Path) -> Path:
    """Fa uno screenshot di tutti i monitor insieme e lo salva come PNG."""
    cartella.mkdir(parents=True, exist_ok=True)
    percorso = cartella / f"schermata_{datetime.now():%Y%m%d_%H%M%S_%f}.png"

    with mss.mss() as sct:
        schermo = sct.grab(sct.monitors[0])  # monitors[0] = tutti insieme
        mss.tools.to_png(schermo.rgb, schermo.size, output=str(percorso))

    return percorso


def crea_strumenti_schermo(
    model: str,
    context_length: int = 4096,
    cartella: Path | str | None = None,
    cattura: Callable[[Path], Path] | None = None,
    motore_visione=None,
) -> list:
    """Crea lo strumento "guarda_schermo".

    Args:
        model: Il modello Ollama da usare per descrivere lo screenshot (deve
            supportare le immagini, lo stesso che usi già per le immagini allegate a mano).
        context_length: Finestra di contesto del motore dedicato alla visione.
        cartella: Dove salvare temporaneamente gli screenshot.
        cattura: Da iniettare nei test al posto della cattura vera.
        motore_visione: Da iniettare nei test al posto di un vero OllamaProvider.
    """
    cartella = Path(cartella) if cartella else CARTELLA_PREDEFINITA
    cattura = cattura or _cattura_schermo
    motore = motore_visione or OllamaProvider(model=model, context_length=context_length)

    def guarda_schermo(domanda: str = "") -> str:
        """Guarda cosa c'è in questo momento sullo schermo e lo descrive.

        Usalo quando l'utente chiede "guarda lo schermo", "cosa vedi sullo
        schermo", "guarda cosa sto facendo", "che errore vedi nel terminale" e simili.

        Args:
            domanda: Cosa chiedere nello specifico riguardo allo schermo, ad
                esempio "che errore mostra il terminale?". Se vuoto, descrive genericamente cosa c'è.
        """
        try:
            percorso = cattura(cartella)
        except Exception as errore:
            logger.exception("Screenshot non riuscito")
            return f"Non sono riuscito a catturare lo schermo: {errore}"

        prompt = str(domanda).strip() or DOMANDA_PREDEFINITA

        try:
            pezzi = list(
                motore.generate_response_stream(
                    prompt, history=None, immagini=[str(percorso)]
                )
            )
        except Exception as errore:
            logger.exception("Analisi dello screenshot non riuscita")
            return f"Ho catturato lo schermo ma non sono riuscito ad analizzarlo: {errore}"
        finally:
            Path(percorso).unlink(missing_ok=True)

        descrizione = "".join(pezzi).strip()
        return descrizione or "Non sono riuscito a descrivere lo schermo."

    return [guarda_schermo]