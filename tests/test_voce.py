import io
import sys
import threading
import time
import types

import pytest
from PySide6.QtWidgets import QApplication

from ai.mock_provider import MockAIProvider
from core.app import FRASE_DI_PROVA, RaphaelApp
from ui.finestra import FinestraRaphael
from voce import sintesi
from voce.sintesi import (
    MotoreConRiserva,
    MotoreEdge,
    Voce,
    correggi_fonemi,
    crea_voce,
    perche_manca_la_voce,
)
from voce.testo_parlato import (
    MASSIMI_CARATTERI_PARLATI,
    applica_pronunce,
    dividi_in_blocchi,
    dividi_in_frasi,
    normalizza_per_la_voce,
    prepara_per_la_voce,
)


# -------------------------------------------------------- testo parlato


def test_toglie_markdown_ed_emoji():
    testo = "## Titolo\n**Ciao!** Ecco la lista:\n- primo punto\n- secondo ⏰ punto"

    assert prepara_per_la_voce(testo) == (
        "Titolo\nCiao! Ecco la lista:\nprimo punto\nsecondo punto"
    )


def test_niente_spazi_strani_prima_della_punteggiatura():
    assert prepara_per_la_voce("- ripassa gli **integrali doppi**;") == "ripassa gli integrali doppi;"


def test_le_righe_degli_strumenti_si_leggono_senza_simboli():
    assert prepara_per_la_voce("*⚙️ Ho aperto Discord.*") == "Ho aperto Discord."


def test_link_codice_e_formule_non_vengono_letti():
    testo = (
        "Guarda [la documentazione](https://docs.python.org) oppure https://unict.it\n"
        "```python\nprint('ciao')\n```\n"
        "La formula $E = mc^2$ è famosa. Usa `pip` per installare."
    )

    parlato = prepara_per_la_voce(testo)

    assert "https" not in parlato
    assert "print" not in parlato
    assert "mc^2" not in parlato
    assert "la documentazione" in parlato
    assert "Il codice è nel messaggio." in parlato
    assert "Usa pip per installare." in parlato


def test_le_fonti_della_ricerca_non_vengono_lette():
    testo = "Domani a Catania c'è il sole.\n\n**Fonti:**\n\n1. Meteo (https://meteo.it)"

    assert prepara_per_la_voce(testo) == "Domani a Catania c'è il sole."


def test_una_frase_che_inizia_con_fonti_resta():
    testo = "Fonti di energia rinnovabile: sole e vento.\nSono pulite."

    assert prepara_per_la_voce(testo) == testo


def test_le_risposte_lunghissime_vengono_accorciate():
    testo = "Questa è una frase di prova. " * 200

    parlato = prepara_per_la_voce(testo)

    assert len(parlato) < MASSIMI_CARATTERI_PARLATI + 60
    assert parlato.endswith("Il resto lo trovi scritto nella chat.")


def test_divide_in_frasi():
    assert dividi_in_frasi("Ciao! Come stai? Io bene.\nE tu") == [
        "Ciao!", "Come stai?", "Io bene.", "E tu",
    ]


def test_le_frasi_troppo_lunghe_si_spezzano_sulle_virgole():
    frase = ", ".join(["un pezzo di frase abbastanza lungo"] * 12) + "."

    pezzi = dividi_in_frasi(frase)

    assert len(pezzi) > 1
    assert all(len(pezzo) <= 230 for pezzo in pezzi)


def test_niente_da_dire():
    assert dividi_in_frasi(prepara_per_la_voce("⚙️ 🔊 ---")) == []


@pytest.mark.parametrize(
    "scritto, detto",
    [
        ("Alle 21:30 esci.", "Alle 21 e 30 esci."),
        ("Alle 9.05 lezione.", "Alle 9 e 5 lezione."),
        ("Alle 18:00 cena.", "Alle 18 cena."),
        ("Il 50% dei voti.", "Il 50 per cento dei voti."),
        ("Ti avviserò alle 18 (tra 20 minuti).", "Ti avviserò alle 18, tra 20 minuti."),
        ("Versione 3.14 di Python.", "Versione 3.14 di Python."),
        ("Ci vediamo alle 9.30 in aula.", "Ci vediamo alle 9 e 30 in aula."),
    ],
)
def test_orari_e_simboli_detti_come_una_persona(scritto, detto):
    assert normalizza_per_la_voce(scritto) == detto


