"""Crea l'eseguibile di Raphael con PyInstaller.

Uso, dalla cartella principale del progetto con l'ambiente virtuale attivo:

    python scripts/crea_exe.py

Il risultato è la cartella dist/Raphael, con dentro Raphael.exe.
"""

import sys
from pathlib import Path

import PyInstaller.__main__


RADICE = Path(__file__).resolve().parents[1]
SEPARATORE = ";" if sys.platform == "win32" else ":"


def main():
    PyInstaller.__main__.run(
        [
            str(RADICE / "src" / "main.py"),
            "--name", "Raphael",
            "--windowed",
            "--noconfirm",
            "--clean",
            "--icon", str(RADICE / "assets" / "raphael.ico"),
            "--paths", str(RADICE / "src"),
            "--add-data", f"{RADICE / 'assets'}{SEPARATORE}assets",
            "--collect-all", "ddgs",
            "--collect-data", "pylatexenc",
            "--distpath", str(RADICE / "dist"),
            "--workpath", str(RADICE / "build"),
            "--specpath", str(RADICE / "build"),
        ]
    )


if __name__ == "__main__":
    main()