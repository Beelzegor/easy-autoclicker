"""Pruebas del grabador/reproductor de macros y del gestor de hotkeys."""

import time

from pynput import keyboard, mouse

from easyautoclicker.hotkeys import HotkeyManager
from easyautoclicker.macro import MacroRecorder


class FakeKeyboard:
    def __init__(self):
        self.calls = []

    def press(self, key):
        self.calls.append(("press", key))

    def release(self, key):
        self.calls.append(("release", key))


class FakeMouse:
    def __init__(self):
        self.calls = []
        self.position = (0, 0)

    def press(self, button):
        self.calls.append(("press", button))

    def release(self, button):
        self.calls.append(("release", button))

    def scroll(self, dx, dy):
        self.calls.append(("scroll", dx, dy))


def make_macro():
    kb, ms = FakeKeyboard(), FakeMouse()
    return MacroRecorder(ms, kb), kb, ms


def wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        time.sleep(0.01)
    return predicate()


def test_duracion_y_resumen():
    macro, _, _ = make_macro()
    assert macro.duration == 0.0
    assert macro.describe() == "Sin macro grabada"
    macro.load_dict({"events": [{"t": 0.0, "type": "move", "x": 1, "y": 1},
                                {"t": 2.5, "type": "move", "x": 2, "y": 2}]}, name="prueba")
    assert macro.duration == 2.5
    assert macro.describe() == "prueba: 2 eventos, 2.5s"


def test_reproduce_los_eventos_en_orden():
    macro, kb, ms = make_macro()
    macro.load_dict(
        {
            "events": [
                {"t": 0.0, "type": "key_down", "key": "a"},
                {"t": 0.0, "type": "key_up", "key": "a"},
                {"t": 0.0, "type": "scroll", "x": 0, "y": 0, "dx": 0, "dy": -1},
            ]
        }
    )
    macro.play(loop_forever=False, repeat=1)
    assert wait_until(lambda: not macro.is_playing)
    assert kb.calls == [("press", "a"), ("release", "a")]
    assert ms.calls == [("scroll", 0, -1)]


def test_velocidad_acelera_la_reproduccion():
    macro, kb, _ = make_macro()
    macro.load_dict(
        {"events": [{"t": 0.0, "type": "key_down", "key": "a"},
                    {"t": 0.4, "type": "key_up", "key": "a"}]}
    )
    inicio = time.monotonic()
    macro.play(loop_forever=False, repeat=1, speed=4)
    assert wait_until(lambda: not macro.is_playing)
    assert time.monotonic() - inicio < 0.35
    assert kb.calls == [("press", "a"), ("release", "a")]


def test_detener_libera_lo_que_quedo_pulsado():
    macro, kb, ms = make_macro()
    macro.load_dict(
        {
            "events": [
                {"t": 0.0, "type": "key_down", "key": "w"},
                {"t": 0.0, "type": "click", "x": 0, "y": 0, "button": "left", "pressed": True},
                {"t": 10.0, "type": "key_up", "key": "w"},
            ]
        }
    )
    macro.play(loop_forever=False, repeat=1)
    assert wait_until(lambda: ("press", "w") in kb.calls)
    macro.stop_playback()
    assert ("release", "w") in kb.calls
    assert ("release", mouse.Button.left) in ms.calls


def test_no_reproduce_una_macro_vacia():
    macro, _, _ = make_macro()
    macro.play(loop_forever=False, repeat=1)
    assert not macro.is_playing


def test_evento_invalido_no_corta_la_macro():
    macro, kb, _ = make_macro()
    macro.load_dict(
        {
            "events": [
                {"t": 0.0, "type": "key_down", "key": "tecla_inventada"},
                {"t": 0.0, "type": "key_down", "key": "b"},
            ]
        }
    )
    macro.play(loop_forever=False, repeat=1)
    assert wait_until(lambda: not macro.is_playing)
    assert ("press", "b") in kb.calls


def test_to_dict_y_load_dict_van_y_vuelven():
    macro, _, _ = make_macro()
    eventos = [{"t": 1.0, "type": "move", "x": 3, "y": 4}]
    macro.load_dict({"events": eventos, "name": "ida"})
    data = macro.to_dict()
    otra, _, _ = make_macro()
    otra.load_dict(data)
    assert otra.events == eventos
    assert otra.name == "ida"


# --------------------------------------------------------------- hotkeys --
def test_hotkeys_detecta_conflictos():
    manager = HotkeyManager(dispatch=lambda action: None)
    manager.set_bindings({"toggle": "f6", "panic": "esc"})
    assert manager.conflicting_action("f6") == "toggle"
    assert manager.conflicting_action("f6", ignore_action="toggle") is None
    assert manager.conflicting_action("f10") is None


def test_hotkeys_normaliza_y_descarta_vacias():
    manager = HotkeyManager(dispatch=lambda action: None)
    manager.set_bindings({"toggle": "shift+ctrl+a", "play": ""})
    assert manager.bindings() == {"toggle": "ctrl+shift+a"}


def test_uses_key_sirve_para_filtrar_la_grabacion():
    manager = HotkeyManager(dispatch=lambda action: None)
    manager.set_bindings({"toggle": "f6", "play": "ctrl+shift+p"})
    assert manager.uses_key("f6")
    assert manager.uses_key("shift")
    assert not manager.uses_key("a")
    assert not manager.uses_key("")


def test_dispara_la_accion_de_la_combinacion():
    disparadas = []
    manager = HotkeyManager(dispatch=disparadas.append)
    manager.set_bindings({"toggle": "ctrl+f6", "panic": "esc"})

    manager._on_press(keyboard.Key.ctrl_l)
    manager._on_press(keyboard.Key.f6)
    assert disparadas == ["toggle"]

    # Sin el modificador no coincide.
    manager._on_release(keyboard.Key.ctrl_l)
    manager._on_press(keyboard.Key.f6)
    assert disparadas == ["toggle"]

    manager._on_press(keyboard.Key.esc)
    assert disparadas == ["toggle", "panic"]


def test_en_pausa_no_dispara_nada():
    disparadas = []
    manager = HotkeyManager(dispatch=disparadas.append)
    manager.set_bindings({"toggle": "f6"})
    manager.paused = True
    manager._on_press(keyboard.Key.f6)
    assert disparadas == []


def test_hotkey_de_una_letra_se_ignora_mientras_se_escribe():
    disparadas = []
    escribiendo = {"valor": True}
    manager = HotkeyManager(
        dispatch=disparadas.append, should_ignore_plain=lambda: escribiendo["valor"]
    )
    manager.set_bindings({"toggle": "k"})

    manager._on_press(keyboard.KeyCode.from_char("k"))
    assert disparadas == []

    escribiendo["valor"] = False
    manager._on_press(keyboard.KeyCode.from_char("k"))
    assert disparadas == ["toggle"]
