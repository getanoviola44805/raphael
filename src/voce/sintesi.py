"""La voce di Raphael: trasforma il testo in parlato e lo riproduce.

Due motori, uno di riserva all'altro:
- Giuseppe (voce neurale Microsoft, via edge-tts): la più naturale, ma serve
  internet e il testo letto passa dai server Microsoft;
- Nicola (Kokoro, sul tuo PC): funziona sempre, anche senza internet.
Se Giuseppe non risponde, Raphael passa da solo a Nicola per un minuto e poi
riprova. Con /voce offline usa solo Nicola.

Come funziona la lettura:
- il testo viene ripulito e diviso in blocchi di frasi (testo_parlato.py);
- un thread prepara l'audio di un blocco alla volta;
- un altro thread lo suona in un flusso continuo: mentre senti un blocco il
  successivo è già pronto, e tra i due non ci sono stacchi;
- ferma() zittisce Raphael subito e scarta i blocchi in attesa.

Un motore è un oggetto con genera(testo) -> (audio, frequenza): se ne possono
aggiungere altri senza toccare il resto del programma.
"""

import asyncio
import importlib.util
import io
import logging
import queue
import threading
import time
from pathlib import Path

from .testo_parlato import dividi_in_blocchi, normalizza_per_la_voce, prepara_per_la_voce


logger = logging.getLogger(__name__)

VOCE_ONLINE = "it-IT-GiuseppeMultilingualNeural"
VOCE_OFFLINE = "im_nicola"     # le altre voci di Kokoro: "if_sara"
VELOCITA_ONLINE = "+10%"       # "+0%" è la velocità normale, "+20%" ancora più svelta
VELOCITA_OFFLINE = 1.1         # 1.0 è la velocità normale
LINGUA = "it"
FILE_MODELLO = "kokoro-v1.0.onnx"
FILE_VOCI = "voices-v1.0.bin"

ATTESA_CONNESSIONE_S = 5
ATTESA_RISPOSTA_S = 15
RIPROVA_ONLINE_DOPO_S = 60
PAUSA_TRA_BLOCCHI_S = 0.12
DISSOLVENZA_S = 0.004          # evita i "clic" all'inizio e alla fine di ogni blocco

# Kokoro scrive alcune vocali italiane con i suoni inglesi (la "i" di "sit",
# la "u" di "book"): è il motivo dell'accento straniero. Qui le correggiamo.
VOCALI_DA_CORREGGERE = {"ɪ": "i", "ʊ": "u"}
# Le parole dette male (Raphael, file...) si correggono in PRONUNCE,
# dentro testo_parlato.py: valgono per tutte e due le voci.

_FINE = object()  # segnale interno: il testo è finito


# ------------------------------------------------------------- motori


def correggi_fonemi(fonemi: str) -> str:
    for sbagliata, giusta in VOCALI_DA_CORREGGERE.items():
        fonemi = fonemi.replace(sbagliata, giusta)
    return fonemi


class MotoreKokoro:
    """Voce sul PC con Kokoro: funziona senza internet."""

    nome = "Nicola (sul PC)"

    def __init__(self, cartella: Path, voce: str = VOCE_OFFLINE, velocita: float = VELOCITA_OFFLINE):
        self.cartella = Path(cartella)
        self.voce = voce
        self.velocita = velocita
        self._kokoro = None
        self._lucchetto = threading.Lock()

    def carica(self):
        with self._lucchetto:
            if self._kokoro is None:
                from kokoro_onnx import Kokoro

                self._kokoro = Kokoro(
                    str(self.cartella / FILE_MODELLO), str(self.cartella / FILE_VOCI)
                )
                logger.info("Voce Kokoro caricata (%s)", self.voce)
        return self._kokoro

    def genera(self, testo: str):
        kokoro = self.carica()
        fonemi = correggi_fonemi(kokoro.tokenizer.phonemize(testo, LINGUA))
        return kokoro.create(
            fonemi, voice=self.voce, speed=self.velocita, lang=LINGUA, is_phonemes=True
        )


class MotoreEdge:
    """Voce neurale Microsoft (la stessa del lettore di Edge): serve internet."""

    nome = "Giuseppe (online)"

    def __init__(self, voce: str = VOCE_ONLINE, velocita: str = VELOCITA_ONLINE, scarica=None):
        self.voce = voce
        self.velocita = velocita
        self._scarica = scarica or self._scarica_da_microsoft

    def carica(self):
        return None

    def _scarica_da_microsoft(self, testo: str) -> bytes:
        import edge_tts

        async def scarica():
            comunicazione = edge_tts.Communicate(
                testo,
                self.voce,
                rate=self.velocita,
                connect_timeout=ATTESA_CONNESSIONE_S,
                receive_timeout=ATTESA_RISPOSTA_S,
            )
            audio = bytearray()
            async for pezzo in comunicazione.stream():
                if pezzo["type"] == "audio":
                    audio.extend(pezzo["data"])
            return bytes(audio)

        return asyncio.run(scarica())

    def genera(self, testo: str):
        import soundfile

        mp3 = self._scarica(testo)
        if not mp3:
            raise RuntimeError("Il servizio vocale non ha mandato audio")
        audio, frequenza = soundfile.read(io.BytesIO(mp3), dtype="float32")
        return audio, frequenza


