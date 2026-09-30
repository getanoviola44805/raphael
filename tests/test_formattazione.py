from ui.formattazione import converti_latex


def test_testo_senza_formule_resta_uguale():
    testo = "Ciao! Le serie di Fourier sono molto utili."

    assert converti_latex(testo) == testo


def test_converte_formula_in_linea():
    risultato = converti_latex(r"La pulsazione è $\omega = \frac{2\pi}{T}$.")

    assert "ω" in risultato
    assert "π" in risultato
    assert "$" not in risultato
    assert "\\" not in risultato


def test_converte_formula_su_riga_separata():
    risultato = converti_latex(r"Ecco la formula: $$E = mc^2 + \pi$$")

    assert "π" in risultato
    assert "$" not in risultato


def test_non_tocca_il_codice():
    testo = "Nel codice `prezzo = $x$` non cambia nulla."

    assert converti_latex(testo) == testo