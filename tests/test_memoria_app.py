from unittest.mock import patch

import pytest

from ai.mock_provider import MockAIProvider
from ai.ollama_provider import OllamaProvider
from core.app import RaphaelApp
from memory.memoria import MemoriaLungoTermine


@pytest.fixture
def app(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.json")

    return RaphaelApp(ai_provider=MockAIProvider())


def test_comando_ricorda(app):
    risposta = app.gestisci_comando("/ricorda preferisco risposte brevi")

    assert risposta == "Ho memorizzato: preferisco risposte brevi"
    assert app.memoria.elenca() == ["preferisco risposte brevi"]


def test_comando_ricorda_senza_testo(app):
    risposta = app.gestisci_comando("/ricorda")

    assert "dopo /ricorda" in risposta
    assert app.memoria.elenca() == []


def test_comando_memoria(app):
    app.gestisci_comando("/ricorda Si chiama Gaetano")

    risposta = app.gestisci_comando("/memoria")

    assert "1. Si chiama Gaetano" in risposta


def test_comando_dimentica(app):
    app.gestisci_comando("/ricorda Si chiama Gaetano")

    risposta = app.gestisci_comando("/dimentica 1")

    assert risposta == "Ho dimenticato: Si chiama Gaetano"
    assert app.memoria.elenca() == []


def test_comando_dimentica_tutto(app):
    app.gestisci_comando("/ricorda Uno")
    app.gestisci_comando("/ricorda Due")

    risposta = app.gestisci_comando("/dimentica tutto")

    assert risposta == "Ho dimenticato tutto (2 ricordi)."


def test_i_comandi_memoria_non_vanno_al_modello(app):
    risposta = app.gestisci_comando("/memoria")

    assert "Risposta simulata" not in risposta


def test_la_memoria_resta_tra_un_avvio_e_l_altro(app):
    app.gestisci_comando("/ricorda Vive a Catania")

    app2 = RaphaelApp(ai_provider=MockAIProvider())

    assert app2.memoria.elenca() == ["Vive a Catania"]


def test_il_prompt_di_sistema_contiene_i_ricordi(app):
    from core import config

    assert app._prompt_di_sistema() == config.SYSTEM_PROMPT

    app.memoria.aggiungi("Si chiama Gaetano")

    prompt = app._prompt_di_sistema()
    assert prompt.startswith(config.SYSTEM_PROMPT)
    assert "- Si chiama Gaetano" in prompt


def test_il_provider_predefinito_ha_gli_strumenti_memoria(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.json")

    app = RaphaelApp()
    nomi = [strumento.__name__ for strumento in app.ai_router.provider.strumenti]

    assert "ricorda" in nomi
    assert "dimentica" in nomi


def test_il_provider_rilegge_il_prompt_a_ogni_domanda():
    memoria = MemoriaLungoTermine()
    provider = OllamaProvider(
        system_prompt=lambda: "Sei Raphael.\n\n" + memoria.testo_per_prompt()
    )
    risposta_finta = {"message": {"content": "Ok"}}

    with patch(
        "ai.ollama_provider.ollama.chat", return_value=risposta_finta
    ) as chat_finto:
        provider.generate_response("ciao")
        primo_prompt = chat_finto.call_args.kwargs["messages"][0]["content"]

        memoria.aggiungi("Si chiama Gaetano")
        provider.generate_response("ciao")
        secondo_prompt = chat_finto.call_args.kwargs["messages"][0]["content"]

    assert "Gaetano" not in primo_prompt
    assert "- Si chiama Gaetano" in secondo_prompt


def test_lo_strumento_ricorda_funziona_dentro_il_flusso(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.json")
    app = RaphaelApp()

    def risposte_finte(**kwargs):
        if kwargs["messages"][-1]["role"] == "user":
            yield {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "ricorda",
                                "arguments": {"informazione": "Si chiama Gaetano"},
                            }
                        }
                    ],
                },
                "done": True,
            }
        else:
            yield {"message": {"content": "Piacere, Gaetano!"}, "done": True}

    with patch("ai.ollama_provider.ollama.chat", side_effect=risposte_finte):
        risposta = app.gestisci_comando("Mi chiamo Gaetano")

    assert "Ho memorizzato: Si chiama Gaetano" in risposta
    assert "Piacere, Gaetano!" in risposta
    assert app.memoria.elenca() == ["Si chiama Gaetano"]