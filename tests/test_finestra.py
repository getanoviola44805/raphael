import time

import pytest
from PySide6.QtWidgets import QApplication

from ai.mock_provider import MockAIProvider
from ai.provider import AIProvider
from core.app import RaphaelApp
from ui.finestra import FinestraRaphael, componi_markdown_chat


class ProviderAPezzi(AIProvider):
    def generate_response(self, prompt, history=None):
        return "Risposta intera"

    def generate_response_stream(self, prompt, history=None):
        yield "Prima parte, "
        yield "seconda parte."


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


def test_componi_markdown_chat_mostra_la_risposta_parziale():
    testo = componi_markdown_chat(
        [], "Raphael", in_attesa=True, risposta_parziale="Sto scrivendo una ris"
    )

    assert "Sto scrivendo una ris" in testo
    assert "sta scrivendo..." not in testo


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


def test_la_finestra_unisce_i_pezzi_della_risposta(qapp):
    raphael = RaphaelApp(ai_provider=ProviderAPezzi())
    finestra = FinestraRaphael(raphael)

    finestra.casella.setText("raccontami qualcosa")
    finestra.invia()
    aspetta_risposta(finestra, qapp)

    assert "Prima parte, seconda parte." in finestra.chat.toPlainText()
    assert finestra.messaggi[-1]["content"] == "Prima parte, seconda parte."


def test_aggiornare_la_chat_non_sposta_chi_sta_rileggendo(qapp):
    raphael = RaphaelApp(ai_provider=MockAIProvider())
    for numero in range(30):
        raphael.history.add_message("user", f"domanda {numero}")
        raphael.history.add_message("assistant", "risposta lunga\n\n" * 5)

    finestra = FinestraRaphael(raphael)
    finestra.resize(600, 300)
    finestra.show()
    qapp.processEvents()

    barra = finestra.chat.verticalScrollBar()
    barra.setValue(barra.maximum() // 2)
    posizione = barra.value()

    finestra.risposta_parziale = "nuovo testo"
    finestra._aggiorna_chat()

    assert barra.value() == posizione


def test_lo_streaming_aggiorna_solo_la_risposta_in_arrivo(qapp):
    raphael = RaphaelApp(ai_provider=MockAIProvider())
    raphael.history.add_message("user", "domanda vecchia")
    raphael.history.add_message("assistant", "risposta vecchia")
    finestra = FinestraRaphael(raphael)

    finestra.messaggi.append({"role": "user", "content": "domanda nuova"})
    finestra._imposta_attesa(True)
    finestra._prepara_risposta_in_arrivo()
    assert "sta scrivendo" in finestra.chat.toPlainText()

    for pezzo in ["Ecco:\n\n- uno\n", "- due\n\n", "## Titolo\n\n", "Fine."]:
        finestra._ricevi_pezzo(pezzo)
        finestra._aggiorna_se_serve()

    testo = finestra.chat.toPlainText()
    assert "risposta vecchia" in testo
    assert "domanda nuova" in testo
    assert "sta scrivendo" not in testo
    assert testo.rstrip().endswith("Fine.")
    assert "- Ecco:" not in finestra.chat.toMarkdown()