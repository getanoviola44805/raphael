from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv()

APP_NAME = "Raphael"
APP_VERSION = "0.1.0"

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
HISTORY_FILE = DATA_DIR / "history.json"

AI_API_KEY = os.getenv("AI_API_KEY")