def test_il_primo_blocco_e_corto_gli_altri_piu_lunghi():
    testo = (
        "Certo! Ecco un piano per stasera. "
        "Ripassa gli integrali doppi: parti dalla teoria, poi fai due esercizi. "
        "Dopo una pausa passa al teorema di Green. Se ti blocchi chiedimi pure."
    )

    blocchi = dividi_in_blocchi(testo)

    assert blocchi[0] == "Certo! Ecco un piano per stasera."
    assert len(blocchi) == 2
    # I due punti non spezzano il discorso.
    assert "teoria, poi fai due esercizi." in blocchi[1]


# -------------------------------------------------------- pronuncia


def test_le_vocali_inglesi_diventano_italiane():
    assert correggi_fonemi("ezertʃˈitsɪ ʊn") == "ezertʃˈitsi un"


def test_il_dizionario_delle_pronunce():
    assert applica_pronunce("Vengo da Niscemi.", {"Niscemi": "Nìscemi"}) == "Vengo da Nìscemi."
    assert applica_pronunce("NISCEMI", {"Niscemi": "Nìscemi"}) == "Nìscemi"
    assert applica_pronunce("Niscemiani", {"Niscemi": "Nìscemi"}) == "Niscemiani"


def test_raphael_e_file_si_dicono_bene():
    detto = normalizza_per_la_voce("Raphael ha salvato il file. Ecco i file di Raphael.")

    assert detto == "Rafaèl ha salvato il fàil. Ecco i fàil di Rafaèl."


def test_il_dizionario_vale_per_tutte_le_voci():
    riproduttore = RiproduttoreFinto()
    voce = Voce(MotoreFinto(), riproduttore)

    voce.parla("Sono Raphael.")
    assert voce.aspetta(5)

    assert riproduttore.riprodotte == ["Sono Rafaèl."]


# ---------------------------------------------------------------- Voce


class MotoreFinto:
    def __init__(self):
        self.generate = []
        self.caricato = False

    def carica(self):
        self.caricato = True

    def genera(self, frase):
        self.generate.append(frase)
        return frase, 24000


class RiproduttoreFinto:
    def __init__(self, blocca=False):
        self.riprodotte = []
        self.blocca = blocca
        self.fermato = threading.Event()
        self.concluso = False

    def riproduci(self, audio, frequenza):
        self.riprodotte.append(audio)
        if self.blocca:
            self.fermato.wait(5)

    def concludi(self):
        self.concluso = True

    def ferma(self):
        self.fermato.set()


FRASE_LUNGA = (
    "Questa è una frase abbastanza lunga da riempire da sola il primo blocco "
    "del parlato, quindi ne servono due"
)


def test_legge_tutti_i_blocchi_in_ordine():
    riproduttore = RiproduttoreFinto()
    voce = Voce(MotoreFinto(), riproduttore)

    assert voce.parla(f"Ciao! {FRASE_LUNGA} uno. {FRASE_LUNGA} due.")
    assert voce.aspetta(5)

    assert riproduttore.riprodotte == [
        "Ciao!", f"{FRASE_LUNGA} uno. {FRASE_LUNGA} due.",
    ]
    assert riproduttore.concluso
    assert not voce.sta_parlando()


def test_piu_testi_di_seguito_vengono_letti_tutti():
    riproduttore = RiproduttoreFinto()
    voce = Voce(MotoreFinto(), riproduttore)

    voce.parla("Uno.")
    voce.parla("Due.")
    assert voce.aspetta(5)

    assert riproduttore.riprodotte == ["Uno.", "Due."]


