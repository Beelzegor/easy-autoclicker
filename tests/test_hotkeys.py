"""Pruebas del motor de hotkeys globales (sin escuchar el teclado real)."""

from pynput import keyboard

from easyautoclicker.hotkeys import HotkeyManager


def make_manager(bindings, typing=False):
    fired = []
    manager = HotkeyManager(dispatch=fired.append, should_ignore_plain=lambda: typing)
    manager.set_bindings(bindings)
    return manager, fired


def test_tecla_simple_dispara_al_presionar():
    manager, fired = make_manager({"toggle": "f6"})
    manager._on_press(keyboard.Key.f6)
    assert fired == ["toggle"]


def test_combinacion_dispara_con_los_modificadores_apretados():
    manager, fired = make_manager({"toggle": "ctrl+shift+a"})
    manager._on_press(keyboard.Key.ctrl_l)
    manager._on_press(keyboard.Key.shift)
    manager._on_press(keyboard.KeyCode.from_char("a"))
    assert fired == ["toggle"]


def test_modificador_suelto_dispara_al_soltarlo():
    manager, fired = make_manager({"panic": "shift"})
    manager._on_press(keyboard.Key.shift)
    assert fired == []
    manager._on_release(keyboard.Key.shift)
    assert fired == ["panic"]


def test_modificador_no_dispara_si_se_uso_en_combinacion():
    manager, fired = make_manager({"panic": "ctrl", "toggle": "ctrl+c"})
    manager._on_press(keyboard.Key.ctrl_l)
    manager._on_press(keyboard.KeyCode.from_char("c"))
    manager._on_release(keyboard.KeyCode.from_char("c"))
    manager._on_release(keyboard.Key.ctrl_l)
    assert fired == ["toggle"]


def test_cualquier_lado_del_teclado_sirve():
    manager, fired = make_manager({"panic": "ctrl"})
    manager._on_press(keyboard.Key.ctrl_r)
    manager._on_release(keyboard.Key.ctrl_r)
    assert fired == ["panic"]


def test_en_pausa_no_dispara_nada():
    manager, fired = make_manager({"toggle": "f6", "panic": "shift"})
    manager.paused = True
    manager._on_press(keyboard.Key.f6)
    manager._on_press(keyboard.Key.shift)
    manager._on_release(keyboard.Key.shift)
    assert fired == []


def test_escribiendo_no_dispara_hotkeys_de_una_tecla():
    manager, fired = make_manager({"toggle": "a", "panic": "shift"}, typing=True)
    manager._on_press(keyboard.KeyCode.from_char("a"))
    manager._on_press(keyboard.Key.shift)
    manager._on_release(keyboard.Key.shift)
    assert fired == []


def test_escribiendo_si_dispara_combinaciones_y_funciones():
    manager, fired = make_manager({"toggle": "f6", "play": "ctrl+shift+p"}, typing=True)
    manager._on_press(keyboard.Key.f6)
    manager._on_press(keyboard.Key.ctrl_l)
    manager._on_press(keyboard.Key.shift)
    manager._on_press(keyboard.KeyCode.from_char("p"))
    assert fired == ["toggle", "play"]


def test_conflicto_detecta_la_accion_que_ya_usa_la_combinacion():
    manager, _ = make_manager({"toggle": "f6", "panic": "esc"})
    assert manager.conflicting_action("f6") == "toggle"
    assert manager.conflicting_action("f6", ignore_action="toggle") is None
    assert manager.conflicting_action("f7") is None


def test_uses_key_mira_dentro_de_las_combinaciones():
    manager, _ = make_manager({"play": "ctrl+shift+p"})
    assert manager.uses_key("ctrl")
    assert manager.uses_key("p")
    assert not manager.uses_key("q")
