"""Pruebas de la interpretación de nombres de tecla y combinaciones."""

from pynput import keyboard

from easyautoclicker.keys import (
    combo_label,
    key_to_text,
    normalize_combo,
    normalize_key_name,
    parse_combo,
    release_combo,
    resolve_key_name,
    split_combo,
    tap_combo,
)


class FakeKeyboard:
    """Controlador de teclado falso que anota lo que se le pide."""

    def __init__(self):
        self.calls = []

    def press(self, key):
        self.calls.append(("press", key))

    def release(self, key):
        self.calls.append(("release", key))


def test_alias_en_espanol():
    assert normalize_key_name("espacio") == "space"
    assert normalize_key_name("  INTRO  ") == "enter"
    assert normalize_key_name("página abajo") == "page_down"
    assert normalize_key_name("suprimir") == "delete"


def test_modificadores_sin_lado():
    assert normalize_key_name("ctrl_l") == "ctrl"
    assert normalize_key_name("shift_r") == "shift"
    assert normalize_key_name("control") == "ctrl"


def test_caracter_suelto_se_deja_igual():
    assert normalize_key_name("A") == "a"
    assert normalize_key_name("7") == "7"


def test_resolve_devuelve_teclas_de_pynput():
    assert resolve_key_name("espacio") is keyboard.Key.space
    assert resolve_key_name("f9") is keyboard.Key.f9
    assert resolve_key_name("a") == "a"
    assert resolve_key_name("") is None
    assert resolve_key_name("no_existe_esta_tecla") is None


def test_key_to_text_normaliza_lado():
    assert key_to_text(keyboard.Key.ctrl_l) == "ctrl"
    assert key_to_text(keyboard.Key.space) == "space"
    assert key_to_text(keyboard.KeyCode.from_char("B")) == "b"


def test_split_combo_respeta_el_mas_literal():
    assert split_combo("ctrl+shift+a") == ["ctrl", "shift", "a"]
    assert split_combo("+") == ["+"]
    assert split_combo("ctrl++") == ["ctrl", "+"]
    assert split_combo("") == []


def test_normalize_combo_ordena_modificadores():
    assert normalize_combo("shift+ctrl+a") == "ctrl+shift+a"
    assert normalize_combo("control + mayus + a") == "ctrl+shift+a"
    assert normalize_combo("espacio") == "space"
    assert normalize_combo("") == ""


def test_combo_label_para_la_interfaz():
    assert combo_label("ctrl+shift+a") == "CTRL+SHIFT+A"
    assert combo_label("") == "(sin asignar)"


def test_parse_combo_falla_completo_si_una_tecla_no_existe():
    assert parse_combo("ctrl+a") == [keyboard.Key.ctrl, "a"]
    assert parse_combo("ctrl+tecla_inventada") == []


def test_tap_combo_libera_al_reves():
    fake = FakeKeyboard()
    tap_combo(fake, [keyboard.Key.ctrl, keyboard.Key.shift, "a"])
    assert fake.calls == [
        ("press", keyboard.Key.ctrl),
        ("press", keyboard.Key.shift),
        ("press", "a"),
        ("release", "a"),
        ("release", keyboard.Key.shift),
        ("release", keyboard.Key.ctrl),
    ]


def test_tap_combo_libera_aunque_falle_una_pulsacion():
    class Rompe(FakeKeyboard):
        def press(self, key):
            if key == "a":
                raise RuntimeError("fallo")
            super().press(key)

    fake = Rompe()
    try:
        tap_combo(fake, [keyboard.Key.ctrl, "a"])
    except RuntimeError:
        pass
    assert ("release", keyboard.Key.ctrl) in fake.calls


def test_release_combo_tolera_errores():
    class Rompe(FakeKeyboard):
        def release(self, key):
            raise RuntimeError("fallo")

    release_combo(Rompe(), [keyboard.Key.ctrl])  # no debe propagar