def test_ferma_zittisce_subito_e_scarta_il_resto():
    riproduttore = RiproduttoreFinto(blocca=True)
    voce = Voce(MotoreFinto(), riproduttore)

    voce.parla(f"Ciao! {FRASE_LUNGA} uno. {FRASE_LUNGA} due. {FRASE_LUNGA} tre. {FRASE_LUNGA} quattro. {FRASE_LUNGA} cinque.")
    limite = time.time() + 5
    while not riproduttore.riprodotte and time.time() < limite:
        time.sleep(0.01)

    voce.ferma()

    assert not voce.sta_parlando()
    time.sleep(0.2)
    assert riproduttore.riprodotte == ["Ciao!"]
    assert riproduttore.fermato.is_set()


def test_dopo_ferma_si_puo_parlare_di_nuovo():
    riproduttore = RiproduttoreFinto()
    voce = Voce(MotoreFinto(), riproduttore)

    voce.parla("Vecchio.")
    voce.ferma()
    riproduttore.riprodotte.clear()
    voce.parla("Nuovo.")
    assert voce.aspetta(5)

    assert riproduttore.riprodotte == ["Nuovo."]


def test_un_errore_del_motore_non_blocca_le_altre_frasi():
    class MotoreCapriccioso(MotoreFinto):
        def genera(self, frase):
            if frase.startswith("Rotta"):
                raise RuntimeError("frase impossibile")
            return super().genera(frase)

    riproduttore = RiproduttoreFinto()
    voce = Voce(MotoreCapriccioso(), riproduttore)

    voce.parla(f"Rotta! {FRASE_LUNGA}.")
    assert voce.aspetta(5)

    assert riproduttore.riprodotte == [f"{FRASE_LUNGA}."]


def test_un_testo_vuoto_non_fa_parlare():
    voce = Voce(MotoreFinto(), RiproduttoreFinto())

    assert voce.parla("   ") is False
    assert not voce.sta_parlando()


def test_prepara_carica_il_modello():
    motore = MotoreFinto()

    Voce(motore, RiproduttoreFinto()).prepara()

    assert motore.caricato


def test_senza_motori_la_voce_non_c_e(tmp_path, monkeypatch):
    monkeypatch.setattr(sintesi, "_installato", lambda nome: nome == "sounddevice")

    assert "almeno uno dei due motori" in perche_manca_la_voce(tmp_path)
    assert crea_voce(tmp_path) is None


def test_senza_sounddevice_la_voce_non_c_e(tmp_path, monkeypatch):
    monkeypatch.setattr(sintesi, "_installato", lambda nome: nome != "sounddevice")

    assert "sounddevice" in perche_manca_la_voce(tmp_path)


def test_con_edge_ma_senza_kokoro_c_e_solo_la_voce_online(tmp_path, monkeypatch):
    monkeypatch.setattr(sintesi, "_installato", lambda nome: nome != "kokoro_onnx")

    voce = crea_voce(tmp_path)

    assert isinstance(voce.motore.principale, MotoreEdge)
    assert voce.motore.riserva is None


# ------------------------------------------------------ motori


class MotoreNominato:
    def __init__(self, nome, rotto=False):
        self.nome = nome
        self.rotto = rotto
        self.usato = 0

    def carica(self):
        pass

    def genera(self, testo):
        self.usato += 1
        if self.rotto:
            raise ConnectionError("niente internet")
        return f"{self.nome}: {testo}", 24000


def test_se_internet_manca_passa_alla_voce_del_pc():
    online = MotoreNominato("Giuseppe", rotto=True)
    pc = MotoreNominato("Nicola")
    motore = MotoreConRiserva(online, pc)

    assert motore.genera("Ciao") == ("Nicola: Ciao", 24000)
    # Per un po' non riprova la voce online: niente attese a ogni frase.
    assert motore.genera("Di nuovo") == ("Nicola: Di nuovo", 24000)
    assert online.usato == 1
    assert motore.descrizione() == "Nicola"


def test_dopo_un_po_riprova_la_voce_online():
    online = MotoreNominato("Giuseppe", rotto=True)
    motore = MotoreConRiserva(online, MotoreNominato("Nicola"), riprova_dopo_s=0)

    motore.genera("Ciao")
    online.rotto = False

    assert motore.genera("Eccomi") == ("Giuseppe: Eccomi", 24000)


