"""Il riquadro dei promemoria: compare in basso a destra, sopra a tutto.

È una finestrella scura e arrotondata con la sfera di Raphael, il testo del
promemoria e due bottoni: "Rimanda" (5 minuti, 15 minuti, 1 ora) e "Fatto".
Resta aperta finché non rispondi, così se eri lontano dal PC la trovi al
ritorno. Se arrivano più promemoria insieme, i riquadri si impilano.

Il gestore ha già il gancio per la voce: quando Raphael saprà parlare, basterà
assegnare gestore.parla e il promemoria verrà anche letto ad alta voce.
"""

import logging
import sys
from datetime import datetime, timedelta

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import stile
from .componenti import Sfera


logger = logging.getLogger(__name__)

LARGHEZZA_SCHEDA = 380
MARGINE_OMBRA = 18        # spazio trasparente attorno alla scheda per l'ombra
DISTANZA_DAL_BORDO = 6    # distanza dall'angolo dello schermo (oltre all'ombra)
SOVRAPPOSIZIONE_OMBRE = 26  # le ombre di due avvisi si sovrappongono: le schede restano a 10 px
MASSIMO_AVVISI = 4
RITARDO_TOLLERATO = timedelta(minutes=2)
DURATA_COMPARSA_MS = 280
DURATA_SCOMPARSA_MS = 180
CHIUSURA_DOPO_RIMANDO_MS = 1600

SCELTE_RIMANDO = [("Tra 5 minuti", 5), ("Tra 15 minuti", 15), ("Tra 1 ora", 60)]

ARANCIO = "#e8a948"

FOGLIO_AVVISO = f"""
QLabel {{
    background: transparent;
    color: {stile.TESTO};
}}
QLabel#etichettaAvviso {{
    color: {stile.TESTO_SECONDARIO};
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 1px;
}}
QLabel#orarioAvviso {{
    color: {stile.TESTO_DEBOLE};
    font-size: 9pt;
}}
QLabel#orarioAvviso[ritardo="true"] {{
    color: {ARANCIO};
}}
QLabel#testoAvviso {{
    color: {stile.TESTO};
    font-size: 13pt;
    font-weight: 600;
}}
QLabel#confermaAvviso {{
    color: {stile.TESTO_SECONDARIO};
}}
QPushButton#chiudiAvviso {{
    background: transparent;
    border: none;
    border-radius: 13px;
    color: {stile.TESTO_DEBOLE};
    font-size: 11pt;
}}
QPushButton#chiudiAvviso:hover {{
    background-color: {stile.SUPERFICIE_ALTA};
    color: {stile.TESTO};
}}
QPushButton#rimandaAvviso {{
    background-color: {stile.SUPERFICIE_ALTA};
    border: 1px solid {stile.BORDO};
    border-radius: 17px;
    color: {stile.TESTO};
    padding: 0 16px;
}}
QPushButton#rimandaAvviso:hover {{
    border-color: {stile.BORDO_ATTIVO};
}}
QPushButton#rimandaAvviso::menu-indicator {{
    image: none;
    width: 0;
}}
QPushButton#fattoAvviso {{
    border: none;
    border-radius: 17px;
    color: white;
    font-weight: 600;
    padding: 0 20px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {stile.ACCENTO_BLU}, stop:1 {stile.ACCENTO_VIOLA});
}}
QPushButton#fattoAvviso:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #6690ff, stop:1 #ab74ff);
}}
QMenu {{
    background-color: {stile.SUPERFICIE_ALTA};
    border: 1px solid {stile.BORDO};
    border-radius: 12px;
    padding: 6px;
    color: {stile.TESTO};
}}
QMenu::item {{
    padding: 7px 18px;
    border-radius: 8px;
}}
QMenu::item:selected {{
    background-color: {stile.BORDO_ATTIVO};
}}
"""


def suona_avviso():
    """Il "din" di Windows per gli avvisi (altrove il bip del sistema)."""
    if sys.platform == "win32":
        try:
            import winsound

            winsound.MessageBeep(winsound.MB_ICONASTERISK)
            return
        except Exception:
            pass
    QApplication.beep()


