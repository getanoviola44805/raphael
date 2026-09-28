import logging

from ai.ollama_provider import OllamaProvider
from ai.router import AIRouter
from conversation.history import ConversationHistory

from . import config
from .command_handler import CommandHandler
from .config import APP_NAME, APP_VERSION


logger = logging.getLogger(__name__)


class RaphaelApp:
    def __init__(self, ai_provider=None):
        self.name = APP_NAME
        self.version = APP_VERSION
        self.command_handler = CommandHandler(self.name, self.version)

        if ai_provider is None:
            ai_provider = OllamaProvider(
                model=config.OLLAMA_MODEL,
                system_prompt=config.SYSTEM_PROMPT,
                context_length=config.OLLAMA_CONTEXT_LENGTH,
            )

        self.ai_router = AIRouter(ai_provider)
        self.history = ConversationHistory()
        self.history.load_from_file(config.HISTORY_FILE)

        logger.info(
            "%s Core avviato - Versione %s",
            self.name,
            self.version,
        )

    def gestisci_comando(self, comando):
        self.history.add_message("user", comando)

        risposta = self.command_handler.handle(comando)

        if risposta == "Comando non riconosciuto.":
            risposta = self.ai_router.generate_response(
                comando,
                self.history.get_recent_messages(config.MAX_HISTORY_MESSAGES),
            )

        self.history.add_message("assistant", risposta)

        return risposta

    def start(self):
        print(f"Benvenuto in {self.name}!")

        while True:
            comando = input("Tu: ").strip()

            if comando.lower() in {"esci", "exit", "quit"}:
                self.history.save_to_file(config.HISTORY_FILE)
                print(f"{self.name}: A presto.")
                break

            risposta = self.gestisci_comando(comando)
            print(f"{self.name}: {risposta}")