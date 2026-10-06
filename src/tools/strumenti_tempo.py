"""Strumenti per promemoria e timer, collegati all'agenda di Raphael."""

from datetime import datetime

from core.promemoria import MASSIMO_ANTICIPO, descrivi_quando, interpreta_quando


ESEMPI_QUANDO = (
    "per esempio 'tra 10 minuti', 'alle 18:30', 'domani alle 9', "
    "'venerdì alle 15' oppure '5/10 alle 15'"
)


def crea_strumenti_tempo(agenda, adesso=datetime.now) -> list:
    def imposta_promemoria(quando: str, testo: str) -> str:
        """Imposta un promemoria o un timer: all'ora giusta l'utente riceve una notifica.

        Usalo per "ricordami di...", "svegliami alle...", "timer di 10 minuti",
        "avvisami tra mezz'ora". Per un timer usa quando = "tra N minuti".

        Args:
            quando: Quando avvisare, in italiano, ad esempio "tra 10 minuti", "alle 18:30", "domani alle 9", "venerdì alle 15" oppure "2026-10-05 15:00".
            testo: Cosa ricordare, breve, ad esempio "Togliere la pasta" oppure "Prenotare l'appello di Fisica 2".
        """
        ora_attuale = adesso()
        momento = interpreta_quando(quando, ora_attuale)

        if momento is None:
            return f"Non ho capito quando: '{quando}'. Scrivilo {ESEMPI_QUANDO}."
        if momento <= ora_attuale:
            return f"{descrivi_quando(momento, ora_attuale).capitalize()} è già passato."
        if momento - ora_attuale > MASSIMO_ANTICIPO:
            return "Posso impostare promemoria al massimo per il prossimo anno."

        testo = " ".join(str(testo).split()) or "Promemoria"

        try:
            agenda.aggiungi(testo, momento)
        except ValueError as errore:
            return f"Non posso aggiungere il promemoria: {errore}."

        return f"⏰ Ti avviserò {descrivi_quando(momento, ora_attuale)}: {testo}"

    def elenca_promemoria() -> str:
        """Mostra i promemoria e i timer ancora in attesa."""
        return agenda.formatta_elenco(adesso())

    def cancella_promemoria(riferimento: str) -> str:
        """Cancella un promemoria o un timer in attesa.

        Args:
            riferimento: Il numero del promemoria come compare nell'elenco, una parte del suo testo, oppure "tutti".
        """
        return agenda.cancella(riferimento)

    return [imposta_promemoria, elenca_promemoria, cancella_promemoria]