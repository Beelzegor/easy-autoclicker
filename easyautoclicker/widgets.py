"""Widgets y ayudas de interfaz reutilizables.

Incluye validación visual de campos numéricos, tooltips y un diálogo para
capturar una tecla o combinación sin tener que escribir su nombre.
"""

import tkinter as tk
from tkinter import ttk

from pynput import keyboard

from .constants import MODIFIER_NAMES
from .keys import combo_label, key_to_text, normalize_combo

INVALID_STYLE = "Invalid.TEntry"
_styles_ready = False


def setup_styles(root):
    """Registra los estilos propios (una sola vez por proceso de Tk)."""
    global _styles_ready
    if _styles_ready:
        return
    style = ttk.Style(root)
    try:
        style.configure(INVALID_STYLE, fieldbackground="#ffd6d6")
    except tk.TclError:
        pass
    _styles_ready = True


def attach_number_check(entry, var, allow_float=True, minimum=None, maximum=None):
    """Marca el campo en rojo cuando su contenido no es un número válido.

    No corrige el texto mientras se escribe (sería molesto); sólo avisa. La
    lógica de ejecución sigue usando valores seguros por su cuenta.
    """
    default_style = entry.cget("style") or "TEntry"

    def check(*_):
        text = var.get().strip()
        ok = True
        if not text:
            ok = False
        elif not allow_float and not text.lstrip("+-").isdigit():
            ok = False
        else:
            try:
                value = float(text)
            except (TypeError, ValueError):
                ok = False
            else:
                if minimum is not None and value < minimum:
                    ok = False
                elif maximum is not None and value > maximum:
                    ok = False
        entry.configure(style=default_style if ok else INVALID_STYLE)

    var.trace_add("write", check)
    check()
    return check


class Tooltip:
    """Tooltip simple que aparece al dejar el cursor sobre un widget."""

    DELAY_MS = 450

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self._window = None
        self._after_id = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._after_id = self.widget.after(self.DELAY_MS, self._show)

    def _cancel(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        if self._window is not None:
            return
        try:
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        except tk.TclError:
            return
        self._window = tk.Toplevel(self.widget)
        self._window.wm_overrideredirect(True)
        self._window.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self._window,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            wraplength=320,
            padx=6,
            pady=3,
        ).pack()

    def _hide(self, _event=None):
        self._cancel()
        if self._window is not None:
            self._window.destroy()
            self._window = None


def tooltip(widget, text):
    """Atajo para colgar un tooltip de un widget y devolverlo."""
    Tooltip(widget, text)
    return widget


class ScrollableFrame:
    """Marco con scroll vertical propio, para listas que pueden crecer mucho.

    El contenido va dentro de ``.inner``; la rueda del mouse sólo mueve esta
    lista mientras el cursor está encima.
    """

    def __init__(self, parent, height=220):
        self.container = ttk.Frame(parent)
        self.canvas = tk.Canvas(self.container, height=height, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.container, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)

        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self._window, width=e.width),
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.container.bind("<Enter>", lambda e: self._bind_wheel(), add="+")
        self.container.bind("<Leave>", lambda e: self._unbind_wheel(), add="+")

    def pack(self, **kwargs):
        self.container.pack(**kwargs)
        return self

    def _bind_wheel(self):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def scroll_to_bottom(self):
        self.canvas.update_idletasks()
        self.canvas.yview_moveto(1.0)


class CaptureDialog:
    """Pide al usuario que presione una tecla o combinación y la devuelve.

    Escucha con pynput (igual que el resto del programa) para que el nombre de
    la tecla capturada coincida exactamente con el que se usa al ejecutar.
    """

    def __init__(self, parent, on_done, title="Capturar tecla", allow_combo=True):
        self.parent = parent
        self.on_done = on_done
        self.allow_combo = allow_combo
        self._held = set()
        self._listener = None
        self._done = False

        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.resizable(False, False)
        self.window.transient(parent)

        message = (
            "Presiona la tecla o combinación que quieras usar."
            if allow_combo
            else "Presiona la tecla que quieras usar."
        )
        ttk.Label(self.window, text=message, wraplength=280, justify="left").pack(
            padx=14, pady=(14, 6)
        )
        self.preview_var = tk.StringVar(value="Esperando...")
        ttk.Label(self.window, textvariable=self.preview_var, font=("", 11, "bold")).pack(
            padx=14, pady=(0, 8)
        )
        ttk.Button(self.window, text="Cancelar", command=self.cancel).pack(pady=(0, 12))

        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self.window.bind("<Escape>", lambda e: self.cancel())
        self._start_listener()
        self._center()
        try:
            self.window.grab_set()
        except tk.TclError:
            pass

    def _center(self):
        self.window.update_idletasks()
        try:
            px = self.parent.winfo_rootx() + self.parent.winfo_width() // 2
            py = self.parent.winfo_rooty() + self.parent.winfo_height() // 2
        except tk.TclError:
            return
        w = self.window.winfo_width()
        h = self.window.winfo_height()
        self.window.wm_geometry(f"+{max(px - w // 2, 0)}+{max(py - h // 2, 0)}")

    def _start_listener(self):
        def on_press(key):
            try:
                name = key_to_text(key)
                if name in MODIFIER_NAMES:
                    if self.allow_combo:
                        self._held.add(name)
                        self.parent.after(0, self._update_preview)
                    return
                mods = [m for m in MODIFIER_NAMES if m in self._held] if self.allow_combo else []
                combo = normalize_combo("+".join(mods + [name]))
                self.parent.after(0, lambda: self._finish(combo))
            except Exception:
                pass

        def on_release(key):
            try:
                self._held.discard(key_to_text(key))
            except Exception:
                pass

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()

    def _update_preview(self):
        if self._done:
            return
        mods = [m for m in MODIFIER_NAMES if m in self._held]
        self.preview_var.set("+".join(m.upper() for m in mods) + "+..." if mods else "Esperando...")

    def _stop_listener(self):
        listener, self._listener = self._listener, None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass

    def _finish(self, combo):
        if self._done:
            return
        self._done = True
        self.preview_var.set(combo_label(combo))
        self._stop_listener()
        self._close()
        self.on_done(combo)

    def cancel(self):
        if self._done:
            return
        self._done = True
        self._stop_listener()
        self._close()

    def _close(self):
        try:
            self.window.grab_release()
        except tk.TclError:
            pass
        try:
            self.window.destroy()
        except tk.TclError:
            pass