def quando_era(quando: datetime, adesso: datetime) -> str:
    """Scrive l'ora prevista di un promemoria arrivato in ritardo."""
    giorni = (adesso.date() - quando.date()).days
    if giorni == 0:
        return f"oggi alle {quando:%H:%M}"
    if giorni == 1:
        return f"ieri alle {quando:%H:%M}"
    return f"il {quando:%d/%m} alle {quando:%H:%M}"


def _leggi_quando(voce) -> datetime | None:
    try:
        return datetime.fromisoformat(voce["quando"])
    except (KeyError, TypeError, ValueError):
        return None


class _Scheda(QWidget):
    """Il fondo della notifica: rettangolo arrotondato con bordo sfumato e un alone."""

    def paintEvent(self, evento):
        pittore = QPainter(self)
        pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
        rettangolo = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)

        forma = QPainterPath()
        forma.addRoundedRect(rettangolo, stile.RAGGIO_GRANDE, stile.RAGGIO_GRANDE)
        pittore.fillPath(forma, QColor(stile.SUPERFICIE))

        # Un alone blu→viola appena accennato nell'angolo in alto a sinistra.
        alone = QRadialGradient(
            QPointF(rettangolo.left() + 40, rettangolo.top() + 30), rettangolo.width() * 0.7
        )
        colore_alone = QColor(stile.ACCENTO)
        colore_alone.setAlpha(34)
        alone.setColorAt(0.0, colore_alone)
        colore_alone.setAlpha(0)
        alone.setColorAt(1.0, colore_alone)
        pittore.fillPath(forma, QBrush(alone))

        bordo = QLinearGradient(rettangolo.topLeft(), rettangolo.bottomRight())
        blu = QColor(stile.ACCENTO_BLU)
        blu.setAlpha(150)
        viola = QColor(stile.ACCENTO_VIOLA)
        viola.setAlpha(60)
        bordo.setColorAt(0.0, blu)
        bordo.setColorAt(1.0, viola)
        pittore.setPen(QPen(QBrush(bordo), 1.2))
        pittore.drawPath(forma)


