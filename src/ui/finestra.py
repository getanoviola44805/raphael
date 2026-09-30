import sys
import threading

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QFont, QPalette
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

from .formattazione import converti_latex


MESSAGGI_MOSTRATI_ALL_AVVIO = 20


def componi_markdown_chat(messaggi, nome_assistente, in_attesa=False):
    blocchi = []

    for messaggio in messaggi:
        if messaggio["role"] == "user":
            blocchi.append(f"**Tu:** {messaggio['content']}")
        else:
            testo = converti_latex(messaggio["content"])
            blocchi.append(f"**{nome_assistente}:**\n\n{testo}")

    if in_attesa:
        blocchi.append(f"*{nome_assistente} sta scrivendo...*")

    return "\n\n---\n\n".join(blocchi)


class _Segnali(QObject):
    risposta_pronta = Signal(str)


class FinestraRaphael(QMainWindow):
    def __init__(self, raphael):
        super().__init__()
        self.raphael = raphael
        self.messaggi = list(
            raphael.history.get_recent_messages(MESSAGGI_MOSTRATI_ALL_AVVIO)
        )
        self.in_attesa = False

        self.segnali = _Segnali()
        self.segnali.risposta_pronta.connect(self._ricevi_risposta)

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

        self._aggiorna_chat()
        self.casella.setFocus()

    def invia(self):
        testo = self.casella.text().strip()

        if not testo or self.in_attesa:
            return

        self.casella.clear()
        self.messaggi.append({"role": "user", "content": testo})
        self._imposta_attesa(True)
        self._aggiorna_chat()

        lavoro = threading.Thread(
            target=self._chiedi_a_raphael,
            args=(testo,),
            daemon=True,
        )
        lavoro.start()

    def _chiedi_a_raphael(self, testo):
        try:
            risposta = self.raphael.gestisci_comando(testo)
        except Exception as errore:
            risposta = f"⚠️ Si è verificato un errore: {errore}"

        self.segnali.risposta_pronta.emit(risposta)

    def _ricevi_risposta(self, risposta):
        self.messaggi.append({"role": "assistant", "content": risposta})
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

    def _aggiorna_chat(self):
        self.chat.setMarkdown(
            componi_markdown_chat(self.messaggi, self.raphael.name, self.in_attesa)
        )
        barra = self.chat.verticalScrollBar()
        barra.setValue(barra.maximum())

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


def avvia_finestra(raphael):
    applicazione = QApplication.instance() or QApplication(sys.argv)
    applicazione.setStyle("Fusion")
    applicazione.setPalette(_tema_scuro())
    applicazione.setFont(QFont("Segoe UI", 11))

    finestra = FinestraRaphael(raphael)
    finestra.show()

    return applicazione.exec()