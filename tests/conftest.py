import pytest


@pytest.fixture(autouse=True)
def memoria_temporanea(tmp_path, monkeypatch):
    """Ogni test usa un file di memoria suo, così non tocca i ricordi veri."""
    from core import config

    monkeypatch.setattr(config, "MEMORY_FILE", tmp_path / "memoria.json")


@pytest.fixture(autouse=True)
def registro_temporaneo(tmp_path, monkeypatch):
    """Ogni test scrive il registro delle azioni in un file suo."""
    from core import config

    monkeypatch.setattr(config, "ACTIONS_LOG_FILE", tmp_path / "registro_azioni.jsonl")


@pytest.fixture(autouse=True)
def promemoria_temporanei(tmp_path, monkeypatch):
    """Ogni test usa un file di promemoria suo, così non tocca quelli veri."""
    from core import config

    monkeypatch.setattr(config, "REMINDERS_FILE", tmp_path / "promemoria.json")


@pytest.fixture(autouse=True)
def dati_temporanei(tmp_path, monkeypatch):
    """La cartella dei dati punta a una cartella vuota: niente voce vera nei test."""
    from core import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "dati")





@pytest.fixture(autouse=True)
def senza_voce_vera(monkeypatch):
    """Nei test Raphael non parla davvero: niente casse e niente internet."""
    monkeypatch.setattr("core.app.crea_voce", lambda cartella: None)