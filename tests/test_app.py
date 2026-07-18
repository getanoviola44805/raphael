import pytest

from ai.mock_provider import MockAIProvider
from core.app import RaphaelApp


@pytest.fixture
def app(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.json")

    return RaphaelApp(ai_provider=MockAIProvider())


def test_comando_ciao(app):
    risposta = app.gestisci_comando("ciao")

    assert risposta == "Ciao! Sono Raphael."


def test_comando_versione(app):
    risposta = app.gestisci_comando("versione")

    assert risposta == "Sto usando la versione 0.1.0."


def test_comando_sconosciuto(app):
    risposta = app.gestisci_comando("qualcosa")

    assert risposta == "Risposta simulata a: qualcosa"


def test_history_registra_messaggi(app):
    app.gestisci_comando("ciao")

    messaggi = app.history.get_messages()

    assert messaggi[0]["role"] == "user"
    assert messaggi[0]["content"] == "ciao"
    assert messaggi[1]["role"] == "assistant"


def test_app_salva_e_ricarica_history(app, tmp_path, monkeypatch):
    from core import config

    app.gestisci_comando("ciao")
    app.history.save_to_file(config.HISTORY_FILE)

    app2 = RaphaelApp(ai_provider=MockAIProvider())
    assert len(app2.history.get_messages()) == 2
    assert app2.history.get_messages()[0]["content"] == "ciao"