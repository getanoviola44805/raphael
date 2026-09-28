from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv()

APP_NAME = "Raphael"
APP_VERSION = "0.1.0"

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
HISTORY_FILE = DATA_DIR / "history.json"

AI_API_KEY = os.getenv("AI_API_KEY")
SYSTEM_PROMPT = (
    "Sei Raphael, un assistente personale AI che gira sul computer dell'utente. "
    "Rispondi sempre in italiano, in modo naturale e cordiale, come farebbe "
    "una persona competente. Dai risposte complete e ben spiegate: se una "
    "domanda richiede dettagli, approfondisci; se è semplice, rispondi in modo "
    "diretto senza allungare inutilmente. Se non conosci qualcosa o non sei "
    "sicuro, dillo chiaramente invece di inventare."
)