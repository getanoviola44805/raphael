from unittest.mock import patch

import pytest

from ai.mock_provider import MockAIProvider
from core.app import RaphaelApp


@pytest.fixture
def app(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.json")
    return RaphaelApp(ai_provider=MockAIProvider())


def test_comando_registro_vuoto(app):
    assert "non ho fatto nessuna azione" in app.gestisci_comando("/registro").lower()


def test_comando_registro_giorno_sbagliato(app):
    assert "Non ho capito" in app.gestisci_comando("/registro boh")


def test_comando_annulla_senza_azioni(app):
    assert "Non c'è nessuna azione" in app.gestisci_comando("/annulla")


def test_comando_sola_lettura(app):
    assert "attivata" in app.gestisci_comando("/solalettura on")
    assert app.azioni.sola_lettura is True
    assert "attiva 🔒" in app.gestisci_comando("/solalettura")
    assert "disattivata" in app.gestisci_comando("/solalettura off")
    assert app.azioni.sola_lettura is False


def test_il_provider_predefinito_ha_gli_strumenti_azioni(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.json")
    app = RaphaelApp()
    nomi = {strumento.__name__ for strumento in app.ai_router.provider.strumenti}

    assert {
        "crea_cartella",
        "salva_testo",
        "annulla_ultima_azione",
        "azioni_recenti",
        "attiva_sola_lettura",
    } <= nomi


def test_gli_strumenti_finiscono_nel_registro(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.json")
    app = RaphaelApp()

    def risposte_finte(**kwargs):
        if kwargs["messages"][-1]["role"] == "user":
            yield {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "data_e_ora", "arguments": {}}},
                        {"function": {"name": "ricorda", "arguments": {"informazione": "Vive a Catania"}}},
                    ],
                },
                "done": True,
            }
        else:
            yield {"message": {"content": "Fatto."}, "done": True}

    with patch("ai.ollama_provider.ollama.chat", side_effect=risposte_finte):
        app.gestisci_comando("Ricordati che vivo a Catania")

    riepilogo = app.gestisci_comando("/registro")

    assert "Ho memorizzato: Vive a Catania" in riepilogo
    assert "Oggi è" not in riepilogo