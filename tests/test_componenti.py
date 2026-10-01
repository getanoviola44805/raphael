import pytest
from PySide6.QtWidgets import QApplication

from ui import componenti
from ui.componenti import (
    CasellaTesto,
    CerchioRotante,
    MessaggioRaphael,
    MessaggioUtente,
)


# Il nome della classe inizia con "Test", quindi pytest la scambierebbe per un
# gruppo di test: la usiamo passando dal modulo, senza importarla direttamente.
def nuovo_testo():
    return componenti.TestoAdattivo()


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def test_il_cerchio_gira_e_si_ferma(qapp):
    cerchio = CerchioRotante()

    cerchio.avvia()
    angolo = cerchio._angolo
    cerchio._avanza()

    assert cerchio.sta_girando()
    assert cerchio._angolo != angolo

    cerchio.ferma()
    assert not cerchio.sta_girando()


def test_il_testo_cresce_con_il_contenuto(qapp):
    testo = nuovo_testo()
    testo.resize(300, 10)
    testo.imposta_testo("una riga")
    altezza_corta = testo.height()

    testo.imposta_testo("\n\n".join(f"paragrafo {numero}" for numero in range(10)))

    assert testo.height() > altezza_corta * 3


def test_i_blocchi_di_codice_hanno_lo_sfondo(qapp):
    from PySide6.QtGui import QTextFormat

    testo = nuovo_testo()
    testo.imposta_testo("Prima\n\n```python\nprint('ciao')\n```")

    blocchi = []
    blocco = testo.document().begin()
    while blocco.isValid():
        blocchi.append(blocco)
        blocco = blocco.next()

    codice = [b for b in blocchi if b.blockFormat().hasProperty(QTextFormat.Property.BlockCodeFence)]
    assert codice
    assert codice[0].blockFormat().background().color().name() != "#000000"


def test_il_fumetto_dell_utente_si_adatta_al_testo(qapp):
    corto = MessaggioUtente("ciao")
    lungo = MessaggioUtente("parola " * 80)
    for messaggio in (corto, lungo):
        messaggio.resize(700, 100)
        messaggio.show()
        qapp.processEvents()

    assert corto.testo.width() < 150
    assert lungo.testo.width() <= 700 * MessaggioUtente.PROPORZIONE_MASSIMA
    assert lungo.testo.height() > corto.testo.height()


def test_messaggio_raphael_completo_ha_il_tasto_copia(qapp):
    messaggio = MessaggioRaphael("Raphael", "Ciao!")

    assert not messaggio.bottone_copia.isHidden()
    assert messaggio.testo_semplice() == "Ciao!"


def test_messaggio_raphael_in_arrivo_non_ha_ancora_il_tasto_copia(qapp):
    messaggio = MessaggioRaphael("Raphael")
    messaggio.imposta_testo("Sto scriv")

    assert messaggio.bottone_copia.isHidden()


def test_la_casella_cresce_fino_a_un_massimo(qapp):
    casella = CasellaTesto()
    casella.resize(400, 30)
    altezza_iniziale = casella.height()

    casella.setText("\n".join(["riga"] * 4))
    altezza_quattro = casella.height()
    casella.setText("\n".join(["riga"] * 30))

    assert altezza_quattro > altezza_iniziale
    assert casella.height() > altezza_quattro
    assert casella.height() <= CasellaTesto.RIGHE_MASSIME * casella.fontMetrics().lineSpacing() + 10