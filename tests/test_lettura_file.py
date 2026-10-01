import zipfile
from pathlib import Path

import pytest

from tools import lettura_file
from tools.lettura_file import MAX_CARATTERI_PER_PARTE, elenca_cartella, leggi_file


@pytest.fixture
def casa(tmp_path, monkeypatch):
    """Una finta cartella utente con Desktop, Documenti e Download."""
    for nome in ["Desktop", "Documents", "Downloads"]:
        (tmp_path / nome).mkdir()

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


def crea_docx(percorso, paragrafi):
    corpo = "".join(f"<w:p><w:r><w:t>{testo}</w:t></w:r></w:p>" for testo in paragrafi)
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        f'wordprocessingml/2006/main"><w:body>{corpo}</w:body></w:document>'
    )
    with zipfile.ZipFile(percorso, "w") as archivio:
        archivio.writestr("word/document.xml", xml)


def crea_pptx(percorso, diapositive):
    with zipfile.ZipFile(percorso, "w") as archivio:
        for numero, testo in enumerate(diapositive, start=1):
            xml = (
                '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/'
                '2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/'
                f'2006/main"><a:p><a:r><a:t>{testo}</a:t></a:r></a:p></p:sld>'
            )
            archivio.writestr(f"ppt/slides/slide{numero}.xml", xml)


def crea_pdf(percorso, testo):
    contenuto = f"BT /F1 12 Tf 72 720 Td ({testo}) Tj ET".encode()
    oggetti = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(contenuto) + contenuto + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    dati = b"%PDF-1.4\n"
    posizioni = []
    for numero, oggetto in enumerate(oggetti, start=1):
        posizioni.append(len(dati))
        dati += b"%d 0 obj\n" % numero + oggetto + b"\nendobj\n"
    inizio_xref = len(dati)
    dati += b"xref\n0 %d\n0000000000 65535 f \n" % (len(oggetti) + 1)
    for posizione in posizioni:
        dati += b"%010d 00000 n \n" % posizione
    dati += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(oggetti) + 1,
        inizio_xref,
    )
    percorso.write_bytes(dati)


def test_legge_un_file_di_testo_dal_percorso(casa):
    file = casa / "Documents" / "appunti.txt"
    file.write_text("Il campo elettrico è E = F/q", encoding="utf-8")

    risultato = leggi_file(str(file))

    assert risultato.startswith("Ho letto appunti.txt.")
    assert "Il campo elettrico è E = F/q" in risultato


def test_trova_il_file_solo_dal_nome(casa):
    cartella = casa / "Documents" / "Fisica"
    cartella.mkdir()
    (cartella / "formule.md").write_text("# Formule\nF = m·a", encoding="utf-8")

    risultato = leggi_file("formule.md")

    assert "F = m·a" in risultato


def test_trova_il_file_anche_senza_estensione(casa):
    (casa / "Desktop" / "lista spesa.txt").write_text("latte", encoding="utf-8")

    assert "latte" in leggi_file("lista spesa")


def test_accetta_un_percorso_relativo_alla_casa(casa):
    (casa / "Documents" / "nota.txt").write_text("ciao", encoding="utf-8")

    assert "ciao" in leggi_file("Documents/nota.txt")


def test_chiede_quale_file_se_ce_ne_sono_piu_di_uno(casa):
    (casa / "Desktop" / "relazione.txt").write_text("uno", encoding="utf-8")
    (casa / "Documents" / "relazione.txt").write_text("due", encoding="utf-8")

    risultato = leggi_file("relazione.txt")

    assert "più file" in risultato
    assert "uno" not in risultato


def test_file_inesistente(casa):
    assert "Non ho trovato" in leggi_file("non_esiste.txt")


def test_legge_testo_salvato_alla_windows(casa):
    file = casa / "Documents" / "vecchio.txt"
    file.write_bytes("perché così".encode("cp1252"))

    assert "perché così" in leggi_file(str(file))


def test_legge_un_documento_word(casa):
    file = casa / "Documents" / "tesina.docx"
    crea_docx(file, ["Introduzione", "Le equazioni di Maxwell"])

    risultato = leggi_file(str(file))

    assert "Introduzione\nLe equazioni di Maxwell" in risultato


