from unittest.mock import patch

from tools.web_search import (
    cerca_sul_web,
    formatta_fonti,
    prepara_domanda_con_risultati,
)


RISULTATI_FINTI = [
    {
        "titolo": "Meteo Catania",
        "link": "https://esempio.it/meteo",
        "estratto": "Domani sole e 25 gradi.",
    },
    {
        "titolo": "Previsioni Sicilia",
        "link": "https://esempio.it/sicilia",
        "estratto": "Tempo stabile su tutta l'isola.",
    },
]


def test_cerca_sul_web_converte_i_risultati():
    risultati_ddgs = [
        {"title": "Titolo", "href": "https://esempio.it", "body": "Testo"},
    ]

    with patch("tools.web_search.DDGS") as ddgs_finto:
        ddgs_finto.return_value.text.return_value = risultati_ddgs
        risultati = cerca_sul_web("prova")

    assert risultati == [
        {"titolo": "Titolo", "link": "https://esempio.it", "estratto": "Testo"}
    ]


def test_cerca_sul_web_gestisce_gli_errori():
    with patch("tools.web_search.DDGS") as ddgs_finto:
        ddgs_finto.return_value.text.side_effect = Exception("nessuna connessione")
        risultati = cerca_sul_web("prova")

    assert risultati == []


def test_prepara_domanda_contiene_risultati_e_domanda():
    testo = prepara_domanda_con_risultati("che tempo fa?", RISULTATI_FINTI)

    assert "[1] Meteo Catania" in testo
    assert "Domani sole e 25 gradi." in testo
    assert "[2] Previsioni Sicilia" in testo
    assert "che tempo fa?" in testo


def test_formatta_fonti_elenca_i_link():
    fonti = formatta_fonti(RISULTATI_FINTI)

    assert "1. Meteo Catania (https://esempio.it/meteo)" in fonti
    assert "2. Previsioni Sicilia (https://esempio.it/sicilia)" in fonti

def test_ricerca_web_restituisce_i_risultati_con_i_link(monkeypatch):
    from tools import web_search

    monkeypatch.setattr(
        web_search, "cerca_sul_web", lambda domanda: RISULTATI_FINTI
    )

    esito = web_search.ricerca_web("meteo Catania")

    assert esito.startswith("Ho cercato sul web: 'meteo Catania' (2 risultati).")
    assert "[1] Meteo Catania" in esito
    assert "Link: https://esempio.it/meteo" in esito
    assert "Domani sole e 25 gradi." in esito


def test_ricerca_web_senza_risultati(monkeypatch):
    from tools import web_search

    monkeypatch.setattr(web_search, "cerca_sul_web", lambda domanda: [])

    esito = web_search.ricerca_web("qualcosa")

    assert "non ha dato risultati" in esito


def test_ricerca_web_e_uno_strumento_valido_per_ollama():
    from ollama._utils import convert_function_to_tool

    from tools.web_search import ricerca_web

    schema = convert_function_to_tool(ricerca_web)

    assert schema.function.name == "ricerca_web"
    assert "domanda" in schema.function.parameters.required