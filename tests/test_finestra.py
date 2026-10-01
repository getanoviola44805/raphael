import time

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from ai.mock_provider import MockAIProvider
from ai.provider import AIProvider
from core.app import RaphaelApp
from ui.componenti import MessaggioRaphael, MessaggioUtente
from ui.finestra import LATO_MASSIMO_IMMAGINE, FinestraRaphael, salva_immagine_ridotta


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


def test_la_finestra_vuota_mostra_il_benvenuto(qapp):
    raphael = RaphaelApp(ai_provider=MockAIProvider())
    finestra = FinestraRaphael(raphael)

    assert not finestra.benvenuto.isHidden()
    assert finestra.widget_messaggi() == []


def test_la_finestra_mostra_la_cronologia(qapp):
    raphael = RaphaelApp(ai_provider=MockAIProvider())
    raphael.history.add_message("user", "messaggio vecchio")
    raphael.history.add_message("assistant", "risposta vecchia")

    finestra = FinestraRaphael(raphael)
    messaggi = finestra.widget_messaggi()

    assert isinstance(messaggi[0], MessaggioUtente)
    assert isinstance(messaggi[1], MessaggioRaphael)
    assert "messaggio vecchio" in finestra.testo_della_chat()
    assert "risposta vecchia" in finestra.testo_della_chat()
    assert finestra.benvenuto.isHidden()


def test_le_risposte_mostrano_le_formule_senza_latex(qapp):
    raphael = RaphaelApp(ai_provider=MockAIProvider())
    raphael.history.add_message("assistant", r"La formula è $\omega = 2\pi f$")

    finestra = FinestraRaphael(raphael)

    assert "ω" in finestra.testo_della_chat()
    assert "$" not in finestra.testo_della_chat()


def test_la_finestra_invia_e_riceve(qapp):
    raphael = RaphaelApp(ai_provider=MockAIProvider())
    finestra = FinestraRaphael(raphael)

    finestra.casella.setText("ciao")
    finestra.invia()
    aspetta_risposta(finestra, qapp)

    assert not finestra.in_attesa
    assert "Ciao! Sono Raphael." in finestra.testo_della_chat()
    assert finestra.casella.isEnabled()
    assert finestra.casella.text() == ""
    assert finestra.attesa.isHidden()


def test_durante_l_attesa_gira_il_cerchio(qapp):
    raphael = RaphaelApp(ai_provider=MockAIProvider())
    finestra = FinestraRaphael(raphael)

    finestra._imposta_attesa(True)

    assert not finestra.attesa.isHidden()
    assert finestra.attesa.cerchio.sta_girando()
    assert "sta pensando" in finestra.stato.text()
    assert not finestra.casella.isEnabled()

    finestra._imposta_attesa(False)

    assert finestra.attesa.isHidden()
    assert not finestra.attesa.cerchio.sta_girando()


def test_la_finestra_unisce_i_pezzi_della_risposta(qapp):
    raphael = RaphaelApp(ai_provider=ProviderAPezzi())
    finestra = FinestraRaphael(raphael)

    finestra.casella.setText("raccontami qualcosa")
    finestra.invia()
    aspetta_risposta(finestra, qapp)

    assert "Prima parte, seconda parte." in finestra.testo_della_chat()
    assert finestra.messaggi[-1]["content"] == "Prima parte, seconda parte."
    assert finestra.widget_messaggi()[-1].bottone_copia.isVisibleTo(finestra)


def test_lo_streaming_aggiorna_solo_la_risposta_in_arrivo(qapp):
    raphael = RaphaelApp(ai_provider=MockAIProvider())
    raphael.history.add_message("user", "domanda vecchia")
    raphael.history.add_message("assistant", "risposta vecchia")
    finestra = FinestraRaphael(raphael)
    vecchia = finestra.widget_messaggi()[1]

    finestra._imposta_attesa(True)
    for pezzo in ["Ecco:\n\n- uno\n", "- due\n\n", "## Titolo\n\n", "Fine."]:
        finestra._ricevi_pezzo(pezzo)
        finestra._aggiorna_se_serve()

    in_arrivo = finestra.widget_messaggi()[-1]
    assert in_arrivo is not vecchia
    assert vecchia.testo_semplice() == "risposta vecchia"
    assert in_arrivo.testo_semplice().rstrip().endswith("Fine.")
    assert "- Ecco:" not in in_arrivo.testo.toMarkdown()


