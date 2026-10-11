"""Ejecutor de secuencias: pasos ordenados que corren uno después del otro."""

import threading

from .keys import resolve_key_name


class SequenceRunner:
    """Ejecuta una lista ordenada de pasos (tecla, clic o espera), en orden."""

    def __init__(self, keyboard_controller, mouse_controller, on_status=None, on_step=None):
        self.keyboard_controller = keyboard_controller
        self.mouse_controller = mouse_controller
        self.on_status = on_status or (lambda text: None)
        self.on_step = on_step or (lambda index: None)

        self._running = False
        self._stop_event = threading.Event()
        self._thread = None

    @property
    def is_running(self):
        return self._running

    def start(self, steps, loop_forever=True, repeat=1):
        if self._running or not steps:
            return
        self._running = True
        self._stop_event.clear()

        def run_once():
            for i, step in enumerate(steps):
                if self._stop_event.is_set():
                    return False
                self.on_step(i)
                if not self._run_step(step):
                    return False
            return True

        def loop():
            count = 0
            while not self._stop_event.is_set():
                ok = run_once()
                if not ok:
                    break
                count += 1
                if not loop_forever and count >= repeat:
                    break
            self._running = False
            self.on_step(-1)
            self.on_status("Secuencia terminada")

        self.on_status("Ejecutando secuencia...")
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._running = False

    def _run_step(self, step):
        kind = step.get("kind")
        try:
            if kind == "key_press":
                return self._run_key_press(step)
            if kind == "key_hold":
                return self._run_key_hold(step)
            if kind == "click":
                return self._run_click(step)
            if kind == "wait":
                return self._wait(step.get("duration", 1.0))
        except Exception:
            pass
        return True

    def _run_key_press(self, step):
        key = resolve_key_name(step.get("key", ""))
        if key is None:
            return True
        times = max(int(step.get("times", 1)), 1)
        interval = max(float(step.get("interval_ms", 50)), 0.0) / 1000.0
        for i in range(times):
            if self._stop_event.is_set():
                return False
            self.keyboard_controller.press(key)
            self.keyboard_controller.release(key)
            if i < times - 1 and interval > 0 and self._stop_event.wait(interval):
                return False
        return True

    def _run_key_hold(self, step):
        key = resolve_key_name(step.get("key", ""))
        if key is None:
            return True
        duration = max(float(step.get("duration", 1.0)), 0.0)
        self.keyboard_controller.press(key)
        stopped = self._stop_event.wait(duration)
        self.keyboard_controller.release(key)
        return not stopped

    def _run_click(self, step):
        from .constants import MOUSE_BUTTONS

        button = MOUSE_BUTTONS.get(step.get("button", "Izquierdo"))
        if button is None:
            return True
        times = max(int(step.get("times", 1)), 1)
        interval = max(float(step.get("interval_ms", 50)), 0.0) / 1000.0
        for i in range(times):
            if self._stop_event.is_set():
                return False
            self.mouse_controller.click(button)
            if i < times - 1 and interval > 0 and self._stop_event.wait(interval):
                return False
        return True

    def _wait(self, duration):
        duration = max(float(duration), 0.0)
        return not self._stop_event.wait(duration)
