import pytest

from tools.audio import (
    TASTO_MUTO,
    TASTO_PLAY_PAUSA,
    TASTO_PRECEDENTE,
    TASTO_SUCCESSIVO,
    TASTO_VOLUME_GIU,
    TASTO_VOLUME_SU,
    AudioNonDisponibile,
    crea_strumenti_audio,
)


class SessioneFinta:
    def __init__(self, nome, volume=50):
        self.nome = nome
        self.volume = volume
        self.muto = False

    def leggi_volume(self):
        return self.volume

    def imposta_volume(self, percentuale):
        self.volume = max(0, min(100, percentuale))

    def imposta_muto(self, muto):
        self.muto = muto


class AudioFinto:
    """Finge il mixer di Windows, così i test girano ovunque."""

    def __init__(self, volume=40, pycaw=True):
        self.volume = volume
        self.muto = False
        self.pycaw = pycaw
        self.tasti = []
        self.aperti = []
        self.brano = ("Blinding Lights", "The Weeknd")
        self.app = [SessioneFinta("Discord.exe", 80), SessioneFinta("Spotify.exe", 60)]

    def _serve_pycaw(self):
        if not self.pycaw:
            raise AudioNonDisponibile("Per regolare il volume serve la libreria pycaw.")

    def leggi_volume(self):
        self._serve_pycaw()
        return self.volume

    def imposta_volume(self, percentuale):
        self._serve_pycaw()
        self.volume = percentuale

    def e_muto(self):
        self._serve_pycaw()
        return self.muto

    def imposta_muto(self, muto):
        self._serve_pycaw()
        self.muto = muto

    def sessioni(self):
        self._serve_pycaw()
        return self.app

    def premi_tasto(self, codice):
        self.tasti.append(codice)

    def cosa_suona(self):
        return self.brano

    def apri(self, indirizzo):
        self.aperti.append(indirizzo)


@pytest.fixture
def audio():
    return AudioFinto()


@pytest.fixture
def strumenti(audio):
    volume, musica = crea_strumenti_audio(audio)
    return volume, musica


def test_imposta_il_volume(audio, strumenti):
    volume, _ = strumenti

    assert volume("imposta", 30) == "🔊 Volume al 30%."
    assert audio.volume == 30


def test_alza_e_abbassa(audio, strumenti):
    volume, _ = strumenti

    assert volume("alza") == "🔊 Volume al 50%."
    assert volume("abbassa", 25) == "🔊 Volume al 25%."
    assert volume("abbassa", 90) == "🔊 Volume al 0%."
    assert volume("alza", 500) == "🔊 Volume al 100%."


def test_sinonimi(audio, strumenti):
    volume, _ = strumenti

    volume("aumenta", 10)
    assert audio.volume == 50
    volume("giù", 20)
    assert audio.volume == 30


def test_muto_e_riattiva(audio, strumenti):
    volume, _ = strumenti

    assert volume("muto") == "🔇 Audio silenziato."
    assert audio.muto is True
    assert "il volume è al 40% (muto)" in volume("leggi").lower()
    assert "riattivato" in volume("riattiva")
    assert audio.muto is False


def test_alzare_il_volume_toglie_il_muto(audio, strumenti):
    volume, _ = strumenti
    audio.muto = True

    volume("imposta", 20)

    assert audio.muto is False


def test_imposta_senza_valore(strumenti):
    volume, _ = strumenti

    assert "a quanto" in volume("imposta")


def test_azione_sbagliata(strumenti):
    volume, _ = strumenti

    assert "non valida" in volume("balla")


def test_volume_di_una_app(audio, strumenti):
    volume, _ = strumenti

    assert volume("imposta", 20, app="discord") == "🔊 Volume di Discord al 20%."
    assert audio.app[0].volume == 20
    assert audio.app[1].volume == 60
    assert volume("abbassa", 10, app="Spotify.exe") == "🔊 Volume di Spotify al 50%."
    assert volume("muto", app="spotify") == "🔇 Ho silenziato Spotify."
    assert audio.app[1].muto is True
    assert volume("leggi", app="discord") == "🔊 Il volume di Discord è al 20%."
    assert audio.volume == 40


def test_app_che_non_usa_l_audio(strumenti):
    volume, _ = strumenti

    assert "Non trovo 'Teams'" in volume("alza", app="Teams")


def test_senza_pycaw_usa_i_tasti_della_tastiera():
    audio = AudioFinto(pycaw=False)
    volume, _ = crea_strumenti_audio(audio)

    assert "alzato il volume di circa 10%" in volume("alza")
    assert audio.tasti == [TASTO_VOLUME_SU] * 5

    audio.tasti.clear()
    volume("abbassa", 4)
    assert audio.tasti == [TASTO_VOLUME_GIU] * 2

    audio.tasti.clear()
    volume("muto")
    assert audio.tasti == [TASTO_MUTO]


def test_senza_pycaw_spiega_come_installarlo():
    volume, _ = crea_strumenti_audio(AudioFinto(pycaw=False))

    assert "pycaw" in volume("imposta", 30)
    assert "pycaw" in volume("leggi")


def test_tasti_della_musica(audio, strumenti):
    _, musica = strumenti

    assert "play/pausa" in musica("pausa")
    assert "successivo" in musica("avanti")
    assert "precedente" in musica("indietro")
    assert audio.tasti == [TASTO_PLAY_PAUSA, TASTO_SUCCESSIVO, TASTO_PRECEDENTE]


def test_cosa_sta_suonando(audio, strumenti):
    _, musica = strumenti

    assert musica("cosa_suona") == "🎵 Sta suonando: Blinding Lights di The Weeknd."

    audio.brano = None
    assert "non sta suonando niente" in musica("cosa suona")


def test_cosa_suona_senza_il_componente(audio, strumenti):
    _, musica = strumenti

    def manca():
        raise AudioNonDisponibile("Serve un componente facoltativo.")

    audio.cosa_suona = manca

    assert musica("cosa_suona") == "Serve un componente facoltativo."


def test_cerca_su_youtube_e_spotify(audio, strumenti):
    _, musica = strumenti

    assert musica("cerca", "lo-fi per studiare") == "🎵 Ho cercato 'lo-fi per studiare' su YouTube."
    assert audio.aperti[-1] == "https://www.youtube.com/results?search_query=lo-fi+per+studiare"

    musica("cerca", "Ludovico Einaudi", dove="Spotify")
    assert audio.aperti[-1] == "spotify:search:Ludovico%20Einaudi"


def test_spotify_non_installato_apre_il_sito(audio, strumenti):
    _, musica = strumenti
    aperti = []

    def apri(indirizzo):
        if indirizzo.startswith("spotify:"):
            raise OSError("app non trovata")
        aperti.append(indirizzo)

    audio.apri = apri
    musica("cerca", "Einaudi", dove="spotify")

    assert aperti == ["https://open.spotify.com/search/Einaudi"]


def test_cerca_senza_testo_e_azione_sbagliata(strumenti):
    _, musica = strumenti

    assert musica("cerca") == "Dimmi cosa cercare."
    assert "non valida" in musica("balla")


def test_i_nomi_degli_strumenti():
    nomi = [strumento.__name__ for strumento in crea_strumenti_audio(AudioFinto())]

    assert nomi == ["volume", "musica"]