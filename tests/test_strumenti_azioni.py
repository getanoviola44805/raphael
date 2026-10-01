import time
from pathlib import Path

import pytest

from core.azioni import GestoreAzioni
from tools.strumenti_azioni import crea_strumenti_azioni, destinazione


@pytest.fixture
def casa(tmp_path, monkeypatch):
    for nome in ["Desktop", "Documents", "Downloads"]:
        (tmp_path / nome).mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


@pytest.fixture
def gestore():
    return GestoreAzioni(chiedi_conferma=lambda azione: True)


@pytest.fixture
def strumenti(gestore):
    return {strumento.__name__: strumento for strumento in crea_strumenti_azioni(gestore)}


def test_destinazione(casa):
    assert destinazione("Fisica/riassunto.md") == casa / "Documents" / "Fisica" / "riassunto.md"
    assert destinazione("Desktop/nota.txt") == casa / "Desktop" / "nota.txt"
    assert destinazione("Scrivania/nota.txt") == casa / "Desktop" / "nota.txt"
    assert destinazione("Documenti/a.txt") == casa / "Documents" / "a.txt"


def test_crea_cartella_con_sottocartelle(casa, strumenti):
    esito = strumenti["crea_cartella"]("Università/Fisica 2/Esercizi")

    cartella = casa / "Documents" / "Università" / "Fisica 2" / "Esercizi"
    assert cartella.is_dir()
    assert esito == f"Ho creato la cartella {cartella}."


def test_crea_cartella_chiede_conferma(casa):
    domande = []
    gestore = GestoreAzioni(chiedi_conferma=lambda azione: domande.append(azione) or False)
    crea_cartella = crea_strumenti_azioni(gestore)[0]

    esito = crea_cartella("Prova")

    assert len(domande) == 1
    assert str(casa / "Documents" / "Prova") in domande[0].descrizione
    assert not (casa / "Documents" / "Prova").exists()
    assert "non ha confermato" in esito


def test_crea_cartella_esistente(casa, strumenti):
    assert "esiste già" in strumenti["crea_cartella"]("Documents")


def test_annulla_la_cartella_creata(casa, gestore, strumenti):
    strumenti["crea_cartella"]("Nuova/Interna")

    esito = gestore.annulla_ultima()

    assert "Ho tolto la cartella" in esito
    assert not (casa / "Documents" / "Nuova").exists()


def test_non_annulla_una_cartella_che_si_e_riempita(casa, gestore, strumenti):
    strumenti["crea_cartella"]("Piena")
    (casa / "Documents" / "Piena" / "mio.txt").write_text("x", encoding="utf-8")

    esito = gestore.annulla_ultima()

    assert "ci hai messo dentro" in esito
    assert (casa / "Documents" / "Piena" / "mio.txt").exists()


def test_non_crea_cartelle_fuori_casa_o_di_sistema(casa, strumenti, tmp_path_factory):
    fuori = tmp_path_factory.mktemp("fuori") / "x"

    assert "cartella utente" in strumenti["crea_cartella"](str(fuori))
    assert "Per sicurezza" in strumenti["crea_cartella"](str(casa / "AppData" / "x"))
    assert not fuori.exists()


def test_salva_testo(casa, strumenti):
    esito = strumenti["salva_testo"]("Fisica/riassunto.md", "# Maxwell\n∇·E = ρ/ε₀")

    file = casa / "Documents" / "Fisica" / "riassunto.md"
    assert file.read_text(encoding="utf-8") == "# Maxwell\n∇·E = ρ/ε₀"
    assert esito.startswith("Ho salvato il testo")


def test_salva_testo_aggiunge_txt_se_manca_l_estensione(casa, strumenti):
    strumenti["salva_testo"]("Desktop/lista spesa", "latte")

    assert (casa / "Desktop" / "lista spesa.txt").read_text(encoding="utf-8") == "latte"


def test_salva_testo_non_sovrascrive(casa, strumenti):
    file = casa / "Documents" / "nota.txt"
    file.write_text("originale", encoding="utf-8")

    esito = strumenti["salva_testo"]("nota.txt", "nuovo")

    assert file.read_text(encoding="utf-8") == "originale"
    assert (casa / "Documents" / "nota (2).txt").read_text(encoding="utf-8") == "nuovo"
    assert "esiste già" in esito


def test_salva_testo_in_fondo(casa, strumenti):
    file = casa / "Documents" / "diario.txt"
    file.write_text("prima riga", encoding="utf-8")

    strumenti["salva_testo"]("diario.txt", "seconda riga", aggiungi=True)

    assert file.read_text(encoding="utf-8") == "prima riga\nseconda riga"


def test_annulla_il_testo_aggiunto(casa, gestore, strumenti):
    file = casa / "Documents" / "diario.txt"
    file.write_text("prima riga", encoding="utf-8")
    strumenti["salva_testo"]("diario.txt", "seconda riga", aggiungi=True)

    gestore.annulla_ultima()

    assert file.read_text(encoding="utf-8") == "prima riga"


def test_annulla_il_file_salvato(casa, gestore, strumenti):
    strumenti["salva_testo"]("Nuova cartella/nota.txt", "ciao")

    esito = gestore.annulla_ultima()

    assert "Ho tolto il file" in esito
    assert not (casa / "Documents" / "Nuova cartella").exists()


def test_non_annulla_un_file_modificato_dopo(casa, gestore, strumenti):
    strumenti["salva_testo"]("nota.txt", "ciao")
    file = casa / "Documents" / "nota.txt"
    time.sleep(0.01)
    file.write_text("ciao, l'ho cambiato io", encoding="utf-8")

    esito = gestore.annulla_ultima()

    assert "modificato" in esito
    assert file.exists()


def test_salva_testo_rifiuta_gli_eseguibili(casa, strumenti):
    for nome in ["virus.bat", "script.ps1", "programma.exe", "tesi.docx"]:
        esito = strumenti["salva_testo"](nome, "contenuto")
        assert "Non posso salvare" in esito
        assert not (casa / "Documents" / nome).exists()


def test_salva_testo_rifiuta_file_di_chiavi(casa, strumenti):
    assert "chiavi" in strumenti["salva_testo"](".env", "AI_API_KEY=1")
    assert "chiavi" in strumenti["salva_testo"]("chiave.pem", "segreto")
    assert not (casa / "Documents" / ".env.txt").exists()


def test_salva_testo_vuoto(casa, strumenti):
    assert "Non c'è nessun testo" in strumenti["salva_testo"]("nota.txt", "   ")


def test_la_conferma_mostra_l_anteprima(casa):
    domande = []
    gestore = GestoreAzioni(chiedi_conferma=lambda azione: domande.append(azione) or True)
    salva_testo = crea_strumenti_azioni(gestore)[1]

    salva_testo("nota.txt", "Testo da salvare")

    assert "Testo da salvare" in domande[0].dettagli


def test_azioni_recenti_e_sola_lettura(casa, gestore, strumenti):
    strumenti["crea_cartella"]("Prova")

    assert "Ho creato la cartella" in strumenti["azioni_recenti"]()
    assert "Non ho capito" in strumenti["azioni_recenti"]("boh")

    strumenti["attiva_sola_lettura"]()
    esito = strumenti["crea_cartella"]("Altra")

    assert "sola lettura" in esito
    assert not (casa / "Documents" / "Altra").exists()


def test_annulla_ultima_azione_come_strumento(casa, strumenti):
    strumenti["crea_cartella"]("Prova")

    assert "Ho tolto" in strumenti["annulla_ultima_azione"]()