def test_in_modalita_offline_usa_solo_il_pc():
    online = MotoreNominato("Giuseppe")
    motore = MotoreConRiserva(online, MotoreNominato("Nicola"))
    motore.solo_offline = True

    assert motore.genera("Ciao") == ("Nicola: Ciao", 24000)
    assert online.usato == 0


def test_senza_riserva_l_errore_arriva_alla_voce():
    motore = MotoreConRiserva(MotoreNominato("Giuseppe", rotto=True), None)

    with pytest.raises(ConnectionError):
        motore.genera("Ciao")


def test_il_motore_online_decodifica_l_mp3():
    soundfile = pytest.importorskip("soundfile")
    import numpy

    tono = (0.2 * numpy.sin(numpy.linspace(0, 400, 24000))).astype("float32")
    mp3 = io.BytesIO()
    soundfile.write(mp3, tono, 24000, format="MP3")
    ricevuti = []

    def scarica_finto(testo):
        ricevuti.append(testo)
        return mp3.getvalue()

    audio, frequenza = MotoreEdge(scarica=scarica_finto).genera("Ciao Gaetano")

    assert ricevuti == ["Ciao Gaetano"]
    assert frequenza == 24000
    assert len(audio) > 20000


def test_il_motore_online_senza_audio_da_errore():
    with pytest.raises(RuntimeError):
        MotoreEdge(scarica=lambda testo: b"").genera("Ciao")


# ---------------------------------------------------------- RaphaelApp


class VoceFinta:
    def __init__(self):
        self.detti = []
        self.fermate = 0
        self.preparata = False

    def parla(self, testo):
        self.detti.append(testo)
        return True

    def ferma(self):
        self.fermate += 1

    def prepara(self):
        self.preparata = True


