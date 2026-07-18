from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    def generate_response(self, prompt: str, history: list | None = None) -> str:
        """Genera una risposta a partire dal messaggio dell'utente,
        tenendo conto opzionalmente della cronologia della conversazione."""
        raise NotImplementedError