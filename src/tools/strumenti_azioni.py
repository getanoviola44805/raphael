"""Strumenti che cambiano qualcosa sul PC, sempre passando dal GestoreAzioni.

In questo pacchetto: creare cartelle, salvare testo in un file, annullare
l'ultima azione, leggere il registro e attivare la modalità sola lettura.
Prima di chiedere conferma ogni strumento controlla che l'azione sia sicura e
calcola il percorso definitivo, così nel riquadro di conferma l'utente vede
esattamente cosa succederà.
"""

import os
from pathlib import Path

from core.azioni import (
    RISCHIO_MEDIO,
    Azione,
    AzioneNonRiuscita,
    interpreta_giorno,
)

from .lettura_file import (
    CARTELLE_ITALIANE,
    ESTENSIONI_PROTETTE,
    ESTENSIONI_TESTO,
    NOMI_PROTETTI,
    _controlla_cartella,
)
from .pc_control import ESTENSIONI_ESEGUIBILI, _normalizza


MAX_CARATTERI_DA_SALVARE = 200_000
CARATTERI_ANTEPRIMA = 400
CARTELLA_PREDEFINITA = "Documents"
CARTELLE_PRINCIPALI = {
    "Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos",
}
ESTENSIONI_SCRIVIBILI = ESTENSIONI_TESTO - ESTENSIONI_ESEGUIBILI

# Strumenti che il registro non deve annotare una seconda volta: le azioni le
# registra già il gestore, gli altri sono solo consultazioni.
STRUMENTI_GIA_REGISTRATI = {
    "crea_cartella",
    "salva_testo",
    "annulla_ultima_azione",
    "azioni_recenti",
}


# ---------------------------------------------------------------- percorsi


def destinazione(testo: str) -> Path:
    """Trasforma ciò che ha scritto il modello in un percorso nella cartella utente.

    "Fisica/riassunto.md" finisce in Documenti, "Desktop/nota.txt" sul Desktop,
    e anche i nomi italiani come "Scrivania" o "Documenti" vengono capiti.
    """
    testo = str(testo).strip().strip('"').strip("'")

    if not testo:
        raise AzioneNonRiuscita("Dimmi il nome o il percorso da usare.")

    percorso = Path(testo).expanduser()
    if percorso.is_absolute():
        return percorso

    casa = Path.home()
    parti = percorso.parts
    prima = CARTELLE_ITALIANE.get(_normalizza(parti[0]), parti[0])

    if prima in CARTELLE_PRINCIPALI or prima.startswith("OneDrive"):
        return casa.joinpath(prima, *parti[1:])

    return casa / CARTELLA_PREDEFINITA / percorso


def _controlla(percorso: Path):
    errore = _controlla_cartella(percorso)
    if errore:
        raise AzioneNonRiuscita(errore)


def _cartelle_mancanti(cartella: Path) -> list[Path]:
    """Le cartelle che andranno create, dalla più interna alla più esterna."""
    mancanti = []
    while not cartella.exists():
        mancanti.append(cartella)
        cartella = cartella.parent
    return mancanti


def _togli_cartelle_vuote(cartelle: list[Path]):
    for cartella in cartelle:
        if cartella.is_dir() and not any(cartella.iterdir()):
            cartella.rmdir()


def _nome_libero(percorso: Path) -> Path:
    numero = 2
    candidato = percorso
    while candidato.exists():
        candidato = percorso.with_name(f"{percorso.stem} ({numero}){percorso.suffix}")
        numero += 1
    return candidato


# --------------------------------------------------------------- strumenti


