import re

from pylatexenc.latex2text import (
    LatexNodes2Text,
    MacroTextSpec,
    get_default_latex_context_db,
)


def _frazione(nodo, l2tobj):
    argomenti = nodo.nodeargd.argnlist
    numeratore = l2tobj.nodelist_to_text([argomenti[0]]).strip()
    denominatore = l2tobj.nodelist_to_text([argomenti[1]]).strip()

    def tra_parentesi(parte):
        if len(parte) == 1 or parte.isdigit():
            return parte
        return f"({parte})"

    return f"{tra_parentesi(numeratore)}/{tra_parentesi(denominatore)}"


def _crea_convertitore():
    contesto = get_default_latex_context_db()
    contesto.add_context_category(
        "raphael",
        prepend=True,
        macros=[
            MacroTextSpec(nome, simplify_repl=_frazione)
            for nome in ("frac", "dfrac", "tfrac")
        ],
    )
    return LatexNodes2Text(
        latex_context=contesto,
        strict_latex_spaces="based-on-source",
    )


_convertitore = _crea_convertitore()

# Blocchi di codice (```...```) e codice in linea (`...`): non vanno toccati
_BLOCCHI_CODICE = re.compile(r"(```.*?```|`[^`\n]+`)", re.DOTALL)

# Formule LaTeX: $$...$$, \[...\], \(...\), $...$
_FORMULE = re.compile(
    r"\$\$(.+?)\$\$"
    r"|\\\[(.+?)\\\]"
    r"|\\\((.+?)\\\)"
    r"|(?<![\$\w])\$(?!\s)([^$\n]+?)(?<!\s)\$(?![\$\w])",
    re.DOTALL,
)


def _latex_in_testo(formula: str) -> str:
    try:
        return _convertitore.latex_to_text(formula).strip()
    except Exception:
        return formula


def _sostituisci(match):
    formula = next(gruppo for gruppo in match.groups() if gruppo is not None)
    return _latex_in_testo(formula)


def converti_latex(testo: str) -> str:
    parti = _BLOCCHI_CODICE.split(testo)
    risultato = []

    for indice, parte in enumerate(parti):
        if indice % 2 == 1:
            risultato.append(parte)
        else:
            risultato.append(_FORMULE.sub(_sostituisci, parte))

    return "".join(risultato)