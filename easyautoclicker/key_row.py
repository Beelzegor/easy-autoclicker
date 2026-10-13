"""Fila de la pestaña "Teclas": una tecla con su propio hilo de pulsado."""

import random
import threading
import tkinter as tk
from tkinter import ttk

from .keys import parse_combo, press_combo, release_combo, tap_combo
from .widgets import CaptureDialog, attach_number_check, tooltip

KEY_MODES = ["Pulsar", "Mantener"]


class KeyRow:
    """Una fila de la lista de teclas configuradas.

    Cada fila corre en su propio hilo, así que varias teclas pueden pulsarse
    al mismo tiempo. Acepta combinaciones como ``ctrl+shift+a``.
    """

    def __init__(self, parent, on_action, data=None):
        data = data or {}
        self._on_action = on_action

        self.frame = ttk.Frame(parent, relief="groove", borderwidth=1)
        self.frame.pack(fill="x", pady=3, padx=2)

        top = ttk.Frame(self.frame)
        top.pack(fill="x", padx=4, pady=(4, 2))

        self.enabled = tk.BooleanVar(value=data.get("enabled", True))
        tooltip(
            ttk.Checkbutton(top, variable=self.enabled),
            "Desmarca para dejar la tecla configurada pero sin ejecutarla.",
        ).pack(side="left")

        ttk.Label(top, text="Tecla:").pack(side="left", padx=(4, 2))
        self.key_var = tk.StringVar(value=data.get("key", ""))
        self.key_entry = ttk.Entry(top, textvariable=self.key_var, width=14)
        self.key_entry.pack(side="left")
        tooltip(
            self.key_entry,
            "Nombre de la tecla (espacio, enter, f1, a...) o una combinación "
            "como ctrl+shift+a.",
        )

        ttk.Button(top, text="Capturar", width=9, command=self._capture_key).pack(
            side="left", padx=(4, 0)
        )

        ttk.Label(top, text="Modo:").pack(side="left", padx=(10, 2))
        self.mode_var = tk.StringVar(value=data.get("mode", "Pulsar"))
        mode_combo = ttk.Combobox(
            top, textvariable=self.mode_var, values=KEY_MODES, state="readonly", width=9
        )
        mode_combo.pack(side="left")
        mode_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_mode_state())
        tooltip(
            mode_combo,
            "Pulsar: tap repetido. Mantener: la tecla queda presionada todo el "
            "rato (útil para correr en un juego).",
        )

        ttk.Button(top, text="Quitar", command=lambda: on_action(self, "delete")).pack(
            side="right", padx=(4, 2)
        )
        ttk.Button(top, text="Duplicar", command=lambda: on_action(self, "duplicate")).pack(
            side="right"
        )

        fields = ttk.Frame(self.frame)
        fields.pack(fill="x", padx=4, pady=(0, 4))

        ttk.Label(fields, text="Intervalo (ms):").pack(side="left")
        self.interval_var = tk.StringVar(value=str(data.get("interval_ms", 100)))
        self.interval_entry = ttk.Entry(fields, textvariable=self.interval_var, width=7)
        self.interval_entry.pack(side="left", padx=(2, 6))
        attach_number_check(self.interval_entry, self.interval_var, minimum=1)

        ttk.Label(fields, text="±").pack(side="left")
        self.jitter_var = tk.StringVar(value=str(data.get("jitter_ms", 0)))
        self.jitter_entry = ttk.Entry(fields, textvariable=self.jitter_var, width=6)
        self.jitter_entry.pack(side="left", padx=(2, 10))
        attach_number_check(self.jitter_entry, self.jitter_var, minimum=0)
        tooltip(
            self.jitter_entry,
            "Variación aleatoria del intervalo, en ms. Con 0 el ritmo es exacto.",
        )

        ttk.Label(fields, text="Retraso (ms):").pack(side="left")
        self.delay_var = tk.StringVar(value=str(data.get("delay_ms", 0)))
        delay_entry = ttk.Entry(fields, textvariable=self.delay_var, width=7)
        delay_entry.pack(side="left", padx=(2, 10))
        attach_number_check(delay_entry, self.delay_var, minimum=0)
        tooltip(delay_entry, "Espera antes de la primera pulsación de esta tecla.")

        ttk.Label(fields, text="Repeticiones:").pack(side="left")
        self.repeat_var = tk.StringVar(value=str(data.get("repeat", 0)))
        self.repeat_entry = ttk.Entry(fields, textvariable=self.repeat_var, width=6)
        self.repeat_entry.pack(side="left", padx=(2, 0))
        attach_number_check(self.repeat_entry, self.repeat_var, allow_float=False, minimum=0)
        tooltip(self.repeat_entry, "0 = sin límite.")

        self._thread = None
        self._stop_event = threading.Event()
        self._held_keys = []
        self._controller = None
        self._apply_mode_state()

    # ------------------------------------------------------------- estado --
    def _capture_key(self):
        CaptureDialog(
            self.frame.winfo_toplevel(),
            lambda combo: self.key_var.set(combo),
            title="Capturar tecla",
        )

    def _apply_mode_state(self):
        """En modo Mantener no hay intervalo ni repeticiones que valgan."""
        state = "disabled" if self.mode_var.get() == "Mantener" else "normal"
        for entry in (self.interval_entry, self.jitter_entry, self.repeat_entry):
            entry.configure(state=state)

    def destroy(self):
        self.stop()
        self.frame.destroy()

    def to_dict(self):
        return {
            "enabled": self.enabled.get(),
            "key": self.key_var.get(),
            "interval_ms": self._safe_float(self.interval_var.get(), 100),
            "jitter_ms": self._safe_float(self.jitter_var.get(), 0),
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

    def get_jitter_seconds(self):
        return max(self._safe_float(self.jitter_var.get(), 0), 0.0) / 1000.0

    def get_delay_seconds(self):
        return max(self._safe_float(self.delay_var.get(), 0), 0.0) / 1000.0

    def get_repeat_count(self):
        return max(self._safe_int(self.repeat_var.get(), 0), 0)

    # --------------------------------------------------------- ejecución --
    def start(self, controller):
        combo = parse_combo(self.key_var.get())
        if not self.enabled.get() or not combo:
            return
        self._controller = controller
        self._stop_event.clear()
        interval = self.get_interval_seconds()
        jitter = self.get_jitter_seconds()
        delay = self.get_delay_seconds()
        repeat = self.get_repeat_count()
        hold = self.mode_var.get() == "Mantener"

        def next_wait():
            if jitter <= 0:
                return interval
            return max(interval + random.uniform(-jitter, jitter), 0.001)

        def loop():
            if delay > 0 and self._stop_event.wait(delay):
                return
            if hold:
                self._held_keys = press_combo(controller, combo)
                self._stop_event.wait()
                return
            count = 0
            while not self._stop_event.is_set():
                tap_combo(controller, combo)
                count += 1
                if repeat and count >= repeat:
                    break
                if self._stop_event.wait(next_wait()):
                    break

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._held_keys and self._controller is not None:
            release_combo(self._controller, self._held_keys)
        self._held_keys = []
        self._thread = None
