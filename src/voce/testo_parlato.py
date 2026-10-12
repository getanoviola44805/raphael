"""Prepara il testo delle risposte per essere letto ad alta voce.

Nella chat le risposte hanno Markdown, emoji, link, formule e blocchi di
codice: letti così come sono suonerebbero male ("asterisco asterisco...").
Qui si tiene solo quello che ha senso ascoltare, si scrivono orari e simboli
come li direbbe una persona ("alle 21 e 30") e si divide il testo in blocchi
di qualche frase: il primo è corto, così la voce parte subito, gli altri più
lunghi, così l'intonazione scorre come in un discorso vero.
"""

import re


MASSIMI_CARATTERI_PARLATI = 1500
LUNGHEZZA_MASSIMA_FRASE = 220
PRIMO_BLOCCO = 90       # caratteri: corto, così la voce parte subito
BLOCCO_MASSIMO = 320    # caratteri: gli altri blocchi possono essere più lunghi

# Parole che le voci pronunciano male: si riscrivono come vanno dette.
# L'accento grave indica dove cade l'accento. Vale per tutte le voci.
# Se senti una parola detta male, aggiungila qui.
PRONUNCE = {
    "Raphael": "Rafaèl",
    "file": "fàil",
    "Niscemi": "Nìscemi",
}

_BLOCCO_CODICE = re.compile(r"```.*?(?:```|$)", re.DOTALL)
_FORMULA_BLOCCO = re.compile(r"\$\$.*?\$\$|\\\[.*?\\\]", re.DOTALL)
_FORMULA_IN_LINEA = re.compile(r"\$[^$\n]+\$|\\\(.*?\\\)")
_CODICE_IN_LINEA = re.compile(r"`([^`\n]*)`")
_LINK_MARKDOWN = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_INDIRIZZO = re.compile(r"https?://\S+|www\.\S+")
# Solo il titolo "Fonti:" da solo sulla riga (come lo scrive la ricerca web) e
# tutto quello che segue: una frase come "Fonti di energia..." resta.
_FONTI = re.compile(
    r"^[ \t]*(?:#+[ \t]*)?(?:\*\*)?(?:fonti|sources)[ \t]*:?[ \t]*(?:\*\*)?[ \t]*:?[ \t]*$.*",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
_TITOLO = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_CITAZIONE = re.compile(r"^\s*>\s?", re.MULTILINE)
_PUNTO_ELENCO = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+", re.MULTILINE)
_RIGA_TABELLA = re.compile(r"^\s*\|?\s*:?-{3,}.*$", re.MULTILINE)
_SEGNI_MARKDOWN = re.compile(r"\*\*|__|\*|~~")
_SPAZI = re.compile(r"[ \t]+")
_SPAZIO_PRIMA_DELLA_PUNTEGGIATURA = re.compile(r"[ \t]+([,;:.!?])")
_FINE_FRASE = re.compile(r"(?<=[.!?…;:])\s+|\n+")
_FINE_PERIODO = re.compile(r"(?<=[.!?…])\s+|\n+")
# "21:30" è sempre un orario; "21.30" solo dopo "alle", "ore"... (3.14 è un numero).
_ORARIO = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_ORARIO_COL_PUNTO = re.compile(
    r"\b(alle|ore|dalle|entro le|verso le)\s+([01]?\d|2[0-3])\.([0-5]\d)\b", re.IGNORECASE
)
_PARENTESI = re.compile(r"\s*\(([^()\n]{1,80})\)")
_PERCENTUALE = re.compile(r"(\d)\s*%")

# Emoji e simboli: la voce li leggerebbe col loro nome inglese o li salterebbe male.
_EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U00002B00-\U00002BFF"
    "\U0000FE0F"
    "\U0000200D"
    "\U00002300-\U000023FF"
    "]+"
)


