import sys
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from core import config
from core.azioni import RISCHIO_ALTO
from core.percorsi import percorso_risorsa

from . import stile
from .componenti import (
    CasellaTesto,
    MessaggioRaphael,
    MessaggioUtente,
    RigaAttesa,
    Sfera,
    bottone_icona,
    carattere_interfaccia,
)


MESSAGGI_MOSTRATI_ALL_AVVIO = 20
INTERVALLO_AGGIORNAMENTO_MS = 100
LATO_MASSIMO_IMMAGINE = 1600
LATO_MINIATURA = 40
FILTRO_IMMAGINI = "Immagini (*.png *.jpg *.jpeg *.webp *.bmp *.gif)"
DOMANDA_PREDEFINITA_IMMAGINE = "Descrivi questa immagine."
TEMPO_MASSIMO_CONFERMA_S = 300
DISTANZA_DAL_FONDO = 40
DURATA_NOTIFICA_MS = 8000


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


class RichiestaConferma:
    """Una domanda di conferma che passa dal thread del modello alla finestra."""

    def __init__(self, azione):
        self.azione = azione
        self.evento = threading.Event()
        self.confermata = False

    def rispondi(self, confermata):
        if self.evento.is_set():
            return
        self.confermata = bool(confermata)
        self.evento.set()


class _Segnali(QObject):
    pezzo_ricevuto = Signal(str)
    risposta_completata = Signal()
    conferma_richiesta = Signal(object)
    conferma_scaduta = Signal(object)
    promemoria_arrivato = Signal(object)