def test_legge_una_presentazione(casa):
    file = casa / "Documents" / "esposizione.pptx"
    crea_pptx(file, ["Titolo", "Conclusioni"])

    risultato = leggi_file(str(file))

    assert "--- Diapositiva 1 ---\nTitolo" in risultato
    assert "--- Diapositiva 2 ---\nConclusioni" in risultato


def test_legge_un_pdf(casa):
    file = casa / "Downloads" / "dispensa.pdf"
    crea_pdf(file, "Teorema di Gauss")

    risultato = leggi_file(str(file))

    assert "--- Pagina 1 ---" in risultato
    assert "Teorema di Gauss" in risultato


def test_i_file_lunghi_si_leggono_a_parti(casa):
    file = casa / "Documents" / "lungo.txt"
    file.write_text("a" * MAX_CARATTERI_PER_PARTE + "FINE", encoding="utf-8")

    prima = leggi_file(str(file))
    seconda = leggi_file(str(file), parte=2)

    assert "(parte 1 di 2)" in prima
    assert "parte=2" in prima
    assert "FINE" not in prima
    assert "(parte 2 di 2)" in seconda
    assert "FINE" in seconda
    assert "solo 2 parti" in leggi_file(str(file), parte=3)


def test_non_legge_fuori_dalla_cartella_utente(casa, tmp_path_factory):
    fuori = tmp_path_factory.mktemp("altrove") / "segreto.txt"
    fuori.write_text("segreto", encoding="utf-8")

    risultato = leggi_file(str(fuori))

    assert "cartella utente" in risultato
    assert "segreto\n" not in risultato


def test_non_legge_le_cartelle_nascoste_o_di_sistema(casa):
    for nome in [".ssh", "AppData"]:
        cartella = casa / nome
        cartella.mkdir()
        (cartella / "config.txt").write_text("riservato", encoding="utf-8")

        risultato = leggi_file(str(cartella / "config.txt"))

        assert "Per sicurezza" in risultato
        assert "riservato" not in risultato


def test_non_legge_file_con_chiavi_e_password(casa):
    for nome in [".env", "certificato.pem"]:
        file = casa / "Documents" / nome
        file.write_text("AI_API_KEY=123", encoding="utf-8")

        risultato = leggi_file(str(file))

        assert "chiavi o password" in risultato
        assert "123" not in risultato


def test_rifiuta_i_formati_sconosciuti(casa):
    file = casa / "Documents" / "foto.jpg"
    file.write_bytes(b"\xff\xd8")

    assert "Non so leggere i file .jpg" in leggi_file(str(file))


def test_file_vuoto(casa):
    file = casa / "Documents" / "vuoto.txt"
    file.write_text("", encoding="utf-8")

    assert "è vuoto" in leggi_file(str(file))


def test_una_cartella_non_si_legge_come_file(casa):
    assert "elenca_cartella" in leggi_file(str(casa / "Documents"))


def test_elenca_una_cartella(casa):
    cartella = casa / "Documents" / "Fisica 2"
    cartella.mkdir()
    (cartella / "Esercizi").mkdir()
    (cartella / "formule.pdf").write_bytes(b"")
    (cartella / ".nascosto").write_text("x", encoding="utf-8")

    risultato = elenca_cartella("Fisica 2")

    assert "contiene 2 elementi" in risultato
    assert "📁 Esercizi" in risultato
    assert "📄 formule.pdf" in risultato
    assert ".nascosto" not in risultato


def test_elenca_capisce_i_nomi_italiani(casa):
    (casa / "Documents" / "tesi.docx").write_bytes(b"")

    assert "tesi.docx" in elenca_cartella("Documenti")


def test_elenca_cartella_inesistente(casa):
    assert "Non ho trovato" in elenca_cartella("Chimica")


def test_elenca_non_entra_nelle_cartelle_di_sistema(casa):
    (casa / "AppData").mkdir()

    assert "Per sicurezza" in elenca_cartella(str(casa / "AppData"))


def test_gli_strumenti_hanno_i_nomi_giusti():
    nomi = [strumento.__name__ for strumento in lettura_file.STRUMENTI_LETTURA]

    assert nomi == ["leggi_file", "elenca_cartella"]