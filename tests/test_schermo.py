from pathlib import Path

from tools.schermo import crea_strumenti_schermo


class MotoreFinto:
    def __init__(self, risposta="Vedo il codice di Raphael aperto in VS Code."):
        self.risposta = risposta
        self.chiamate = []

    def generate_response_stream(self, prompt, history=None, immagini=None):
        self.chiamate.append((prompt, history, immagini))
        if isinstance(self.risposta, Exception):
            raise self.risposta
        yield self.risposta


def cattura_finta(percorsi_creati):
    def _cattura(cartella):
        percorso = Path(cartella) / "finta.png"
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_bytes(b"finto-png")
        percorsi_creati.append(percorso)
        return percorso
    return _cattura


def test_guarda_schermo_descrive_lo_schermo(tmp_path):
    motore = MotoreFinto()
    creati = []
    (guarda_schermo,) = crea_strumenti_schermo(
        model="finto", cartella=tmp_path, cattura=cattura_finta(creati), motore_visione=motore
    )

    esito = guarda_schermo()

    assert esito == "Vedo il codice di Raphael aperto in VS Code."
    assert motore.chiamate[0][0] == (
        "Descrivi brevemente e in modo chiaro cosa vedi in questo screenshot dello schermo."
    )
    assert motore.chiamate[0][2] == [str(creati[0])]


def test_guarda_schermo_con_una_domanda_specifica(tmp_path):
    motore = MotoreFinto("Il terminale mostra 'ModuleNotFoundError: mss'.")
    (guarda_schermo,) = crea_strumenti_schermo(
        model="finto", cartella=tmp_path, cattura=cattura_finta([]), motore_visione=motore
    )

    esito = guarda_schermo("che errore vedi nel terminale?")

    assert "ModuleNotFoundError" in esito
    assert motore.chiamate[0][0] == "che errore vedi nel terminale?"


def test_lo_screenshot_viene_cancellato_dopo_l_analisi(tmp_path):
    creati = []
    (guarda_schermo,) = crea_strumenti_schermo(
        model="finto", cartella=tmp_path, cattura=cattura_finta(creati), motore_visione=MotoreFinto()
    )

    guarda_schermo()

    assert not creati[0].exists()


def test_screenshot_non_riuscito(tmp_path):
    def cattura_che_fallisce(cartella):
        raise OSError("schermo non disponibile")

    (guarda_schermo,) = crea_strumenti_schermo(
        model="finto", cartella=tmp_path, cattura=cattura_che_fallisce, motore_visione=MotoreFinto()
    )

    assert "Non sono riuscito a catturare lo schermo" in guarda_schermo()


def test_analisi_non_riuscita_cancella_comunque_lo_screenshot(tmp_path):
    creati = []
    motore = MotoreFinto(RuntimeError("modello non disponibile"))
    (guarda_schermo,) = crea_strumenti_schermo(
        model="finto", cartella=tmp_path, cattura=cattura_finta(creati), motore_visione=motore
    )

    esito = guarda_schermo()

    assert "non sono riuscito ad analizzarlo" in esito
    assert not creati[0].exists()


def test_risposta_vuota(tmp_path):
    motore = MotoreFinto("   ")
    (guarda_schermo,) = crea_strumenti_schermo(
        model="finto", cartella=tmp_path, cattura=cattura_finta([]), motore_visione=motore
    )

    assert guarda_schermo() == "Non sono riuscito a descrivere lo schermo."


def test_il_nome_dello_strumento():
    (guarda_schermo,) = crea_strumenti_schermo(model="finto", motore_visione=MotoreFinto())
    assert guarda_schermo.__name__ == "guarda_schermo"