def _centrato(widget):
    """Mette un widget al centro, con una larghezza massima comoda da leggere."""
    widget.setMaximumWidth(stile.LARGHEZZA_COLONNA)
    contenitore = QWidget()
    layout = QHBoxLayout(contenitore)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addStretch(1)
    layout.addWidget(widget, 100)
    layout.addStretch(1)
    return contenitore


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
        self._risposta_in_arrivo = None
        self._segui_il_fondo = True
        self.richiesta_conferma = None

        self.segnali = _Segnali()
        self.segnali.pezzo_ricevuto.connect(self._ricevi_pezzo)
        self.segnali.risposta_completata.connect(self._completa_risposta)
        self.segnali.conferma_richiesta.connect(self._mostra_conferma)
        self.segnali.conferma_scaduta.connect(self._conferma_scaduta)
        self.segnali.promemoria_arrivato.connect(self._mostra_notifica_promemoria)

        self.timer_aggiornamento = QTimer(self)
        self.timer_aggiornamento.setInterval(INTERVALLO_AGGIORNAMENTO_MS)
        self.timer_aggiornamento.timeout.connect(self._aggiorna_se_serve)

        self.setWindowTitle(raphael.name)
        self.resize(980, 760)
        self.setPalette(stile.tavolozza_scura())
        self.setStyleSheet(stile.FOGLIO_DI_STILE)

        self.tray_icon = QSystemTrayIcon(QIcon(str(percorso_risorsa("raphael.ico"))), self)
        self.tray_icon.setToolTip(raphael.name)
        self.tray_icon.show()

        sfondo = QWidget()
        sfondo.setObjectName("sfondo")
        layout = QVBoxLayout(sfondo)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._crea_area_chat(), 1)
        layout.addWidget(self._crea_zona_scrittura())
        self.setCentralWidget(sfondo)

        for messaggio in self.messaggi:
            self._aggiungi_messaggio(messaggio["role"], messaggio["content"])
        self._aggiorna_benvenuto()

        self._mostra_allegato()
        self.casella.setFocus()

        # Da qui in poi è la finestra a chiedere conferma delle azioni a rischio.
        if hasattr(raphael, "azioni"):
            raphael.azioni.chiedi_conferma = self.chiedi_conferma

        # E a mostrare il popup quando scatta un promemoria.
        # Il core legge notifica_esterna a ogni promemoria, quindi non importa
        # come il Pianificatore ha salvato il callback nel suo costruttore.
        if hasattr(raphael, "notifica_esterna"):
            raphael.notifica_esterna = self._ricevi_promemoria

    # ------------------------------------------------------- costruzione

    def _crea_area_chat(self):
        self.colonna = QWidget()
        self.layout_colonna = QVBoxLayout(self.colonna)
        self.layout_colonna.setContentsMargins(24, 28, 24, 12)
        self.layout_colonna.setSpacing(26)

        self.benvenuto = self._crea_benvenuto()
        self.attesa = RigaAttesa()
        self.stato = self.attesa.etichetta

        self.layout_colonna.addWidget(self.benvenuto)
        self.layout_colonna.addWidget(self.attesa)
        self.layout_colonna.addStretch(1)

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setFrameShape(QFrame.Shape.NoFrame)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.area.setWidget(_centrato(self.colonna))

        barra = self.area.verticalScrollBar()
        barra.valueChanged.connect(self._ricorda_se_in_fondo)
        barra.rangeChanged.connect(self._resta_in_fondo)
        return self.area

    def _crea_benvenuto(self):
        benvenuto = QWidget()
        layout = QVBoxLayout(benvenuto)
        layout.setContentsMargins(0, 120, 0, 0)
        layout.setSpacing(14)

        sfera = Sfera(56)
        titolo = QLabel("Ciao! Come posso aiutarti?")
        titolo.setObjectName("benvenuto")
        sottotitolo = QLabel(
            "Chiedimi qualsiasi cosa, fammi leggere un file, aprire un programma "
            "o cercare sul web."
        )
        sottotitolo.setObjectName("sottotitolo")
        sottotitolo.setWordWrap(True)
        sottotitolo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(sfera, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(titolo, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(sottotitolo)
        return benvenuto

    def _crea_zona_scrittura(self):
        colonna = QWidget()
        layout = QVBoxLayout(colonna)
        layout.setContentsMargins(24, 6, 24, 14)
        layout.setSpacing(10)

        self._crea_barra_conferma()
        layout.addWidget(self.barra_conferma)
        layout.addWidget(self._crea_casella_scrittura())

        nota = QLabel("Raphael può sbagliare: controlla le informazioni importanti.")
        nota.setObjectName("sottotitolo")
        nota.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nota.setStyleSheet(f"color: {stile.TESTO_DEBOLE}; font-size: 9pt;")
        layout.addWidget(nota)

        return _centrato(colonna)

    def _crea_casella_scrittura(self):
        self.casella_scrittura = QFrame()
        self.casella_scrittura.setObjectName("casellaScrittura")

        # Il chip dell'immagine allegata, con miniatura e ✕.
        self.chip_allegato = QFrame()
        self.chip_allegato.setObjectName("chipAllegato")
        self.miniatura = QLabel()
        self.miniatura.setFixedSize(LATO_MINIATURA, LATO_MINIATURA)
        self.etichetta_allegato = QLabel("")
        self.bottone_togli_allegato = QPushButton("✕")
        self.bottone_togli_allegato.setObjectName("bottoneTogli")
        self.bottone_togli_allegato.setFixedSize(22, 22)
        self.bottone_togli_allegato.setToolTip("Togli l'immagine allegata")
        self.bottone_togli_allegato.clicked.connect(self.togli_allegato)
        riga_chip = QHBoxLayout(self.chip_allegato)
        riga_chip.setContentsMargins(6, 6, 6, 6)
        riga_chip.setSpacing(8)
        riga_chip.addWidget(self.miniatura)
        riga_chip.addWidget(self.etichetta_allegato)
        riga_chip.addWidget(self.bottone_togli_allegato)

        riga_allegato = QHBoxLayout()
        riga_allegato.setContentsMargins(0, 0, 0, 0)
        riga_allegato.addWidget(self.chip_allegato)
        riga_allegato.addStretch(1)

        self.casella = CasellaTesto()
        self.casella.setPlaceholderText(
            "Scrivi a Raphael...   (/cerca per il web, /memoria per i ricordi, "
            "/registro per le azioni)"
        )
        self.casella.invio_premuto.connect(self.invia)
        self.casella.installEventFilter(self)

        self.bottone_allega = bottone_icona(
            "📎", "Allega un'immagine (puoi anche incollarla con Ctrl+V)"
        )
        self.bottone_allega.clicked.connect(self.scegli_immagine)

        self.bottone_ragiona = QPushButton("🧠 Ragiona")
        self.bottone_ragiona.setObjectName("bottoneRagiona")
        self.bottone_ragiona.setCheckable(True)
        self.bottone_ragiona.setFixedHeight(30)
        self.bottone_ragiona.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bottone_ragiona.setToolTip(
            "Il modello ragiona passo passo prima di rispondere: "
            "più lento, ma più preciso su matematica, fisica ed esercizi"
        )

        self.bottone = QPushButton("↑")
        self.bottone.setObjectName("bottoneInvia")
        self.bottone.setFixedSize(34, 34)
        self.bottone.setToolTip("Invia (Invio). Per andare a capo: Maiusc+Invio")
        self.bottone.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bottone.clicked.connect(self.invia)

        riga_strumenti = QHBoxLayout()
        riga_strumenti.setContentsMargins(0, 0, 0, 0)
        riga_strumenti.setSpacing(6)
        riga_strumenti.addWidget(self.bottone_allega)
        riga_strumenti.addWidget(self.bottone_ragiona)
        riga_strumenti.addStretch(1)
        riga_strumenti.addWidget(self.bottone)

        layout = QVBoxLayout(self.casella_scrittura)
        layout.setContentsMargins(16, 12, 10, 10)
        layout.setSpacing(8)
        layout.addLayout(riga_allegato)
        layout.addWidget(self.casella)
        layout.addLayout(riga_strumenti)
        return self.casella_scrittura

    # ---------------------------------------------------------- messaggi

    def _aggiungi_widget(self, widget):
        # I messaggi vanno prima della riga d'attesa e dello spazio finale.
        posizione = self.layout_colonna.indexOf(self.attesa)
        self.layout_colonna.insertWidget(posizione, widget)

    def _aggiungi_messaggio(self, ruolo, testo):
        if ruolo == "user":
            widget = MessaggioUtente(testo)
        else:
            widget = MessaggioRaphael(self.raphael.name, testo)
        self._aggiungi_widget(widget)
        return widget

    def _aggiorna_benvenuto(self):
        vuota = not self.messaggi and self._risposta_in_arrivo is None
        self.benvenuto.setVisible(vuota and not self.in_attesa)

    def widget_messaggi(self):
        widget = []
        for indice in range(self.layout_colonna.count()):
            elemento = self.layout_colonna.itemAt(indice).widget()
            if isinstance(elemento, (MessaggioUtente, MessaggioRaphael)):
                widget.append(elemento)
        return widget

    def testo_della_chat(self):
        return "\n\n".join(widget.testo_semplice() for widget in self.widget_messaggi())

    def _ricorda_se_in_fondo(self, valore):
        barra = self.area.verticalScrollBar()
        self._segui_il_fondo = valore >= barra.maximum() - DISTANZA_DAL_FONDO

    def _resta_in_fondo(self, minimo, massimo):
        # Quando la chat cresce, la segue solo se l'utente era già in fondo:
        # chi sta rileggendo un messaggio vecchio non viene spostato.
        if self._segui_il_fondo:
            self.area.verticalScrollBar().setValue(massimo)

    def vai_in_fondo(self):
        self._segui_il_fondo = True
        barra = self.area.verticalScrollBar()
        barra.setValue(barra.maximum())

    # ----------------------------------------------------------- allegati

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

        if oggetto is self.casella and evento.type() in (
            QEvent.Type.FocusIn,
            QEvent.Type.FocusOut,
        ):
            attiva = evento.type() == QEvent.Type.FocusIn
            self.casella_scrittura.setProperty("attiva", attiva)
            self.casella_scrittura.style().unpolish(self.casella_scrittura)
            self.casella_scrittura.style().polish(self.casella_scrittura)

        return super().eventFilter(oggetto, evento)

    def scegli_immagine(self):
        percorso, _ = QFileDialog.getOpenFileName(
            self, "Allega un'immagine", "", FILTRO_IMMAGINI
        )

        if not percorso:
            return

        immagine = QImage(percorso)

        if immagine.isNull():
            QMessageBox.warning(self, self.raphael.name, "Non riesco a leggere questa immagine.")
            return

        self.allega_immagine(immagine, Path(percorso).stem)

    def allega_immagine(self, immagine, nome_base):
        self.allegato = salva_immagine_ridotta(
            immagine, self.cartella_allegati, nome_base
        )
        self.nome_allegato = nome_base
        self._mostra_allegato()
        self.casella.setFocus()

    def togli_allegato(self):
        self.allegato = None
        self._mostra_allegato()

    def _mostra_allegato(self):
        if self.allegato is None:
            self.etichetta_allegato.setText("")
            self.miniatura.clear()
            self.chip_allegato.hide()
            return

        miniatura = QPixmap(str(self.allegato)).scaled(
            LATO_MINIATURA,
            LATO_MINIATURA,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.miniatura.setPixmap(miniatura)
        self.etichetta_allegato.setText(f"🖼️ {self.nome_allegato}")
        self.chip_allegato.show()

    # ------------------------------------------------------------- invio

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
        self._aggiungi_messaggio("user", testo_mostrato)

        self.risposta_parziale = ""
        self._risposta_in_arrivo = None
        self._imposta_attesa(True, ragiona)
        self.vai_in_fondo()
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

    def _aggiorna_risposta_in_arrivo(self):
        if not self.risposta_parziale.strip():
            return

        if self._risposta_in_arrivo is None:
            self._risposta_in_arrivo = MessaggioRaphael(self.raphael.name)
            self._aggiungi_widget(self._risposta_in_arrivo)
            self._aggiorna_benvenuto()
            if not self.richiesta_conferma:
                self.stato.setText(f"{self.raphael.name} sta scrivendo...")

        # Si aggiorna solo il messaggio in arrivo: il resto della chat non
        # viene ridisegnato, quindi lo streaming resta fluido.
        self._risposta_in_arrivo.imposta_testo(self.risposta_parziale)

    def _completa_risposta(self):
        self.timer_aggiornamento.stop()
        self._da_aggiornare = False

        if self._risposta_in_arrivo is None:
            self._risposta_in_arrivo = MessaggioRaphael(self.raphael.name)
            self._aggiungi_widget(self._risposta_in_arrivo)

        self._risposta_in_arrivo.imposta_testo(self.risposta_parziale)
        self._risposta_in_arrivo.completa()
        self.messaggi.append({"role": "assistant", "content": self.risposta_parziale})

        self.risposta_parziale = ""
        self._risposta_in_arrivo = None
        self._imposta_attesa(False)
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
            self.attesa.nascondi()
            self.casella.setFocus()
        elif ragiona:
            self.attesa.mostra(
                f"{self.raphael.name} sta ragionando... "
                "(con il ragionamento attivo può volerci qualche minuto)"
            )
        else:
            self.attesa.mostra(f"{self.raphael.name} sta pensando...")

        self._aggiorna_benvenuto()

    # ------------------------------------------------------------ conferma

    def _crea_barra_conferma(self):
        self.barra_conferma = QFrame()
        self.barra_conferma.setObjectName("barraConferma")

        self.titolo_conferma = QLabel("")
        self.titolo_conferma.setObjectName("titoloConferma")
        self.testo_conferma = QLabel("")
        self.testo_conferma.setWordWrap(True)
        self.testo_conferma.setTextFormat(Qt.TextFormat.PlainText)
        self.testo_conferma.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.dettagli_conferma = QLabel("")
        self.dettagli_conferma.setObjectName("dettagliConferma")
        self.dettagli_conferma.setWordWrap(True)
        self.dettagli_conferma.setTextFormat(Qt.TextFormat.PlainText)

        self.bottone_conferma = QPushButton("✔ Conferma")
        self.bottone_conferma.setObjectName("bottoneConferma")
        self.bottone_conferma.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bottone_conferma.clicked.connect(lambda: self._rispondi_conferma(True))

        self.bottone_rifiuta = QPushButton("✕ Annulla")
        self.bottone_rifiuta.setObjectName("bottoneRifiuta")
        self.bottone_rifiuta.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bottone_rifiuta.clicked.connect(lambda: self._rispondi_conferma(False))

        for bottone in (self.bottone_conferma, self.bottone_rifiuta):
            bottone.setFixedHeight(32)

        intestazione = QHBoxLayout()
        intestazione.setSpacing(10)
        intestazione.addWidget(Sfera(20))
        intestazione.addWidget(self.titolo_conferma, 1)

        riga_bottoni = QHBoxLayout()
        riga_bottoni.addStretch(1)
        riga_bottoni.addWidget(self.bottone_rifiuta)
        riga_bottoni.addWidget(self.bottone_conferma)

        layout = QVBoxLayout(self.barra_conferma)
        layout.setContentsMargins(16, 14, 14, 12)
        layout.setSpacing(6)
        layout.addLayout(intestazione)
        layout.addWidget(self.testo_conferma)
        layout.addWidget(self.dettagli_conferma)
        layout.addLayout(riga_bottoni)
        self.barra_conferma.hide()

    def chiedi_conferma(self, azione):
        """Chiamata dal thread del modello: aspetta che l'utente risponda."""
        if threading.current_thread() is threading.main_thread():
            # Dal thread della finestra non si può aspettare un clic sulla
            # finestra stessa: in questo raro caso si usa una finestrella.
            risposta = QMessageBox.question(
                self, self.raphael.name, f"{azione.descrizione}\n\nConfermi?"
            )
            return risposta == QMessageBox.StandardButton.Yes

        richiesta = RichiestaConferma(azione)
        self.segnali.conferma_richiesta.emit(richiesta)

        if not richiesta.evento.wait(TEMPO_MASSIMO_CONFERMA_S):
            richiesta.rispondi(False)
            self.segnali.conferma_scaduta.emit(richiesta)

        return richiesta.confermata

    def _mostra_conferma(self, richiesta):
        self.richiesta_conferma = richiesta
        azione = richiesta.azione
        delicata = azione.rischio == RISCHIO_ALTO

        if delicata:
            self.titolo_conferma.setText("⚠️ Azione delicata: controlla bene")
        else:
            self.titolo_conferma.setText(f"{self.raphael.name} vuole fare questa azione")

        self.barra_conferma.setProperty("delicata", delicata)
        self.barra_conferma.style().unpolish(self.barra_conferma)
        self.barra_conferma.style().polish(self.barra_conferma)

        self.testo_conferma.setText(azione.descrizione)
        self.dettagli_conferma.setText(azione.dettagli)
        self.dettagli_conferma.setVisible(bool(azione.dettagli))
        self.barra_conferma.show()
        self.bottone_rifiuta.setFocus()
        self.attesa.mostra("Aspetto la tua conferma...")
        QApplication.alert(self)

    def _rispondi_conferma(self, confermata):
        richiesta = self.richiesta_conferma
        if richiesta is None:
            return

        self._chiudi_barra_conferma()
        richiesta.rispondi(confermata)

    def _conferma_scaduta(self, richiesta):
        if self.richiesta_conferma is richiesta:
            self._chiudi_barra_conferma()

    def _chiudi_barra_conferma(self):
        self.richiesta_conferma = None
        self.barra_conferma.hide()
        if self.in_attesa:
            self.attesa.mostra(f"{self.raphael.name} sta pensando...")

    # ---------------------------------------------------------- promemoria

    def _ricevi_promemoria(self, voce):
        """Chiamata dal thread del pianificatore: passa l'avviso alla finestra.

        Qui siamo nel thread del pianificatore: per toccare la UI si passa
        attraverso il segnale, che viene recapitato nel thread della finestra.
        """
        self.segnali.promemoria_arrivato.emit(voce)

    def _mostra_notifica_promemoria(self, voce):
        testo = voce["testo"] if isinstance(voce, dict) else str(voce)

        if self.tray_icon.isSystemTrayAvailable() and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                self.raphael.name,
                testo,
                QIcon(str(percorso_risorsa("raphael.ico"))),
                DURATA_NOTIFICA_MS,
            )
        else:
            # Senza system tray (o con notifiche disattivate) il promemoria
            # resta comunque visibile con un popup della finestra.
            QMessageBox.information(self, self.raphael.name, f"⏰ {testo}")

    def closeEvent(self, evento):
        if self.richiesta_conferma is not None:
            self.richiesta_conferma.rispondi(False)
        self.raphael.salva_cronologia()
        super().closeEvent(evento)


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
    applicazione.setPalette(stile.tavolozza_scura())
    applicazione.setFont(carattere_interfaccia())

    finestra = FinestraRaphael(raphael)
    finestra.show()
    stile.barra_del_titolo_scura(finestra)

    return applicazione.exec()