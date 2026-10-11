"""Fila de la pestaña "Secuencia": un paso con su tipo y parámetros."""

import tkinter as tk
from tkinter import ttk

from .constants import MOUSE_BUTTONS

STEP_KINDS = {
    "Pulsar tecla N veces": "key_press",
    "Mantener tecla X segundos": "key_hold",
    "Clic N veces": "click",
    "Esperar X segundos": "wait",
}
STEP_KIND_LABELS = {v: k for k, v in STEP_KINDS.items()}


class StepRow:
    """Una fila de la lista de pasos de la secuencia."""

    def __init__(self, parent, on_remove, data=None):
        data = data or {}

        self.frame = ttk.Frame(parent, relief="groove", borderwidth=1)
        self.frame.pack(fill="x", pady=3, padx=2)

        top = ttk.Frame(self.frame)
        top.pack(fill="x", padx=4, pady=(4, 2))

        self.kind_var = tk.StringVar(value=STEP_KIND_LABELS.get(data.get("kind", "key_press"), "Pulsar tecla N veces"))
        self.kind_combo = ttk.Combobox(
            top, textvariable=self.kind_var, values=list(STEP_KINDS.keys()), state="readonly", width=24
        )
        self.kind_combo.pack(side="left")
        self.kind_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_fields())

        ttk.Button(top, text="▲", width=2, command=lambda: on_remove(self, "up")).pack(side="right")
        ttk.Button(top, text="▼", width=2, command=lambda: on_remove(self, "down")).pack(side="right", padx=(0, 2))
        ttk.Button(top, text="Quitar", command=lambda: on_remove(self, "delete")).pack(side="right", padx=(6, 2))

        self.fields = ttk.Frame(self.frame)
        self.fields.pack(fill="x", padx=4, pady=(0, 4))

        self.key_var = tk.StringVar(value=data.get("key", ""))
        self.times_var = tk.StringVar(value=str(data.get("times", 1)))
        self.duration_var = tk.StringVar(value=str(data.get("duration", 1.0)))
        self.interval_var = tk.StringVar(value=str(data.get("interval_ms", 50)))
        self.button_var = tk.StringVar(value=data.get("button", "Izquierdo"))

        self._refresh_fields()

    def _clear_fields(self):
        for child in self.fields.winfo_children():
            child.destroy()

    def _refresh_fields(self):
        self._clear_fields()
        kind = STEP_KINDS.get(self.kind_var.get(), "key_press")

        if kind == "key_press":
            ttk.Label(self.fields, text="Tecla:").pack(side="left")
            ttk.Entry(self.fields, textvariable=self.key_var, width=8).pack(side="left", padx=(2, 10))
            ttk.Label(self.fields, text="Veces:").pack(side="left")
            ttk.Entry(self.fields, textvariable=self.times_var, width=6).pack(side="left", padx=(2, 10))
            ttk.Label(self.fields, text="Intervalo (ms):").pack(side="left")
            ttk.Entry(self.fields, textvariable=self.interval_var, width=7).pack(side="left", padx=(2, 0))

        elif kind == "key_hold":
            ttk.Label(self.fields, text="Tecla:").pack(side="left")
            ttk.Entry(self.fields, textvariable=self.key_var, width=8).pack(side="left", padx=(2, 10))
            ttk.Label(self.fields, text="Duración (s):").pack(side="left")
            ttk.Entry(self.fields, textvariable=self.duration_var, width=7).pack(side="left", padx=(2, 0))

        elif kind == "click":
            ttk.Label(self.fields, text="Botón:").pack(side="left")
            ttk.Combobox(
                self.fields, textvariable=self.button_var, values=list(MOUSE_BUTTONS.keys()),
                state="readonly", width=10,
            ).pack(side="left", padx=(2, 10))
            ttk.Label(self.fields, text="Veces:").pack(side="left")
            ttk.Entry(self.fields, textvariable=self.times_var, width=6).pack(side="left", padx=(2, 10))
            ttk.Label(self.fields, text="Intervalo (ms):").pack(side="left")
            ttk.Entry(self.fields, textvariable=self.interval_var, width=7).pack(side="left", padx=(2, 0))

        elif kind == "wait":
            ttk.Label(self.fields, text="Duración (s):").pack(side="left")
            ttk.Entry(self.fields, textvariable=self.duration_var, width=7).pack(side="left", padx=(2, 0))

    def set_highlight(self, active):
        self.frame.configure(relief="solid", borderwidth=2 if active else 1)

    def destroy(self):
        self.frame.destroy()

    def to_dict(self):
        kind = STEP_KINDS.get(self.kind_var.get(), "key_press")
        return {
            "kind": kind,
            "key": self.key_var.get(),
            "times": self._safe_int(self.times_var.get(), 1),
            "duration": self._safe_float(self.duration_var.get(), 1.0),
            "interval_ms": self._safe_float(self.interval_var.get(), 50),
            "button": self.button_var.get(),
        }

    def summary(self):
        kind = STEP_KINDS.get(self.kind_var.get(), "key_press")
        if kind == "key_press":
            return f"Pulsar '{self.key_var.get()}' x{self.times_var.get()}"
        if kind == "key_hold":
            return f"Mantener '{self.key_var.get()}' {self.duration_var.get()}s"
        if kind == "click":
            return f"Clic {self.button_var.get()} x{self.times_var.get()}"
        return f"Esperar {self.duration_var.get()}s"

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(value, default):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
