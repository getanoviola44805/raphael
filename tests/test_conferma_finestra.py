import time

import pytest
from PySide6.QtWidgets import QApplication

from ai.provider import AIProvider
from core.app import RaphaelApp
from core.azioni import RISCHIO_ALTO, Azione
from ui.finestra import FinestraRaphael


class ProviderCheAgisce(AIProvider):
    """Finge un modello che usa uno strumento con conferma."""

    def __init__(self, rischio="medio"):
        self.app = None
        self.fatto = []
        self.rischio = rischio

    def generate_response(self, prompt, history=None):
        return ""

    def generate_response_stream(self, prompt, history=None):
        def esegui():
            self.fatto.append("cartella")
            return "Ho creato la cartella Prova."

        esito = self.app.azioni.esegui(
            Azione(
                descrizione="Creare la cartella Prova",
                esegui=esegui,
                rischio=self.rischio,
                dettagli="Dettagli di prova",
            )
        )
        yield esito


@pytest.fixture(autouse=True)
def isola_history_file(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.json")


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def prepara(rischio="medio"):
    provider = ProviderCheAgisce(rischio)
    app = RaphaelApp(ai_provider=provider)
    provider.app = app
    finestra = FinestraRaphael(app)
    return finestra, provider


def aspetta(condizione, qapp, secondi=5):
    limite = time.time() + secondi
    while not condizione() and time.time() < limite:
        qapp.processEvents()
        time.sleep(0.01)
    return condizione()


def test_la_finestra_prende_il_posto_della_conferma(qapp):
    finestra, _ = prepara()

    assert finestra.raphael.azioni.chiedi_conferma == finestra.chiedi_conferma


def test_conferma_con_il_pulsante(qapp):
    finestra, provider = prepara()
    finestra.casella.setText("crea la cartella Prova")
    finestra.invia()

    assert aspetta(lambda: finestra.richiesta_conferma is not None, qapp)
    assert not finestra.barra_conferma.isHidden()
    assert finestra.testo_conferma.text() == "Creare la cartella Prova"
    assert finestra.dettagli_conferma.text() == "Dettagli di prova"
    assert "conferma" in finestra.stato.text()

    finestra.bottone_conferma.click()

    assert aspetta(lambda: not finestra.in_attesa, qapp)
    assert provider.fatto == ["cartella"]
    assert finestra.barra_conferma.isHidden()
    assert "Ho creato la cartella Prova." in finestra.messaggi[-1]["content"]


def test_annulla_con_il_pulsante(qapp):
    finestra, provider = prepara()
    finestra.casella.setText("crea la cartella Prova")
    finestra.invia()

    assert aspetta(lambda: finestra.richiesta_conferma is not None, qapp)
    finestra.bottone_rifiuta.click()

    assert aspetta(lambda: not finestra.in_attesa, qapp)
    assert provider.fatto == []
    assert "non ha confermato" in finestra.messaggi[-1]["content"]


def test_le_azioni_delicate_hanno_un_avviso(qapp):
    finestra, _ = prepara(RISCHIO_ALTO)
    finestra.casella.setText("fai una cosa delicata")
    finestra.invia()

    assert aspetta(lambda: finestra.richiesta_conferma is not None, qapp)
    assert "delicata" in finestra.titolo_conferma.text()

    finestra.bottone_rifiuta.click()
    aspetta(lambda: not finestra.in_attesa, qapp)


def test_chiudere_la_finestra_vale_come_annulla(qapp):
    finestra, provider = prepara()
    finestra.casella.setText("crea la cartella Prova")
    finestra.invia()

    assert aspetta(lambda: finestra.richiesta_conferma is not None, qapp)
    richiesta = finestra.richiesta_conferma
    finestra.close()

    assert richiesta.evento.is_set()
    assert richiesta.confermata is False
    aspetta(lambda: not finestra.in_attesa, qapp)
    assert provider.fatto == []