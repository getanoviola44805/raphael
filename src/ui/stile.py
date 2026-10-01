"""Colori e stile dell'interfaccia di Raphael: tutto scuro, pulito e arrotondato.

Tutte le finestre (chat, pannello compatto, riquadri di conferma) prendono i
colori da qui, così Raphael ha lo stesso aspetto ovunque.
"""

import sys

from PySide6.QtGui import QColor, QPalette


# Sfondi, dal più scuro al più chiaro.
SFONDO = "#16171b"
SUPERFICIE = "#1f2025"
SUPERFICIE_ALTA = "#2a2b31"
BORDO = "#2f3037"
BORDO_ATTIVO = "#4a4c56"

# Testi.
TESTO = "#ececf1"
TESTO_SECONDARIO = "#9b9ca6"
TESTO_DEBOLE = "#6c6e78"

# L'accento di Raphael: lo stesso blu→viola dell'icona.
ACCENTO_BLU = "#4f7cff"
ACCENTO_VIOLA = "#9b5cff"
ACCENTO = "#7a6bff"

VERDE = "#2fa865"
ROSSO = "#e05561"
SFONDO_CODICE = "#111216"

RAGGIO_GRANDE = 22
RAGGIO_MEDIO = 16
RAGGIO_PICCOLO = 12

LARGHEZZA_COLONNA = 780


FOGLIO_DI_STILE = f"""
QMainWindow, QWidget#sfondo {{
    background-color: {SFONDO};
}}
QWidget {{
    color: {TESTO};
}}
QToolTip {{
    background-color: {SUPERFICIE_ALTA};
    color: {TESTO};
    border: 1px solid {BORDO};
    border-radius: 8px;
    padding: 6px 8px;
}}
QScrollArea, QScrollArea > QWidget > QWidget {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 0;
}}
QScrollBar::handle:vertical {{
    background: {SUPERFICIE_ALTA};
    border-radius: 4px;
    min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{
    background: {BORDO_ATTIVO};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    height: 0;
    background: transparent;
}}

QFrame#casellaScrittura {{
    background-color: {SUPERFICIE};
    border: 1px solid {BORDO};
    border-radius: {RAGGIO_GRANDE}px;
}}
QFrame#casellaScrittura[attiva="true"] {{
    border: 1px solid {BORDO_ATTIVO};
}}
QPlainTextEdit#testoDaInviare {{
    background: transparent;
    border: none;
    color: {TESTO};
    selection-background-color: {ACCENTO};
    padding: 0;
}}

QPushButton#bottoneIcona {{
    background: transparent;
    border: none;
    border-radius: 17px;
    color: {TESTO_SECONDARIO};
    font-size: 16px;
}}
QPushButton#bottoneIcona:hover {{
    background-color: {SUPERFICIE_ALTA};
    color: {TESTO};
}}

QPushButton#bottoneRagiona {{
    background: transparent;
    border: 1px solid {BORDO};
    border-radius: 15px;
    color: {TESTO_SECONDARIO};
    padding: 0 14px;
}}
QPushButton#bottoneRagiona:hover {{
    border-color: {BORDO_ATTIVO};
    color: {TESTO};
}}
QPushButton#bottoneRagiona:checked {{
    background-color: rgba(122, 107, 255, 46);
    border: 1px solid {ACCENTO};
    color: {TESTO};
}}

QPushButton#bottoneInvia {{
    border: none;
    border-radius: 17px;
    color: white;
    font-size: 17px;
    font-weight: bold;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {ACCENTO_BLU}, stop:1 {ACCENTO_VIOLA});
}}
QPushButton#bottoneInvia:disabled {{
    background: {SUPERFICIE_ALTA};
    color: {TESTO_DEBOLE};
}}

QFrame#chipAllegato {{
    background-color: {SUPERFICIE_ALTA};
    border-radius: {RAGGIO_PICCOLO}px;
}}
QPushButton#bottoneTogli {{
    background: transparent;
    border: none;
    border-radius: 11px;
    color: {TESTO_SECONDARIO};
}}
QPushButton#bottoneTogli:hover {{
    background-color: {BORDO_ATTIVO};
    color: {TESTO};
}}

QFrame#fumettoUtente {{
    background-color: {SUPERFICIE_ALTA};
    border-radius: {RAGGIO_MEDIO + 2}px;
}}

QPushButton#bottoneCopia {{
    background: transparent;
    border: none;
    border-radius: 8px;
    color: {TESTO_DEBOLE};
    padding: 3px 8px;
}}
QPushButton#bottoneCopia:hover {{
    background-color: {SUPERFICIE_ALTA};
    color: {TESTO};
}}

QLabel#stato {{
    color: {TESTO_SECONDARIO};
}}
QLabel#nomeRaphael {{
    color: {TESTO_SECONDARIO};
    font-weight: 600;
}}
QLabel#benvenuto {{
    color: {TESTO};
    font-size: 24px;
    font-weight: 600;
}}
QLabel#sottotitolo {{
    color: {TESTO_SECONDARIO};
}}

QFrame#barraConferma {{
    background-color: #24223a;
    border: 1px solid {ACCENTO};
    border-radius: {RAGGIO_MEDIO}px;
}}
QFrame#barraConferma[delicata="true"] {{
    background-color: #33212a;
    border: 1px solid {ROSSO};
}}
QFrame#barraConferma QLabel {{
    background: transparent;
    border: none;
}}
QLabel#titoloConferma {{
    font-weight: 600;
}}
QLabel#dettagliConferma {{
    color: {TESTO_SECONDARIO};
}}
QPushButton#bottoneConferma, QPushButton#bottoneRifiuta {{
    border-radius: 16px;
    padding: 0 18px;
    border: none;
}}
QPushButton#bottoneConferma {{
    background-color: {VERDE};
    color: white;
}}
QPushButton#bottoneConferma:hover {{
    background-color: #38c176;
}}
QPushButton#bottoneRifiuta {{
    background-color: {SUPERFICIE_ALTA};
    color: {TESTO};
}}
QPushButton#bottoneRifiuta:hover {{
    background-color: {BORDO_ATTIVO};
}}
"""


def tavolozza_scura() -> QPalette:
    palette = QPalette()
    colori = {
        QPalette.ColorRole.Window: SFONDO,
        QPalette.ColorRole.WindowText: TESTO,
        QPalette.ColorRole.Base: SUPERFICIE,
        QPalette.ColorRole.AlternateBase: SUPERFICIE_ALTA,
        QPalette.ColorRole.Text: TESTO,
        QPalette.ColorRole.Button: SUPERFICIE_ALTA,
        QPalette.ColorRole.ButtonText: TESTO,
        QPalette.ColorRole.Highlight: ACCENTO,
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.Link: "#8fb0ff",
        QPalette.ColorRole.PlaceholderText: TESTO_DEBOLE,
        QPalette.ColorRole.ToolTipBase: SUPERFICIE_ALTA,
        QPalette.ColorRole.ToolTipText: TESTO,
    }
    for ruolo, colore in colori.items():
        palette.setColor(ruolo, QColor(colore))
    return palette


def barra_del_titolo_scura(finestra):
    """Su Windows 10 e 11 rende scura anche la barra in alto della finestra."""
    if sys.platform != "win32":
        return

    try:
        import ctypes

        valore = ctypes.c_int(1)
        for attributo in (20, 19):  # 20 su Windows 11 e 10 recenti, 19 sui più vecchi
            risultato = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                int(finestra.winId()),
                attributo,
                ctypes.byref(valore),
                ctypes.sizeof(valore),
            )
            if risultato == 0:
                break
    except Exception:
        pass