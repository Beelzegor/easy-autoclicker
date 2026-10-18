"""Pruebas del ejecutor de secuencias con controladores falsos."""

import time

from pynput import keyboard, mouse

from easyautoclicker.sequence import SequenceRunner, step_summary


class FakeKeyboard:
    def __init__(self):
        self.calls = []

    def press(self, key):
        self.calls.append(("press", key))

    def release(self, key):
        self.calls.append(("release", key))

    def type(self, text):
        self.calls.append(("type", text))


class FakeMouse:
    def __init__(self):
        self.calls = []
        self.position = (0, 0)

    def click(self, button, count=1):
        self.calls.append(("click", button, count))

    def press(self, button):
        self.calls.append(("press", button))

    def release(self, button):
        self.calls.append(("release", button))

    def scroll(self, dx, dy):
        self.calls.append(("scroll", dx, dy))


def run_and_wait(runner, steps, timeout=5.0, **kwargs):
    runner.start(steps, **kwargs)
    deadline = time.monotonic() + timeout
    while runner.is_running and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not runner.is_running, "la secuencia no terminó a tiempo"


def make_runner():
    kb, ms = FakeKeyboard(), FakeMouse()
    return SequenceRunner(kb, ms), kb, ms


def test_pasos_en_orden():
    runner, kb, ms = make_runner()
    steps = [
        {"kind": "key_press", "key": "a", "times": 2, "interval_ms": 0},
        {"kind": "click", "button": "Derecho", "times": 1, "interval_ms": 0},
    ]
    run_and_wait(runner, steps, loop_forever=False, repeat=1)
    assert kb.calls == [("press", "a"), ("release", "a"), ("press", "a"), ("release", "a")]
    assert ms.calls == [("click", mouse.Button.right, 1)]


def test_pasos_deshabilitados_se_saltean():
    runner, kb, ms = make_runner()
    steps = [
        {"kind": "key_press", "key": "a", "times": 1, "interval_ms": 0, "enabled": False},
        {"kind": "key_press", "key": "b", "times": 1, "interval_ms": 0},
    ]
    run_and_wait(runner, steps, loop_forever=False, repeat=1)
    assert kb.calls == [("press", "b"), ("release", "b")]


def test_sin_pasos_habilitados_no_arranca():
    runner, _, _ = make_runner()
    runner.start([{"kind": "wait", "duration": 0, "enabled": False}], loop_forever=False)
    assert not runner.is_running


def test_repeticiones_contadas():
    runner, kb, _ = make_runner()
    steps = [{"kind": "key_press", "key": "x", "times": 1, "interval_ms": 0}]
    run_and_wait(runner, steps, loop_forever=False, repeat=3)
    assert kb.calls.count(("press", "x")) == 3


def test_combinacion_en_un_paso():
    runner, kb, _ = make_runner()
    steps = [{"kind": "key_press", "key": "ctrl+c", "times": 1, "interval_ms": 0}]
    run_and_wait(runner, steps, loop_forever=False, repeat=1)
    assert kb.calls == [
        ("press", keyboard.Key.ctrl),
        ("press", "c"),
        ("release", "c"),
        ("release", keyboard.Key.ctrl),
    ]


def test_mantener_tecla_libera_siempre():
    runner, kb, _ = make_runner()
    steps = [{"kind": "key_hold", "key": "shift", "duration": 0.02}]
    run_and_wait(runner, steps, loop_forever=False, repeat=1)
    assert kb.calls == [("press", keyboard.Key.shift), ("release", keyboard.Key.shift)]


def test_mantener_clic_libera_el_boton():
    runner, _, ms = make_runner()
    steps = [{"kind": "click_hold", "button": "Izquierdo", "duration": 0.02}]
    run_and_wait(runner, steps, loop_forever=False, repeat=1)
    assert ms.calls == [("press", mouse.Button.left), ("release", mouse.Button.left)]


