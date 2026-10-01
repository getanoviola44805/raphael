"""I mattoncini dell'interfaccia: cerchio che gira, sfera, testi e messaggi.

Sono pensati per essere riusati anche dal pannello compatto e dalla modalità voce.
"""

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QRadialGradient,
    QTextBlockFormat,
    QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from . import stile
from .formattazione import converti_latex


ALTEZZA_RIGA = 135  # percentuale: righe un po' distanziate si leggono meglio


# ------------------------------------------------------------- animazioni


class CerchioRotante(QWidget):
    """Un anello sfumato blu→viola che gira: indica che Raphael sta lavorando."""

    def __init__(self, lato=18, spessore=2.4, parent=None):
        super().__init__(parent)
        self.setFixedSize(lato, lato)
        self._spessore = spessore
        self._angolo = 0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._avanza)

    def avvia(self):
        self._timer.start()
        self.show()

    def ferma(self):
        self._timer.stop()

    def sta_girando(self):
        return self._timer.isActive()

    def _avanza(self):
        self._angolo = (self._angolo + 7) % 360
        self.update()

    def paintEvent(self, evento):
        pittore = QPainter(self)
        pittore.setRenderHint(QPainter.RenderHint.Antialiasing)

        margine = self._spessore / 2 + 0.5
        rettangolo = QRectF(self.rect()).adjusted(margine, margine, -margine, -margine)

        sfumatura = QConicalGradient(rettangolo.center(), -self._angolo)
        sfumatura.setColorAt(0.0, QColor(stile.ACCENTO_VIOLA))
        sfumatura.setColorAt(0.75, QColor(stile.ACCENTO_BLU))
        trasparente = QColor(stile.ACCENTO_BLU)
        trasparente.setAlpha(0)
        sfumatura.setColorAt(1.0, trasparente)

        penna = QPen(QBrush(sfumatura), self._spessore)
        penna.setCapStyle(Qt.PenCapStyle.RoundCap)
        pittore.setPen(penna)
        pittore.drawArc(rettangolo, int(-self._angolo * 16), int(-280 * 16))


class Sfera(QWidget):
    """La sfera di Raphael: un cerchio sfumato con un riflesso di luce."""

    def __init__(self, lato=24, parent=None):
        super().__init__(parent)
        self.setFixedSize(lato, lato)

    def paintEvent(self, evento):
        pittore = QPainter(self)
        pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
        rettangolo = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        sfumatura = QLinearGradient(rettangolo.topLeft(), rettangolo.bottomRight())
        sfumatura.setColorAt(0.0, QColor(stile.ACCENTO_BLU))
        sfumatura.setColorAt(1.0, QColor(stile.ACCENTO_VIOLA))
        pittore.setPen(Qt.PenStyle.NoPen)
        pittore.setBrush(sfumatura)
        pittore.drawEllipse(rettangolo)

        luce = QRadialGradient(
            QPointF(rettangolo.left() + rettangolo.width() * 0.35,
                    rettangolo.top() + rettangolo.height() * 0.3),
            rettangolo.width() * 0.45,
        )
        luce.setColorAt(0.0, QColor(255, 255, 255, 120))
        luce.setColorAt(1.0, QColor(255, 255, 255, 0))
        pittore.setBrush(luce)
        pittore.drawEllipse(rettangolo)


# ------------------------------------------------------------------ testi