def test_aggiornare_la_chat_non_sposta_chi_sta_rileggendo(qapp):
    raphael = RaphaelApp(ai_provider=MockAIProvider())
    for numero in range(30):
        raphael.history.add_message("user", f"domanda {numero}")
        raphael.history.add_message("assistant", "risposta lunga\n\n" * 5)

    finestra = FinestraRaphael(raphael)
    finestra.resize(600, 400)
    finestra.show()
    for _ in range(5):
        qapp.processEvents()

    barra = finestra.area.verticalScrollBar()
    barra.setValue(barra.maximum() // 2)
    posizione = barra.value()

    finestra._imposta_attesa(True)
    finestra._ricevi_pezzo("nuovo testo\n\n" * 10)
    finestra._aggiorna_se_serve()
    qapp.processEvents()

    assert barra.value() == posizione
    finestra._imposta_attesa(False)


def test_la_chat_segue_la_risposta_se_si_e_in_fondo(qapp):
    raphael = RaphaelApp(ai_provider=MockAIProvider())
    for numero in range(10):
        raphael.history.add_message("user", f"domanda {numero}")
        raphael.history.add_message("assistant", "risposta\n\n" * 5)

    finestra = FinestraRaphael(raphael)
    finestra.resize(600, 400)
    finestra.show()
    qapp.processEvents()
    finestra.vai_in_fondo()

    finestra._imposta_attesa(True)
    finestra._ricevi_pezzo("riga\n\n" * 30)
    finestra._aggiorna_se_serve()
    for _ in range(5):
        qapp.processEvents()

    barra = finestra.area.verticalScrollBar()
    assert barra.value() == barra.maximum()
    finestra._imposta_attesa(False)


def test_invio_con_il_tasto_e_a_capo_con_maiuscolo(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    raphael = RaphaelApp(ai_provider=MockAIProvider())
    finestra = FinestraRaphael(raphael)

    finestra.casella.setText("prima riga")
    QTest.keyClick(finestra.casella, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    QTest.keyClicks(finestra.casella, "seconda riga")
    assert finestra.casella.text() == "prima riga\nseconda riga"

    QTest.keyClick(finestra.casella, Qt.Key.Key_Return)
    aspetta_risposta(finestra, qapp)

    assert finestra.messaggi[0]["content"] == "prima riga\nseconda riga"


def test_il_tasto_copia_copia_la_risposta(qapp):
    raphael = RaphaelApp(ai_provider=MockAIProvider())
    raphael.history.add_message("assistant", "**Testo** da copiare")
    finestra = FinestraRaphael(raphael)

    finestra.widget_messaggi()[0].copia()

    assert QApplication.clipboard().text() == "**Testo** da copiare"


class ProviderCheRegistra(AIProvider):
    def __init__(self):
        self.opzioni = None

    def generate_response(self, prompt, history=None):
        return "ok"

    def generate_response_stream(self, prompt, history=None, **opzioni):
        self.opzioni = opzioni
        yield "ok"


def immagine_di_prova(larghezza, altezza):
    immagine = QImage(larghezza, altezza, QImage.Format.Format_RGB32)
    immagine.fill(QColor("steelblue"))
    return immagine


def test_le_immagini_grandi_vengono_rimpicciolite(qapp, tmp_path):
    percorso = salva_immagine_ridotta(immagine_di_prova(4000, 3000), tmp_path, "foto")

    salvata = QImage(str(percorso))
    assert percorso.exists()
    assert max(salvata.width(), salvata.height()) == LATO_MASSIMO_IMMAGINE
    assert salvata.width() > salvata.height()


def test_le_immagini_piccole_restano_uguali(qapp, tmp_path):
    percorso = salva_immagine_ridotta(immagine_di_prova(800, 600), tmp_path, "foto")

    salvata = QImage(str(percorso))
    assert (salvata.width(), salvata.height()) == (800, 600)


def test_il_bottone_ragiona_attiva_il_ragionamento(qapp, tmp_path):
    provider = ProviderCheRegistra()
    finestra = FinestraRaphael(RaphaelApp(ai_provider=provider), tmp_path)

    finestra.bottone_ragiona.setChecked(True)
    finestra.casella.setText("risolvi questo esercizio")
    finestra.invia()
    aspetta_risposta(finestra, qapp)

    assert provider.opzioni == {"ragiona": True}


def test_invio_di_un_immagine_senza_testo(qapp, tmp_path):
    provider = ProviderCheRegistra()
    raphael = RaphaelApp(ai_provider=provider)
    finestra = FinestraRaphael(raphael, tmp_path)

    finestra.allega_immagine(immagine_di_prova(100, 100), "esercizio")
    allegato = finestra.allegato
    assert "esercizio" in finestra.etichetta_allegato.text()
    assert not finestra.chip_allegato.isHidden()
    assert not finestra.miniatura.pixmap().isNull()

    finestra.invia()
    aspetta_risposta(finestra, qapp)

    assert provider.opzioni == {"immagini": [allegato]}
    assert finestra.allegato is None
    domanda = raphael.history.get_messages()[-2]["content"]
    assert domanda.startswith("Descrivi questa immagine.")
    assert "[Immagine allegata:" in domanda


def test_togli_allegato(qapp, tmp_path):
    finestra = FinestraRaphael(RaphaelApp(ai_provider=MockAIProvider()), tmp_path)

    finestra.allega_immagine(immagine_di_prova(50, 50), "prova")
    finestra.togli_allegato()

    assert finestra.allegato is None
    assert finestra.etichetta_allegato.text() == ""
    assert finestra.chip_allegato.isHidden()


def test_ctrl_v_con_un_immagine_negli_appunti_la_allega(qapp, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    finestra = FinestraRaphael(RaphaelApp(ai_provider=MockAIProvider()), tmp_path)
    QApplication.clipboard().setImage(immagine_di_prova(200, 100))

    QTest.keyClick(finestra.casella, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)

    assert finestra.allegato is not None
    assert finestra.allegato.name.startswith("incollata_")
    assert finestra.casella.text() == ""