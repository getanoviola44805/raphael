class CommandHandler:
    def __init__(self, app_name, app_version):
        self.app_name = app_name
        self.app_version = app_version

    def handle(self, command):
        comando = command.lower().strip()

        if comando == "ciao":
            return f"Ciao! Sono {self.app_name}."

        if comando == "versione":
            return f"Sto usando la versione {self.app_version}."

        return "Comando non riconosciuto."