import re

from pylatexenc.latex2text import LatexNodes2Text


_convertitore = LatexNodes2Text()

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