def crea_strumenti_azioni(gestore) -> list:
    def crea_cartella(percorso: str) -> str:
        """Crea una nuova cartella nel computer dell'utente, anche con le sottocartelle.

        Se l'utente dà solo un nome, la cartella viene creata in Documenti.
        L'utente vedrà un riquadro e dovrà confermare: non chiedergli il
        permesso a parole prima di usarlo.

        Args:
            percorso: Il percorso della cartella, ad esempio "Università/Fisica 2/Esercizi" oppure "Desktop/Progetti".
        """
        try:
            cartella = destinazione(percorso)
            _controlla(cartella)
        except AzioneNonRiuscita as errore:
            return str(errore)

        if cartella.is_dir():
            return f"La cartella {cartella} esiste già."
        if cartella.exists():
            return f"Esiste già un file che si chiama {cartella}."

        mancanti = _cartelle_mancanti(cartella)

        def esegui():
            cartella.mkdir(parents=True, exist_ok=True)
            return f"Ho creato la cartella {cartella}."

        def annulla():
            if cartella.is_dir() and any(cartella.iterdir()):
                raise AzioneNonRiuscita(
                    f"Non tolgo la cartella {cartella}: nel frattempo ci hai messo dentro dei file."
                )
            _togli_cartelle_vuote(mancanti)
            return f"Ho tolto la cartella {cartella}."

        return gestore.esegui(
            Azione(
                descrizione=f"Creare la cartella {cartella}",
                esegui=esegui,
                annulla=annulla,
                rischio=RISCHIO_MEDIO,
            )
        )

    def salva_testo(percorso: str, testo: str, aggiungi: bool | None = None) -> str:
        """Salva un testo in un file: riassunti, appunti, liste, schemi o codice.

        Se il file esiste già, viene creato un nuovo file con un numero nel
        nome, a meno che l'utente non chieda di aggiungere il testo in fondo.
        Se manca l'estensione si usa .txt; per testo formattato usa .md.
        L'utente vedrà un riquadro e dovrà confermare: non chiedergli il
        permesso a parole prima di usarlo.

        Args:
            percorso: Dove salvare il file, ad esempio "Fisica/riassunto Maxwell.md" oppure "Desktop/lista.txt".
            testo: Il testo completo da scrivere nel file.
            aggiungi: Vero per aggiungere il testo in fondo a un file che esiste già.
        """
        try:
            file = destinazione(percorso)
            if file.name.startswith(".") or file.name.lower() in NOMI_PROTETTI:
                return "Per sicurezza non scrivo file nascosti o file di chiavi e password."
            if not file.suffix:
                file = file.with_name(file.name + ".txt")
            _controlla(file.parent)
        except AzioneNonRiuscita as errore:
            return str(errore)

        estensione = file.suffix.lower()
        if file.name.lower() in NOMI_PROTETTI or estensione in ESTENSIONI_PROTETTE:
            return "Per sicurezza non scrivo file di chiavi o password."
        if estensione not in ESTENSIONI_SCRIVIBILI:
            return (
                f"Non posso salvare testo in un file {estensione}: usa per esempio "
                ".txt o .md (per sicurezza non creo mai programmi o script eseguibili)."
            )
        if file.is_dir():
            return f"{file} è una cartella: dimmi anche il nome del file."

        testo = str(testo)
        if not testo.strip():
            return "Non c'è nessun testo da salvare."
        if len(testo) > MAX_CARATTERI_DA_SALVARE:
            return "Il testo è troppo lungo da salvare in una volta."

        anteprima = testo[:CARATTERI_ANTEPRIMA]
        if len(testo) > CARATTERI_ANTEPRIMA:
            anteprima += "…"
        dettagli = f"Anteprima ({len(testo)} caratteri):\n{anteprima}"

        if aggiungi and file.is_file():
            return gestore.esegui(_azione_aggiungi(file, testo, dettagli))

        nota = ""
        if file.exists():
            originale = file
            file = _nome_libero(file)
            nota = f" ({originale.name} esiste già, quindi uso un nuovo nome)"

        return gestore.esegui(_azione_nuovo_file(file, testo, dettagli, nota))

    def annulla_ultima_azione() -> str:
        """Annulla l'ultima azione fatta sul PC, come una cartella creata o un file salvato.

        Usalo quando l'utente dice "annulla", "torna indietro" o che non voleva
        quello che hai appena fatto.
        """
        return gestore.annulla_ultima()

    def azioni_recenti(giorno: str | None = None) -> str:
        """Mostra il registro di tutto quello che hai fatto sul PC in un certo giorno.

        Usalo quando l'utente chiede cosa hai fatto, cosa hai aperto o salvato,
        o vuole controllare le tue azioni.

        Args:
            giorno: Il giorno da mostrare, ad esempio "oggi", "ieri" oppure "2026-10-01". Se manca si usa oggi.
        """
        data = interpreta_giorno(giorno)
        if data is None:
            return f"Non ho capito il giorno '{giorno}'. Usa per esempio oggi, ieri o 2026-10-01."
        return gestore.registro.riepilogo(data)

    def attiva_sola_lettura() -> str:
        """Attiva la modalità sola lettura: da quel momento non fai più nessuna azione che cambia qualcosa sul PC.

        Usalo quando l'utente ti chiede di non toccare niente o di limitarti a
        guardare. Solo l'utente può disattivarla, con /solalettura off.
        """
        return gestore.imposta_sola_lettura(True)

    return [
        crea_cartella,
        salva_testo,
        annulla_ultima_azione,
        azioni_recenti,
        attiva_sola_lettura,
    ]


def _azione_nuovo_file(file: Path, testo: str, dettagli: str, nota: str) -> Azione:
    mancanti = _cartelle_mancanti(file.parent)
    scritto = {}

    def esegui():
        file.parent.mkdir(parents=True, exist_ok=True)
        with file.open("x", encoding="utf-8") as uscita:
            uscita.write(testo)
        stato = file.stat()
        scritto["firma"] = (stato.st_size, stato.st_mtime_ns)
        return f"Ho salvato il testo in {file}{nota}."

    def annulla():
        if not file.exists():
            _togli_cartelle_vuote(mancanti)
            return f"Il file {file.name} non c'era già più."
        stato = file.stat()
        if (stato.st_size, stato.st_mtime_ns) != scritto.get("firma"):
            raise AzioneNonRiuscita(
                f"Non tolgo {file.name}: è stato modificato dopo che l'ho salvato."
            )
        file.unlink()
        _togli_cartelle_vuote(mancanti)
        return f"Ho tolto il file {file.name} che avevo salvato."

    return Azione(
        descrizione=f"Salvare un nuovo file: {file}",
        esegui=esegui,
        annulla=annulla,
        rischio=RISCHIO_MEDIO,
        dettagli=dettagli,
    )


def _azione_aggiungi(file: Path, testo: str, dettagli: str) -> Azione:
    stato = {}

    def esegui():
        stato["dimensione_prima"] = file.stat().st_size
        with file.open("a", encoding="utf-8") as uscita:
            uscita.write("\n" + testo)
        stato["dimensione_dopo"] = file.stat().st_size
        return f"Ho aggiunto il testo in fondo a {file}."

    def annulla():
        if file.stat().st_size != stato.get("dimensione_dopo"):
            raise AzioneNonRiuscita(
                f"Non tocco {file.name}: è stato modificato dopo la mia aggiunta."
            )
        with file.open("r+b") as contenuto:
            contenuto.truncate(stato["dimensione_prima"])
            contenuto.flush()
            os.fsync(contenuto.fileno())
        return f"Ho tolto il testo che avevo aggiunto a {file.name}."

    return Azione(
        descrizione=f"Aggiungere testo in fondo al file {file}",
        esegui=esegui,
        annulla=annulla,
        rischio=RISCHIO_MEDIO,
        dettagli=dettagli,
    )