class TestoAdattivo(QTextBrowser):
    """Un testo selezionabile che cresce in altezza quanto serve, senza barre.

    Con markdown=True mostra titoli, elenchi, grassetti e blocchi di codice;
    altrimenti mostra il testo così com'è.
    """

    def __init__(self, markdown=True, parent=None):
        super().__init__(parent)
        self._markdown = markdown
        self._testo = ""

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setOpenExternalLinks(True)
        self.setStyleSheet("QTextBrowser { background: transparent; border: none; }")
        self.viewport().setAutoFillBackground(False)
        self.document().setDocumentMargin(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(1)

    def testo(self):
        return self._testo

    def imposta_testo(self, testo):
        self._testo = testo

        if self._markdown:
            self.setMarkdown(converti_latex(testo))
            self._rifinisci()
        else:
            self.setPlainText(testo)

        self.adatta_altezza()

    def _rifinisci(self):
        """Righe più ariose e blocchi di codice su sfondo scuro, come in un editor."""
        documento = self.document()
        blocco = documento.begin()

        while blocco.isValid():
            formato = blocco.blockFormat()
            nuovo = QTextBlockFormat()

            if formato.hasProperty(QTextFormat.Property.BlockCodeFence):
                nuovo.setBackground(QColor(stile.SFONDO_CODICE))
                nuovo.setLeftMargin(12)
                nuovo.setRightMargin(12)
            else:
                nuovo.setLineHeight(
                    ALTEZZA_RIGA, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value
                )

            QTextCursor(blocco).mergeBlockFormat(nuovo)
            blocco = blocco.next()

    def larghezza_ideale(self, massima):
        documento = self.document()
        documento.setTextWidth(massima)
        return math.ceil(documento.idealWidth())

    def adatta_altezza(self):
        larghezza = self.viewport().width()
        if larghezza <= 0:
            return
        self.document().setTextWidth(larghezza)
        altezza = max(1, math.ceil(self.document().size().height()))
        if altezza != self.height():
            self.setFixedHeight(altezza)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self.adatta_altezza()

    def wheelEvent(self, evento):
        # La rotellina deve far scorrere la chat, non il singolo messaggio.
        evento.ignore()


# --------------------------------------------------------------- messaggi


class MessaggioUtente(QWidget):
    """Il messaggio dell'utente: un fumetto arrotondato allineato a destra."""

    PROPORZIONE_MASSIMA = 0.8
    MARGINE_ORIZZONTALE = 16
    MARGINE_VERTICALE = 10

    def __init__(self, testo, parent=None):
        super().__init__(parent)
        self.testo = TestoAdattivo(markdown=False)
        self.testo.imposta_testo(testo)

        self.fumetto = QFrame()
        self.fumetto.setObjectName("fumettoUtente")
        interno = QVBoxLayout(self.fumetto)
        interno.setContentsMargins(
            self.MARGINE_ORIZZONTALE, self.MARGINE_VERTICALE,
            self.MARGINE_ORIZZONTALE, self.MARGINE_VERTICALE,
        )
        interno.addWidget(self.testo)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        layout.addWidget(self.fumetto)

    def testo_semplice(self):
        return self.testo.toPlainText()

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        massima = int(self.width() * self.PROPORZIONE_MASSIMA) - 2 * self.MARGINE_ORIZZONTALE
        massima = max(massima, 60)
        larghezza = min(self.testo.larghezza_ideale(massima) + 2, massima)
        self.testo.setFixedWidth(larghezza)
        self.testo.adatta_altezza()


class MessaggioRaphael(QWidget):
    """La risposta di Raphael: sfera e nome, poi il testo pulito e il tasto Copia."""

    def __init__(self, nome, testo="", parent=None):
        super().__init__(parent)

        intestazione = QHBoxLayout()
        intestazione.setContentsMargins(0, 0, 0, 0)
        intestazione.setSpacing(8)
        intestazione.addWidget(Sfera(22))
        self.nome = QLabel(nome)
        self.nome.setObjectName("nomeRaphael")
        intestazione.addWidget(self.nome)
        intestazione.addStretch(1)

        self.testo = TestoAdattivo(markdown=True)

        self.bottone_copia = QPushButton("⧉ Copia")
        self.bottone_copia.setObjectName("bottoneCopia")
        self.bottone_copia.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bottone_copia.setToolTip("Copia la risposta")
        self.bottone_copia.clicked.connect(self.copia)
        self.bottone_copia.hide()

        piede = QHBoxLayout()
        piede.setContentsMargins(0, 0, 0, 0)
        piede.addWidget(self.bottone_copia)
        piede.addStretch(1)

        corpo = QVBoxLayout()
        corpo.setContentsMargins(30, 0, 0, 0)
        corpo.setSpacing(4)
        corpo.addWidget(self.testo)
        corpo.addLayout(piede)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(intestazione)
        layout.addLayout(corpo)

        if testo:
            self.imposta_testo(testo)
            self.completa()

    def imposta_testo(self, testo):
        self.testo.imposta_testo(testo)

    def completa(self):
        self.bottone_copia.setVisible(bool(self.testo.testo().strip()))

    def copia(self):
        QApplication.clipboard().setText(self.testo.testo())
        self.bottone_copia.setText("✓ Copiato")
        QTimer.singleShot(1500, lambda: self.bottone_copia.setText("⧉ Copia"))

    def testo_semplice(self):
        return self.testo.toPlainText()


class RigaAttesa(QWidget):
    """Il cerchio che gira con una frase, dove arriverà la risposta."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cerchio = CerchioRotante(18)
        self.etichetta = QLabel("")
        self.etichetta.setObjectName("stato")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.cerchio)
        layout.addWidget(self.etichetta)
        layout.addStretch(1)
        self.hide()

    def mostra(self, testo):
        self.etichetta.setText(testo)
        self.cerchio.avvia()
        self.show()

    def nascondi(self):
        self.cerchio.ferma()
        self.etichetta.setText("")
        self.hide()


# ------------------------------------------------------------ scrittura


class CasellaTesto(QPlainTextEdit):
    """La casella in cui si scrive: cresce con il testo fino a 8 righe.

    Invio manda il messaggio, Maiusc+Invio va a capo.
    """

    invio_premuto = Signal()
    RIGHE_MASSIME = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("testoDaInviare")
        self.setTabChangesFocus(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document().setDocumentMargin(2)
        self.document().contentsChanged.connect(self._adatta_altezza)
        self._adatta_altezza()

    # Stessi nomi di una casella di una riga, così il resto del codice non cambia.
    def text(self):
        return self.toPlainText()

    def setText(self, testo):
        self.setPlainText(testo)
        self.moveCursor(QTextCursor.MoveOperation.End)

    def keyPressEvent(self, evento):
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            evento.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.invio_premuto.emit()
            return
        super().keyPressEvent(evento)

    def _adatta_altezza(self):
        righe = self.document().documentLayout().documentSize().height()
        righe = min(max(int(righe), 1), self.RIGHE_MASSIME)
        altezza = righe * self.fontMetrics().lineSpacing() + 10
        if altezza != self.height():
            self.setFixedHeight(altezza)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._adatta_altezza()


def bottone_icona(testo, suggerimento):
    bottone = QPushButton(testo)
    bottone.setObjectName("bottoneIcona")
    bottone.setFixedSize(34, 34)
    bottone.setToolTip(suggerimento)
    bottone.setCursor(Qt.CursorShape.PointingHandCursor)
    return bottone


def carattere_interfaccia():
    carattere = QFont("Segoe UI", 11)
    carattere.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return carattere