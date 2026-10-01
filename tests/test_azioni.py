import json
from datetime import date, timedelta

from core.azioni import (
    RISCHIO_ALTO,
    RISCHIO_BASSO,
    Azione,
    AzioneNonRiuscita,
    GestoreAzioni,
    RegistroAzioni,
    interpreta_giorno,
)


def azione_di_prova(fatto, rischio="medio", annullabile=True):
    def esegui():
        fatto.append("fatto")
        return "Fatto."

    def annulla():
        fatto.remove("fatto")
        return "Annullato."

    return Azione(
        descrizione="Fare una prova",
        esegui=esegui,
        annulla=annulla if annullabile else None,
        rischio=rischio,
    )


def test_senza_interfaccia_le_azioni_a_rischio_non_partono():
    fatto = []
    gestore = GestoreAzioni()

    esito = gestore.esegui(azione_di_prova(fatto))

    assert fatto == []
    assert "non ha confermato" in esito


def test_l_azione_parte_solo_se_l_utente_conferma():
    fatto = []
    domande = []

    def conferma(azione):
        domande.append(azione.descrizione)
        return True

    gestore = GestoreAzioni(chiedi_conferma=conferma)

    assert gestore.esegui(azione_di_prova(fatto)) == "Fatto."
    assert fatto == ["fatto"]
    assert domande == ["Fare una prova"]


def test_le_azioni_innocue_non_chiedono_conferma():
    fatto = []
    gestore = GestoreAzioni()

    gestore.esegui(azione_di_prova(fatto, rischio=RISCHIO_BASSO))

    assert fatto == ["fatto"]


def test_se_la_conferma_si_rompe_non_si_fa_niente():
    fatto = []

    def conferma_rotta(azione):
        raise RuntimeError("finestra chiusa")

    gestore = GestoreAzioni(chiedi_conferma=conferma_rotta)

    gestore.esegui(azione_di_prova(fatto))

    assert fatto == []


def test_la_sola_lettura_blocca_anche_se_l_utente_confermerebbe():
    fatto = []
    gestore = GestoreAzioni(chiedi_conferma=lambda azione: True)
    gestore.imposta_sola_lettura(True)

    esito = gestore.esegui(azione_di_prova(fatto, rischio=RISCHIO_ALTO))

    assert fatto == []
    assert "sola lettura" in esito


def test_la_sola_lettura_lascia_passare_le_azioni_innocue():
    fatto = []
    gestore = GestoreAzioni()
    gestore.imposta_sola_lettura(True)

    gestore.esegui(azione_di_prova(fatto, rischio=RISCHIO_BASSO))

    assert fatto == ["fatto"]


def test_annulla_l_ultima_azione():
    fatto = []
    gestore = GestoreAzioni(chiedi_conferma=lambda azione: True)
    gestore.esegui(azione_di_prova(fatto))

    assert gestore.annulla_ultima() == "Annullato."
    assert fatto == []
    assert "Non c'è nessuna azione" in gestore.annulla_ultima()


def test_le_azioni_rifiutate_non_si_annullano():
    fatto = []
    gestore = GestoreAzioni()
    gestore.esegui(azione_di_prova(fatto))

    assert not gestore.puo_annullare()


def test_errore_dell_azione_spiegato_all_utente():
    gestore = GestoreAzioni(chiedi_conferma=lambda azione: True)

    def esegui():
        raise AzioneNonRiuscita("La cartella non esiste.")

    esito = gestore.esegui(Azione("Prova", esegui))

    assert esito == "La cartella non esiste."
    assert not gestore.puo_annullare()


def test_errore_imprevisto_non_blocca_raphael():
    gestore = GestoreAzioni(chiedi_conferma=lambda azione: True)

    def esegui():
        raise OSError("disco pieno")

    esito = gestore.esegui(Azione("Salvare un file", esegui))

    assert "disco pieno" in esito


def test_il_registro_annota_tutto(tmp_path):
    percorso = tmp_path / "registro.jsonl"
    registro = RegistroAzioni(percorso)
    gestore = GestoreAzioni(registro, chiedi_conferma=lambda azione: True)
    fatto = []

    gestore.esegui(azione_di_prova(fatto))
    gestore.annulla_ultima()
    gestore.chiedi_conferma = lambda azione: False
    gestore.esegui(azione_di_prova(fatto))

    righe = [json.loads(riga) for riga in percorso.read_text(encoding="utf-8").splitlines()]
    assert [riga["esito"] for riga in righe] == ["eseguita", "annullata", "rifiutata"]


def test_riepilogo_del_giorno():
    registro = RegistroAzioni()
    registro.registra("Creare la cartella X", "eseguita", "Ho creato la cartella X.")
    registro.registra("Salvare un file", "rifiutata")

    riepilogo = registro.riepilogo()

    assert "oggi (2 azioni)" in riepilogo
    assert "✅ Ho creato la cartella X." in riepilogo
    assert "Non confermata: Salvare un file" in riepilogo


def test_riepilogo_di_un_giorno_vuoto():
    registro = RegistroAzioni()

    assert "ieri non ho fatto nessuna azione" in registro.riepilogo(
        date.today() - timedelta(days=1)
    ).lower()


def test_il_registro_sopravvive_a_righe_rovinate(tmp_path):
    percorso = tmp_path / "registro.jsonl"
    registro = RegistroAzioni(percorso)
    registro.registra("Prova", "eseguita", "Ok.")
    with percorso.open("a", encoding="utf-8") as file:
        file.write("{ riga rotta\n")

    assert len(registro.voci()) == 1


def test_interpreta_giorno():
    oggi = date.today()

    assert interpreta_giorno(None) == oggi
    assert interpreta_giorno("oggi") == oggi
    assert interpreta_giorno("Ieri") == oggi - timedelta(days=1)
    assert interpreta_giorno("2026-10-01") == date(2026, 10, 1)
    assert interpreta_giorno("1/10/2026") == date(2026, 10, 1)
    assert interpreta_giorno("boh") is None