import sys

from core.app import RaphaelApp
from core.logging_config import configure_logging


def main():
    configure_logging()

    app = RaphaelApp()
    app.prepara_in_background()

    if "--terminale" in sys.argv:
        app.pianificatore.avvia()
        app.start()
    else:
        from ui.finestra import avvia_finestra

        sys.exit(avvia_finestra(app))


if __name__ == "__main__":
    main()