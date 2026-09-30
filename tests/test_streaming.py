import pytest

from ai.provider import AIProvider
from core.app import RaphaelApp


class ProviderAPezzi(AIProvider):
    def generate_response(self, prompt, history=None):
        return "Risposta intera"

    def generate_response_stream(self, prompt, history=None):
        yield "Uno, "
        yield "due, "
        yield "tre."


@pytest.fixture(autouse=True)
def isola_history_file(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.json")


def test_gestisci_comando_stream_restituisce_i_pezzi():
    app = RaphaelApp(ai_provider=ProviderAPezzi())

    pezzi = list(app.gestisci_comando_stream("conta fino a tre"))

    assert pezzi == ["Uno, ", "due, ", "tre."]


def test_la_risposta_completa_finisce_nella_cronologia():
    app = RaphaelApp(ai_provider=ProviderAPezzi())

    list(app.gestisci_comando_stream("conta fino a tre"))

    messaggi = app.history.get_messages()
    assert messaggi[-2] == {"role": "user", "content": "conta fino a tre"}
    assert messaggi[-1] == {"role": "assistant", "content": "Uno, due, tre."}


def test_gestisci_comando_restituisce_la_risposta_intera():
    app = RaphaelApp(ai_provider=ProviderAPezzi())

    assert app.gestisci_comando("conta fino a tre") == "Uno, due, tre."


def test_i_comandi_arrivano_in_un_solo_pezzo():
    app = RaphaelApp(ai_provider=ProviderAPezzi())

    pezzi = list(app.gestisci_comando_stream("ciao"))

    assert pezzi == ["Ciao! Sono Raphael."]


def test_la_ricerca_in_streaming_aggiunge_le_fonti_alla_fine():
    risultati = [
        {"titolo": "Sito", "link": "https://esempio.it", "estratto": "Testo"},
    ]
    app = RaphaelApp(
        ai_provider=ProviderAPezzi(),
        ricerca_web=lambda domanda, massimo: risultati,
    )

    pezzi = list(app.gestisci_comando_stream("/cerca qualcosa"))

    assert pezzi[:3] == ["Uno, ", "due, ", "tre."]
    assert "https://esempio.it" in pezzi[-1]

class ProviderCheRegistra(AIProvider):
    def __init__(self):
        self.opzioni = None

    def generate_response(self, prompt, history=None):
        return "ok"

    def generate_response_stream(self, prompt, history=None, **opzioni):
        self.opzioni = opzioni
        yield "ok"


def test_senza_opzioni_il_provider_non_riceve_niente_in_piu():
    provider = ProviderCheRegistra()
    app = RaphaelApp(ai_provider=provider)

    list(app.gestisci_comando_stream("domanda"))

    assert provider.opzioni == {}


def test_il_ragionamento_arriva_al_provider():
    provider = ProviderCheRegistra()
    app = RaphaelApp(ai_provider=provider)

    list(app.gestisci_comando_stream("domanda", ragiona=True))

    assert provider.opzioni == {"ragiona": True}


def test_le_immagini_arrivano_al_provider_e_restano_nella_cronologia():
    provider = ProviderCheRegistra()
    app = RaphaelApp(ai_provider=provider)

    list(app.gestisci_comando_stream("cosa vedi?", immagini=["C:/foto/esercizio.jpg"]))

    assert provider.opzioni == {"immagini": ["C:/foto/esercizio.jpg"]}
    ultima_domanda = app.history.get_messages()[-2]["content"]
    assert ultima_domanda == "cosa vedi?\n\n[Immagine allegata: esercizio.jpg]"


def test_un_comando_con_immagine_va_comunque_al_modello():
    provider = ProviderCheRegistra()
    app = RaphaelApp(ai_provider=provider)

    risposta = "".join(app.gestisci_comando_stream("ciao", immagini=["foto.jpg"]))

    assert risposta == "ok"