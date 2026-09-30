from core.app import RaphaelApp


def test_raphael_si_avvia_con_il_provider_predefinito(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.json")

    app = RaphaelApp()

    strumenti = app.ai_router.provider.strumenti
    assert strumenti
    assert all(callable(strumento) for strumento in strumenti)
    assert "ricerca_web" in [strumento.__name__ for strumento in strumenti]