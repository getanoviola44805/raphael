import logging
import shutil

from rich.console import Console
from rich.markdown import Markdown

from ai.ollama_provider import OllamaProvider
from ai.router import AIRouter
from conversation.history import ConversationHistory
from tools.web_search import (
    cerca_sul_web,
    formatta_fonti,
    prepara_domanda_con_risultati,
)
from ui.formattazione import converti_latex

from . import config
from .command_handler import CommandHandler
from .config import APP_NAME, APP_VERSION


logger = logging.getLogger(__name__)

COMANDO_RICERCA = "/cerca"


def e_una_ricerca(comando):
    comando = comando.lower()
    return comando == COMANDO_RICERCA or comando.startswith(COMANDO_RICERCA + " ")


class RaphaelApp:
    def __init__(self, ai_provider=None, ricerca_web=None):
        self.name = APP_NAME
        self.version = APP_VERSION
        self.command_handler = CommandHandler(self.name, self.version)

        larghezza = min(100, shutil.get_terminal_size().columns - 1)
        self.console = Console(width=larghezza)

        if ai_provider is None:
            ai_provider = OllamaProvider(
                model=config.OLLAMA_MODEL,
                system_prompt=config.SYSTEM_PROMPT,
                context_length=config.OLLAMA_CONTEXT_LENGTH,
            )

        if ricerca_web is None:
            ricerca_web = cerca_sul_web

        self.ai_router = AIRouter(ai_provider)
        self.ricerca_web = ricerca_web
        self.history = ConversationHistory()
        self.history.load_from_file(config.HISTORY_FILE)

        logger.info(
            "%s Core avviato - Versione %s",
            self.name,
            self.version,
        )

    def gestisci_comando(self, comando):
        self.history.add_message("user", comando)

        if e_una_ricerca(comando):
            domanda = comando[len(COMANDO_RICERCA):].strip()
            risposta = self.rispondi_con_ricerca(domanda)
        else:
            risposta = self.command_handler.handle(comando)

            if risposta == "Comando non riconosciuto.":
                risposta = self.ai_router.generate_response(
                    comando,
                    self.history.get_recent_messages(config.MAX_HISTORY_MESSAGES),
                )

        self.history.add_message("assistant", risposta)

        return risposta

    def rispondi_con_ricerca(self, domanda):
        if not domanda:
            return (
                "Scrivi cosa vuoi cercare dopo /cerca, ad esempio: "
                "/cerca meteo Catania domani"
            )

        risultati = self.ricerca_web(domanda, config.WEB_SEARCH_MAX_RESULTS)

        if not risultati:
            return (
                "⚠️ Non sono riuscito a cercare sul web in questo momento. "
                "Controlla la connessione a internet e riprova."
            )

        domanda_arricchita = prepara_domanda_con_risultati(domanda, risultati)

        messaggi_precedenti = self.history.get_recent_messages(
            config.MAX_HISTORY_MESSAGES
        )[:-1]
        messaggi = messaggi_precedenti + [
            {"role": "user", "content": domanda_arricchita}
        ]

        risposta = self.ai_router.generate_response(domanda_arricchita, messaggi)

        return f"{risposta}\n\n{formatta_fonti(risultati)}"

    def salva_cronologia(self):
        self.history.save_to_file(config.HISTORY_FILE)

    def mostra_risposta(self, risposta):
        self.console.print(f"[bold cyan]{self.name}:[/bold cyan]")
        self.console.print(Markdown(converti_latex(risposta)))
        self.console.print()

    def start(self):
        self.console.print(f"[bold]Benvenuto in {self.name}![/bold]")

        while True:
            comando = input("Tu: ").strip()

            if not comando:
                continue

            if comando.lower() in {"esci", "exit", "quit"}:
                self.salva_cronologia()
                self.console.print(f"[bold cyan]{self.name}:[/bold cyan] A presto.")
                break

            if e_una_ricerca(comando):
                self.console.print("[dim]Sto cercando sul web...[/dim]")

            risposta = self.gestisci_comando(comando)
            self.mostra_risposta(risposta)