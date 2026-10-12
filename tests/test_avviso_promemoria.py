from datetime import datetime, timedelta

import pytest
from PySide6.QtWidgets import QApplication

from ai.mock_provider import MockAIProvider
from core.app import RaphaelApp
from ui.finestra import FinestraRaphael
from ui.notifica import MASSIMO_AVVISI, AvvisoPromemoria, GestoreAvvisi, quando_era


ADESSO = datetime(2026, 10, 12, 15, 30)


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def isola_history_file(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.json")


def voce(testo="Chiamare Marco", quando=ADESSO):
    return {"id": 1, "testo": testo, "quando": quando.isoformat(timespec="seconds")}


def gestore_di_prova():
    return GestoreAvvisi(animato=False, suono=False)


def test_l_avviso_mostra_il_testo_e_l_ora(qapp):
    avviso = AvvisoPromemoria(voce(), adesso=ADESSO, animato=False)

    assert avviso.testo.text() == "Chiamare Marco"
    assert avviso.orario.text() == "Adesso · 15:30"
    assert not avviso.in_ritardo


def test_l_avviso_dice_se_arriva_in_ritardo(qapp):
    stamattina = ADESSO.replace(hour=9, minute=0)
    avviso = AvvisoPromemoria(voce(quando=stamattina), adesso=ADESSO, animato=False)

    assert avviso.in_ritardo
    assert avviso.orario.text() == "In ritardo · era per oggi alle 09:00"


def test_quando_era_scrive_oggi_ieri_o_la_data():
    assert quando_era(ADESSO.replace(hour=8, minute=0), ADESSO) == "oggi alle 08:00"
    assert quando_era(ADESSO - timedelta(days=1), ADESSO) == "ieri alle 15:30"
    assert quando_era(ADESSO - timedelta(days=5), ADESSO) == "il 07/10 alle 15:30"


def test_il_testo_non_viene_interpretato_come_html(qapp):
    avviso = AvvisoPromemoria(voce("<b>esame</b>"), adesso=ADESSO, animato=False)

    assert avviso.testo.text() == "<b>esame</b>"


def test_il_gestore_mostra_l_avviso_e_lo_toglie_quando_premi_fatto(qapp):
    gestore = gestore_di_prova()

    avviso = gestore.mostra(voce(), adesso=ADESSO)
    assert avviso.isVisible()
    assert gestore.avvisi == [avviso]

    avviso.bottone_fatto.click()

    assert gestore.avvisi == []
    assert avviso.e_chiuso()


def test_piu_avvisi_si_impilano_dal_basso(qapp):
    gestore = gestore_di_prova()

    primo = gestore.mostra(voce("Primo"), adesso=ADESSO)
    secondo = gestore.mostra(voce("Secondo"), adesso=ADESSO)

    assert secondo.y() < primo.y()
    assert secondo.x() == primo.x()

    primo.chiudi()
    # Chiuso il primo, il secondo scende al suo posto.
    assert gestore.avvisi == [secondo]
    assert secondo.y() > primo.y() - 1 - secondo.height()


def test_non_si_accumulano_troppi_avvisi(qapp):
    gestore = gestore_di_prova()

    for numero in range(MASSIMO_AVVISI + 2):
        gestore.mostra(voce(f"Promemoria {numero}"), adesso=ADESSO)

    assert len(gestore.avvisi) == MASSIMO_AVVISI
    assert gestore.avvisi[-1].testo.text() == f"Promemoria {MASSIMO_AVVISI + 1}"


def test_rimanda_avvisa_con_i_minuti_scelti(qapp):
    gestore = gestore_di_prova()
    ricevuti = []
    gestore.rimanda.connect(lambda v, minuti: ricevuti.append((v["testo"], minuti)))

    avviso = gestore.mostra(voce(), adesso=ADESSO)
    avviso.scelte_rimando[1].trigger()  # "Tra 15 minuti"

    assert ricevuti == [("Chiamare Marco", 15)]
    assert avviso.conferma.isVisibleTo(avviso)
    assert "te lo ricordo alle" in avviso.conferma.text()
    assert not avviso.bottone_fatto.isVisibleTo(avviso)


def test_chiudi_tutti(qapp):
    gestore = gestore_di_prova()
    gestore.mostra(voce("Uno"), adesso=ADESSO)
    gestore.mostra(voce("Due"), adesso=ADESSO)

    gestore.chiudi_tutti()

    assert gestore.avvisi == []


def test_il_gancio_per_la_voce_legge_il_promemoria(qapp):
    gestore = gestore_di_prova()
    detti = []
    gestore.parla = detti.append

    gestore.mostra(voce("Bere un bicchiere d'acqua"), adesso=ADESSO)

    assert detti == ["Promemoria: Bere un bicchiere d'acqua"]


def test_se_la_voce_si_rompe_l_avviso_compare_lo_stesso(qapp):
    gestore = gestore_di_prova()

    def voce_rotta(testo):
        raise RuntimeError("altoparlanti scollegati")

    gestore.parla = voce_rotta

    avviso = gestore.mostra(voce(), adesso=ADESSO)

    assert avviso.isVisible()


# ------------------------------------------------------- con la finestra


def finestra_di_prova():
    raphael = RaphaelApp(ai_provider=MockAIProvider())
    finestra = FinestraRaphael(raphael)
    finestra.avvisi.animato = False
    finestra.avvisi.suono = False
    return raphael, finestra


def test_il_promemoria_dal_pianificatore_apre_il_riquadro(qapp):
    raphael, finestra = finestra_di_prova()

    # Il pianificatore chiama la finestra dal suo thread: la voce arriva col segnale.
    raphael._notifica_promemoria(voce("Studiare Analisi"))
    qapp.processEvents()

    assert [avviso.testo.text() for avviso in finestra.avvisi.avvisi] == ["Studiare Analisi"]
    finestra.close()


def test_rimanda_rimette_il_promemoria_in_agenda(qapp):
    raphael, finestra = finestra_di_prova()
    prima = datetime.now()

    avviso = finestra.avvisi.mostra(voce("Studiare Analisi"))
    avviso.scelte_rimando[0].trigger()  # "Tra 5 minuti"

    in_attesa = raphael.agenda.in_attesa()
    assert [v["testo"] for v in in_attesa] == ["Studiare Analisi"]
    quando = datetime.fromisoformat(in_attesa[0]["quando"])
    assert timedelta(minutes=4) < quando - prima < timedelta(minutes=6)
    finestra.close()


def test_chiudendo_la_finestra_si_chiudono_gli_avvisi_e_il_pianificatore(qapp):
    raphael, finestra = finestra_di_prova()
    raphael.pianificatore.avvia()
    finestra.avvisi.mostra(voce())

    finestra.close()

    assert finestra.avvisi.avvisi == []
    assert raphael.pianificatore._fermati.is_set()