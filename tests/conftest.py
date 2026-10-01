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