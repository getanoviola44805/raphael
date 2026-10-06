import time
from datetime import datetime, timedelta

import pytest

from core.promemoria import (
    AgendaPromemoria,
    Pianificatore,
    descrivi_quando,
    interpreta_quando,
)
from tools.strumenti_tempo import crea_strumenti_tempo


# Giovedì 1 ottobre 2026, ore 15:00: tutti i test partono da qui.
ADESSO = datetime(2026, 10, 1, 15, 0)


@pytest.mark.parametrize(
    "testo, atteso",
    [
        ("tra 10 minuti", datetime(2026, 10, 1, 15, 10)),
        ("10 min", datetime(2026, 10, 1, 15, 10)),
        ("fra un'ora", datetime(2026, 10, 1, 16, 0)),
        ("un'ora e mezza", datetime(2026, 10, 1, 16, 30)),
        ("tra 1 ora e 20 minuti", datetime(2026, 10, 1, 16, 20)),
        ("mezz'ora", datetime(2026, 10, 1, 15, 30)),
        ("un quarto d'ora", datetime(2026, 10, 1, 15, 15)),
        ("tra due giorni", datetime(2026, 10, 3, 15, 0)),
        ("alle 18:30", datetime(2026, 10, 1, 18, 30)),
        ("alle 9", datetime(2026, 10, 2, 9, 0)),
        ("ore 7.15", datetime(2026, 10, 2, 7, 15)),
        ("domani", datetime(2026, 10, 2, 9, 0)),
        ("domani alle 9", datetime(2026, 10, 2, 9, 0)),
        ("dopodomani alle 21:15", datetime(2026, 10, 3, 21, 15)),
        ("venerdì alle 18", datetime(2026, 10, 2, 18, 0)),
        ("giovedì alle 9", datetime(2026, 10, 8, 9, 0)),
        ("giovedì alle 16", datetime(2026, 10, 1, 16, 0)),
        ("5/10 alle 15", datetime(2026, 10, 5, 15, 0)),
        ("5 ottobre", datetime(2026, 10, 5, 9, 0)),
        ("1/9", datetime(2027, 9, 1, 9, 0)),
        ("2026-10-03T08:30", datetime(2026, 10, 3, 8, 30)),
        ("2026-10-03 08:30:00", datetime(2026, 10, 3, 8, 30)),
        ("2026-10-03", datetime(2026, 10, 3, 9, 0)),
        ("alle 8 di sera", datetime(2026, 10, 1, 20, 0)),
        ("stasera alle 9", datetime(2026, 10, 1, 21, 0)),
        ("oggi pomeriggio alle 4", datetime(2026, 10, 1, 16, 0)),
        ("mezzogiorno", datetime(2026, 10, 2, 12, 0)),
        ("tra 3 settimane", datetime(2026, 10, 22, 15, 0)),
    ],
)
def test_interpreta_quando(testo, atteso):
    assert interpreta_quando(testo, ADESSO) == atteso


@pytest.mark.parametrize("testo", ["boh", "", "quando vuoi", "31/02 alle 9", "alle 25"])
def test_interpreta_quando_non_capisce(testo):
    assert interpreta_quando(testo, ADESSO) is None


def test_descrivi_quando():
    assert descrivi_quando(datetime(2026, 10, 1, 15, 10), ADESSO) == "oggi alle 15:10 (tra 10 minuti)"
    assert descrivi_quando(datetime(2026, 10, 1, 16, 30), ADESSO) == "oggi alle 16:30 (tra 1 ora e 30 minuti)"
    assert descrivi_quando(datetime(2026, 10, 2, 9, 0), ADESSO) == "domani alle 09:00"
    assert descrivi_quando(datetime(2026, 10, 3, 9, 0), ADESSO) == "sabato alle 09:00"
    assert descrivi_quando(datetime(2026, 10, 22, 9, 0), ADESSO) == "giovedì 22 ottobre 2026 alle 09:00"


def test_agenda_salva_e_ricarica(tmp_path):
    percorso = tmp_path / "promemoria.json"
    AgendaPromemoria(percorso).aggiungi("Prenotare l'appello", datetime(2026, 10, 2, 9, 0))

    agenda = AgendaPromemoria(percorso)

    assert [voce["testo"] for voce in agenda.in_attesa()] == ["Prenotare l'appello"]


def test_agenda_file_rovinato(tmp_path):
    percorso = tmp_path / "promemoria.json"
    percorso.write_text("{ rotto", encoding="utf-8")

    assert AgendaPromemoria(percorso).in_attesa() == []


def test_i_promemoria_sono_in_ordine_di_tempo():
    agenda = AgendaPromemoria()
    agenda.aggiungi("Dopo", datetime(2026, 10, 3, 9, 0))
    agenda.aggiungi("Prima", datetime(2026, 10, 2, 9, 0))

    assert [voce["testo"] for voce in agenda.in_attesa()] == ["Prima", "Dopo"]
    assert agenda.formatta_elenco(ADESSO).splitlines()[1] == "1. Prima, domani alle 09:00"


