from .config import APP_NAME, APP_VERSION
from .command_handler import CommandHandler
import logging
logger = logging.getLogger(__name__)


class RaphaelApp:
    def __init__(self):
        self.name = APP_NAME
        self.version = APP_VERSION
        self.command_handler = CommandHandler(self.name, self.version)

        logger.info("%s Core avviato - Versione %s", self.name, self.version)

    def gestisci_comando(self, comando):
        return self.command_handler.handle(comando)
        

    
    def start(self):
        print(f"Benvenuto in {self.name}!")

        while True:
            comando = input("Tu: ").strip()

            if comando.lower() in {"esci", "exit", "quit"}:
                print(f"{self.name}: A presto.")
                break

            risposta = self.gestisci_comando(comando)
            print(f"{self.name}: {risposta}")