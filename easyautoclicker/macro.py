"""Grabador y reproductor de macros de mouse + teclado."""

import threading
import time

from pynput import keyboard, mouse

from .keys import key_to_text, resolve_key_name


class MacroRecorder:
    """Grabador y reproductor de macros de mouse + teclado."""

    MOVE_SAMPLE_INTERVAL = 0.015

    def __init__(self, mouse_controller, keyboard_controller, on_status=None):
        self.mouse_controller = mouse_controller
        self.keyboard_controller = keyboard_controller
        self.on_status = on_status or (lambda text: None)

        self.events = []
        self._recording = False
        self._playing = False
        self._start_time = 0.0
        self._last_move_t = -1.0
        self._m_listener = None
        self._k_listener = None
        self._stop_playback = threading.Event()
        self._play_thread = None

    @property
    def is_recording(self):
        return self._recording

    @property
    def is_playing(self):
        return self._playing

    def start_recording(self):
        if self._recording:
            return
        self.events = []
        self._recording = True
        self._start_time = time.perf_counter()
        self._last_move_t = -1.0

        def on_move(x, y):
            t = time.perf_counter() - self._start_time
            if t - self._last_move_t < self.MOVE_SAMPLE_INTERVAL:
                return
            self._last_move_t = t
            self.events.append({"t": t, "type": "move", "x": x, "y": y})

        def on_click(x, y, button, pressed):
            self.events.append(
                {
                    "t": time.perf_counter() - self._start_time,
                    "type": "click",
                    "x": x,
                    "y": y,
                    "button": button.name,
                    "pressed": pressed,
                }
            )

        def on_scroll(x, y, dx, dy):
            self.events.append(
                {"t": time.perf_counter() - self._start_time, "type": "scroll", "x": x, "y": y, "dx": dx, "dy": dy}
            )

        def on_press(key):
            self.events.append(
                {"t": time.perf_counter() - self._start_time, "type": "key_down", "key": key_to_text(key)}
            )

        def on_release(key):
            self.events.append(
                {"t": time.perf_counter() - self._start_time, "type": "key_up", "key": key_to_text(key)}
            )

        self._m_listener = mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
        self._k_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._m_listener.start()
        self._k_listener.start()
        self.on_status(f"Grabando... ({len(self.events)} eventos)")

    def stop_recording(self):
        if not self._recording:
            return
        self._recording = False
        if self._m_listener:
            self._m_listener.stop()
        if self._k_listener:
            self._k_listener.stop()
        self.on_status(f"Grabación detenida ({len(self.events)} eventos)")

    def play(self, loop_forever=False, repeat=1):
        if self._playing or not self.events:
            return
        self._playing = True
        self._stop_playback.clear()

        def run_once():
            origin = time.perf_counter()
            for ev in self.events:
                target = origin + ev["t"]
                wait = target - time.perf_counter()
                if wait > 0 and self._stop_playback.wait(wait):
                    return False
                if self._stop_playback.is_set():
                    return False
                self._apply_event(ev)
            return True

        def loop():
            count = 0
            while not self._stop_playback.is_set():
                ok = run_once()
                if not ok:
                    break
                count += 1
                if not loop_forever and count >= repeat:
                    break
            self._playing = False
            self.on_status("Reproducción terminada")

        self.on_status("Reproduciendo macro...")
        self._play_thread = threading.Thread(target=loop, daemon=True)
        self._play_thread.start()

    def _apply_event(self, ev):
        try:
            if ev["type"] == "move":
                self.mouse_controller.position = (ev["x"], ev["y"])
            elif ev["type"] == "click":
                self.mouse_controller.position = (ev["x"], ev["y"])
                button = getattr(mouse.Button, ev["button"])
                if ev["pressed"]:
                    self.mouse_controller.press(button)
                else:
                    self.mouse_controller.release(button)
            elif ev["type"] == "scroll":
                self.mouse_controller.scroll(ev["dx"], ev["dy"])
            elif ev["type"] == "key_down":
                self.keyboard_controller.press(resolve_key_name(ev["key"]))
            elif ev["type"] == "key_up":
                self.keyboard_controller.release(resolve_key_name(ev["key"]))
        except Exception:
            pass

    def stop_playback(self):
        self._stop_playback.set()
        self._playing = False

    def to_dict(self):
        return {"events": self.events}

    def load_dict(self, data):
        self.events = data.get("events", [])