def prepara_per_la_voce(testo: str) -> str:
    """Il testo da leggere ad alta voce, senza Markdown, emoji, link e codice."""
    if not testo:
        return ""

    testo = _FONTI.sub("", testo)
    testo = _BLOCCO_CODICE.sub(" Il codice è nel messaggio. ", testo)
    testo = _FORMULA_BLOCCO.sub(" ", testo)
    testo = _FORMULA_IN_LINEA.sub(" ", testo)
    testo = _CODICE_IN_LINEA.sub(r"\1", testo)
    testo = _LINK_MARKDOWN.sub(r"\1", testo)
    testo = _INDIRIZZO.sub("", testo)
    testo = _RIGA_TABELLA.sub("", testo)
    testo = _TITOLO.sub("", testo)
    testo = _CITAZIONE.sub("", testo)
    testo = _PUNTO_ELENCO.sub("", testo)
    testo = _SEGNI_MARKDOWN.sub("", testo)
    testo = testo.replace("|", " ")
    testo = _EMOJI.sub("", testo)

    righe = [_SPAZI.sub(" ", riga).strip() for riga in testo.splitlines()]
    righe = [_SPAZIO_PRIMA_DELLA_PUNTEGGIATURA.sub(r"\1", riga) for riga in righe]
    testo = "\n".join(riga for riga in righe if riga)

    if len(testo) > MASSIMI_CARATTERI_PARLATI:
        taglio = testo.rfind(".", 0, MASSIMI_CARATTERI_PARLATI)
        testo = testo[: taglio + 1 if taglio > 0 else MASSIMI_CARATTERI_PARLATI]
        testo += "\nIl resto lo trovi scritto nella chat."

    return testo.strip()


def normalizza_per_la_voce(testo: str) -> str:
    """Scrive orari, percentuali e parentesi come li direbbe una persona."""
    testo = _ORARIO_COL_PUNTO.sub(
        lambda trovato: f"{trovato.group(1)} {_ore_e_minuti(trovato.group(2), trovato.group(3))}",
        testo,
    )
    testo = _ORARIO.sub(lambda trovato: _ore_e_minuti(trovato.group(1), trovato.group(2)), testo)
    testo = _PERCENTUALE.sub(r"\1 per cento", testo)
    testo = _PARENTESI.sub(r", \1,", testo)
    testo = testo.replace(" & ", " e ").replace(" = ", " uguale ")
    testo = re.sub(r",\s*([.!?;:,])", r"\1", testo)
    return applica_pronunce(testo)


def applica_pronunce(testo: str, pronunce: dict | None = None) -> str:
    """Riscrive le parole del dizionario come vanno pronunciate."""
    for parola, pronuncia in (PRONUNCE if pronunce is None else pronunce).items():
        testo = re.sub(rf"\b{re.escape(parola)}\b", pronuncia, testo, flags=re.IGNORECASE)
    return testo


def _ore_e_minuti(ore: str, minuti: str) -> str:
    if minuti == "00":
        return str(int(ore))
    return f"{int(ore)} e {int(minuti)}"


def dividi_in_blocchi(testo: str) -> list[str]:
    """Raggruppa le frasi in blocchi: il primo corto, gli altri più lunghi."""
    blocchi, attuale = [], ""
    for frase in _periodi(testo):
        limite = PRIMO_BLOCCO if not blocchi else BLOCCO_MASSIMO
        if attuale and len(attuale) + len(frase) + 1 > limite:
            blocchi.append(attuale)
            attuale = frase
        else:
            attuale = f"{attuale} {frase}".strip()
    if attuale:
        blocchi.append(attuale)
    return blocchi


def _periodi(testo: str) -> list[str]:
    """Come dividi_in_frasi, ma spezza solo su . ! ? e a capo, non sui due punti."""
    periodi = []
    for pezzo in _FINE_PERIODO.split(testo or ""):
        pezzo = pezzo.strip()
        if pezzo and any(carattere.isalnum() for carattere in pezzo):
            periodi.extend(_spezza_se_lunga(pezzo))
    return periodi


def dividi_in_frasi(testo: str) -> list[str]:
    """Divide il testo in frasi brevi: la prima si sente subito, le altre seguono."""
    frasi = []
    for pezzo in _FINE_FRASE.split(testo or ""):
        pezzo = pezzo.strip()
        if not pezzo or not any(carattere.isalnum() for carattere in pezzo):
            continue
        frasi.extend(_spezza_se_lunga(pezzo))
    return frasi


def _spezza_se_lunga(frase: str) -> list[str]:
    if len(frase) <= LUNGHEZZA_MASSIMA_FRASE:
        return [frase]

    pezzi, attuale = [], ""
    for parte in re.split(r"(?<=,)\s+", frase):
        if attuale and len(attuale) + len(parte) + 1 > LUNGHEZZA_MASSIMA_FRASE:
            pezzi.append(attuale)
            attuale = parte
        else:
            attuale = f"{attuale} {parte}".strip()
    if attuale:
        pezzi.append(attuale)
    return pezzi