from .config import APP_NAME, APP_VERSION


class RaphaelApp:
    def __init__(self):
        self.name = APP_NAME
        self.version = APP_VERSION

        print(f"{self.name} Core avviato - Versione {self.version}")

    def gestisci_comando(self, comando):
        comando = comando.lower().strip()

        if comando == "ciao":
            return f"Ciao! Sono {self.name}."

        if comando == "versione":
            return f"Sto usando la versione {self.version}."

        return "Comando non riconosciuto."

    def start(self):
        print(f"Benvenuto in {self.name}!")

        while True:
            comando = input("Tu: ").strip()

            if comando.lower() in {"esci", "exit", "quit"}:
                print(f"{self.name}: A presto.")
                break

            risposta = self.gestisci_comando(comando)
            print(f"{self.name}: {risposta}")