class MotoreConRiserva:
    """Usa il motore principale; se non funziona, passa alla riserva per un po'."""

    def __init__(self, principale=None, riserva=None, riprova_dopo_s: float = RIPROVA_ONLINE_DOPO_S):
        if principale is None and riserva is None:
            raise ValueError("Serve almeno un motore")
        self.principale = principale
        self.riserva = riserva
        self.riprova_dopo_s = riprova_dopo_s
        self.solo_offline = False
        self._principale_fermo_fino_a = 0.0

    def carica(self):
        if self.riserva is not None:
            self.riserva.carica()

    def _usa_principale(self) -> bool:
        if self.principale is None:
            return False
        if self.solo_offline and self.riserva is not None:
            return False
        return time.monotonic() >= self._principale_fermo_fino_a

    def descrizione(self) -> str:
        if self._usa_principale():
            return self.principale.nome
        return self.riserva.nome if self.riserva is not None else self.principale.nome

    def genera(self, testo: str):
        if self._usa_principale():
            try:
                return self.principale.genera(testo)
            except Exception as errore:
                if self.riserva is None:
                    raise
                logger.warning("Voce online non disponibile (%s): uso quella del PC", errore)
                self._principale_fermo_fino_a = time.monotonic() + self.riprova_dopo_s
        return self.riserva.genera(testo)


# ------------------------------------------------------------- riproduttore


