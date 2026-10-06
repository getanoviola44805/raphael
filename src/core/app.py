import logging
import shutil
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

from ai.ollama_provider import OllamaProvider
from ai.router import AIRouter
from conversation.history import ConversationHistory
from memory.memoria import MemoriaLungoTermine
from tools.lettura_file import STRUMENTI_LETTURA
from tools.pc_control import STRUMENTI_PC
from tools.schermo import crea_strumenti_schermo
from tools.strumenti_azioni import STRUMENTI_GIA_REGISTRATI, crea_strumenti_azioni
from tools.strumenti_memoria import crea_strumenti_memoria
from tools.strumenti_tempo import crea_strumenti_tempo
from tools.web_search import (
    cerca_sul_web,
    formatta_fonti,
    prepara_domanda_con_risultati,
)
from tools.web_search import ricerca_web as strumento_ricerca_web
from ui.formattazione import converti_latex

from . import config
from .azioni import ESITO_STRUMENTO, GestoreAzioni, RegistroAzioni, interpreta_giorno
from .command_handler import CommandHandler
from .config import APP_NAME, APP_VERSION
from .promemoria import AgendaPromemoria, Pianificatore


logger = logging.getLogger(__name__)

COMANDO_RICERCA = "/cerca"
COMANDO_MEMORIA = "/memoria"
COMANDO_RICORDA = "/ricorda"
COMANDO_DIMENTICA = "/dimentica"
COMANDO_REGISTRO = "/registro"
COMANDO_ANNULLA = "/annulla"
COMANDO_SOLA_LETTURA = "/solalettura"

# Strumenti di sola consultazione che non serve annotare nel registro.
STRUMENTI_DA_NON_REGISTRARE = STRUMENTI_GIA_REGISTRATI | {"data_e_ora"}


def _e_il_comando(comando, nome):
    comando = comando.lower()
    return comando == nome or comando.startswith(nome + " ")


def e_una_ricerca(comando):
    return _e_il_comando(comando, COMANDO_RICERCA)


