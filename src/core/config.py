from pathlib import Path

APP_NAME = "Raphael"
APP_VERSION = "0.1.0"

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
HISTORY_FILE = DATA_DIR / "history.json"