def test_detener_libera_la_tecla_mantenida():
    runner, kb, _ = make_runner()
    runner.start([{"kind": "key_hold", "key": "w", "duration": 5}], loop_forever=False)
    time.sleep(0.1)
    runner.stop()
    deadline = time.monotonic() + 2
    while ("release", "w") not in kb.calls and time.monotonic() < deadline:
        time.sleep(0.01)
    assert ("press", "w") in kb.calls
    assert ("release", "w") in kb.calls


def test_mover_mouse_y_rueda():
    runner, _, ms = make_runner()
    steps = [
        {"kind": "mouse_move", "x": 120, "y": 340},
        {"kind": "scroll", "scroll_amount": -2, "times": 2, "interval_ms": 0},
    ]
    run_and_wait(runner, steps, loop_forever=False, repeat=1)
    assert ms.position == (120, 340)
    assert ms.calls == [("scroll", 0, -2), ("scroll", 0, -2)]


def test_escribir_texto_caracter_por_caracter():
    runner, kb, _ = make_runner()
    steps = [{"kind": "type_text", "text": "hola", "interval_ms": 0}]
    run_and_wait(runner, steps, loop_forever=False, repeat=1)
    assert kb.calls == [("type", c) for c in "hola"]


def test_espera_aleatoria_respeta_el_rango():
    runner, _, _ = make_runner()
    inicio = time.monotonic()
    run_and_wait(
        runner,
        [{"kind": "wait_random", "min_duration": 0.05, "max_duration": 0.1}],
        loop_forever=False,
        repeat=1,
    )
    assert time.monotonic() - inicio >= 0.05


def test_paso_desconocido_no_rompe():
    runner, kb, _ = make_runner()
    steps = [
        {"kind": "paso_del_futuro"},
        {"kind": "key_press", "key": "a", "times": 1, "interval_ms": 0},
    ]
    run_and_wait(runner, steps, loop_forever=False, repeat=1)
    assert ("press", "a") in kb.calls


def test_resumenes_legibles():
    assert step_summary({"kind": "key_press", "key": "a", "times": 3}) == "Pulsar 'a' x3"
    assert step_summary({"kind": "wait", "duration": 2}) == "Esperar 2s"
    assert step_summary({"kind": "mouse_move", "x": 5, "y": 6}) == "Mover mouse a 5,6"


def test_detener_deja_la_secuencia_realmente_parada():
    runner = SequenceRunner(FakeKeyboard(), FakeMouse())
    steps = [{"enabled": True, "kind": "key_press", "key": "a", "times": 1000, "interval_ms": 20}]
    runner.start(steps, loop_forever=True)
    time.sleep(0.05)
    runner.stop()
    assert not runner.is_running
    assert runner._thread is None or not runner._thread.is_alive()


def test_arrancar_justo_despues_de_detener_no_duplica_la_secuencia():
    estados = []
    runner = SequenceRunner(
        FakeKeyboard(), FakeMouse(), on_status=estados.append
    )
    steps = [{"enabled": True, "kind": "key_press", "key": "a", "times": 1000, "interval_ms": 20}]
    runner.start(steps, loop_forever=True)
    time.sleep(0.05)
    runner.stop()
    runner.start(steps, loop_forever=True)
    assert runner.is_running
    time.sleep(0.05)
    assert "Secuencia terminada" not in estados[-1]
    runner.stop()
    assert not runner.is_running


def test_el_aviso_final_de_una_vuelta_vieja_no_apaga_la_nueva():
    pasos_marcados = []
    runner = SequenceRunner(
        FakeKeyboard(), FakeMouse(), on_step=pasos_marcados.append
    )
    steps = [{"enabled": True, "kind": "wait", "duration": 5}]
    runner.start(steps, loop_forever=True)
    runner.stop()
    runner.start(steps, loop_forever=True)
    time.sleep(0.05)
    assert runner.is_running
    assert pasos_marcados[-1] == 0
    runner.stop()
