"""Grabador y reproductor de macros de mouse + teclado."""

import threading
import time

from pynput import keyboard, mouse

from .keys import key_to_text, resolve_key_name


class MacroRecorder:
    """Grabador y reproductor de macros de mouse + teclado.

    La reproducción respeta los tiempos reales de la grabación, con un
    multiplicador de velocidad opcional, y libera todo lo que haya quedado
    pulsado si se detiene a mitad de camino.
    """

    MOVE_SAMPLE_INTERVAL = 0.015

    def __init__(
        self,
        mouse_controller,
        keyboard_controller,
        on_status=None,
        should_ignore_key=None,
    ):
        self.mouse_controller = mouse_controller
        self.keyboard_controller = keyboard_controller
        self.on_status = on_status or (lambda text: None)
        self._should_ignore_key = should_ignore_key or (lambda name: False)

        self.events = []
        self.record_moves = True
        self.name = ""

        self._recording = False
        self._playing = False
        self._start_time = 0.0
        self._last_move_t = -1.0
        self._m_listener = None
        self._k_listener = None
        self._stop_playback = threading.Event()
        self._play_thread = None
        self._held_keys = set()
        self._held_buttons = set()

    # ---------------------------------------------------------- consultas --
    @property
    def is_recording(self):
        return self._recording

    @property
    def is_playing(self):
        return self._playing

    @property
    def duration(self):
        """Duración en segundos de la macro grabada."""
        if not self.events:
            return 0.0
        return float(self.events[-1].get("t", 0.0))

    def describe(self):
        """Resumen legible del contenido de la macro."""
        if not self.events:
            return "Sin macro grabada"
        prefix = f"{self.name}: " if self.name else ""
        return f"{prefix}{len(self.events)} eventos, {self.duration:.1f}s"

    def clear(self):
        if self._recording or self._playing:
            return
        self.events = []
        self.name = ""
        self.on_status("Sin macro grabada")

    # --------------------------------------------------------- grabación --
    def start_recording(self):
        if self._recording or self._playing:
            return
        self.events = []
        self.name = ""
        self._recording = True
        self._start_time = time.perf_counter()
        self._last_move_t = -1.0

        def now():
            return time.perf_counter() - self._start_time

        def on_move(x, y):
            if not self.record_moves:
                return
            t = now()
            if t - self._last_move_t < self.MOVE_SAMPLE_INTERVAL:
                return
            self._last_move_t = t
            self.events.append({"t": t, "type": "move", "x": x, "y": y})

        def on_click(x, y, button, pressed):
            self.events.append(
                {
                    "t": now(),
                    "type": "click",
                    "x": x,
                    "y": y,
                    "button": button.name,
                    "pressed": pressed,
                }
            )
            self._report_recording()

        def on_scroll(x, y, dx, dy):
            self.events.append(
                {"t": now(), "type": "scroll", "x": x, "y": y, "dx": dx, "dy": dy}
            )
            self._report_recording()

        def on_press(key):
            name = key_to_text(key)
            if self._should_ignore_key(name):
                return
            self.events.append({"t": now(), "type": "key_down", "key": name})
            self._report_recording()

        def on_release(key):
            name = key_to_text(key)
            if self._should_ignore_key(name):
                return
            self.events.append({"t": now(), "type": "key_up", "key": name})

        self._m_listener = mouse.Listener(
            on_move=on_move, on_click=on_click, on_scroll=on_scroll
        )
        self._k_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._m_listener.start()
        self._k_listener.start()
        self.on_status("Grabando... (0 eventos)")

    def _report_recording(self):
        if self._recording:
            self.on_status(f"Grabando... ({len(self.events)} eventos)")

    def stop_recording(self):
        if not self._recording:
            return
        self._recording = False
        for listener in (self._m_listener, self._k_listener):
            if listener is not None:
                try:
                    listener.stop()
                except Exception:
                    pass
        self._m_listener = self._k_listener = None
        self.on_status(f"Grabación detenida ({len(self.events)} eventos, {self.duration:.1f}s)")

    # ------------------------------------------------------ reproducción --
    def play(self, loop_forever=False, repeat=1, speed=1.0):
        if self._playing or self._recording or not self.events:
            return
        speed = max(float(speed), 0.05)
        self._playing = True
        self._stop_playback.clear()
        self._held_keys.clear()
        self._held_buttons.clear()

        def run_once():
            origin = time.perf_counter()
            for ev in self.events:
                target = origin + float(ev.get("t", 0.0)) / speed
                wait = target - time.perf_counter()
                if wait > 0 and self._stop_playback.wait(wait):
                    return False
                if self._stop_playback.is_set():
                    return False
                self._apply_event(ev)
            return True

        def loop():
            count = 0
            try:
                while not self._stop_playback.is_set():
                    if not run_once():
                        break
                    count += 1
                    if not loop_forever:
                        if count >= repeat:
                            break
                        self.on_status(f"Reproduciendo macro... ({count}/{repeat})")
                    else:
                        self.on_status(f"Reproduciendo macro... (vuelta {count + 1})")
            finally:
                self._release_held()
                self._playing = False
                self.on_status(f"Reproducción terminada ({count} vuelta(s))")

        self.on_status("Reproduciendo macro...")
        self._play_thread = threading.Thread(target=loop, daemon=True)
        self._play_thread.start()

    def _apply_event(self, ev):
        try:
            kind = ev["type"]
            if kind == "move":
                self.mouse_controller.position = (ev["x"], ev["y"])
            elif kind == "click":
                self.mouse_controller.position = (ev["x"], ev["y"])
                button = getattr(mouse.Button, ev["button"])
                if ev["pressed"]:
                    self.mouse_controller.press(button)
                    self._held_buttons.add(button)
                else:
                    self.mouse_controller.release(button)
                    self._held_buttons.discard(button)
            elif kind == "scroll":
                self.mouse_controller.scroll(ev["dx"], ev["dy"])
            elif kind == "key_down":
                key = resolve_key_name(ev["key"])
                if key is not None:
                    self.keyboard_controller.press(key)
                    self._held_keys.add(ev["key"])
            elif kind == "key_up":
                key = resolve_key_name(ev["key"])
                if key is not None:
                    self.keyboard_controller.release(key)
                    self._held_keys.discard(ev["key"])
        except Exception:
            pass

    def _release_held(self):
        """Suelta teclas y botones que quedaron pulsados al cortar la macro."""
        for name in list(self._held_keys):
            key = resolve_key_name(name)
            if key is not None:
                try:
                    self.keyboard_controller.release(key)
                except Exception:
                    pass
        self._held_keys.clear()
        for button in list(self._held_buttons):
            try:
                self.mouse_controller.release(button)
            except Exception:
                pass
        self._held_buttons.clear()

    def stop_playback(self):
        self._stop_playback.set()
        self._release_held()
        self._playing = False

    # --------------------------------------------------------- guardado --
    def to_dict(self):
        return {"version": 2, "name": self.name, "events": self.events}

    def load_dict(self, data, name=""):
        self.events = list(data.get("events", []))
        self.name = data.get("name") or name
        self.on_status(self.describe())
