from abc import ABC, abstractmethod
from collections.abc import Iterator


class AIProvider(ABC):
    @abstractmethod
    def generate_response(self, prompt: str, history: list | None = None) -> str:
        """Genera una risposta a partire dal messaggio dell'utente,
        tenendo conto opzionalmente della cronologia della conversazione."""
        raise NotImplementedError

    def generate_response_stream(
        self, prompt: str, history: list | None = None, **opzioni
    ) -> Iterator[str]:
        """Genera la risposta un pezzo alla volta.

        Di base restituisce tutta la risposta in un unico pezzo e ignora le
        opzioni aggiuntive (ragionamento, immagini...): i provider che le
        supportano possono sovrascrivere questo metodo."""
        yield self.generate_response(prompt, history)