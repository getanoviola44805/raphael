"""Volume e musica: Raphael regola l'audio di Windows e comanda il lettore.

- Il volume (generale o di una singola app, come Discord o Spotify) si regola
  con la libreria pycaw, che parla direttamente con il mixer di Windows.
- Play, pausa e brano successivo usano i tasti multimediali: funzionano con
  Spotify, YouTube nel browser, VLC e quasi tutti i lettori.
- "Cosa sta suonando" usa un componente facoltativo di Windows (winrt): se non
  è installato, Raphael lo dice e spiega come aggiungerlo.

Sono tutte azioni innocue, quindi non chiedono conferma.
"""

import asyncio
import ctypes
import logging
import os
import sys
import unicodedata
import webbrowser
from urllib.parse import quote, quote_plus


logger = logging.getLogger(__name__)

PASSO_PREDEFINITO = 10
PUNTI_PER_TASTO = 2  # ogni pressione del tasto volume cambia il volume del 2%

TASTO_MUTO = 0xAD
TASTO_VOLUME_GIU = 0xAE
TASTO_VOLUME_SU = 0xAF
TASTO_SUCCESSIVO = 0xB0
TASTO_PRECEDENTE = 0xB1
TASTO_STOP = 0xB2
TASTO_PLAY_PAUSA = 0xB3
RILASCIA_TASTO = 0x0002

AZIONI_MUSICA = {
    "play": TASTO_PLAY_PAUSA,
    "riproduci": TASTO_PLAY_PAUSA,
    "pausa": TASTO_PLAY_PAUSA,
    "play_pausa": TASTO_PLAY_PAUSA,
    "avanti": TASTO_SUCCESSIVO,
    "successivo": TASTO_SUCCESSIVO,
    "indietro": TASTO_PRECEDENTE,
    "precedente": TASTO_PRECEDENTE,
    "stop": TASTO_STOP,
}
MESSAGGI_MUSICA = {
    TASTO_PLAY_PAUSA: "⏯️ Ho premuto play/pausa.",
    TASTO_SUCCESSIVO: "⏭️ Passo al brano successivo.",
    TASTO_PRECEDENTE: "⏮️ Torno al brano precedente.",
    TASTO_STOP: "⏹️ Ho fermato la riproduzione.",
}

COME_INSTALLARE_PYCAW = (
    "Per regolare il volume serve la libreria pycaw: nel terminale scrivi "
    "pip install pycaw e riavvia Raphael."
)
COME_INSTALLARE_WINRT = (
    "Per sapere cosa sta suonando serve un componente facoltativo: nel terminale "
    "scrivi pip install winrt-Windows.Media.Control winrt-Windows.Foundation "
    "e riavvia Raphael."
)


class AudioNonDisponibile(Exception):
    """Il controllo dell'audio non è disponibile su questo computer."""


def _normalizza(testo: str) -> str:
    testo = unicodedata.normalize("NFKD", str(testo).lower())
    testo = "".join(c for c in testo if not unicodedata.combining(c))
    return " ".join(testo.replace("_", " ").split())


def _limita(valore) -> int:
    return max(0, min(100, int(round(float(valore)))))


# ------------------------------------------------------- Windows vero e proprio


def _inizializza_com():
    """Ogni thread che parla con il mixer di Windows deve prima "presentarsi"."""
    import comtypes

    try:
        comtypes.CoInitialize()
    except OSError:
        pass  # il thread era già inizializzato: va bene così


class SessioneAudio:
    """Il volume di una singola app nel mixer di Windows."""

    def __init__(self, nome: str, controllo):
        self.nome = nome
        self._controllo = controllo

    def leggi_volume(self) -> int:
        return _limita(self._controllo.GetMasterVolume() * 100)

    def imposta_volume(self, percentuale: int):
        self._controllo.SetMasterVolume(_limita(percentuale) / 100, None)

    def imposta_muto(self, muto: bool):
        self._controllo.SetMute(int(bool(muto)), None)


