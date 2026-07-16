from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    def generate_response(self, prompt: str) -> str:
        """Genera una risposta a partire dal messaggio dell'utente."""
        raise NotImplementedError