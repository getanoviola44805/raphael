import sys
import threading

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPalette,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core.percorsi import percorso_risorsa

from .formattazione import converti_latex


MESSAGGI_MOSTRATI_ALL_AVVIO = 20
INTERVALLO_AGGIORNAMENTO_MS = 100


def componi_markdown_chat(
    messaggi, nome_assistente, in_attesa=False, risposta_parziale=""
):
    blocchi = []

    for messaggio in messaggi:
        if messaggio["role"] == "user":
            blocchi.append(f"**Tu:** {messaggio['content']}")
        else:
            testo = converti_latex(messaggio["content"])
            blocchi.append(f"**{nome_assistente}:**\n\n{testo}")

    if risposta_parziale:
        testo = converti_latex(risposta_parziale)
        blocchi.append(f"**{nome_assistente}:**\n\n{testo}")
    elif in_attesa:
        blocchi.append(f"*{nome_assistente} sta scrivendo...*")

    return "\n\n---\n\n".join(blocchi)


class _Segnali(QObject):
    pezzo_ricevuto = Signal(str)
    risposta_completata = Signal()


class FinestraRaphael(QMainWindow):
    def __init__(self, raphael):
        super().__init__()
        self.raphael = raphael
        self.messaggi = list(
            raphael.history.get_recent_messages(MESSAGGI_MOSTRATI_ALL_AVVIO)
        )
        self.in_attesa = False
        self.risposta_parziale = ""
        self._da_aggiornare = False
        self._inizio_risposta = None

        self.segnali = _Segnali()
        self.segnali.pezzo_ricevuto.connect(self._ricevi_pezzo)
        self.segnali.risposta_completata.connect(self._completa_risposta)

        self.timer_aggiornamento = QTimer(self)
        self.timer_aggiornamento.setInterval(INTERVALLO_AGGIORNAMENTO_MS)
        self.timer_aggiornamento.timeout.connect(self._aggiorna_se_serve)

        self.setWindowTitle(f"{raphael.name} {raphael.version}")
        self.resize(900, 700)

        self.chat = QTextBrowser()
        self.chat.setOpenExternalLinks(True)
        self.chat.document().setDocumentMargin(12)

        self.stato = QLabel("")

        self.casella = QLineEdit()
        self.casella.setPlaceholderText(
            "Scrivi un messaggio... (usa /cerca per cercare sul web)"
        )
        self.casella.returnPressed.connect(self.invia)

        self.bottone = QPushButton("Invia")
        self.bottone.clicked.connect(self.invia)

        riga_input = QHBoxLayout()
        riga_input.addWidget(self.casella)
        riga_input.addWidget(self.bottone)

        layout = QVBoxLayout()
        layout.addWidget(self.chat)
        layout.addWidget(self.stato)
        layout.addLayout(riga_input)

        contenitore = QWidget()
        contenitore.setLayout(layout)
        self.setCentralWidget(contenitore)

        self._aggiorna_chat(forza_scorrimento=True)
        self.casella.setFocus()

    def invia(self):
        testo = self.casella.text().strip()

        if not testo or self.in_attesa:
            return

        self.casella.clear()
        self.messaggi.append({"role": "user", "content": testo})
        self.risposta_parziale = ""
        self._imposta_attesa(True)
        self._prepara_risposta_in_arrivo()
        self.timer_aggiornamento.start()

        lavoro = threading.Thread(
            target=self._chiedi_a_raphael,
            args=(testo,),
            daemon=True,
        )
        lavoro.start()

    def _chiedi_a_raphael(self, testo):
        try:
            for pezzo in self.raphael.gestisci_comando_stream(testo):
                self.segnali.pezzo_ricevuto.emit(pezzo)
        except Exception as errore:
            self.segnali.pezzo_ricevuto.emit(
                f"\n\n⚠️ Si è verificato un errore: {errore}"
            )

        self.segnali.risposta_completata.emit()

    def _ricevi_pezzo(self, pezzo):
        self.risposta_parziale += pezzo
        self._da_aggiornare = True

    def _aggiorna_se_serve(self):
        if self._da_aggiornare:
            self._da_aggiornare = False
            self._aggiorna_risposta_in_arrivo()

    def _prepara_risposta_in_arrivo(self):
        # Disegna una sola volta i messaggi precedenti e l'intestazione della
        # risposta: durante lo streaming verrà aggiornata solo la parte finale.
        precedenti = componi_markdown_chat(self.messaggi, self.raphael.name)
        intestazione = f"**{self.raphael.name}:**"

        if precedenti:
            testo = f"{precedenti}\n\n---\n\n{intestazione}"
        else:
            testo = intestazione

        self.chat.setMarkdown(testo)

        cursore = QTextCursor(self.chat.document())
        cursore.movePosition(QTextCursor.MoveOperation.End)
        cursore.insertBlock(QTextBlockFormat(), QTextCharFormat())
        self._inizio_risposta = cursore.position()

        self._sostituisci_risposta(f"*{self.raphael.name} sta scrivendo...*")

        barra = self.chat.verticalScrollBar()
        barra.setValue(barra.maximum())

    def _aggiorna_risposta_in_arrivo(self):
        if self._inizio_risposta is None:
            return

        barra = self.chat.verticalScrollBar()
        posizione = barra.value()
        era_in_fondo = posizione >= barra.maximum() - 20

        self.chat.setUpdatesEnabled(False)
        self._sostituisci_risposta(converti_latex(self.risposta_parziale))

        if era_in_fondo:
            barra.setValue(barra.maximum())
        else:
            barra.setValue(posizione)

        self.chat.setUpdatesEnabled(True)

    def _sostituisci_risposta(self, markdown):
        cursore = QTextCursor(self.chat.document())
        cursore.setPosition(self._inizio_risposta)
        cursore.movePosition(
            QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor
        )
        cursore.removeSelectedText()

        # Toglie la formattazione rimasta dall'aggiornamento precedente
        # (elenchi, titoli...), così il nuovo testo riparte da zero.
        elenco = cursore.currentList()
        if elenco is not None:
            elenco.remove(cursore.block())
        cursore.setBlockFormat(QTextBlockFormat())
        cursore.setBlockCharFormat(QTextCharFormat())
        cursore.setCharFormat(QTextCharFormat())

        cursore.insertMarkdown(markdown)

    def _completa_risposta(self):
        self.timer_aggiornamento.stop()
        self.messaggi.append(
            {"role": "assistant", "content": self.risposta_parziale}
        )
        self.risposta_parziale = ""
        self._da_aggiornare = False
        self._inizio_risposta = None
        self._imposta_attesa(False)
        self._aggiorna_chat()
        self.raphael.salva_cronologia()

    def _imposta_attesa(self, attesa):
        self.in_attesa = attesa
        self.casella.setEnabled(not attesa)
        self.bottone.setEnabled(not attesa)
        self.stato.setText(f"{self.raphael.name} sta pensando..." if attesa else "")

        if not attesa:
            self.casella.setFocus()

    def _aggiorna_chat(self, forza_scorrimento=False):
        barra = self.chat.verticalScrollBar()
        posizione = barra.value()
        era_in_fondo = posizione >= barra.maximum() - 20

        # Ridisegna tutto in un colpo solo: senza questa accortezza la finestra
        # mostrerebbe per un istante la chat tornata in cima, causando uno scatto.
        self.chat.setUpdatesEnabled(False)

        self.chat.setMarkdown(
            componi_markdown_chat(
                self.messaggi,
                self.raphael.name,
                self.in_attesa,
                self.risposta_parziale,
            )
        )

        if forza_scorrimento or era_in_fondo:
            barra.setValue(barra.maximum())
        else:
            barra.setValue(posizione)

        self.chat.setUpdatesEnabled(True)

    def closeEvent(self, evento):
        self.raphael.salva_cronologia()
        super().closeEvent(evento)


def _tema_scuro():
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#1e1f22"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e6e6e6"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#26282c"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#2e3035"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e6e6e6"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#2e3035"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e6e6e6"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#3d7bd9"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#6cb4ff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#8a8f98"))
    return palette


def _imposta_identita_windows():
    # Senza questo, avviando Raphael con "python" la barra delle applicazioni
    # mostrerebbe l'icona di Python invece di quella di Raphael.
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Raphael.Assistente"
        )


def avvia_finestra(raphael):
    _imposta_identita_windows()

    applicazione = QApplication.instance() or QApplication(sys.argv)
    applicazione.setWindowIcon(QIcon(str(percorso_risorsa("raphael.ico"))))
    applicazione.setStyle("Fusion")
    applicazione.setPalette(_tema_scuro())
    applicazione.setFont(QFont("Segoe UI", 11))

    finestra = FinestraRaphael(raphael)
    finestra.show()

    return applicazione.exec()