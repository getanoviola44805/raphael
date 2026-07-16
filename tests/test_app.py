from core.app import RaphaelApp


def test_comando_ciao():
    app = RaphaelApp()

    risposta = app.gestisci_comando("ciao")

    assert risposta == "Ciao! Sono Raphael."


def test_comando_versione():
    app = RaphaelApp()

    risposta = app.gestisci_comando("versione")

    assert risposta == "Sto usando la versione 0.1.0."


def test_comando_sconosciuto():
    app = RaphaelApp()

    risposta = app.gestisci_comando("qualcosa")

    assert risposta == "Risposta simulata a: qualcosa"