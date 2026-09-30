from unittest.mock import patch

import httpx

from ai.ollama_provider import OllamaProvider


def test_ollama_provider_gestisce_connessione_assente():
    provider = OllamaProvider()

    with patch("ai.ollama_provider.ollama.chat", side_effect=ConnectionError):
        risposta = provider.generate_response("ciao")

    assert "Non riesco a contattare Ollama" in risposta


def test_ollama_provider_invia_system_prompt():
    provider = OllamaProvider(system_prompt="Sei Raphael.")
    risposta_finta = {"message": {"content": "Ciao!"}}

    with patch("ai.ollama_provider.ollama.chat", return_value=risposta_finta) as chat_finto:
        risposta = provider.generate_response("ciao")

    messaggi_inviati = chat_finto.call_args.kwargs["messages"]

    assert messaggi_inviati[0] == {"role": "system", "content": "Sei Raphael."}
    assert messaggi_inviati[1] == {"role": "user", "content": "ciao"}
    assert risposta == "Ciao!"


def pezzi_finti(*testi):
    for testo in testi:
        yield {"message": {"content": testo}, "done": False}
    yield {"message": {"content": ""}, "done": True, "done_reason": "stop"}


def test_stream_restituisce_i_pezzi_in_ordine():
    provider = OllamaProvider()

    with patch(
        "ai.ollama_provider.ollama.chat",
        return_value=pezzi_finti("Ciao", ", come ", "stai?"),
    ):
        pezzi = list(provider.generate_response_stream("ciao"))

    assert pezzi == ["Ciao", ", come ", "stai?"]


def test_stream_chiede_lo_streaming_a_ollama():
    provider = OllamaProvider(system_prompt="Sei Raphael.")

    with patch(
        "ai.ollama_provider.ollama.chat",
        return_value=pezzi_finti("ok"),
    ) as chat_finto:
        list(provider.generate_response_stream("ciao"))

    assert chat_finto.call_args.kwargs["stream"] is True
    assert chat_finto.call_args.kwargs["messages"][0]["role"] == "system"


def test_stream_gestisce_ollama_spento():
    provider = OllamaProvider()

    def connessione_rifiutata():
        raise httpx.ConnectError("connessione rifiutata")
        yield

    with patch(
        "ai.ollama_provider.ollama.chat",
        return_value=connessione_rifiutata(),
    ):
        pezzi = list(provider.generate_response_stream("ciao"))

    assert len(pezzi) == 1
    assert "Non riesco a contattare Ollama" in pezzi[0]


def test_stream_vuoto_avvisa_l_utente():
    provider = OllamaProvider()

    with patch("ai.ollama_provider.ollama.chat", return_value=pezzi_finti()):
        pezzi = list(provider.generate_response_stream("ciao"))

    assert len(pezzi) == 1
    assert "Non sono riuscito a generare una risposta" in pezzi[0]

def chiamata_strumento(nome, argomenti):
    yield {
        "message": {
            "content": "",
            "tool_calls": [{"function": {"name": nome, "arguments": argomenti}}],
        },
        "done": False,
    }
    yield {"message": {"content": ""}, "done": True, "done_reason": "stop"}


def test_stream_esegue_lo_strumento_richiesto_dal_modello():
    aperti = []

    def apri_programma(nome: str) -> str:
        """Apre un programma.

        Args:
            nome: Il nome del programma.
        """
        aperti.append(nome)
        return f"Ho aperto {nome}."

    provider = OllamaProvider(strumenti=[apri_programma])

    with patch(
        "ai.ollama_provider.ollama.chat",
        side_effect=[
            chiamata_strumento("apri_programma", {"nome": "Chrome"}),
            pezzi_finti("Fatto, ", "Chrome è aperto."),
        ],
    ) as chat_finto:
        pezzi = list(provider.generate_response_stream("apri chrome"))

    assert aperti == ["Chrome"]
    assert "".join(pezzi).endswith("Fatto, Chrome è aperto.")
    assert "Ho aperto Chrome." in "".join(pezzi)

    secondo_giro = chat_finto.call_args_list[1].kwargs["messages"]
    assert secondo_giro[-1] == {
        "role": "tool",
        "content": "Ho aperto Chrome.",
        "tool_name": "apri_programma",
    }
    assert chat_finto.call_args_list[0].kwargs["tools"] == [apri_programma]


def test_stream_gestisce_uno_strumento_sconosciuto():
    provider = OllamaProvider(strumenti=[])

    with patch(
        "ai.ollama_provider.ollama.chat",
        side_effect=[
            chiamata_strumento("formatta_disco", {}),
            pezzi_finti("Non posso farlo."),
        ],
    ):
        pezzi = list(provider.generate_response_stream("formatta il disco"))

    assert "non esiste" in "".join(pezzi)
    assert "".join(pezzi).endswith("Non posso farlo.")


def test_stream_riprova_senza_strumenti_se_il_modello_non_li_supporta():
    import ollama as libreria_ollama

    def data_e_ora() -> str:
        """Restituisce la data."""
        return "oggi"

    def non_supportato():
        raise libreria_ollama.ResponseError("model does not support tools", 400)
        yield

    provider = OllamaProvider(strumenti=[data_e_ora])

    with patch(
        "ai.ollama_provider.ollama.chat",
        side_effect=[non_supportato(), pezzi_finti("Ciao!")],
    ) as chat_finto:
        pezzi = list(provider.generate_response_stream("ciao"))

    assert pezzi == ["Ciao!"]
    assert "tools" not in chat_finto.call_args_list[1].kwargs