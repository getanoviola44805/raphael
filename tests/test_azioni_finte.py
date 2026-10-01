"""Il modello non deve poter fingere di aver fatto un'azione.

Le righe "⚙️ ..." le scrive solo il programma quando uno strumento viene usato
davvero: non devono finire nella cronologia mandata al modello, e se il modello
prova a scriverle da solo il simbolo viene tolto.
"""

from unittest.mock import patch

from ai.ollama_provider import OllamaProvider, pulisci_risposta_precedente


def pezzi_finti(*testi):
    for testo in testi:
        yield {"message": {"content": testo}, "done": False}
    yield {"message": {"content": ""}, "done": True, "done_reason": "stop"}


def test_le_righe_degli_strumenti_spariscono_dalle_vecchie_risposte():
    testo = (
        "Certo!\n\n*⚙️ Ho aperto https://www.amazon.it nel browser.*\n\n"
        "Buono shopping.\n\n⚙️ Riapro Zalando: zalando.it\n"
    )

    pulito = pulisci_risposta_precedente(testo)

    assert "⚙" not in pulito
    assert "amazon" not in pulito.lower()
    assert "Certo!" in pulito
    assert "Buono shopping." in pulito


def test_una_risposta_fatta_solo_di_strumenti_non_resta_vuota():
    assert pulisci_risposta_precedente("*⚙️ Ho creato la cartella X.*") == "Fatto."


def test_il_modello_non_vede_le_righe_degli_strumenti():
    provider = OllamaProvider(system_prompt="Sei Raphael.")
    cronologia = [
        {"role": "user", "content": "apri amazon"},
        {"role": "assistant", "content": "Ecco!\n\n*⚙️ Ho aperto amazon.it nel browser.*"},
        {"role": "user", "content": "*⚙️ i messaggi dell'utente restano com'erano*"},
    ]

    with patch(
        "ai.ollama_provider.ollama.chat", return_value=pezzi_finti("ok")
    ) as chat_finto:
        list(provider.generate_response_stream("apri zalando", cronologia))

    inviati = chat_finto.call_args.kwargs["messages"]
    assert inviati[2] == {"role": "assistant", "content": "Ecco!"}
    assert "⚙" in inviati[3]["content"]


def test_se_il_modello_scrive_l_ingranaggio_da_solo_viene_tolto():
    provider = OllamaProvider()

    with patch(
        "ai.ollama_provider.ollama.chat",
        return_value=pezzi_finti("Sto aprendo Amazon!\n\n*", "⚙", "️ Apro Amazon*"),
    ):
        risposta = "".join(provider.generate_response_stream("apri amazon"))

    assert "\u2699" not in risposta
    assert "Apro Amazon" in risposta


def test_l_ingranaggio_vero_resta_quando_lo_strumento_viene_usato():
    def apri_sito(indirizzo: str) -> str:
        """Apre un sito.

        Args:
            indirizzo: L'indirizzo.
        """
        return f"Ho aperto {indirizzo} nel browser."

    provider = OllamaProvider(strumenti=[apri_sito])

    def risposte_finte(**kwargs):
        if kwargs["messages"][-1]["role"] == "user":
            yield {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "apri_sito", "arguments": {"indirizzo": "amazon.it"}}}
                    ],
                },
                "done": True,
            }
        else:
            yield {"message": {"content": "Fatto!"}, "done": True}

    with patch("ai.ollama_provider.ollama.chat", side_effect=risposte_finte):
        risposta = "".join(provider.generate_response_stream("apri amazon"))

    assert "⚙️ Ho aperto amazon.it nel browser." in risposta