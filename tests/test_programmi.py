"""Riconoscere un programma anche se l'utente lo chiama in un altro modo."""

from tools import pc_control


PROGRAMMI = [
    {"nome": "Autodesk Fusion", "id": "fusion"},
    {"nome": "Microsoft Teams", "id": "teams"},
    {"nome": "WordPad", "id": "wordpad"},
    {"nome": "Google Chrome", "id": "chrome"},
    {"nome": "Visual Studio Code", "id": "vscode"},
]


def test_trova_il_programma_con_un_nome_diverso():
    assert pc_control.trova_programma("Fusion 360", PROGRAMMI)["nome"] == "Autodesk Fusion"
    assert pc_control.trova_programma("Autodesk Fusion 360", PROGRAMMI)["nome"] == "Autodesk Fusion"


def test_le_parole_generiche_non_bastano():
    assert pc_control.trova_programma("Microsoft Word", PROGRAMMI) is None
    assert pc_control.trova_programma("Google Maps", PROGRAMMI) is None


def test_i_numeri_da_soli_non_bastano():
    assert pc_control.trova_programma("360", PROGRAMMI) is None


def test_la_corrispondenza_esatta_vince_ancora():
    assert pc_control.trova_programma("google chrome", PROGRAMMI)["nome"] == "Google Chrome"
    assert pc_control.trova_programma("vs code", PROGRAMMI)["nome"] == "Visual Studio Code"