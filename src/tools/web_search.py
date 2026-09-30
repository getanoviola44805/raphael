import logging
from datetime import date

from ddgs import DDGS


logger = logging.getLogger(__name__)


def cerca_sul_web(domanda: str, max_risultati: int = 5) -> list[dict]:
    try:
        risultati = DDGS(timeout=10).text(
            domanda,
            region="it-it",
            max_results=max_risultati,
        )
    except Exception as errore:
        logger.warning("Ricerca web non riuscita: %s", errore)
        return []

    return [
        {
            "titolo": risultato.get("title", ""),
            "link": risultato.get("href", ""),
            "estratto": risultato.get("body", ""),
        }
        for risultato in risultati
    ]


def prepara_domanda_con_risultati(domanda: str, risultati: list[dict]) -> str:
    blocchi = [
        f"[{numero}] {risultato['titolo']}\n{risultato['estratto']}"
        for numero, risultato in enumerate(risultati, start=1)
    ]
    oggi = date.today().strftime("%d/%m/%Y")

    return (
        f"Data di oggi: {oggi}.\n\n"
        "Ecco i risultati di una ricerca sul web appena eseguita per "
        "rispondere alla domanda dell'utente:\n\n"
        + "\n\n".join(blocchi)
        + "\n\n"
        f"Domanda dell'utente: {domanda}\n\n"
        "Rispondi basandoti su questi risultati, che sono più aggiornati delle "
        "tue conoscenze. Quando usi un'informazione, indica tra parentesi quadre "
        "il numero del risultato da cui viene, ad esempio [1]. Se i risultati "
        "non contengono la risposta, dillo chiaramente invece di inventare. "
        "Non dire che non hai accesso a internet: la ricerca è già stata fatta."
    )


def formatta_fonti(risultati: list[dict]) -> str:
    righe = [
        f"{numero}. {risultato['titolo']} ({risultato['link']})"
        for numero, risultato in enumerate(risultati, start=1)
    ]
    return "**Fonti:**\n\n" + "\n".join(righe)


def ricerca_web(domanda: str) -> str:
    """Cerca informazioni aggiornate su internet.

    Usala per notizie, meteo, prezzi, orari, eventi e per tutto ciò che può
    essere cambiato di recente o che non conosci con certezza.

    Args:
        domanda: Cosa cercare, scritto come in un motore di ricerca, ad esempio "meteo Catania domani".

    Returns:
        I risultati della ricerca, numerati, con titolo, link ed estratto.
    """
    risultati = cerca_sul_web(domanda)

    if not risultati:
        return (
            f"La ricerca sul web per '{domanda}' non ha dato risultati "
            "o non è riuscita: controlla la connessione a internet."
        )

    oggi = date.today().strftime("%d/%m/%Y")
    blocchi = [
        f"[{numero}] {risultato['titolo']}\n"
        f"Link: {risultato['link']}\n"
        f"{risultato['estratto']}"
        for numero, risultato in enumerate(risultati, start=1)
    ]

    return (
        f"Ho cercato sul web: '{domanda}' ({len(risultati)} risultati).\n"
        f"Data di oggi: {oggi}.\n\n" + "\n\n".join(blocchi)
    )