import logging
import threading
from unittest.mock import patch

import pytest

from ai.mock_provider import MockAIProvider
from ai.ollama_provider import MANTIENI_CARICATO, OllamaProvider
from core.app import STRUMENTI_CONCLUSIVI, RaphaelApp


@pytest.fixture(autouse=True)
def isola_history_file(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.json")


def pezzi_finti(*testi):
    for testo in testi:
        yield {"message": {"content": testo}, "done": False}
    yield {"message": {"content": ""}, "done": True, "done_reason": "stop"}


def chiamata_strumento(nome, argomenti):
    yield {
        "message": {
            "content": "",
            "tool_calls": [{"function": {"name": nome, "arguments": argomenti}}],
        },
        "done": True,
    }


def apri_programma(nome: str) -> str:
    """Apre un programma.

    Args:
        nome: Il nome del programma.
    """
    if nome == "Pippo":
        return "Non ho trovato nessun programma installato che si chiami 'Pippo'."
    return f"Ho aperto {nome}."


# ----------------------------------------------------- provider Ollama


def test_il_modello_resta_caricato_tra_una_domanda_e_l_altra():
    provider = OllamaProvider()

    with patch("ai.ollama_provider.ollama.chat", return_value=pezzi_finti("ok")) as chat:
        list(provider.generate_response_stream("ciao"))

    assert chat.call_args.kwargs["keep_alive"] == MANTIENI_CARICATO


def test_uno_strumento_conclusivo_riuscito_non_fa_il_secondo_giro():
    provider = OllamaProvider(
        strumenti=[apri_programma], strumenti_conclusivi={"apri_programma"}
    )

    with patch(
        "ai.ollama_provider.ollama.chat",
        side_effect=[chiamata_strumento("apri_programma", {"nome": "Discord"})],
    ) as chat:
        risposta = "".join(provider.generate_response_stream("apri discord"))

    assert chat.call_count == 1
    assert "⚙️ Ho aperto Discord." in risposta


def test_se_lo_strumento_fallisce_il_modello_fa_il_secondo_giro():
    provider = OllamaProvider(
        strumenti=[apri_programma], strumenti_conclusivi={"apri_programma"}
    )

    with patch(
        "ai.ollama_provider.ollama.chat",
        side_effect=[
            chiamata_strumento("apri_programma", {"nome": "Pippo"}),
            pezzi_finti("Non trovo Pippo: vuoi che lo cerchi?"),
        ],
    ) as chat:
        risposta = "".join(provider.generate_response_stream("apri pippo"))

    assert chat.call_count == 2
    assert risposta.endswith("vuoi che lo cerchi?")


def test_senza_strumenti_conclusivi_il_secondo_giro_resta():
    provider = OllamaProvider(strumenti=[apri_programma])

    with patch(
        "ai.ollama_provider.ollama.chat",
        side_effect=[
            chiamata_strumento("apri_programma", {"nome": "Discord"}),
            pezzi_finti("Fatto!"),
        ],
    ) as chat:
        list(provider.generate_response_stream("apri discord"))

    assert chat.call_count == 2


def test_prepara_carica_il_modello_con_le_stesse_istruzioni():
    provider = OllamaProvider(
        system_prompt="Sei Raphael.", context_length=16384, strumenti=[apri_programma]
    )

    with patch("ai.ollama_provider.ollama.chat", return_value={}) as chat:
        assert provider.prepara() is True

    argomenti = chat.call_args.kwargs
    # Stesso num_ctx delle domande vere, altrimenti Ollama ricaricherebbe il modello.
    assert argomenti["options"]["num_ctx"] == 16384
    assert argomenti["options"]["num_predict"] == 1
    assert argomenti["messages"][0] == {"role": "system", "content": "Sei Raphael."}
    assert argomenti["tools"] == [apri_programma]
    assert argomenti["keep_alive"] == MANTIENI_CARICATO


def test_prepara_non_si_rompe_se_ollama_e_spento():
    provider = OllamaProvider()

    with patch("ai.ollama_provider.ollama.chat", side_effect=ConnectionError):
        assert provider.prepara() is False


def test_il_registro_mostra_quanto_tempo_ci_ha_messo(caplog):
    provider = OllamaProvider()
    fine = {
        "message": {"content": ""},
        "done": True,
        "done_reason": "stop",
        "total_duration": 3_500_000_000,
        "load_duration": 2_000_000_000,
        "prompt_eval_duration": 1_000_000_000,
        "eval_duration": 500_000_000,
    }

    with caplog.at_level(logging.INFO, logger="ai.ollama_provider"):
        with patch("ai.ollama_provider.ollama.chat", return_value=iter([fine])):
            list(provider.generate_response_stream("ciao"))

    assert "durata=3.5s (caricamento 2.0s, lettura 1.0s, scrittura 0.5s)" in caplog.text


# --------------------------------------------------------- RaphaelApp


def app_con_strumenti_finti():
    app = RaphaelApp(ai_provider=MockAIProvider())
    aperti = []

    def apri_programma_finto(nome):
        aperti.append(nome)
        return f"Ho aperto {nome}."

    app._strumenti_rapidi["apri_programma"] = apri_programma_finto
    app.comandi_rapidi.trova_programma = lambda nome: {"nome": "Discord", "id": "d"}
    return app, aperti


def test_apri_viene_eseguito_subito_senza_il_modello():
    app, aperti = app_con_strumenti_finti()

    with patch.object(app.ai_router, "generate_response_stream") as modello:
        risposta = app.gestisci_comando("apri Discord")

    modello.assert_not_called()
    assert aperti == ["Discord"]
    assert risposta == "*⚙️ Ho aperto Discord.*"


def test_il_comando_rapido_finisce_nel_registro_e_nella_cronologia():
    app, _ = app_con_strumenti_finti()

    app.gestisci_comando("apri Discord")

    assert "Ho aperto Discord." in app.gestisci_comando("/registro")
    ultimi = app.history.get_recent_messages(4)
    assert ultimi[0] == {"role": "user", "content": "apri Discord"}
    assert ultimi[1]["content"] == "*⚙️ Ho aperto Discord.*"


def test_il_promemoria_rapido_finisce_davvero_in_agenda():
    app = RaphaelApp(ai_provider=MockAIProvider())

    risposta = app.gestisci_comando("ricordami tra 20 secondi di bere un bicchiere d'acqua")

    assert "⏰ Ti avviserò" in risposta
    assert [voce["testo"] for voce in app.agenda.in_attesa()] == ["Bere un bicchiere d'acqua"]


def test_le_domande_normali_vanno_ancora_al_modello():
    app, aperti = app_con_strumenti_finti()

    with patch.object(
        app.ai_router, "generate_response_stream", return_value=iter(["Ciao!"])
    ) as modello:
        risposta = app.gestisci_comando("raccontami una barzelletta")

    modello.assert_called_once()
    assert risposta == "Ciao!"
    assert aperti == []


def test_col_ragionamento_attivo_decide_sempre_il_modello():
    app, aperti = app_con_strumenti_finti()

    with patch.object(
        app.ai_router, "generate_response_stream", return_value=iter(["Ok"])
    ) as modello:
        list(app.gestisci_comando_stream("apri Discord", ragiona=True))

    modello.assert_called_once()
    assert aperti == []


def test_app_usa_gli_strumenti_conclusivi():
    app = RaphaelApp()

    assert app.ai_router.provider.strumenti_conclusivi == STRUMENTI_CONCLUSIVI
    assert {"apri_programma", "imposta_promemoria"} <= STRUMENTI_CONCLUSIVI


def test_prepara_in_background_carica_modello_e_programmi(monkeypatch):
    app = RaphaelApp(ai_provider=MockAIProvider())
    fatti = []
    finito = threading.Event()

    def prepara_modello():
        fatti.append("modello")
        finito.set()

    app.ai_router.provider.prepara = prepara_modello
    monkeypatch.setattr("core.app.prepara_elenco_programmi", lambda: fatti.append("programmi"))

    app.prepara_in_background()

    assert finito.wait(2)
    assert "modello" in fatti