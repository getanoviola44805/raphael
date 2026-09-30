import pytest

from tools import pc_control


PROGRAMMI_FINTI = [
    {"nome": "Google Chrome", "id": "Chrome"},
    {"nome": "Discord", "id": "com.squirrel.Discord.Discord"},
    {"nome": "Blocco note", "id": "Microsoft.WindowsNotepad_8wekyb3d8bbwe!App"},
    {"nome": "Calcolatrice", "id": "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"},
    {"nome": "Visual Studio Code", "id": "Microsoft.VisualStudioCode"},
    {"nome": "Chrome Remote Desktop", "id": "ChromeRemote"},
]


@pytest.fixture
def aperture(monkeypatch):
    aperti = []
    monkeypatch.setattr(pc_control, "_avvia", aperti.append)
    monkeypatch.setattr(pc_control, "_programmi_in_cache", PROGRAMMI_FINTI)
    return aperti


def test_trova_programma_preferisce_la_corrispondenza_esatta():
    trovato = pc_control.trova_programma("discord", PROGRAMMI_FINTI)

    assert trovato["nome"] == "Discord"


def test_trova_programma_usa_i_sinonimi():
    assert pc_control.trova_programma("chrome", PROGRAMMI_FINTI)["nome"] == "Google Chrome"
    assert pc_control.trova_programma("VS Code", PROGRAMMI_FINTI)["nome"] == "Visual Studio Code"


def test_trova_programma_ignora_maiuscole_e_accenti():
    trovato = pc_control.trova_programma("CALCOLATRICE", PROGRAMMI_FINTI)

    assert trovato["nome"] == "Calcolatrice"


def test_trova_programma_restituisce_none_se_non_esiste():
    assert pc_control.trova_programma("Photoshop", PROGRAMMI_FINTI) is None


def test_apri_programma_avvia_l_app_trovata(aperture):
    esito = pc_control.apri_programma("Blocco note")

    assert esito == "Ho aperto Blocco note."
    assert aperture == ["shell:AppsFolder\\Microsoft.WindowsNotepad_8wekyb3d8bbwe!App"]


def test_apri_programma_sconosciuto_non_avvia_niente(aperture):
    esito = pc_control.apri_programma("Photoshop")

    assert "Non ho trovato" in esito
    assert aperture == []


def test_apri_sito_aggiunge_https(monkeypatch):
    aperti = []
    monkeypatch.setattr(pc_control.webbrowser, "open", aperti.append)

    esito = pc_control.apri_sito("youtube.com")

    assert aperti == ["https://youtube.com"]
    assert "youtube.com" in esito


def test_apri_sito_rifiuta_indirizzi_non_web(monkeypatch):
    aperti = []
    monkeypatch.setattr(pc_control.webbrowser, "open", aperti.append)

    esito = pc_control.apri_sito("file:///C:/Windows")

    assert aperti == []
    assert "solo indirizzi web" in esito


def test_cerca_file_trova_i_file(monkeypatch, tmp_path):
    (tmp_path / "Tesi finale.docx").write_text("")
    (tmp_path / "progetti").mkdir()
    (tmp_path / "progetti" / "tesi_bozza.pdf").write_text("")
    (tmp_path / "foto.jpg").write_text("")
    monkeypatch.setattr(pc_control, "_cartelle_utente", lambda: [tmp_path])

    esito = pc_control.cerca_file("tesi")

    assert "Tesi finale.docx" in esito
    assert "tesi_bozza.pdf" in esito
    assert "foto.jpg" not in esito


def test_cerca_file_salta_le_cartelle_tecniche(monkeypatch, tmp_path):
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "tesi.py").write_text("")
    monkeypatch.setattr(pc_control, "_cartelle_utente", lambda: [tmp_path])

    esito = pc_control.cerca_file("tesi")

    assert "Non ho trovato" in esito


def test_apri_file_apre_un_documento(aperture, tmp_path):
    documento = tmp_path / "appunti.pdf"
    documento.write_text("")

    esito = pc_control.apri_file(str(documento))

    assert esito == "Ho aperto appunti.pdf."
    assert aperture == [str(documento)]


def test_apri_file_rifiuta_gli_eseguibili(aperture, tmp_path):
    programma = tmp_path / "virus.exe"
    programma.write_text("")

    esito = pc_control.apri_file(str(programma))

    assert "Per sicurezza" in esito
    assert aperture == []


def test_apri_file_inesistente(aperture):
    esito = pc_control.apri_file("C:/non/esiste.pdf")

    assert "non esiste" in esito
    assert aperture == []


def test_data_e_ora_in_italiano():
    esito = pc_control.data_e_ora()

    assert esito.startswith("Oggi è ")
    assert any(mese in esito for mese in pc_control.MESI)