class AvvisoPromemoria(QWidget):
    """Una singola notifica di promemoria."""

    rimandato = Signal(object, int)  # la voce e i minuti
    chiuso = Signal(object)          # se stesso

    def __init__(self, voce, adesso: datetime | None = None, animato: bool = True):
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.voce = voce if isinstance(voce, dict) else {"testo": str(voce)}
        self.animato = animato
        self._chiuso = False
        self._animazioni = []
        adesso = adesso or datetime.now()

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Compare senza rubare la tastiera a quello che stai scrivendo.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(FOGLIO_AVVISO)
        self.setWindowTitle("Promemoria")

        self.scheda = _Scheda()
        ombra = QGraphicsDropShadowEffect(self.scheda)
        ombra.setBlurRadius(34)
        ombra.setOffset(0, 8)
        ombra.setColor(QColor(0, 0, 0, 150))
        self.scheda.setGraphicsEffect(ombra)
        self.scheda.setFixedWidth(LARGHEZZA_SCHEDA)

        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(MARGINE_OMBRA, MARGINE_OMBRA, MARGINE_OMBRA, MARGINE_OMBRA)
        esterno.addWidget(self.scheda)

        layout = QVBoxLayout(self.scheda)
        layout.setContentsMargins(18, 16, 14, 16)
        layout.setSpacing(12)
        layout.addLayout(self._crea_intestazione(adesso))

        self.testo = QLabel(self.voce.get("testo", ""))
        self.testo.setObjectName("testoAvviso")
        self.testo.setWordWrap(True)
        self.testo.setTextFormat(Qt.TextFormat.PlainText)
        self.testo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.testo.setContentsMargins(2, 0, 4, 0)
        layout.addWidget(self.testo)

        self.conferma = QLabel("")
        self.conferma.setObjectName("confermaAvviso")
        self.conferma.hide()
        layout.addWidget(self.conferma)

        layout.addLayout(self._crea_bottoni())

        self._timer_chiusura = QTimer(self)
        self._timer_chiusura.setSingleShot(True)
        self._timer_chiusura.timeout.connect(self.chiudi)

        self.adjustSize()

    # ------------------------------------------------------- costruzione

    def _crea_intestazione(self, adesso):
        etichetta = QLabel("PROMEMORIA")
        etichetta.setObjectName("etichettaAvviso")

        quando = _leggi_quando(self.voce)
        self.in_ritardo = quando is not None and adesso - quando > RITARDO_TOLLERATO
        if self.in_ritardo:
            orario = f"In ritardo · era per {quando_era(quando, adesso)}"
        else:
            orario = f"Adesso · {adesso:%H:%M}"

        self.orario = QLabel(orario)
        self.orario.setObjectName("orarioAvviso")
        self.orario.setProperty("ritardo", self.in_ritardo)

        colonna = QVBoxLayout()
        colonna.setSpacing(1)
        colonna.addWidget(etichetta)
        colonna.addWidget(self.orario)

        self.bottone_chiudi = QPushButton("✕")
        self.bottone_chiudi.setObjectName("chiudiAvviso")
        self.bottone_chiudi.setFixedSize(26, 26)
        self.bottone_chiudi.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bottone_chiudi.setToolTip("Chiudi")
        self.bottone_chiudi.clicked.connect(self.chiudi)

        riga = QHBoxLayout()
        riga.setSpacing(12)
        riga.addWidget(Sfera(34))
        riga.addLayout(colonna, 1)
        riga.addWidget(self.bottone_chiudi, 0, Qt.AlignmentFlag.AlignTop)
        return riga

    def _crea_bottoni(self):
        self.bottone_rimanda = QPushButton("Rimanda  ▾")
        self.bottone_rimanda.setObjectName("rimandaAvviso")
        self.bottone_rimanda.setCursor(Qt.CursorShape.PointingHandCursor)

        self.menu_rimanda = QMenu(self.bottone_rimanda)
        self.menu_rimanda.setStyleSheet(FOGLIO_AVVISO)
        self.scelte_rimando = []
        for testo, minuti in SCELTE_RIMANDO:
            azione = self.menu_rimanda.addAction(testo)
            azione.triggered.connect(lambda _=False, m=minuti: self.rimanda(m))
            self.scelte_rimando.append(azione)
        self.bottone_rimanda.setMenu(self.menu_rimanda)

        self.bottone_fatto = QPushButton("Fatto  ✓")
        self.bottone_fatto.setObjectName("fattoAvviso")
        self.bottone_fatto.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bottone_fatto.clicked.connect(self.chiudi)

        for bottone in (self.bottone_rimanda, self.bottone_fatto):
            bottone.setFixedHeight(34)

        riga = QHBoxLayout()
        riga.setSpacing(8)
        riga.addStretch(1)
        riga.addWidget(self.bottone_rimanda)
        riga.addWidget(self.bottone_fatto)
        return riga

    # --------------------------------------------------------- comportamento

    def rimanda(self, minuti: int):
        if self._chiuso:
            return
        self.rimandato.emit(self.voce, minuti)

        nuova_ora = datetime.now() + timedelta(minutes=minuti)
        self.conferma.setText(f"⏰ Ok, te lo ricordo alle {nuova_ora:%H:%M}")
        self.conferma.show()
        self.bottone_rimanda.hide()
        self.bottone_fatto.hide()
        self.adjustSize()
        self._timer_chiusura.start(CHIUSURA_DOPO_RIMANDO_MS)

    def compari(self, posizione: QPoint):
        """Mostra la notifica nel punto indicato, salendo e sfumando dal basso."""
        if not self.animato:
            self.move(posizione)
            self.show()
            return

        self.setWindowOpacity(0.0)
        self.move(posizione + QPoint(0, 26))
        self.show()
        self._anima(b"windowOpacity", 1.0, DURATA_COMPARSA_MS)
        self._anima(b"pos", posizione, DURATA_COMPARSA_MS)

    def sposta(self, posizione: QPoint):
        if self.animato and self.isVisible():
            self._anima(b"pos", posizione, 220)
        else:
            self.move(posizione)

    def chiudi(self):
        if self._chiuso:
            return
        self._chiuso = True
        self._timer_chiusura.stop()

        if not self.animato or not self.isVisible():
            self._chiudi_davvero()
            return

        sparizione = self._anima(b"windowOpacity", 0.0, DURATA_SCOMPARSA_MS)
        sparizione.finished.connect(self._chiudi_davvero)

    def e_chiuso(self) -> bool:
        return self._chiuso

    def _chiudi_davvero(self):
        self.hide()
        self.chiuso.emit(self)

    def _anima(self, proprieta, valore_finale, durata):
        animazione = QPropertyAnimation(self, proprieta, self)
        animazione.setDuration(durata)
        animazione.setEndValue(valore_finale)
        animazione.setEasingCurve(QEasingCurve.Type.OutCubic)
        animazione.finished.connect(lambda: self._dimentica(animazione))
        self._animazioni.append(animazione)
        animazione.start()
        return animazione

    def _dimentica(self, animazione):
        if animazione in self._animazioni:
            self._animazioni.remove(animazione)