class RaphaelApp:
    def __init__(self, ai_provider=None, ricerca_web=None, memoria=None, azioni=None):
        self.name = APP_NAME
        self.version = APP_VERSION
        self.command_handler = CommandHandler(self.name, self.version)

        if memoria is None:
            memoria = MemoriaLungoTermine(config.MEMORY_FILE)
        self.memoria = memoria

        if azioni is None:
            azioni = GestoreAzioni(RegistroAzioni(config.ACTIONS_LOG_FILE))
        self.azioni = azioni

        self.agenda = AgendaPromemoria(config.REMINDERS_FILE)
        # La finestra grafica sovrascrive questo callback per mostrare i popup.
        # Resta None in modalità terminale. Viene letto a OGNI promemoria,
        # quindi funziona anche se il Pianificatore ha catturato il riferimento
        # a _notifica_promemoria nel suo costruttore o nel suo thread.
        self.notifica_esterna = None
        self.pianificatore = Pianificatore(
            self.agenda, notifica=self._notifica_promemoria
        )

        larghezza = min(100, shutil.get_terminal_size().columns - 1)
        self.console = Console(width=larghezza)

        if ai_provider is None:
            ai_provider = OllamaProvider(
                model=config.OLLAMA_MODEL,
                system_prompt=self._prompt_di_sistema,
                context_length=config.OLLAMA_CONTEXT_LENGTH,
                strumenti=(
                    STRUMENTI_PC
                    + STRUMENTI_LETTURA
                    + [strumento_ricerca_web]
                    + crea_strumenti_memoria(self.memoria)
                    + crea_strumenti_azioni(self.azioni)
                    + crea_strumenti_schermo(config.OLLAMA_MODEL, config.OLLAMA_CONTEXT_LENGTH)
                    + crea_strumenti_tempo(self.agenda)
                ),
                osservatore_strumenti=self._registra_strumento,
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

    def _prompt_di_sistema(self):
        ricordi = self.memoria.testo_per_prompt()

        if not ricordi:
            return config.SYSTEM_PROMPT

        return f"{config.SYSTEM_PROMPT}\n\n{ricordi}"

    def _registra_strumento(self, nome, argomenti, esito):
        """Annota nel registro gli strumenti che non passano dal gestore."""
        if nome in STRUMENTI_DA_NON_REGISTRARE:
            return

        valori = ", ".join(str(valore) for valore in (argomenti or {}).values())
        self.azioni.registro.registra(f"{nome}({valori})", ESITO_STRUMENTO, esito)

    def _notifica_promemoria(self, voce):
        """Avviso dei promemoria.

        Se la finestra grafica è aperta, delega a lei (che mostra il popup
        tramite segnale nel thread della UI). In modalità terminale stampa
        sulla console come prima.
        """
        if self.notifica_esterna is not None:
            self.notifica_esterna(voce)
            return
        self.console.print(f"\n[bold yellow]⏰ {voce['testo']}[/bold yellow]\n")

    def gestisci_comando(self, comando):
        return "".join(self.gestisci_comando_stream(comando))

    def gestisci_comando_stream(self, comando, ragiona=False, immagini=None):
        immagini = list(immagini or [])
        testo_utente = comando

        if immagini:
            nomi = ", ".join(Path(immagine).name for immagine in immagini)
            testo_utente = f"{comando}\n\n[Immagine allegata: {nomi}]"

        self.history.add_message("user", testo_utente)
        pezzi_risposta = []

        for pezzo in self._genera_risposta(comando, ragiona, immagini):
            pezzi_risposta.append(pezzo)
            yield pezzo

        self.history.add_message("assistant", "".join(pezzi_risposta))

    def _genera_risposta(self, comando, ragiona=False, immagini=None):
        if e_una_ricerca(comando):
            domanda = comando[len(COMANDO_RICERCA):].strip()
            yield from self._rispondi_con_ricerca(domanda)
            return

        for gestore_comandi in (
            self._gestisci_comando_memoria,
            self._gestisci_comando_azioni,
        ):
            risposta_diretta = gestore_comandi(comando)
            if risposta_diretta is not None:
                yield risposta_diretta
                return

        risposta = self.command_handler.handle(comando)

        if risposta != "Comando non riconosciuto." and not immagini:
            yield risposta
            return

        # Le opzioni vengono passate solo se servono, così i provider che non
        # le conoscono continuano a funzionare come prima.
        opzioni = {}
        if ragiona:
            opzioni["ragiona"] = True
        if immagini:
            opzioni["immagini"] = immagini

        yield from self.ai_router.generate_response_stream(
            comando,
            self.history.get_recent_messages(config.MAX_HISTORY_MESSAGES),
            **opzioni,
        )

    def _gestisci_comando_memoria(self, comando):
        """Risponde ai comandi della memoria, oppure restituisce None."""
        if _e_il_comando(comando, COMANDO_MEMORIA):
            return self.memoria.formatta_elenco()

        if _e_il_comando(comando, COMANDO_RICORDA):
            testo = comando[len(COMANDO_RICORDA):].strip()
            if not testo:
                return (
                    "Scrivi cosa devo ricordare dopo /ricorda, ad esempio: "
                    "/ricorda preferisco risposte brevi"
                )
            return self.memoria.aggiungi(testo)

        if _e_il_comando(comando, COMANDO_DIMENTICA):
            riferimento = comando[len(COMANDO_DIMENTICA):].strip()
            if not riferimento:
                return (
                    "Scrivi cosa devo dimenticare dopo /dimentica: il numero che "
                    "vedi con /memoria, una parte del ricordo, oppure 'tutto'."
                )
            if riferimento.lower() == "tutto":
                return self.memoria.svuota()
            return self.memoria.dimentica(riferimento)

        return None

    def _gestisci_comando_azioni(self, comando):
        """Risponde ai comandi del registro e della sicurezza, oppure restituisce None."""
        if _e_il_comando(comando, COMANDO_REGISTRO):
            testo = comando[len(COMANDO_REGISTRO):].strip()
            giorno = interpreta_giorno(testo)
            if giorno is None:
                return "Non ho capito il giorno. Prova con /registro, /registro ieri o /registro 2026-10-01."
            return self.azioni.registro.riepilogo(giorno)

        if _e_il_comando(comando, COMANDO_ANNULLA):
            return self.azioni.annulla_ultima()

        if _e_il_comando(comando, COMANDO_SOLA_LETTURA):
            scelta = comando[len(COMANDO_SOLA_LETTURA):].strip().lower()
            if scelta in {"on", "si", "sì", "attiva"}:
                return self.azioni.imposta_sola_lettura(True)
            if scelta in {"off", "no", "disattiva"}:
                return self.azioni.imposta_sola_lettura(False)
            stato = "attiva 🔒" if self.azioni.sola_lettura else "disattivata 🔓"
            return (
                f"La modalità sola lettura è {stato}. "
                "Usa /solalettura on oppure /solalettura off per cambiarla."
            )

        return None

    def _rispondi_con_ricerca(self, domanda):
        if not domanda:
            yield (
                "Scrivi cosa vuoi cercare dopo /cerca, ad esempio: "
                "/cerca meteo Catania domani"
            )
            return

        risultati = self.ricerca_web(domanda, config.WEB_SEARCH_MAX_RESULTS)

        if not risultati:
            yield (
                "⚠️ Non sono riuscito a cercare sul web in questo momento. "
                "Controlla la connessione a internet e riprova."
            )
            return

        domanda_arricchita = prepara_domanda_con_risultati(domanda, risultati)

        messaggi_precedenti = self.history.get_recent_messages(
            config.MAX_HISTORY_MESSAGES
        )[:-1]
        messaggi = messaggi_precedenti + [
            {"role": "user", "content": domanda_arricchita}
        ]

        yield from self.ai_router.generate_response_stream(
            domanda_arricchita, messaggi
        )
        yield f"\n\n{formatta_fonti(risultati)}"

    def salva_cronologia(self):
        self.history.save_to_file(config.HISTORY_FILE)

    def mostra_risposta(self, risposta):
        self.console.print(f"[bold cyan]{self.name}:[/bold cyan]")
        self.console.print(Markdown(converti_latex(risposta)))
        self.console.print()

    def _conferma_da_terminale(self, azione):
        self.console.print(f"[bold yellow]⚠️ {azione.descrizione}[/bold yellow]")
        if azione.dettagli:
            self.console.print(azione.dettagli)
        risposta = input("Confermi? (s/n): ").strip().lower()
        return risposta in {"s", "si", "sì", "y", "yes"}

    def start(self):
        self.console.print(f"[bold]Benvenuto in {self.name}![/bold]")
        self.azioni.chiedi_conferma = self._conferma_da_terminale

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