class RiproduttoreSounddevice:
    """Suona i blocchi uno dopo l'altro in un flusso continuo, senza stacchi."""

    PEZZO = 2400  # campioni scritti alla volta: così ferma() agisce in un attimo

    def __init__(self):
        self._flusso = None
        self._frequenza = None
        self._fermato = threading.Event()
        self._lucchetto = threading.Lock()

    def _apri(self, frequenza):
        import sounddevice

        if self._flusso is not None and self._frequenza == frequenza:
            return self._flusso
        self._chiudi()
        self._flusso = sounddevice.OutputStream(
            samplerate=frequenza, channels=1, dtype="float32"
        )
        self._flusso.start()
        self._frequenza = frequenza
        return self._flusso

    def _chiudi(self, fino_alla_fine=False):
        if self._flusso is None:
            return
        try:
            if fino_alla_fine:
                self._flusso.stop()   # aspetta che l'ultimo pezzo sia suonato
            else:
                self._flusso.abort()  # taglia subito
            self._flusso.close()
        except Exception:
            pass
        self._flusso = None

    def riproduci(self, audio, frequenza):
        import numpy

        audio = numpy.asarray(audio, dtype=numpy.float32).reshape(-1).copy()
        dissolvenza = min(len(audio) // 2, int(frequenza * DISSOLVENZA_S))
        if dissolvenza:
            rampa = numpy.linspace(0.0, 1.0, dissolvenza, dtype=numpy.float32)
            audio[:dissolvenza] *= rampa
            audio[-dissolvenza:] *= rampa[::-1]
        audio = numpy.concatenate(
            [audio, numpy.zeros(int(frequenza * PAUSA_TRA_BLOCCHI_S), dtype=numpy.float32)]
        )

        self._fermato.clear()
        with self._lucchetto:
            flusso = self._apri(frequenza)
        for inizio in range(0, len(audio), self.PEZZO):
            if self._fermato.is_set():
                return
            try:
                flusso.write(audio[inizio:inizio + self.PEZZO])
            except Exception:
                if self._fermato.is_set():
                    return
                raise

    def concludi(self):
        """Il testo è finito: lascia suonare l'ultimo pezzo e libera le casse."""
        with self._lucchetto:
            self._chiudi(fino_alla_fine=True)

    def ferma(self):
        self._fermato.set()
        with self._lucchetto:
            self._chiudi()


# -------------------------------------------------------------------- voce


class Voce:
    """Legge i testi ad alta voce, un blocco dopo l'altro, interrompibile."""

    def __init__(self, motore, riproduttore=None):
        self.motore = motore
        self.riproduttore = riproduttore or RiproduttoreSounddevice()
        self._blocchi = queue.Queue()
        self._audio = queue.Queue(maxsize=3)
        self._turno = 0  # cambia a ogni ferma(): i blocchi vecchi vengono scartati
        self._testi_in_corso = 0
        self._parlando = threading.Event()
        self._avviata = False
        self._lucchetto = threading.Lock()

    # ------------------------------------------------------ comandi

    def parla(self, testo: str) -> bool:
        """Mette in coda il testo da leggere. Restituisce False se non c'è niente da dire."""
        blocchi = dividi_in_blocchi(normalizza_per_la_voce(prepara_per_la_voce(testo)))
        if not blocchi:
            return False

        self._avvia_thread()
        with self._lucchetto:
            turno = self._turno
            self._testi_in_corso += 1
            self._parlando.set()
        for blocco in blocchi:
            self._blocchi.put((turno, blocco))
        self._blocchi.put((turno, _FINE))
        return True

    def ferma(self):
        """Zittisce Raphael subito."""
        with self._lucchetto:
            self._turno += 1
            self._testi_in_corso = 0
            self._parlando.clear()
        self._svuota(self._blocchi)
        self._svuota(self._audio)
        self.riproduttore.ferma()

    def sta_parlando(self) -> bool:
        return self._parlando.is_set()

    def aspetta(self, secondi: float = 30) -> bool:
        """Aspetta che Raphael abbia finito di parlare (utile nei test)."""
        limite = time.monotonic() + secondi
        while self._parlando.is_set():
            if time.monotonic() > limite:
                return False
            time.sleep(0.01)
        return True

    def prepara(self):
        """Carica in anticipo la voce del PC, così la riserva è pronta subito."""
        try:
            self.motore.carica()
        except Exception as errore:
            logger.warning("Preparazione della voce non riuscita: %s", errore)

    # ------------------------------------------------------ thread

    def _avvia_thread(self):
        with self._lucchetto:
            if self._avviata:
                return
            self._avviata = True
        threading.Thread(target=self._genera_blocchi, daemon=True, name="voce-genera").start()
        threading.Thread(target=self._riproduci_blocchi, daemon=True, name="voce-riproduci").start()

    def _genera_blocchi(self):
        while True:
            turno, blocco = self._blocchi.get()
            if turno != self._turno:
                continue
            if blocco is _FINE:
                self._audio.put((turno, _FINE, None))
                continue
            try:
                audio, frequenza = self.motore.genera(blocco)
            except Exception:
                logger.exception("Non sono riuscito a generare la voce")
                continue
            if turno == self._turno:
                self._audio.put((turno, audio, frequenza))

    def _riproduci_blocchi(self):
        while True:
            turno, audio, frequenza = self._audio.get()
            if turno != self._turno:
                continue
            if audio is _FINE:
                self._testo_finito(turno)
                continue
            try:
                self.riproduttore.riproduci(audio, frequenza)
            except Exception:
                logger.exception("Non sono riuscito a riprodurre la voce")

    def _testo_finito(self, turno):
        with self._lucchetto:
            if turno != self._turno:
                return
            self._testi_in_corso = max(0, self._testi_in_corso - 1)
            ultimo = self._testi_in_corso == 0
        if ultimo:
            concludi = getattr(self.riproduttore, "concludi", None)
            if concludi is not None:
                try:
                    concludi()
                except Exception:
                    logger.exception("Non sono riuscito a chiudere l'audio")
            with self._lucchetto:
                if turno == self._turno and self._testi_in_corso == 0:
                    self._parlando.clear()

    @staticmethod
    def _svuota(coda):
        while True:
            try:
                coda.get_nowait()
            except queue.Empty:
                return


# ------------------------------------------------------------- creazione


def _installato(nome: str) -> bool:
    return importlib.util.find_spec(nome) is not None


def _kokoro_pronto(cartella: Path) -> bool:
    cartella = Path(cartella)
    return _installato("kokoro_onnx") and all(
        (cartella / nome).exists() for nome in (FILE_MODELLO, FILE_VOCI)
    )


def perche_manca_la_voce(cartella: Path) -> str | None:
    """None se la voce si può usare, altrimenti cosa manca, in italiano."""
    if not _installato("sounddevice"):
        return "Per la voce serve la libreria sounddevice: pip install sounddevice"
    online = _installato("edge_tts") and _installato("soundfile")
    if not online and not _kokoro_pronto(cartella):
        return (
            "Per la voce serve almeno uno dei due motori: "
            "pip install edge-tts soundfile (voce online), oppure kokoro-onnx "
            f"con i file {FILE_MODELLO} e {FILE_VOCI} in {Path(cartella)} (voce sul PC)."
        )
    return None


def crea_voce(cartella: Path):
    """La voce di Raphael, oppure None se non è installata."""
    motivo = perche_manca_la_voce(cartella)
    if motivo:
        logger.info("Voce non disponibile: %s", motivo)
        return None

    principale = MotoreEdge() if _installato("edge_tts") and _installato("soundfile") else None
    riserva = MotoreKokoro(cartella) if _kokoro_pronto(cartella) else None
    return Voce(MotoreConRiserva(principale, riserva))