@pytest.fixture(autouse=True)
def isola_history_file(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.json")


def test_nei_test_la_voce_vera_non_viene_caricata():
    assert RaphaelApp(ai_provider=MockAIProvider()).voce is None


def test_senza_voce_il_comando_spiega_cosa_manca():
    app = RaphaelApp(ai_provider=MockAIProvider(), voce=None)

    risposta = app.gestisci_comando("/voce")

    assert "non è disponibile" in risposta
    assert app.parla("ciao") is False


def test_comandi_voce():
    voce = VoceFinta()
    app = RaphaelApp(ai_provider=MockAIProvider(), voce=voce)

    assert "D'ora in poi" in app.gestisci_comando("/voce on")
    assert app.leggi_risposte is True
    assert "attiva" in app.gestisci_comando("/voce")

    app.gestisci_comando("/voce prova")
    assert voce.detti == [FRASE_DI_PROVA]

    app.gestisci_comando("/voce off")
    assert app.leggi_risposte is False
    assert voce.fermate == 1


def test_comandi_online_e_offline():
    voce = VoceFinta()
    voce.motore = MotoreConRiserva(MotoreNominato("Giuseppe"), MotoreNominato("Nicola"))
    app = RaphaelApp(ai_provider=MockAIProvider(), voce=voce)

    assert "Voce: Giuseppe" in app.gestisci_comando("/voce")
    assert "solo la voce del PC" in app.gestisci_comando("/voce offline")
    assert voce.motore.solo_offline is True
    assert "Voce: Nicola" in app.gestisci_comando("/voce")

    app.gestisci_comando("/voce online")
    assert voce.motore.solo_offline is False


def test_la_voce_si_prepara_all_avvio():
    voce = VoceFinta()
    app = RaphaelApp(ai_provider=MockAIProvider(), voce=voce)
    app.ai_router.provider.prepara = lambda: None

    app.prepara_in_background()

    limite = time.time() + 2
    while not voce.preparata and time.time() < limite:
        time.sleep(0.01)
    assert voce.preparata


# ------------------------------------------------------------ finestra


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def finestra_con_voce(voce):
    raphael = RaphaelApp(ai_provider=MockAIProvider(), voce=voce)
    finestra = FinestraRaphael(raphael)
    finestra.avvisi.animato = False
    finestra.avvisi.suono = False
    return raphael, finestra


def aspetta_risposta(finestra, qapp, secondi=5):
    limite = time.time() + secondi
    while finestra.in_attesa and time.time() < limite:
        qapp.processEvents()
        time.sleep(0.01)


def test_senza_voce_il_bottone_e_spento(qapp):
    _, finestra = finestra_con_voce(None)

    assert not finestra.bottone_voce.isEnabled()
    assert finestra.avvisi.parla is None
    finestra.close()


def test_col_bottone_acceso_la_risposta_viene_letta(qapp):
    voce = VoceFinta()
    raphael, finestra = finestra_con_voce(voce)

    finestra.bottone_voce.setChecked(True)
    assert raphael.leggi_risposte is True

    finestra.casella.setPlainText("raccontami qualcosa")
    finestra.invia()
    aspetta_risposta(finestra, qapp)

    assert voce.detti == [finestra.messaggi[-1]["content"]]
    finestra.close()


def test_col_bottone_spento_non_legge(qapp):
    voce = VoceFinta()
    _, finestra = finestra_con_voce(voce)

    finestra.casella.setPlainText("raccontami qualcosa")
    finestra.invia()
    aspetta_risposta(finestra, qapp)

    assert voce.detti == []
    finestra.close()


def test_una_nuova_domanda_zittisce_raphael(qapp):
    voce = VoceFinta()
    _, finestra = finestra_con_voce(voce)

    finestra.casella.setPlainText("raccontami qualcosa")
    finestra.invia()
    aspetta_risposta(finestra, qapp)

    assert voce.fermate >= 1
    finestra.close()


def test_il_comando_voce_on_accende_anche_il_bottone(qapp):
    voce = VoceFinta()
    _, finestra = finestra_con_voce(voce)

    finestra.casella.setPlainText("/voce on")
    finestra.invia()
    aspetta_risposta(finestra, qapp)

    assert finestra.bottone_voce.isChecked()
    # La conferma di /voce on non viene letta: sarebbe solo rumore.
    assert voce.detti == []
    finestra.close()


def test_i_promemoria_vengono_letti_ad_alta_voce(qapp):
    voce = VoceFinta()
    raphael, finestra = finestra_con_voce(voce)

    raphael._notifica_promemoria({"testo": "Studiare Analisi", "quando": "2026-10-12T21:00:00"})
    qapp.processEvents()

    assert voce.detti == ["Promemoria: Studiare Analisi"]
    finestra.close()


# ------------------------------------------------------ riproduttore


class FlussoFinto:
    aperti = []

    def __init__(self, samplerate, channels, dtype):
        self.frequenza = samplerate
        self.scritti = []
        self.chiuso_come = None
        FlussoFinto.aperti.append(self)

    def start(self):
        pass

    def write(self, dati):
        self.scritti.append(len(dati))

    def stop(self):
        self.chiuso_come = "fino alla fine"

    def abort(self):
        self.chiuso_come = "subito"

    def close(self):
        pass


@pytest.fixture
def casse_finte(monkeypatch):
    FlussoFinto.aperti = []
    monkeypatch.setitem(
        sys.modules, "sounddevice", types.SimpleNamespace(OutputStream=FlussoFinto)
    )
    return FlussoFinto


def test_i_blocchi_suonano_nello_stesso_flusso_senza_stacchi(casse_finte):
    numpy = pytest.importorskip("numpy")
    riproduttore = sintesi.RiproduttoreSounddevice()

    riproduttore.riproduci(numpy.ones(24000, dtype="float32"), 24000)
    riproduttore.riproduci(numpy.ones(12000, dtype="float32"), 24000)
    riproduttore.concludi()

    assert len(casse_finte.aperti) == 1
    flusso = casse_finte.aperti[0]
    pausa = int(24000 * sintesi.PAUSA_TRA_BLOCCHI_S)
    assert sum(flusso.scritti) == 24000 + 12000 + 2 * pausa
    assert flusso.chiuso_come == "fino alla fine"


def test_ferma_taglia_subito_l_audio(casse_finte):
    numpy = pytest.importorskip("numpy")
    riproduttore = sintesi.RiproduttoreSounddevice()

    riproduttore.riproduci(numpy.ones(4800, dtype="float32"), 24000)
    riproduttore.ferma()

    assert casse_finte.aperti[0].chiuso_come == "subito"