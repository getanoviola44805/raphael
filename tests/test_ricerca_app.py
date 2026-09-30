import pytest

from ai.mock_provider import MockAIProvider
from core.app import RaphaelApp


RISULTATI_FINTI = [
    {
        "titolo": "Meteo Catania",
        "link": "https://esempio.it/meteo",
        "estratto": "Domani sole e 25 gradi.",
    },
]


@pytest.fixture(autouse=True)
def isola_history_file(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.json")


def crea_app(risultati):
    ricerche_fatte = []

    def ricerca_finta(domanda, max_risultati):
        ricerche_fatte.append(domanda)
        return risultati

    app = RaphaelApp(ai_provider=MockAIProvider(), ricerca_web=ricerca_finta)
    return app, ricerche_fatte


def test_cerca_usa_i_risultati_e_mostra_le_fonti():
    app, ricerche_fatte = crea_app(RISULTATI_FINTI)

    risposta = app.gestisci_comando("/cerca meteo Catania domani")

    assert ricerche_fatte == ["meteo Catania domani"]
    assert "Domani sole e 25 gradi." in risposta
    assert "Fonti" in risposta
    assert "https://esempio.it/meteo" in risposta


def test_cerca_senza_testo_spiega_come_si_usa():
    app, ricerche_fatte = crea_app(RISULTATI_FINTI)

    risposta = app.gestisci_comando("/cerca")

    assert ricerche_fatte == []
    assert "/cerca meteo Catania domani" in risposta


def test_cerca_senza_risultati_avvisa_l_utente():
    app, _ = crea_app([])

    risposta = app.gestisci_comando("/cerca qualcosa")

    assert "Non sono riuscito a cercare sul web" in risposta


def test_cerca_salva_la_domanda_originale_nella_cronologia():
    app, _ = crea_app(RISULTATI_FINTI)

    app.gestisci_comando("/cerca meteo Catania domani")

    messaggi = app.history.get_messages()
    assert messaggi[0]["content"] == "/cerca meteo Catania domani"
    assert messaggi[1]["role"] == "assistant"