import sys
from pathlib import Path

from core import percorsi


def test_in_sviluppo_i_dati_restano_nel_progetto():
    assert not percorsi.e_eseguibile()
    assert percorsi.cartella_dati() == percorsi.cartella_progetto()


def test_l_icona_esiste():
    assert percorsi.percorso_risorsa("raphael.ico").exists()


def test_nell_eseguibile_i_dati_vanno_in_localappdata(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert percorsi.cartella_dati() == tmp_path / "Raphael"


def test_nell_eseguibile_le_risorse_vengono_dal_pacchetto(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert percorsi.percorso_risorsa("raphael.ico") == Path(tmp_path) / "assets" / "raphael.ico"