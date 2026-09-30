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