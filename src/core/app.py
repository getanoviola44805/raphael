import logging

from ai.mock_provider import MockAIProvider
from ai.router import AIRouter

from .command_handler import CommandHandler
from .config import APP_NAME, APP_VERSION


logger = logging.getLogger(__name__)


class RaphaelApp:
    def __init__(self):
        self.name = APP_NAME
        self.version = APP_VERSION
        self.command_handler = CommandHandler(self.name, self.version)
        self.ai_router = AIRouter(MockAIProvider())

        logger.info(
            "%s Core avviato - Versione %s",
            self.name,
            self.version,
        )

    def gestisci_comando(self, comando):
        risposta = self.command_handler.handle(comando)

        if risposta == "Comando non riconosciuto.":
            return self.ai_router.generate_response(comando)

        return risposta

    def start(self):
        print(f"Benvenuto in {self.name}!")

        while True:
            comando = input("Tu: ").strip()

            if comando.lower() in {"esci", "exit", "quit"}:
                print(f"{self.name}: A presto.")
                break

            risposta = self.gestisci_comando(comando)
            print(f"{self.name}: {risposta}")