class GestoreAvvisi(QObject):
    """Mostra le notifiche dei promemoria e le tiene in ordine sullo schermo."""

    rimanda = Signal(object, int)  # la voce e i minuti

    def __init__(self, animato: bool = True, suono: bool = True, parent=None):
        super().__init__(parent)
        self.animato = animato
        self.suono = suono
        self.avvisi: list[AvvisoPromemoria] = []
        # Gancio per la voce: una funzione che riceve il testo da leggere.
        self.parla = None

    def mostra(self, voce, adesso: datetime | None = None) -> AvvisoPromemoria:
        while len(self.avvisi) >= MASSIMO_AVVISI:
            self.avvisi[0].animato = False
            self.avvisi[0].chiudi()

        avviso = AvvisoPromemoria(voce, adesso=adesso, animato=self.animato)
        avviso.rimandato.connect(self.rimanda)
        avviso.chiuso.connect(self._togli)
        self.avvisi.append(avviso)

        posizioni = self._posizioni()
        for altro, posizione in zip(self.avvisi[:-1], posizioni):
            altro.sposta(posizione)
        avviso.compari(posizioni[-1])

        if self.suono:
            suona_avviso()
        self._leggi_ad_alta_voce(avviso.voce.get("testo", ""))
        return avviso

    def chiudi_tutti(self):
        for avviso in list(self.avvisi):
            avviso.animato = False
            avviso.chiudi()

    def _leggi_ad_alta_voce(self, testo):
        if self.parla is None or not testo:
            return
        try:
            self.parla(f"Promemoria: {testo}")
        except Exception:
            logger.exception("Lettura del promemoria non riuscita")

    def _togli(self, avviso):
        if avviso in self.avvisi:
            self.avvisi.remove(avviso)
            avviso.deleteLater()
            for altro, posizione in zip(self.avvisi, self._posizioni()):
                altro.sposta(posizione)

    def _posizioni(self) -> list[QPoint]:
        """Il primo avviso va nell'angolo in basso a destra, gli altri sopra."""
        schermo = QGuiApplication.primaryScreen()
        area = schermo.availableGeometry() if schermo else None
        destra = area.right() if area else 1280
        basso = area.bottom() if area else 720

        posizioni = []
        y = basso - DISTANZA_DAL_BORDO
        for avviso in self.avvisi:
            y -= avviso.height()
            posizioni.append(QPoint(destra - DISTANZA_DAL_BORDO - avviso.width(), y))
            y += SOVRAPPOSIZIONE_OMBRE
        return posizioni