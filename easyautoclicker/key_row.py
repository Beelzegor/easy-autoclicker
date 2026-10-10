"""Fila de la pestaña "Teclas": una tecla con su propio hilo de pulsado."""

import threading
import tkinter as tk
from tkinter import ttk

from .keys import resolve_key_name


class KeyRow:
    """Una fila de la lista de teclas configuradas."""

    def __init__(self, parent, on_remove, data=None):
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill="x", pady=2)

        data = data or {}

        self.enabled = tk.BooleanVar(value=data.get("enabled", True))
        ttk.Checkbutton(self.frame, variable=self.enabled).pack(side="left")

        ttk.Label(self.frame, text="Tecla:").pack(side="left", padx=(4, 2))
        self.key_var = tk.StringVar(value=data.get("key", ""))
        self.key_entry = ttk.Entry(self.frame, textvariable=self.key_var, width=8)
        self.key_entry.pack(side="left")

        ttk.Label(self.frame, text="Intervalo (ms):").pack(side="left", padx=(6, 2))
        self.interval_var = tk.StringVar(value=str(data.get("interval_ms", 100)))
        ttk.Entry(self.frame, textvariable=self.interval_var, width=7).pack(side="left")

        ttk.Label(self.frame, text="Retraso (ms):").pack(side="left", padx=(6, 2))
        self.delay_var = tk.StringVar(value=str(data.get("delay_ms", 0)))
        ttk.Entry(self.frame, textvariable=self.delay_var, width=7).pack(side="left")

        ttk.Label(self.frame, text="Repeticiones (0=inf):").pack(side="left", padx=(6, 2))
        self.repeat_var = tk.StringVar(value=str(data.get("repeat", 0)))
        ttk.Entry(self.frame, textvariable=self.repeat_var, width=6).pack(side="left")

        self.mode_var = tk.StringVar(value=data.get("mode", "Pulsar"))
        ttk.Combobox(
            self.frame,
            textvariable=self.mode_var,
            values=["Pulsar", "Mantener"],
            state="readonly",
            width=8,
        ).pack(side="left", padx=(6, 0))

        ttk.Button(
            self.frame, text="Quitar", command=lambda: on_remove(self)
        ).pack(side="left", padx=(8, 0))

        self._thread = None
        self._stop_event = threading.Event()
        self._held_key = None
        self._controller = None

    def destroy(self):
        self.stop()
        self.frame.destroy()

    def to_dict(self):
        return {
            "enabled": self.enabled.get(),
            "key": self.key_var.get(),
            "interval_ms": self._safe_float(self.interval_var.get(), 100),
            "delay_ms": self._safe_float(self.delay_var.get(), 0),
            "repeat": self._safe_int(self.repeat_var.get(), 0),
            "mode": self.mode_var.get(),
        }

    @staticmethod
    def _safe_float(value, default):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    def get_interval_seconds(self):
        return max(self._safe_float(self.interval_var.get(), 100), 1.0) / 1000.0

    def get_delay_seconds(self):
        return max(self._safe_float(self.delay_var.get(), 0), 0.0) / 1000.0

    def get_repeat_count(self):
        return max(self._safe_int(self.repeat_var.get(), 0), 0)

    def start(self, controller):
        key = resolve_key_name(self.key_var.get())
        if not self.enabled.get() or key is None:
            return
        self._controller = controller
        self._stop_event.clear()
        interval = self.get_interval_seconds()
        delay = self.get_delay_seconds()
        repeat = self.get_repeat_count()
        mode = self.mode_var.get()

        def loop():
            if delay > 0 and self._stop_event.wait(delay):
                return
            if mode == "Mantener":
                try:
                    controller.press(key)
                    self._held_key = key
                except Exception:
                    pass
                self._stop_event.wait()
                return
            count = 0
            while not self._stop_event.is_set():
                try:
                    controller.press(key)
                    controller.release(key)
                except Exception:
                    pass
                count += 1
                if repeat and count >= repeat:
                    break
                if self._stop_event.wait(interval):
                    break

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._held_key is not None and self._controller is not None:
            try:
                self._controller.release(self._held_key)
            except Exception:
                pass
            self._held_key = None
        self._thread = None
