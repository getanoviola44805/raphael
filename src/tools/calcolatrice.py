"""Calcolatrice esatta: i modelli linguistici sbagliano i conti, Python no.

L'espressione viene analizzata con il modulo ast e si calcolano solo numeri,
operazioni e funzioni matematiche note: nessun altro codice viene eseguito.
"""

import ast
import math
import operator


MAX_ESPONENTE = 10_000
MAX_CIFRE = 10_000
MAX_LUNGHEZZA = 300

OPERAZIONI = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
OPERAZIONI_UNARIE = {ast.UAdd: operator.pos, ast.USub: operator.neg}

FUNZIONI = {
    "sqrt": math.sqrt, "radice": math.sqrt, "cbrt": lambda x: math.copysign(abs(x) ** (1 / 3), x),
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "sen": math.sin, "tg": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan, "atan2": math.atan2,
    "arcsin": math.asin, "arccos": math.acos, "arctan": math.atan,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "log": math.log, "ln": math.log, "log10": math.log10, "log2": math.log2,
    "exp": math.exp, "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil,
    "factorial": math.factorial, "fattoriale": math.factorial,
    "gradi": math.degrees, "degrees": math.degrees,
    "radianti": math.radians, "radians": math.radians,
    "min": min, "max": max, "hypot": math.hypot,
    "comb": math.comb, "perm": math.perm, "gcd": math.gcd, "mcd": math.gcd,
    "lcm": math.lcm, "mcm": math.lcm,
}
FUNZIONI_PESANTI = {"factorial", "fattoriale", "comb", "perm"}
COSTANTI = {"pi": math.pi, "π": math.pi, "e": math.e, "tau": math.tau, "inf": math.inf}

SOSTITUZIONI = {
    "×": "*", "·": "*", "÷": "/", "−": "-", "^": "**", "√": "sqrt", "π": "pi",
}


class _Errore(Exception):
    pass


def _potenza_enorme(base, esponente) -> bool:
    """Evita conti come 9**9**9 che bloccherebbero il computer."""
    if abs(esponente) > MAX_ESPONENTE:
        return True
    if abs(base) <= 1 or esponente <= 0:
        return False
    return esponente * math.log10(abs(base)) > MAX_CIFRE


def _valuta(nodo):
    if isinstance(nodo, ast.Expression):
        return _valuta(nodo.body)

    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)) \
            and not isinstance(nodo.value, bool):
        return nodo.value

    if isinstance(nodo, ast.Name):
        if nodo.id in COSTANTI:
            return COSTANTI[nodo.id]
        raise _Errore(f"non conosco '{nodo.id}'")

    if isinstance(nodo, ast.BinOp) and type(nodo.op) in OPERAZIONI:
        sinistra, destra = _valuta(nodo.left), _valuta(nodo.right)
        if isinstance(nodo.op, ast.Pow) and _potenza_enorme(sinistra, destra):
            raise _Errore("il risultato sarebbe troppo grande")
        return OPERAZIONI[type(nodo.op)](sinistra, destra)

    if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in OPERAZIONI_UNARIE:
        return OPERAZIONI_UNARIE[type(nodo.op)](_valuta(nodo.operand))

    if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and not nodo.keywords:
        funzione = FUNZIONI.get(nodo.func.id)
        if funzione is None:
            raise _Errore(f"non conosco la funzione '{nodo.func.id}'")
        argomenti = [_valuta(argomento) for argomento in nodo.args]
        if nodo.func.id in FUNZIONI_PESANTI and any(abs(a) > 1000 for a in argomenti):
            raise _Errore("il numero è troppo grande per questa funzione")
        return funzione(*argomenti)

    raise _Errore("l'espressione contiene qualcosa che non è un calcolo")


def _prepara(espressione: str) -> str:
    testo = espressione.strip()
    for vecchio, nuovo in SOSTITUZIONI.items():
        testo = testo.replace(vecchio, nuovo)
    # Percentuali: "15%" diventa "(15/100)".
    testo = _percentuali(testo)
    return testo


def _percentuali(testo: str) -> str:
    risultato = []
    numero = []
    for carattere in testo:
        if carattere.isdigit() or carattere == ".":
            numero.append(carattere)
            continue
        if carattere == "%" and numero:
            risultato.append(f"({''.join(numero)}/100)")
            numero = []
            continue
        risultato.extend(numero)
        numero = []
        risultato.append(carattere)
    risultato.extend(numero)
    return "".join(risultato)


def formatta_numero(valore) -> str:
    """Scrive il numero all'italiana: virgola per i decimali, punto per le migliaia."""
    if isinstance(valore, float):
        if math.isinf(valore) or math.isnan(valore):
            return "non definito"
        if valore.is_integer() and abs(valore) < 1e15:
            valore = int(valore)

    if isinstance(valore, int):
        if abs(valore) >= 10**21:
            return f"{valore:.6e}".replace(".", ",")
        return f"{valore:,}".replace(",", ".")

    if valore != 0 and (abs(valore) < 1e-6 or abs(valore) >= 1e15):
        return f"{valore:.10g}".replace(".", ",")

    testo = f"{valore:,.10f}".rstrip("0").rstrip(".")
    return testo.replace(",", "§").replace(".", ",").replace("§", ".")


def calcola(espressione: str) -> str:
    """Calcola esattamente un'espressione matematica. Usalo per QUALSIASI conto, anche semplice, invece di farlo a mente.

    Conosce + - * / ** (o ^), %, parentesi, pi, e, sqrt, sin, cos, tan (in radianti),
    log (naturale), log10, exp, factorial, abs, round, radians, degrees.
    Usa il punto per i decimali.

    Args:
        espressione: L'espressione da calcolare, ad esempio "2450 * 17.3%" oppure "sqrt(3**2 + 4**2)".
    """
    if len(espressione) > MAX_LUNGHEZZA:
        return "L'espressione è troppo lunga."

    preparata = _prepara(espressione)

    try:
        albero = ast.parse(preparata, mode="eval")
        risultato = _valuta(albero)
    except ZeroDivisionError:
        return f"{espressione}: impossibile, c'è una divisione per zero."
    except _Errore as errore:
        return f"Non riesco a calcolare '{espressione}': {errore}."
    except (SyntaxError, ValueError, TypeError, OverflowError) as errore:
        return f"Non riesco a calcolare '{espressione}': {errore}."

    return f"{espressione} = {formatta_numero(risultato)}"