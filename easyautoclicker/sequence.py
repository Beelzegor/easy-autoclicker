"""Ejecutor de secuencias: pasos ordenados que corren uno después del otro."""

import random
import threading

from .constants import MOUSE_BUTTONS
from .keys import parse_combo, press_combo, release_combo, tap_combo

# Tipos de paso soportados, en el orden en que los ofrece la interfaz.
STEP_KINDS = {
    "Pulsar tecla N veces": "key_press",
    "Mantener tecla X segundos": "key_hold",
    "Clic N veces": "click",
    "Mantener clic X segundos": "click_hold",
    "Mover el mouse a X,Y": "mouse_move",
    "Rueda del mouse": "scroll",
    "Escribir texto": "type_text",
    "Esperar X segundos": "wait",
    "Esperar entre X e Y segundos": "wait_random",
}
STEP_KIND_LABELS = {v: k for k, v in STEP_KINDS.items()}


def step_summary(step):
    """Resumen de una línea de un paso, para listas y mensajes."""
    kind = step.get("kind", "key_press")
    key = step.get("key", "")
    times = step.get("times", 1)
    duration = step.get("duration", 1.0)
    if kind == "key_press":
        return f"Pulsar '{key}' x{times}"
    if kind == "key_hold":
        return f"Mantener '{key}' {duration}s"
    if kind == "click":
        return f"Clic {step.get('button', 'Izquierdo')} x{times}"
    if kind == "click_hold":
        return f"Mantener clic {step.get('button', 'Izquierdo')} {duration}s"
    if kind == "mouse_move":
        return f"Mover mouse a {step.get('x', 0)},{step.get('y', 0)}"
    if kind == "scroll":
        return f"Rueda {step.get('scroll_amount', -3)} x{times}"
    if kind == "type_text":
        text = step.get("text", "")
        shown = text if len(text) <= 20 else text[:20] + "..."
        return f"Escribir '{shown}'"
    if kind == "wait_random":
        return f"Esperar {step.get('min_duration', 0.5)}-{step.get('max_duration', 2.0)}s"
    return f"Esperar {duration}s"


