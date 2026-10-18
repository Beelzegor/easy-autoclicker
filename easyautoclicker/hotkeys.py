"""Hotkeys globales con soporte de combinaciones (ctrl/shift/alt + tecla).

El escucha corre en su propio hilo y nunca toca la interfaz directamente: las
acciones se entregan mediante la función ``dispatch`` que recibe al crearse,
que es la encargada de volver al hilo de Tk.
"""

import threading

from pynput import keyboard

from .capture import ComboCapture
from .constants import MODIFIER_NAMES
from .keys import key_to_text, normalize_combo


class HotkeyManager:
    """Escucha el teclado y dispara acciones cuando coincide una combinación."""

    def __init__(self, dispatch, should_ignore_plain=None):
        self._dispatch = dispatch
        self._should_ignore_plain = should_ignore_plain or (lambda: False)

        # Mientras está en pausa no dispara nada: se usa al capturar una
        # combinación nueva, para que la tecla pulsada no ejecute la acción.
        self._paused = False

        self._bindings = {}
        self._lock = threading.Lock()
        # Misma máquina de estados que el diálogo de captura, para que una
        # hotkey se dispare con la misma pulsación con la que se asignó.
        self._combo = ComboCapture()
        self._listener = None

    @property
    def paused(self):
        return self._paused

    @paused.setter
    def paused(self, value):
        value = bool(value)
        if self._paused and not value:
            self._combo.reset()
        self._paused = value

    # ------------------------------------------------------------ registro --
    def set_bindings(self, bindings):
        """Reemplaza el mapa ``{accion: combinación}`` completo."""
        with self._lock:
            self._bindings = {
                action: normalize_combo(combo)
                for action, combo in (bindings or {}).items()
                if normalize_combo(combo)
            }

    def bindings(self):
        with self._lock:
            return dict(self._bindings)

    def conflicting_action(self, combo, ignore_action=None):
        """Devuelve la acción que ya usa esa combinación, si hay alguna."""
        combo = normalize_combo(combo)
        with self._lock:
            for action, assigned in self._bindings.items():
                if action != ignore_action and assigned == combo:
                    return action
        return None

    def uses_key(self, key_text):
        """Indica si alguna hotkey incluye esa tecla (para no grabarla)."""
        key_text = (key_text or "").lower()
        if not key_text:
            return False
        with self._lock:
            for combo in self._bindings.values():
                if key_text in combo.split("+"):
                    return True
        return False

    # ------------------------------------------------------------- escucha --
    def start(self):
        if self._listener is not None:
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        self._combo.reset()
        listener, self._listener = self._listener, None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass

    def _on_press(self, key, injected=False):
        # Las teclas que escribe el propio programa no son pulsaciones de la
        # persona: no disparan hotkeys ni cuentan como modificador apretado.
        if injected:
            return
        try:
            combo = self._combo.press(key_to_text(key))
            if combo and not self.paused:
                self._fire(combo)
        except Exception:
            pass

    def _on_release(self, key, injected=False):
        """Un modificador que se presiona y se suelta solo también es hotkey.

        No se puede disparar al presionarlo (todavía podría venir la segunda
        tecla de una combinación), así que se decide al soltarlo.
        """
        if injected:
            return
        try:
            combo = self._combo.release(key_to_text(key))
            if combo and not self.paused:
                self._fire(combo)
        except Exception:
            pass

    def _fire(self, combo):
        # Una hotkey de una sola tecla imprimible (o un modificador suelto) no
        # debe dispararse mientras se escribe en un campo de la propia ventana.
        plain = "+" not in combo and (len(combo) == 1 or combo in MODIFIER_NAMES)
        if plain and self._should_ignore_plain():
            return
        with self._lock:
            actions = [a for a, assigned in self._bindings.items() if assigned == combo]
        for action in actions:
            self._dispatch(action)
