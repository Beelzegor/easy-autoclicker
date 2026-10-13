"""Fila de la pestaña "Secuencia": un paso con su tipo y parámetros."""

import tkinter as tk
from tkinter import ttk

from .constants import MOUSE_BUTTONS
from .sequence import STEP_KIND_LABELS, STEP_KINDS, step_summary
from .widgets import CaptureDialog, attach_number_check, tooltip


class StepRow:
    """Una fila de la lista de pasos de la secuencia.

    Los campos visibles cambian según el tipo de paso elegido, para no mostrar
    datos que ese tipo no usa.
    """

    def __init__(self, parent, on_action, data=None, get_position=None):
        data = data or {}
        self._on_action = on_action
        self._get_position = get_position or (lambda: (0, 0))
        self._capture_after_id = None

        self.frame = ttk.Frame(parent, relief="groove", borderwidth=1)
        self.frame.pack(fill="x", pady=3, padx=2)

        top = ttk.Frame(self.frame)
        top.pack(fill="x", padx=4, pady=(4, 2))

        self.enabled = tk.BooleanVar(value=data.get("enabled", True))
        tooltip(
            ttk.Checkbutton(top, variable=self.enabled, command=self._notify_change),
            "Desmarca para saltear este paso sin borrarlo.",
        ).pack(side="left", padx=(0, 4))

        self.index_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.index_var, width=3).pack(side="left")

        self.kind_var = tk.StringVar(
            value=STEP_KIND_LABELS.get(data.get("kind", "key_press"), "Pulsar tecla N veces")
        )
        self.kind_combo = ttk.Combobox(
            top, textvariable=self.kind_var, values=list(STEP_KINDS.keys()),
            state="readonly", width=26,
        )
        self.kind_combo.pack(side="left")
        self.kind_combo.bind("<<ComboboxSelected>>", lambda e: self._on_kind_changed())

        ttk.Button(top, text="▼", width=2, command=lambda: on_action(self, "down")).pack(side="right")
        ttk.Button(top, text="▲", width=2, command=lambda: on_action(self, "up")).pack(
            side="right", padx=(0, 2)
        )
        ttk.Button(top, text="Quitar", command=lambda: on_action(self, "delete")).pack(
            side="right", padx=(6, 4)
        )
        ttk.Button(top, text="Duplicar", command=lambda: on_action(self, "duplicate")).pack(
            side="right"
        )

        self.fields = ttk.Frame(self.frame)
        self.fields.pack(fill="x", padx=4, pady=(0, 4))

        self.key_var = tk.StringVar(value=data.get("key", ""))
        self.times_var = tk.StringVar(value=str(data.get("times", 1)))
        self.duration_var = tk.StringVar(value=str(data.get("duration", 1.0)))
        self.interval_var = tk.StringVar(value=str(data.get("interval_ms", 50)))
        self.button_var = tk.StringVar(value=data.get("button", "Izquierdo"))
        self.x_var = tk.StringVar(value=str(data.get("x", 0)))
        self.y_var = tk.StringVar(value=str(data.get("y", 0)))
        self.scroll_var = tk.StringVar(value=str(data.get("scroll_amount", -3)))
        self.text_var = tk.StringVar(value=data.get("text", ""))
        self.min_duration_var = tk.StringVar(value=str(data.get("min_duration", 0.5)))
        self.max_duration_var = tk.StringVar(value=str(data.get("max_duration", 2.0)))

        self._refresh_fields()

    # ------------------------------------------------------------ campos --
    def _notify_change(self):
        self._on_action(self, "changed")

    def _on_kind_changed(self):
        self._refresh_fields()
        self._notify_change()

    def _clear_fields(self):
        if self._capture_after_id is not None:
            try:
                self.frame.after_cancel(self._capture_after_id)
            except Exception:
                pass
            self._capture_after_id = None
        for child in self.fields.winfo_children():
            child.destroy()

    def kind(self):
        return STEP_KINDS.get(self.kind_var.get(), "key_press")

    def set_index_label(self, number):
        self.index_var.set(f"{number}.")

    def _add_label(self, text, pad=(0, 2)):
        ttk.Label(self.fields, text=text).pack(side="left", padx=pad)

    def _add_entry(self, var, width, allow_float=True, minimum=None, hint=None, pad=(2, 10)):
        entry = ttk.Entry(self.fields, textvariable=var, width=width)
        entry.pack(side="left", padx=pad)
        attach_number_check(entry, var, allow_float=allow_float, minimum=minimum)
        if hint:
            tooltip(entry, hint)
        return entry

    def _add_key_field(self):
        self._add_label("Tecla:")
        entry = ttk.Entry(self.fields, textvariable=self.key_var, width=14)
        entry.pack(side="left", padx=(2, 4))
        tooltip(entry, "Tecla o combinación, por ejemplo: espacio, f5, ctrl+shift+a.")
        ttk.Button(
            self.fields, text="Capturar", width=9,
            command=lambda: CaptureDialog(
                self.frame.winfo_toplevel(), self.key_var.set, title="Capturar tecla"
            ),
        ).pack(side="left", padx=(0, 10))

    def _add_button_field(self):
        self._add_label("Botón:")
        ttk.Combobox(
            self.fields, textvariable=self.button_var, values=list(MOUSE_BUTTONS.keys()),
            state="readonly", width=10,
        ).pack(side="left", padx=(2, 10))

    def _add_times_and_interval(self):
        self._add_label("Veces:")
        self._add_entry(self.times_var, 6, allow_float=False, minimum=1)
        self._add_label("Intervalo (ms):")
        self._add_entry(self.interval_var, 7, minimum=0, pad=(2, 0))

    def _refresh_fields(self):
        self._clear_fields()
        kind = self.kind()

        if kind == "key_press":
            self._add_key_field()
            self._add_times_and_interval()

        elif kind == "key_hold":
            self._add_key_field()
            self._add_label("Duración (s):")
            self._add_entry(self.duration_var, 7, minimum=0, pad=(2, 0))

        elif kind == "click":
            self._add_button_field()
            self._add_times_and_interval()

        elif kind == "click_hold":
            self._add_button_field()
            self._add_label("Duración (s):")
            self._add_entry(self.duration_var, 7, minimum=0, pad=(2, 0))

        elif kind == "mouse_move":
            self._add_label("X:")
            self._add_entry(self.x_var, 7, allow_float=False, pad=(2, 6))
            self._add_label("Y:")
            self._add_entry(self.y_var, 7, allow_float=False, pad=(2, 10))
            ttk.Button(self.fields, text="Capturar ahora", command=self._capture_now).pack(
                side="left"
            )
            self.capture_btn = ttk.Button(
                self.fields, text="Capturar en 3s", command=self._capture_delayed
            )
            self.capture_btn.pack(side="left", padx=(4, 0))
            tooltip(self.capture_btn, "Mueve el mouse al lugar deseado antes de que termine.")

        elif kind == "scroll":
            self._add_label("Cantidad:")
            self._add_entry(
                self.scroll_var, 6, allow_float=False,
                hint="Negativo baja, positivo sube.",
            )
            self._add_times_and_interval()

        elif kind == "type_text":
            self._add_label("Texto:")
            entry = ttk.Entry(self.fields, textvariable=self.text_var, width=28)
            entry.pack(side="left", padx=(2, 10))
            tooltip(entry, "Se escribe carácter por carácter, como si lo teclearas.")
            self._add_label("Intervalo (ms):")
            self._add_entry(self.interval_var, 7, minimum=0, pad=(2, 0))

        elif kind == "wait_random":
            self._add_label("Mín (s):")
            self._add_entry(self.min_duration_var, 7, minimum=0, pad=(2, 6))
            self._add_label("Máx (s):")
            self._add_entry(self.max_duration_var, 7, minimum=0, pad=(2, 0))

        else:  # wait
            self._add_label("Duración (s):")
            self._add_entry(self.duration_var, 7, minimum=0, pad=(2, 0))

    def _capture_now(self):
        x, y = self._get_position()
        self.x_var.set(str(int(x)))
        self.y_var.set(str(int(y)))

    def _capture_delayed(self, remaining=3):
        if remaining <= 0:
            self.capture_btn.configure(text="Capturar en 3s", state="normal")
            self._capture_after_id = None
            self._capture_now()
            return
        self.capture_btn.configure(text=f"{remaining}...", state="disabled")
        self._capture_after_id = self.frame.after(
            1000, lambda: self._capture_delayed(remaining - 1)
        )

    # ------------------------------------------------------------ estado --
    def set_highlight(self, active):
        self.frame.configure(relief="solid" if active else "groove", borderwidth=2 if active else 1)

    def destroy(self):
        self._clear_fields()
        self.frame.destroy()

    def to_dict(self):
        return {
            "kind": self.kind(),
            "enabled": self.enabled.get(),
            "key": self.key_var.get(),
            "times": self._safe_int(self.times_var.get(), 1),
            "duration": self._safe_float(self.duration_var.get(), 1.0),
            "interval_ms": self._safe_float(self.interval_var.get(), 50),
            "button": self.button_var.get(),
            "x": self._safe_int(self.x_var.get(), 0),
            "y": self._safe_int(self.y_var.get(), 0),
            "scroll_amount": self._safe_int(self.scroll_var.get(), -3),
            "text": self.text_var.get(),
            "min_duration": self._safe_float(self.min_duration_var.get(), 0.5),
            "max_duration": self._safe_float(self.max_duration_var.get(), 2.0),
        }

    def summary(self):
        return step_summary(self.to_dict())

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