class SequenceRunner:
    """Ejecuta una lista ordenada de pasos, uno después del otro."""

    def __init__(self, keyboard_controller, mouse_controller, on_status=None, on_step=None):
        self.keyboard_controller = keyboard_controller
        self.mouse_controller = mouse_controller
        self.on_status = on_status or (lambda text: None)
        self.on_step = on_step or (lambda index: None)

        self._running = False
        self._stop_event = threading.Event()
        self._thread = None
        self._held_keys = []
        self._held_buttons = []
        # Identifica la vuelta en curso, para descartar avisos de una vieja.
        self._run_id = 0

    @property
    def is_running(self):
        return self._running

    def start(self, steps, loop_forever=True, repeat=1):
        """Arranca la secuencia. ``steps`` son diccionarios como los de StepRow."""
        if self._running:
            return
        if not self._wait_for_thread():
            self.on_status("La secuencia anterior todavía está terminando")
            return
        active = [(i, s) for i, s in enumerate(steps or []) if s.get("enabled", True)]
        if not active:
            self.on_status("No hay pasos habilitados")
            return
        self._run_id += 1
        run_id = self._run_id
        self._running = True
        self._stop_event.clear()
        repeat = max(int(repeat), 1)

        def run_once():
            for index, step in active:
                if self._stop_event.is_set():
                    return False
                self.on_step(index)
                if not self._run_step(step):
                    return False
            return True

        def loop():
            count = 0
            try:
                while not self._stop_event.is_set():
                    if not run_once():
                        break
                    count += 1
                    if not loop_forever:
                        if count >= repeat:
                            break
                        self.on_status(f"Ejecutando secuencia... ({count}/{repeat})")
                    else:
                        self.on_status(f"Ejecutando secuencia... (vuelta {count + 1})")
            finally:
                self._release_held()
                if run_id == self._run_id:
                    self._running = False
                    self.on_step(-1)
                    self.on_status(f"Secuencia terminada ({count} vuelta(s))")

        self.on_status("Ejecutando secuencia...")
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        # Esperar al hilo deja el estado resuelto antes de volver, para que un
        # arranque inmediato no solape dos ejecuciones.
        self._wait_for_thread()
        self._release_held()
        self._running = False

    def _wait_for_thread(self, timeout=2.0):
        """Espera a que termine el hilo anterior. Devuelve si ya no corre."""
        thread = self._thread
        if thread is None or thread is threading.current_thread():
            return True
        thread.join(timeout)
        if thread.is_alive():
            return False
        if self._thread is thread:
            self._thread = None
        return True

    def _release_held(self):
        """Suelta lo que haya quedado pulsado si la secuencia se cortó."""
        if self._held_keys:
            release_combo(self.keyboard_controller, self._held_keys)
            self._held_keys = []
        for button in list(self._held_buttons):
            try:
                self.mouse_controller.release(button)
            except Exception:
                pass
        self._held_buttons = []

    # ------------------------------------------------------------- pasos --
    def _run_step(self, step):
        handlers = {
            "key_press": self._run_key_press,
            "key_hold": self._run_key_hold,
            "click": self._run_click,
            "click_hold": self._run_click_hold,
            "mouse_move": self._run_mouse_move,
            "scroll": self._run_scroll,
            "type_text": self._run_type_text,
            "wait": self._run_wait,
            "wait_random": self._run_wait_random,
        }
        handler = handlers.get(step.get("kind"))
        if handler is None:
            return True
        try:
            return handler(step)
        except Exception:
            return True

    @staticmethod
    def _number(step, field, default):
        try:
            return float(step.get(field, default))
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _count(step, field="times", default=1):
        try:
            return max(int(float(step.get(field, default))), 1)
        except (TypeError, ValueError):
            return max(int(default), 1)

    def _interval(self, step):
        return max(self._number(step, "interval_ms", 50), 0.0) / 1000.0

    def _repeat(self, step, action):
        """Repite ``action`` las veces del paso, esperando el intervalo."""
        times = self._count(step)
        interval = self._interval(step)
        for i in range(times):
            if self._stop_event.is_set():
                return False
            action()
            if i < times - 1 and interval > 0 and self._stop_event.wait(interval):
                return False
        return True

    def _run_key_press(self, step):
        combo = parse_combo(step.get("key", ""))
        if not combo:
            return True
        return self._repeat(step, lambda: tap_combo(self.keyboard_controller, combo))

    def _run_key_hold(self, step):
        combo = parse_combo(step.get("key", ""))
        if not combo:
            return True
        duration = max(self._number(step, "duration", 1.0), 0.0)
        self._held_keys = press_combo(self.keyboard_controller, combo)
        stopped = self._stop_event.wait(duration)
        release_combo(self.keyboard_controller, self._held_keys)
        self._held_keys = []
        return not stopped

    def _run_click(self, step):
        button = MOUSE_BUTTONS.get(step.get("button", "Izquierdo"))
        if button is None:
            return True
        return self._repeat(step, lambda: self.mouse_controller.click(button))

    def _run_click_hold(self, step):
        button = MOUSE_BUTTONS.get(step.get("button", "Izquierdo"))
        if button is None:
            return True
        duration = max(self._number(step, "duration", 1.0), 0.0)
        self.mouse_controller.press(button)
        self._held_buttons.append(button)
        stopped = self._stop_event.wait(duration)
        try:
            self.mouse_controller.release(button)
        except Exception:
            pass
        if button in self._held_buttons:
            self._held_buttons.remove(button)
        return not stopped

    def _run_mouse_move(self, step):
        x = int(self._number(step, "x", 0))
        y = int(self._number(step, "y", 0))
        self.mouse_controller.position = (x, y)
        return True

    def _run_scroll(self, step):
        amount = int(self._number(step, "scroll_amount", -3))
        return self._repeat(step, lambda: self.mouse_controller.scroll(0, amount))

    def _run_type_text(self, step):
        text = step.get("text", "")
        if not text:
            return True
        interval = self._interval(step)
        for char in text:
            if self._stop_event.is_set():
                return False
            try:
                self.keyboard_controller.type(char)
            except Exception:
                pass
            if interval > 0 and self._stop_event.wait(interval):
                return False
        return True

    def _run_wait(self, step):
        duration = max(self._number(step, "duration", 1.0), 0.0)
        return not self._stop_event.wait(duration)

    def _run_wait_random(self, step):
        lo = max(self._number(step, "min_duration", 0.5), 0.0)
        hi = max(self._number(step, "max_duration", 2.0), 0.0)
        if hi < lo:
            lo, hi = hi, lo
        return not self._stop_event.wait(random.uniform(lo, hi))
