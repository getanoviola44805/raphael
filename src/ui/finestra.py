import sys
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QImage,
    QKeySequence,
    QPalette,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core import config
from core.percorsi import percorso_risorsa

from .formattazione import converti_latex


MESSAGGI_MOSTRATI_ALL_AVVIO = 20
INTERVALLO_AGGIORNAMENTO_MS = 100
LATO_MASSIMO_IMMAGINE = 1600
FILTRO_IMMAGINI = "Immagini (*.png *.jpg *.jpeg *.webp *.bmp *.gif)"
DOMANDA_PREDEFINITA_IMMAGINE = "Descrivi questa immagine."


def salva_immagine_ridotta(immagine: QImage, cartella: Path, nome_base: str) -> Path:
    """Salva una copia dell'immagine, rimpicciolita se è molto grande.

    Le foto del telefono possono avere migliaia di pixel per lato: ridurle
    rende la risposta del modello molto più veloce senza perdere leggibilità.
    """
    if max(immagine.width(), immagine.height()) > LATO_MASSIMO_IMMAGINE:
        immagine = immagine.scaled(
            LATO_MASSIMO_IMMAGINE,
            LATO_MASSIMO_IMMAGINE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    cartella.mkdir(parents=True, exist_ok=True)
    istante = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    percorso = cartella / f"{nome_base}_{istante}.jpg"
    immagine.save(str(percorso), "JPG", 92)
    return percorso


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
    def __init__(self, raphael, cartella_allegati=None):
        super().__init__()
        self.raphael = raphael
        self.cartella_allegati = Path(
            cartella_allegati or config.DATA_DIR / "allegati"
        )
        self.allegato = None
        self.nome_allegato = ""
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
        self.casella.installEventFilter(self)

        self.bottone = QPushButton("Invia")
        self.bottone.clicked.connect(self.invia)

        self.bottone_allega = QPushButton("📎")
        self.bottone_allega.setFixedWidth(40)
        self.bottone_allega.setToolTip(
            "Allega un'immagine (puoi anche incollarla con Ctrl+V)"
        )
        self.bottone_allega.clicked.connect(self.scegli_immagine)

        self.bottone_ragiona = QPushButton("🧠 Ragiona")
        self.bottone_ragiona.setCheckable(True)
        self.bottone_ragiona.setStyleSheet(
            "QPushButton:checked { background-color: #3d7bd9; color: white; }"
        )
        self.bottone_ragiona.setToolTip(
            "Il modello ragiona passo passo prima di rispondere: "
            "più lento, ma più preciso su matematica, fisica ed esercizi"
        )

        self.etichetta_allegato = QLabel("")
        self.bottone_togli_allegato = QPushButton("✕")
        self.bottone_togli_allegato.setFixedWidth(28)
        self.bottone_togli_allegato.setToolTip("Togli l'immagine allegata")
        self.bottone_togli_allegato.clicked.connect(self.togli_allegato)

        riga_allegato = QHBoxLayout()
        riga_allegato.addWidget(self.etichetta_allegato)
        riga_allegato.addWidget(self.bottone_togli_allegato)
        riga_allegato.addStretch()

        riga_input = QHBoxLayout()
        riga_input.addWidget(self.bottone_allega)
        riga_input.addWidget(self.casella)
        riga_input.addWidget(self.bottone_ragiona)
        riga_input.addWidget(self.bottone)

        layout = QVBoxLayout()
        layout.addWidget(self.chat)
        layout.addWidget(self.stato)
        layout.addLayout(riga_allegato)
        layout.addLayout(riga_input)

        contenitore = QWidget()
        contenitore.setLayout(layout)
        self.setCentralWidget(contenitore)

        self._mostra_allegato()
        self._aggiorna_chat(forza_scorrimento=True)
        self.casella.setFocus()

    def eventFilter(self, oggetto, evento):
        # Ctrl+V nella casella: se negli appunti c'è un'immagine (per esempio
        # uno screenshot fatto con Win+Shift+S) la allega invece di incollare testo.
        if (
            oggetto is self.casella
            and evento.type() == QEvent.Type.KeyPress
            and evento.matches(QKeySequence.StandardKey.Paste)
        ):
            immagine = QApplication.clipboard().image()

            if not immagine.isNull():
                self.allega_immagine(immagine, "incollata")
                return True

        return super().eventFilter(oggetto, evento)

    def scegli_immagine(self):
        percorso, _ = QFileDialog.getOpenFileName(
            self, "Allega un'immagine", "", FILTRO_IMMAGINI
        )

        if not percorso:
            return

        immagine = QImage(percorso)

        if immagine.isNull():
            self.stato.setText("⚠️ Non riesco a leggere questa immagine.")
            return

        self.allega_immagine(immagine, Path(percorso).stem)

    def allega_immagine(self, immagine, nome_base):
        self.allegato = salva_immagine_ridotta(
            immagine, self.cartella_allegati, nome_base
        )
        self.nome_allegato = nome_base
        self._mostra_allegato()

    def togli_allegato(self):
        self.allegato = None
        self._mostra_allegato()

    def _mostra_allegato(self):
        if self.allegato is None:
            self.etichetta_allegato.setText("")
            self.etichetta_allegato.hide()
            self.bottone_togli_allegato.hide()
        else:
            self.etichetta_allegato.setText(f"🖼️ {self.nome_allegato}")
            self.etichetta_allegato.show()
            self.bottone_togli_allegato.show()

    def invia(self):
        testo = self.casella.text().strip()

        if self.in_attesa or (not testo and self.allegato is None):
            return

        if not testo:
            testo = DOMANDA_PREDEFINITA_IMMAGINE

        immagini = [self.allegato] if self.allegato is not None else None
        ragiona = self.bottone_ragiona.isChecked()

        testo_mostrato = testo
        if immagini:
            testo_mostrato = f"{testo}\n\n[Immagine allegata: {self.allegato.name}]"

        self.casella.clear()
        self.togli_allegato()
        self.messaggi.append({"role": "user", "content": testo_mostrato})
        self.risposta_parziale = ""
        self._imposta_attesa(True, ragiona)
        self._prepara_risposta_in_arrivo()
        self.timer_aggiornamento.start()

        lavoro = threading.Thread(
            target=self._chiedi_a_raphael,
            args=(testo, ragiona, immagini),
            daemon=True,
        )
        lavoro.start()

    def _chiedi_a_raphael(self, testo, ragiona=False, immagini=None):
        try:
            pezzi = self.raphael.gestisci_comando_stream(
                testo, ragiona=ragiona, immagini=immagini
            )
            for pezzo in pezzi:
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

    def _imposta_attesa(self, attesa, ragiona=False):
        self.in_attesa = attesa

        for controllo in (
            self.casella,
            self.bottone,
            self.bottone_allega,
            self.bottone_ragiona,
        ):
            controllo.setEnabled(not attesa)

        if not attesa:
            self.stato.setText("")
        elif ragiona:
            self.stato.setText(
                f"{self.raphael.name} sta ragionando... "
                "(con il ragionamento attivo può volerci qualche minuto)"
            )
        else:
            self.stato.setText(f"{self.raphael.name} sta pensando...")

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