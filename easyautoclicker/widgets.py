"""Widgets y ayudas de interfaz reutilizables.

Incluye validación visual de campos numéricos, tooltips y un diálogo para
capturar una tecla o combinación sin tener que escribir su nombre.
"""

import queue
import tkinter as tk
from tkinter import ttk

from pynput import keyboard

from .capture import ComboCapture
from .keys import combo_label, key_to_text, parse_combo
from .tray import apply_dialog_icon

INVALID_STYLE = "Invalid.TEntry"
_styles_ready = False

_capture_guard = None


def set_capture_guard(callback):
    """Registra qué hacer mientras hay un diálogo de captura abierto.

    Se llama con ``True`` al abrirlo y con ``False`` al cerrarlo. La app lo usa
    para pausar las hotkeys globales: si no, capturar F6 también arrancaría el
    autoclicker en el mismo momento.
    """
    global _capture_guard
    _capture_guard = callback


def _notify_capture(active):
    if _capture_guard is None:
        return
    try:
        _capture_guard(active)
    except Exception:
        pass


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


def attach_key_check(entry, var):
    """Marca el campo en rojo cuando la tecla escrita no existe.

    Antes, un nombre mal escrito no avisaba nada: la fila simplemente no hacía
    nada al ejecutar y había que adivinar por qué.
    """
    default_style = entry.cget("style") or "TEntry"

    def check(*_):
        text = var.get().strip()
        ok = not text or bool(parse_combo(text))
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
        # Sin esto, el tooltip queda colgado en pantalla cuando el widget
        # desaparece debajo del cursor (al quitar una fila, por ejemplo).
        widget.bind("<Destroy>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        try:
            self._after_id = self.widget.after(self.DELAY_MS, self._show)
        except tk.TclError:
            self._after_id = None

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
        try:
            self._window = tk.Toplevel(self.widget)
            self._window.wm_overrideredirect(True)
            self._window.wm_geometry(f"+{x}+{y}")
            # La ventana principal puede estar en "siempre visible": sin esto
            # el tooltip quedaría tapado por ella.
            self._window.attributes("-topmost", True)
        except tk.TclError:
            self._window = None
            return
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
            try:
                self._window.destroy()
            except tk.TclError:
                pass
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

    Dos detalles que importan mientras está abierto:

    - Un modificador suelto (ctrl, shift, alt) también se puede elegir: se
      confirma al soltarlo, no al presionarlo, porque hasta ese momento no se
      sabe si venía una segunda tecla.
    - Ninguna tecla llega a los botones de la ventana. Si no, espacio o enter
      activarían el botón que tenga el foco en vez de capturarse.
    """

    def __init__(self, parent, on_done, title="Capturar tecla", allow_combo=True, on_cancel=None):
        self.parent = parent
        self.on_done = on_done
        self.on_cancel = on_cancel
        self.allow_combo = allow_combo
        self._capture = ComboCapture(allow_combo=allow_combo)
        self._events = queue.SimpleQueue()
        self._listener = None
        self._poll_id = None
        self._done = False
        self._focused = True

        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.resizable(False, False)
        self.window.transient(parent)
        apply_dialog_icon(self.window)

        message = (
            "Presiona la tecla o combinación que quieras usar.\n"
            "Para usar ctrl, shift o alt a secas, presiona y suelta."
            if allow_combo
            else "Presiona la tecla que quieras usar."
        )
        ttk.Label(self.window, text=message, wraplength=300, justify="left").pack(
            padx=14, pady=(14, 6)
        )
        self.preview_var = tk.StringVar(value="Esperando...")
        ttk.Label(self.window, textvariable=self.preview_var, font=("", 11, "bold")).pack(
            padx=14, pady=(0, 8)
        )
        # takefocus=False: el botón nunca toma el foco, así que ninguna tecla
        # lo activa sin querer. Se cancela con el mouse o cerrando la ventana.
        ttk.Button(self.window, text="Cancelar", command=self.cancel, takefocus=False).pack(
            pady=(0, 4)
        )
        ttk.Label(
            self.window,
            text="(cancela con el botón o cerrando la ventana)",
            foreground="gray",
        ).pack(padx=14, pady=(0, 12))

        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        # Nada de teclado para Tk: ni espacio ni enter activan botones, ni el
        # tabulador mueve el foco. Esc tampoco cancela, porque es una tecla
        # perfectamente válida para asignar (es el pánico por defecto).
        self.window.bind("<Key>", lambda e: "break")
        self.window.bind("<FocusIn>", self._on_focus_in, add="+")
        self.window.bind("<FocusOut>", self._on_focus_out, add="+")

        self._center()
        self._make_modal()
        _notify_capture(True)
        self._start_listener()

    # ----------------------------------------------------------- ventana --
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

    def _make_modal(self):
        """Toma el foco y bloquea la ventana de atrás mientras captura."""
        try:
            # grab_set falla si la ventana todavía no está en pantalla.
            self.window.wait_visibility(self.window)
        except tk.TclError:
            pass
        try:
            self.window.grab_set()
        except tk.TclError:
            pass
        try:
            # El foco va a la ventana en sí, no a un widget de adentro.
            self.window.focus_force()
        except tk.TclError:
            pass

    def _on_focus_in(self, _event=None):
        self._focused = True

    def _on_focus_out(self, _event=None):
        # Si el usuario se fue a otro programa, lo que escriba ahí no es para
        # nosotros: se deja de capturar hasta que vuelva.
        self._focused = False
        self._capture.reset()
        self._update_preview()

    # ----------------------------------------------------------- escucha --
    # El hilo del escucha sólo deja el nombre de la tecla en esta cola: ni
    # toca Tk ni hace cuentas. Windows desconecta el hook del teclado si su
    # callback tarda unos milisegundos de más, y llamar a Tk desde otro hilo
    # es justo de las cosas que pueden tardar.
    POLL_MS = 25

    def _start_listener(self):
        self._listener = keyboard.Listener(
            on_press=lambda key: self._queue_event("press", key),
            on_release=lambda key: self._queue_event("release", key),
        )
        self._listener.daemon = True
        self._listener.start()
        self._poll_id = self.window.after(self.POLL_MS, self._drain_events)

    def _queue_event(self, kind, key):
        try:
            self._events.put((kind, key_to_text(key)))
        except Exception:
            pass

    def _drain_events(self):
        """Procesa en el hilo de Tk lo que dejó el escucha."""
        self._poll_id = None
        if self._done:
            return
        combo = None
        while combo is None:
            try:
                kind, name = self._events.get_nowait()
            except queue.Empty:
                break
            if not self._focused:
                continue
            if kind == "press":
                combo = self._capture.press(name)
            else:
                combo = self._capture.release(name)
        if combo:
            self._finish(combo)
            return
        self._update_preview()
        try:
            self._poll_id = self.window.after(self.POLL_MS, self._drain_events)
        except tk.TclError:
            self._poll_id = None

    def _stop_polling(self):
        poll_id, self._poll_id = self._poll_id, None
        if poll_id is not None:
            try:
                self.window.after_cancel(poll_id)
            except tk.TclError:
                pass

    def _update_preview(self):
        if self._done:
            return
        try:
            self.preview_var.set(self._capture.preview() or "Esperando...")
        except tk.TclError:
            pass

    def _stop_listener(self):
        listener, self._listener = self._listener, None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass

    # ------------------------------------------------------------- cierre --
    def _finish(self, combo):
        if self._done:
            return
        self._done = True
        self._stop_polling()
        try:
            self.preview_var.set(combo_label(combo))
        except tk.TclError:
            pass
        self._stop_listener()
        self._close()
        self.on_done(combo)

    def cancel(self):
        if self._done:
            return
        self._done = True
        self._stop_polling()
        self._stop_listener()
        self._close()
        if self.on_cancel is not None:
            self.on_cancel()

    def _close(self):
        _notify_capture(False)
        try:
            self.window.grab_release()
        except tk.TclError:
            pass
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        # El foco vuelve a la ventana, no al botón que abrió el diálogo: así
        # la tecla recién capturada no lo vuelve a apretar.
        try:
            self.parent.winfo_toplevel().focus_set()
        except tk.TclError:
            pass
