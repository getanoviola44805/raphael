from unittest.mock import patch

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