class AudioWindows:
    """Parla con il mixer di Windows tramite pycaw."""

    def _pycaw(self):
        if sys.platform != "win32":
            raise AudioNonDisponibile("Il controllo del volume funziona solo su Windows.")
        try:
            from pycaw import pycaw
        except ImportError as errore:
            raise AudioNonDisponibile(COME_INSTALLARE_PYCAW) from errore
        _inizializza_com()
        return pycaw

    def _generale(self):
        pycaw = self._pycaw()
        altoparlanti = pycaw.AudioUtilities.GetSpeakers()
        controllo = getattr(altoparlanti, "EndpointVolume", None)

        if controllo is None:  # versioni vecchie di pycaw
            from comtypes import CLSCTX_ALL

            interfaccia = altoparlanti.Activate(
                pycaw.IAudioEndpointVolume._iid_, CLSCTX_ALL, None
            )
            controllo = interfaccia.QueryInterface(pycaw.IAudioEndpointVolume)
        return controllo

    def leggi_volume(self) -> int:
        return _limita(self._generale().GetMasterVolumeLevelScalar() * 100)

    def imposta_volume(self, percentuale: int):
        self._generale().SetMasterVolumeLevelScalar(_limita(percentuale) / 100, None)

    def e_muto(self) -> bool:
        return bool(self._generale().GetMute())

    def imposta_muto(self, muto: bool):
        self._generale().SetMute(int(bool(muto)), None)

    def sessioni(self) -> list[SessioneAudio]:
        pycaw = self._pycaw()
        trovate = []
        for sessione in pycaw.AudioUtilities.GetAllSessions():
            processo = sessione.Process
            if processo is not None:
                trovate.append(SessioneAudio(processo.name(), sessione.SimpleAudioVolume))
        return trovate

    def premi_tasto(self, codice: int):
        if sys.platform != "win32":
            raise AudioNonDisponibile("I tasti multimediali funzionano solo su Windows.")
        utente = ctypes.windll.user32
        utente.keybd_event(codice, 0, 0, 0)
        utente.keybd_event(codice, 0, RILASCIA_TASTO, 0)

    def cosa_suona(self) -> tuple[str, str] | None:
        try:
            from winrt.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as Gestore,
            )
        except ImportError as errore:
            raise AudioNonDisponibile(COME_INSTALLARE_WINRT) from errore

        async def leggi():
            gestore = await Gestore.request_async()
            sessione = gestore.get_current_session()
            if sessione is None:
                return None
            info = await sessione.try_get_media_properties_async()
            return info.title or "", info.artist or ""

        return asyncio.run(leggi())

    def apri(self, indirizzo: str):
        if indirizzo.startswith("spotify:"):
            os.startfile(indirizzo)
        else:
            webbrowser.open(indirizzo)


# ------------------------------------------------------------------ strumenti


