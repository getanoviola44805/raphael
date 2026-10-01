"""Strumenti con cui il modello può leggere e scrivere la memoria a lungo termine.

Le funzioni vengono create collegandole a una memoria precisa, così Ollama vede
due semplici strumenti, 'ricorda' e 'dimentica', con il loro parametro di testo.
"""


def crea_strumenti_memoria(memoria) -> list:
    def ricorda(informazione: str) -> str:
        """Salva nella memoria a lungo termine un fatto duraturo sull'utente.

        Usalo quando l'utente ti chiede di ricordare qualcosa, oppure quando ti
        dice di sé qualcosa che resterà vero nel tempo, come il nome, gli studi,
        il lavoro, i progetti in corso o come preferisce le risposte.
        Non usarlo per cose temporanee, di poco conto o già presenti in memoria.
        Non salvare mai password, codici, dati bancari o informazioni sulla salute.

        Args:
            informazione: Il fatto da ricordare, in una frase breve in terza persona, ad esempio "Studia Ingegneria Informatica a Catania".
        """
        return memoria.aggiungi(informazione)

    def dimentica(informazione: str) -> str:
        """Cancella un ricordo dalla memoria a lungo termine.

        Usalo solo quando l'utente ti chiede di dimenticare qualcosa o ti dice
        che un'informazione che ricordi non è più vera.

        Args:
            informazione: Il ricordo da cancellare, scritto come compare in memoria.
        """
        return memoria.dimentica(informazione)

    return [ricorda, dimentica]