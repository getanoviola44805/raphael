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