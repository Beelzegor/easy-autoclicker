"""Pruebas de la máquina de estados de captura de teclas."""

from easyautoclicker.capture import ComboCapture


def test_tecla_sola_se_confirma_al_presionar():
    capture = ComboCapture()
    assert capture.press("f6") == "f6"


def test_combinacion_se_confirma_con_la_tecla_final():
    capture = ComboCapture()
    assert capture.press("ctrl") is None
    assert capture.press("shift") is None
    assert capture.press("a") == "ctrl+shift+a"


def test_modificador_suelto_se_confirma_al_soltarlo():
    capture = ComboCapture()
    assert capture.press("shift") is None
    assert capture.release("shift") == "shift"


def test_modificador_no_se_confirma_si_hubo_otra_tecla():
    capture = ComboCapture()
    capture.press("ctrl")
    assert capture.press("c") == "ctrl+c"
    assert capture.release("c") is None
    assert capture.release("ctrl") is None


def test_dos_modificadores_no_cuentan_como_modificador_suelto():
    capture = ComboCapture()
    capture.press("ctrl")
    capture.press("shift")
    assert capture.release("shift") is None
    assert capture.release("ctrl") is None


def test_el_teclado_puede_repetir_la_misma_tecla_apretada():
    """El autorrepetido de una tecla sostenida no debe ensuciar la captura."""
    capture = ComboCapture()
    capture.press("alt")
    capture.press("alt")
    capture.press("alt")
    assert capture.release("alt") == "alt"


def test_soltar_todo_permite_reintentar():
    capture = ComboCapture()
    capture.press("ctrl")
    capture.press("shift")
    capture.release("shift")
    capture.release("ctrl")
    capture.press("ctrl")
    assert capture.release("ctrl") == "ctrl"


def test_reset_olvida_lo_apretado():
    capture = ComboCapture()
    capture.press("ctrl")
    capture.reset()
    assert capture.held == ()
    assert capture.release("ctrl") is None


def test_sin_combinaciones_los_modificadores_se_ignoran():
    capture = ComboCapture(allow_combo=False)
    assert capture.press("ctrl") is None
    assert capture.release("ctrl") is None
    assert capture.press("a") == "a"


def test_sin_combinaciones_la_tecla_va_sola():
    capture = ComboCapture(allow_combo=False)
    capture.press("ctrl")
    assert capture.press("a") == "a"


def test_preview_muestra_lo_apretado():
    capture = ComboCapture()
    assert capture.preview() == ""
    capture.press("ctrl")
    assert capture.preview() == "CTRL+..."
    capture.press("shift")
    assert capture.preview() == "CTRL+SHIFT+..."


def test_preview_respeta_el_orden_canonico():
    capture = ComboCapture()
    capture.press("shift")
    capture.press("ctrl")
    assert capture.preview() == "CTRL+SHIFT+..."
    assert capture.press("a") == "ctrl+shift+a"


def test_nombre_vacio_no_hace_nada():
    capture = ComboCapture()
    assert capture.press("") is None
    assert capture.release("") is None
    assert capture.held == ()
