import time

import pytest
from PySide6.QtWidgets import QApplication

from ai.mock_provider import MockAIProvider
from core.app import RaphaelApp
from ui.finestra import FinestraRaphael, componi_markdown_chat


@pytest.fixture(autouse=True)
def isola_history_file(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.json")


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def aspetta_risposta(finestra, qapp, secondi=5):
    limite = time.time() + secondi
    while finestra.in_attesa and time.time() < limite:
        qapp.processEvents()
        time.sleep(0.01)


def test_componi_markdown_chat_mostra_i_messaggi():
    messaggi = [
        {"role": "user", "content": "ciao"},
        {"role": "assistant", "content": "Ciao! Sono Raphael."},
    ]

    testo = componi_markdown_chat(messaggi, "Raphael")

    assert "**Tu:** ciao" in testo
    assert "**Raphael:**" in testo
    assert "Ciao! Sono Raphael." in testo


def test_componi_markdown_chat_converte_le_formule():
    messaggi = [{"role": "assistant", "content": r"La formula è $\omega = 2\pi f$"}]

    testo = componi_markdown_chat(messaggi, "Raphael")

    assert "ω" in testo
    assert "$" not in testo


def test_componi_markdown_chat_indica_l_attesa():
    testo = componi_markdown_chat([], "Raphael", in_attesa=True)

    assert "sta scrivendo" in testo


def test_la_finestra_mostra_la_cronologia(qapp):
    raphael = RaphaelApp(ai_provider=MockAIProvider())
    raphael.history.add_message("user", "messaggio vecchio")
    raphael.history.add_message("assistant", "risposta vecchia")

    finestra = FinestraRaphael(raphael)

    assert "messaggio vecchio" in finestra.chat.toPlainText()
    assert "risposta vecchia" in finestra.chat.toPlainText()


def test_la_finestra_invia_e_riceve(qapp):
    raphael = RaphaelApp(ai_provider=MockAIProvider())
    finestra = FinestraRaphael(raphael)

    finestra.casella.setText("ciao")
    finestra.invia()
    aspetta_risposta(finestra, qapp)

    assert not finestra.in_attesa
    assert "Ciao! Sono Raphael." in finestra.chat.toPlainText()
    assert finestra.casella.isEnabled()