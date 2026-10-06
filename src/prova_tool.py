import ollama

from ai.ollama_provider import OllamaProvider
from core import config
from core.app import RaphaelApp


# Creiamo una vera RaphaelApp: così gli strumenti sono IDENTICI a quelli
# che usa il programma vero, non una copia parziale.
app = RaphaelApp()
provider = app.ai_router.provider

messaggi = [
    {"role": "system", "content": config.SYSTEM_PROMPT},
    {"role": "user", "content": "ricordami tra 10 secondi che devo controllare il forno"},
]

pezzi = ollama.chat(
    model=config.OLLAMA_MODEL,
    messages=messaggi,
    think=False,
    options={"num_ctx": config.OLLAMA_CONTEXT_LENGTH},
    stream=True,
    tools=provider.strumenti,
)

for pezzo in pezzi:
    messaggio = pezzo["message"]
    if messaggio.get("content"):
        print("TESTO:", messaggio["content"])
    if messaggio.get("tool_calls"):
        print("TOOL_CALLS:", messaggio["tool_calls"])
    else:
        print("(nessun tool_call in questo pezzo)")