def test_scaduti_li_toglie_dall_agenda(tmp_path):
    agenda = AgendaPromemoria(tmp_path / "promemoria.json")
    agenda.aggiungi("Pasta", datetime(2026, 10, 1, 15, 10))
    agenda.aggiungi("Appello", datetime(2026, 10, 2, 9, 0))

    assert agenda.scaduti(datetime(2026, 10, 1, 15, 5)) == []
    arrivati = agenda.scaduti(datetime(2026, 10, 1, 15, 10))

    assert [voce["testo"] for voce in arrivati] == ["Pasta"]
    assert [voce["testo"] for voce in AgendaPromemoria(tmp_path / "promemoria.json").in_attesa()] == ["Appello"]


def test_cancella_per_numero_testo_e_tutti():
    agenda = AgendaPromemoria()
    agenda.aggiungi("Pasta", datetime(2026, 10, 1, 15, 10))
    agenda.aggiungi("Appello di Fisica", datetime(2026, 10, 2, 9, 0))
    agenda.aggiungi("Chiamare Marco", datetime(2026, 10, 3, 9, 0))

    assert agenda.cancella("1") == "Ho cancellato il promemoria: Pasta"
    assert agenda.cancella("fisica") == "Ho cancellato il promemoria: Appello di Fisica"
    assert "Non esiste" in agenda.cancella("7")
    assert "Non ho trovato" in agenda.cancella("palestra")
    assert agenda.cancella("tutti") == "Ho cancellato tutti i promemoria (1)."
    assert "nessun promemoria" in agenda.cancella("1")


def test_il_pianificatore_avvisa_una_sola_volta():
    agenda = AgendaPromemoria()
    agenda.aggiungi("Pasta", datetime(2026, 10, 1, 15, 10))
    avvisi = []
    pianificatore = Pianificatore(agenda, notifica=avvisi.append)

    assert pianificatore.controlla(datetime(2026, 10, 1, 15, 0)) == 0
    assert pianificatore.controlla(datetime(2026, 10, 1, 15, 11)) == 1
    assert pianificatore.controlla(datetime(2026, 10, 1, 15, 12)) == 0
    assert [voce["testo"] for voce in avvisi] == ["Pasta"]


def test_una_notifica_rotta_non_ferma_il_pianificatore():
    agenda = AgendaPromemoria()
    agenda.aggiungi("Uno", datetime(2026, 10, 1, 15, 10))
    agenda.aggiungi("Due", datetime(2026, 10, 1, 15, 10))

    def notifica_rotta(voce):
        raise RuntimeError("finestra chiusa")

    assert Pianificatore(agenda, notifica=notifica_rotta).controlla(
        datetime(2026, 10, 1, 16, 0)
    ) == 2


def test_il_pianificatore_gira_da_solo():
    agenda = AgendaPromemoria()
    agenda.aggiungi("Subito", datetime.now() - timedelta(seconds=1))
    avvisi = []
    pianificatore = Pianificatore(agenda, notifica=avvisi.append, intervallo_s=0.05)

    pianificatore.avvia()
    limite = time.time() + 2
    while not avvisi and time.time() < limite:
        time.sleep(0.02)
    pianificatore.ferma()

    assert [voce["testo"] for voce in avvisi] == ["Subito"]


@pytest.fixture
def strumenti():
    agenda = AgendaPromemoria()
    elenco = crea_strumenti_tempo(agenda, adesso=lambda: ADESSO)
    return agenda, {strumento.__name__: strumento for strumento in elenco}


def test_strumento_imposta_un_timer(strumenti):
    agenda, s = strumenti

    esito = s["imposta_promemoria"]("tra 10 minuti", "Togliere la pasta")

    assert esito == "⏰ Ti avviserò oggi alle 15:10 (tra 10 minuti): Togliere la pasta"
    assert agenda.in_attesa()[0]["quando"] == "2026-10-01T15:10:00"


def test_strumento_non_capisce_quando(strumenti):
    agenda, s = strumenti

    assert "Non ho capito" in s["imposta_promemoria"]("quando vuoi", "Boh")
    assert agenda.in_attesa() == []


def test_strumento_rifiuta_il_passato_e_il_troppo_lontano(strumenti):
    agenda, s = strumenti

    assert "già passato" in s["imposta_promemoria"]("oggi alle 9", "Colazione")
    assert "prossimo anno" in s["imposta_promemoria"]("2030-01-01 09:00", "Lontano")
    assert agenda.in_attesa() == []


def test_strumenti_elenca_e_cancella(strumenti):
    agenda, s = strumenti
    s["imposta_promemoria"]("domani alle 9", "Prenotare l'appello")

    assert "1. Prenotare l'appello, domani alle 09:00" in s["elenca_promemoria"]()
    assert "Ho cancellato" in s["cancella_promemoria"]("1")
    assert "nessun promemoria" in s["elenca_promemoria"]()