def crea_strumenti_audio(audio=None) -> list:
    audio = audio or AudioWindows()

    def _volume_tasti(azione: str, passo: int) -> str:
        """Piano B senza pycaw: usa i tasti del volume della tastiera."""
        if azione == "muto" or azione == "riattiva":
            audio.premi_tasto(TASTO_MUTO)
            return "🔇 Ho premuto il tasto muto."
        tasto = TASTO_VOLUME_SU if azione == "alza" else TASTO_VOLUME_GIU
        for _ in range(max(1, passo // PUNTI_PER_TASTO)):
            audio.premi_tasto(tasto)
        verso = "alzato" if azione == "alza" else "abbassato"
        return f"🔊 Ho {verso} il volume di circa {passo}%."

    def _volume_app(nome_app: str, azione: str, valore) -> str:
        cercato = _normalizza(nome_app).removesuffix(".exe")
        sessioni = [
            sessione for sessione in audio.sessioni()
            if cercato and cercato in _normalizza(sessione.nome)
        ]
        if not sessioni:
            return (
                f"Non trovo '{nome_app}' tra le app che stanno usando l'audio. "
                "Deve essere aperta e aver già fatto un suono."
            )

        nome = sessioni[0].nome.removesuffix(".exe")
        if azione == "leggi":
            return f"🔊 Il volume di {nome} è al {sessioni[0].leggi_volume()}%."

        for sessione in sessioni:
            if azione == "muto":
                sessione.imposta_muto(True)
            elif azione == "riattiva":
                sessione.imposta_muto(False)
            elif azione == "imposta":
                sessione.imposta_volume(valore)
            else:
                passo = valore if azione == "alza" else -valore
                sessione.imposta_volume(sessione.leggi_volume() + passo)

        if azione == "muto":
            return f"🔇 Ho silenziato {nome}."
        if azione == "riattiva":
            return f"🔊 Ho riattivato l'audio di {nome}."
        return f"🔊 Volume di {nome} al {sessioni[0].leggi_volume()}%."

    def volume(azione: str, valore: int | None = None, app: str | None = None) -> str:
        """Regola il volume del PC, oppure di una singola app come Discord, Spotify o Chrome.

        Args:
            azione: Una tra "imposta", "alza", "abbassa", "muto", "riattiva" oppure "leggi".
            valore: Per "imposta" il volume da 0 a 100; per "alza" e "abbassa" di quanto cambiarlo (se manca, 10).
            app: Il nome dell'app di cui cambiare il volume, ad esempio "Discord". Se manca si usa il volume generale.
        """
        azione = _normalizza(azione)
        sinonimi = {"su": "alza", "aumenta": "alza", "giu": "abbassa", "diminuisci": "abbassa",
                    "silenzia": "muto", "togli muto": "riattiva", "attiva": "riattiva",
                    "quanto": "leggi", "imposta a": "imposta"}
        azione = sinonimi.get(azione, azione)

        if azione not in {"imposta", "alza", "abbassa", "muto", "riattiva", "leggi"}:
            return "Azione non valida: usa imposta, alza, abbassa, muto, riattiva oppure leggi."
        if azione == "imposta" and valore is None:
            return "Dimmi a quanto impostare il volume, da 0 a 100."

        try:
            valore = PASSO_PREDEFINITO if valore is None else _limita(valore)
        except (TypeError, ValueError):
            return "Il valore del volume deve essere un numero da 0 a 100."

        try:
            if app:
                return _volume_app(app, azione, valore)

            if azione == "leggi":
                stato = " (muto)" if audio.e_muto() else ""
                return f"🔊 Il volume è al {audio.leggi_volume()}%{stato}."
            if azione == "muto":
                audio.imposta_muto(True)
                return "🔇 Audio silenziato."
            if azione == "riattiva":
                audio.imposta_muto(False)
                return f"🔊 Audio riattivato, volume al {audio.leggi_volume()}%."

            if azione == "imposta":
                nuovo = valore
            else:
                attuale = audio.leggi_volume()
                nuovo = attuale + valore if azione == "alza" else attuale - valore
            audio.imposta_volume(_limita(nuovo))
            if audio.e_muto() and _limita(nuovo) > 0:
                audio.imposta_muto(False)
            return f"🔊 Volume al {_limita(nuovo)}%."

        except AudioNonDisponibile as errore:
            if not app and azione in {"alza", "abbassa", "muto", "riattiva"}:
                try:
                    return _volume_tasti(azione, valore)
                except AudioNonDisponibile:
                    pass
            return str(errore)
        except Exception as errore:
            logger.exception("Volume non riuscito")
            return f"Non sono riuscito a cambiare il volume: {errore}"

    def musica(azione: str, testo: str | None = None, dove: str | None = None) -> str:
        """Comanda la musica o i video in riproduzione, oppure cerca qualcosa da ascoltare.

        Args:
            azione: Una tra "play", "pausa", "avanti", "indietro", "stop", "cosa_suona" oppure "cerca".
            testo: Per "cerca", cosa cercare, ad esempio "musica lo-fi per studiare".
            dove: Per "cerca", "youtube" oppure "spotify". Se manca si usa YouTube.
        """
        azione = _normalizza(azione).replace(" ", "_")

        try:
            if azione in AZIONI_MUSICA:
                tasto = AZIONI_MUSICA[azione]
                audio.premi_tasto(tasto)
                return MESSAGGI_MUSICA[tasto]

            if azione in {"cosa_suona", "cosa_sta_suonando", "titolo"}:
                brano = audio.cosa_suona()
                if not brano or not brano[0]:
                    return "In questo momento non sta suonando niente che io possa vedere."
                titolo, artista = brano
                return f"🎵 Sta suonando: {titolo}" + (f" di {artista}" if artista else "") + "."

            if azione == "cerca":
                if not testo or not str(testo).strip():
                    return "Dimmi cosa cercare."
                testo = str(testo).strip()
                if _normalizza(dove or "") == "spotify":
                    try:
                        audio.apri(f"spotify:search:{quote(testo)}")
                    except OSError:
                        audio.apri(f"https://open.spotify.com/search/{quote(testo)}")
                    return f"🎵 Ho cercato '{testo}' su Spotify."
                audio.apri(f"https://www.youtube.com/results?search_query={quote_plus(testo)}")
                return f"🎵 Ho cercato '{testo}' su YouTube."

        except AudioNonDisponibile as errore:
            return str(errore)
        except Exception as errore:
            logger.exception("Comando musica non riuscito")
            return f"Non ci sono riuscito: {errore}"

        return "Azione non valida: usa play, pausa, avanti, indietro, stop, cosa_suona oppure cerca."

    return [volume, musica]