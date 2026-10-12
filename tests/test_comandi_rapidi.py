from datetime import datetime

import pytest

from core.comandi_rapidi import Chiamata, ComandiRapidi
from tools.pc_control import trova_programma


ADESSO = datetime(2026, 10, 12, 18, 40)

PROGRAMMI = [
    {"nome": "Discord", "id": "discord"},
    {"nome": "WhatsApp", "id": "whatsapp"},
    {"nome": "Spotify", "id": "spotify"},
    {"nome": "Autodesk Fusion", "id": "fusion"},
    {"nome": "Esplora file", "id": "explorer"},
    {"nome": "YouTube Music", "id": "ytmusic"},
]


@pytest.fixture
def rapidi():
    return ComandiRapidi(
        trova_programma=lambda nome: trova_programma(nome, PROGRAMMI),
        adesso=lambda: ADESSO,
    )


def promemoria(quando, testo):
    return [Chiamata("imposta_promemoria", {"quando": quando, "testo": testo})]


# ------------------------------------------------------------- promemoria


@pytest.mark.parametrize(
    "frase, quando, testo",
    [
        ("ricordami tra 20 secondi di bere un bicchiere d'acqua", "tra 20 secondi", "Bere un bicchiere d'acqua"),
        ("Ricordami di chiamare Marco domani alle 9", "domani alle 9", "Chiamare Marco"),
        ("avvisami tra mezz'ora che la pasta è pronta", "tra mezz'ora", "La pasta è pronta"),
        ("ricordami alle 9 di sera di uscire", "alle 9 sera", "Uscire"),
        ("promemoria domani alle 15 per l'esame di fisica", "domani alle 15", "L'esame di fisica"),
        ("Ehi Raphael, ricordami tra 5 minuti di girare la pasta!", "tra 5 minuti", "Girare la pasta"),
    ],
)
def test_capisce_i_promemoria(rapidi, frase, quando, testo):
    assert rapidi.interpreta(frase) == promemoria(quando, testo)


def test_svegliami_senza_testo(rapidi):
    assert rapidi.interpreta("svegliami alle 7") == promemoria("alle 7", "Sveglia!")


@pytest.mark.parametrize(
    "frase, durata",
    [
        ("timer di 10 minuti", "10 minuti"),
        ("metti un timer da 30 secondi", "30 secondi"),
        ("imposta un timer di un'ora e mezza", "un'ora e mezza"),
    ],
)
def test_capisce_i_timer(rapidi, frase, durata):
    assert rapidi.interpreta(frase) == promemoria(f"tra {durata}", f"Timer di {durata} finito")


@pytest.mark.parametrize(
    "frase",
    [
        "ricordami di bere",              # manca il quando: lo chiede il modello
        "ricordami oggi di studiare",     # "oggi" senza ora: meglio chiedere
        "Ricordati che vivo a Catania",   # è un ricordo, non un promemoria
        "ricordami stamattina di uscire", # già passato
        "timer di boh",
    ],
)
def test_i_promemoria_non_chiari_vanno_al_modello(rapidi, frase):
    assert rapidi.interpreta(frase) is None


# ------------------------------------------------------------------ apri


def test_apre_un_programma(rapidi):
    assert rapidi.interpreta("Ehi Raphael, apri Discord") == [
        Chiamata("apri_programma", {"nome": "Discord"})
    ]


def test_apre_piu_siti_insieme(rapidi):
    assert rapidi.interpreta("apri amazon, zalando e foot locker") == [
        Chiamata("apri_sito", {"indirizzo": "https://www.amazon.it"}),
        Chiamata("apri_sito", {"indirizzo": "https://www.zalando.it"}),
        Chiamata("apri_sito", {"indirizzo": "https://www.footlocker.it"}),
    ]


def test_mescola_siti_e_programmi(rapidi):
    assert rapidi.interpreta("apri youtube e whatsapp") == [
        Chiamata("apri_sito", {"indirizzo": "https://www.youtube.com"}),
        Chiamata("apri_programma", {"nome": "whatsapp"}),
    ]


def test_un_indirizzo_si_apre_nel_browser(rapidi):
    assert rapidi.interpreta("apri unict.it") == [
        Chiamata("apri_sito", {"indirizzo": "unict.it"})
    ]


def test_trova_il_programma_anche_col_nome_vecchio(rapidi):
    assert rapidi.interpreta("apri fusion 360") == [
        Chiamata("apri_programma", {"nome": "fusion 360"})
    ]


def test_un_programma_con_quel_nome_esatto_vince(rapidi):
    assert rapidi.interpreta("apri esplora file per favore") == [
        Chiamata("apri_programma", {"nome": "esplora file"})
    ]


@pytest.mark.parametrize(
    "frase",
    [
        "apri il file tesi",
        "apri la cartella ciao123",
        "apri pippo",                      # non esiste: ci pensa il modello
        "apri discord e pippo",            # se uno non si trova, decide il modello
        "apri il sito dell'università",
    ],
)
def test_le_aperture_non_chiare_vanno_al_modello(rapidi, frase):
    assert rapidi.interpreta(frase) is None


# ------------------------------------------------------------ altro


@pytest.mark.parametrize("frase", ["che ore sono?", "Che giorno è oggi?", "quanti ne abbiamo"])
def test_le_domande_sull_ora(rapidi, frase):
    assert rapidi.interpreta(frase) == [Chiamata("data_e_ora")]


@pytest.mark.parametrize(
    "frase",
    ["ciao", "", "come stai?", "spiegami la legge di Ohm", "apri\ndiscord", "x" * 500],
)
def test_le_frasi_normali_vanno_al_modello(rapidi, frase):
    assert rapidi.interpreta(frase) is None


def test_se_la_ricerca_dei_programmi_si_rompe_non_succede_niente(rapidi):
    def rotta(nome):
        raise RuntimeError("PowerShell non risponde")

    rapidi.trova_programma = rotta

    assert rapidi.interpreta("apri discord") is None
    assert rapidi.interpreta("apri youtube") == [
        Chiamata("apri_sito", {"indirizzo": "https://www.youtube.com"})
    ]