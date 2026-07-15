from core.app import RaphaelApp
from core.logging_config import configure_logging


def main():
    configure_logging()

    app = RaphaelApp()
    app.start()


if __name__ == "__main__":
    main()