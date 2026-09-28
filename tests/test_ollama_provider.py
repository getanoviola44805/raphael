from unittest.mock import patch

from ai.ollama_provider import OllamaProvider


def test_ollama_provider_gestisce_connessione_assente():
    provider = OllamaProvider()

    with patch("ai.ollama_provider.ollama.chat", side_effect=ConnectionError):
        risposta = provider.generate_response("ciao")

    assert "Non riesco a contattare Ollama" in risposta