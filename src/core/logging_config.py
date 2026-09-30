import logging
import sys

from .percorsi import cartella_dati


LOG_DIR = cartella_dati() / "logs"
LOG_FILE = LOG_DIR / "raphael.log"


def configure_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    handlers = [logging.FileHandler(LOG_FILE, encoding="utf-8")]

    # Nell'eseguibile senza finestra del terminale non c'è dove stampare i log:
    # in quel caso vengono scritti solo nel file.
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=handlers,
    )

    logging.getLogger("httpx").setLevel(logging.WARNING)