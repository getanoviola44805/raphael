import json

from memory.memoria import MAX_RICORDI, MemoriaLungoTermine
from tools.strumenti_memoria import crea_strumenti_memoria


def test_aggiunge_e_salva_su_file(tmp_path):
    percorso = tmp_path / "memoria.json"
    memoria = MemoriaLungoTermine(percorso)

    esito = memoria.aggiungi("Si chiama Gaetano")

    assert esito == "Ho memorizzato: Si chiama Gaetano"
    assert memoria.elenca() == ["Si chiama Gaetano"]
    salvati = json.loads(percorso.read_text(encoding="utf-8"))
    assert salvati[0]["testo"] == "Si chiama Gaetano"
    assert salvati[0]["data"]


def test_i_ricordi_restano_dopo_il_riavvio(tmp_path):
    percorso = tmp_path / "memoria.json"
    MemoriaLungoTermine(percorso).aggiungi("Studia Ingegneria Informatica")

    memoria = MemoriaLungoTermine(percorso)

    assert memoria.elenca() == ["Studia Ingegneria Informatica"]


def test_non_salva_i_doppioni():
    memoria = MemoriaLungoTermine()
    memoria.aggiungi("Vive a Catania")

    esito = memoria.aggiungi("vive a catania.")

    assert esito.startswith("Lo sapevo già")
    assert len(memoria.elenca()) == 1


def test_rifiuta_testo_vuoto():
    memoria = MemoriaLungoTermine()

    assert memoria.aggiungi("   ") == "Non c'è niente da ricordare."
    assert memoria.elenca() == []


def test_rifiuta_password_e_dati_bancari():
    memoria = MemoriaLungoTermine()

    for testo in ["La password del wifi è ciao123", "Il PIN è 1234", "IBAN IT00X"]:
        assert "Non salvo" in memoria.aggiungi(testo)

    assert memoria.elenca() == []


def test_le_parole_simili_non_sono_bloccate():
    memoria = MemoriaLungoTermine()

    memoria.aggiungi("Gli piacciono i pinguini")

    assert memoria.elenca() == ["Gli piacciono i pinguini"]


def test_accorcia_i_ricordi_troppo_lunghi():
    memoria = MemoriaLungoTermine()

    memoria.aggiungi("a" * 1000)

    assert len(memoria.elenca()[0]) <= 301


def test_memoria_piena():
    memoria = MemoriaLungoTermine()
    for numero in range(MAX_RICORDI):
        memoria.aggiungi(f"Fatto numero {numero}")

    esito = memoria.aggiungi("Un fatto in più")

    assert "piena" in esito
    assert len(memoria.elenca()) == MAX_RICORDI


def test_dimentica_per_numero():
    memoria = MemoriaLungoTermine()
    memoria.aggiungi("Primo")
    memoria.aggiungi("Secondo")

    esito = memoria.dimentica("1")

    assert esito == "Ho dimenticato: Primo"
    assert memoria.elenca() == ["Secondo"]


def test_dimentica_numero_inesistente():
    memoria = MemoriaLungoTermine()
    memoria.aggiungi("Primo")

    assert memoria.dimentica("5") == "Non esiste il ricordo numero 5."
    assert memoria.elenca() == ["Primo"]


def test_dimentica_per_parte_del_testo():
    memoria = MemoriaLungoTermine()
    memoria.aggiungi("Si chiama Gaetano")
    memoria.aggiungi("Preferisce risposte brevi")

    esito = memoria.dimentica("risposte brevi")

    assert esito == "Ho dimenticato: Preferisce risposte brevi"
    assert memoria.elenca() == ["Si chiama Gaetano"]


def test_dimentica_anche_se_il_modello_riformula():
    memoria = MemoriaLungoTermine()
    memoria.aggiungi("Sta preparando l'esame di Fisica 2")
    memoria.aggiungi("Si chiama Gaetano")

    esito = memoria.dimentica("L'utente sta preparando l'esame di Fisica")

    assert esito == "Ho dimenticato: Sta preparando l'esame di Fisica 2"


def test_dimentica_chiede_quale_se_ci_sono_piu_ricordi_simili():
    memoria = MemoriaLungoTermine()
    memoria.aggiungi("Studia Analisi 2")
    memoria.aggiungi("Studia Fisica 2")

    esito = memoria.dimentica("Studia")

    assert "più ricordi simili" in esito
    assert len(memoria.elenca()) == 2


def test_dimentica_qualcosa_che_non_esiste():
    memoria = MemoriaLungoTermine()
    memoria.aggiungi("Si chiama Gaetano")

    esito = memoria.dimentica("gioca a calcio")

    assert esito.startswith("Non ho trovato")
    assert len(memoria.elenca()) == 1


def test_svuota():
    memoria = MemoriaLungoTermine()
    memoria.aggiungi("Uno")
    memoria.aggiungi("Due")

    assert memoria.svuota() == "Ho dimenticato tutto (2 ricordi)."
    assert memoria.elenca() == []


def test_file_rovinato_non_blocca_raphael(tmp_path):
    percorso = tmp_path / "memoria.json"
    percorso.write_text("{ non è json", encoding="utf-8")

    memoria = MemoriaLungoTermine(percorso)

    assert memoria.elenca() == []


def test_testo_per_prompt():
    memoria = MemoriaLungoTermine()
    assert memoria.testo_per_prompt() == ""

    memoria.aggiungi("Si chiama Gaetano")

    assert "- Si chiama Gaetano" in memoria.testo_per_prompt()


def test_formatta_elenco_numerato():
    memoria = MemoriaLungoTermine()
    assert "Non ho ancora niente" in memoria.formatta_elenco()

    memoria.aggiungi("Si chiama Gaetano")
    memoria.aggiungi("Vive a Catania")

    elenco = memoria.formatta_elenco()

    assert "1. Si chiama Gaetano" in elenco
    assert "2. Vive a Catania" in elenco


def test_strumenti_per_il_modello():
    memoria = MemoriaLungoTermine()
    ricorda, dimentica = crea_strumenti_memoria(memoria)

    assert ricorda.__name__ == "ricorda"
    assert dimentica.__name__ == "dimentica"

    ricorda(informazione="Si chiama Gaetano")
    assert memoria.elenca() == ["Si chiama Gaetano"]

    dimentica(informazione="Si chiama Gaetano")
    assert memoria.elenca() == []