from tools.calcolatrice import calcola, formatta_numero


def test_conti_semplici():
    assert calcola("2 + 3 * 4") == "2 + 3 * 4 = 14"
    assert calcola("(2 + 3) * 4") == "(2 + 3) * 4 = 20"
    assert calcola("7 / 2") == "7 / 2 = 3,5"


def test_percentuali():
    assert calcola("2450 * 17.3%") == "2450 * 17.3% = 423,85"
    assert calcola("50%") == "50% = 0,5"


def test_potenze_e_simboli():
    assert calcola("2^10") == "2^10 = 1.024"
    assert calcola("3 × 4 ÷ 2") == "3 × 4 ÷ 2 = 6"
    assert calcola("√(16)") == "√(16) = 4"


def test_funzioni_matematiche():
    assert calcola("sqrt(3**2 + 4**2)") == "sqrt(3**2 + 4**2) = 5"
    assert calcola("factorial(5)") == "factorial(5) = 120"
    assert calcola("round(pi, 4)") == "round(pi, 4) = 3,1416"
    assert calcola("sin(pi/2)") == "sin(pi/2) = 1"
    assert calcola("log(e)") == "log(e) = 1"


def test_divisione_per_zero():
    assert "divisione per zero" in calcola("1 / 0")


def test_niente_codice_pericoloso():
    for pericoloso in [
        "__import__('os').system('dir')",
        "open('file.txt')",
        "(1).__class__",
        "[x for x in range(10)]",
        "x = 5",
    ]:
        assert calcola(pericoloso).startswith("Non riesco a calcolare")


def test_numeri_enormi_rifiutati():
    assert "troppo grande" in calcola("10 ** 100000")
    assert "troppo grande" in calcola("(9 ** 9999) ** 9999")
    assert "troppo grande" in calcola("9 ^ 9 ^ 9")
    assert "troppo grande" in calcola("factorial(100000)")
    assert "troppo grande" in calcola("comb(1000000, 500000)")
    assert calcola("comb(5, 2)") == "comb(5, 2) = 10"


def test_espressione_troppo_lunga():
    assert "troppo lunga" in calcola("1+" * 200 + "1")


def test_formato_italiano():
    assert formatta_numero(1234567) == "1.234.567"
    assert formatta_numero(1234.5) == "1.234,5"
    assert formatta_numero(0.1 + 0.2) == "0,3"
    assert formatta_numero(2.0) == "2"
    assert formatta_numero(1e-9) == "1e-09"