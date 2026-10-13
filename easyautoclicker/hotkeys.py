"""Hotkeys globales con soporte de combinaciones (ctrl/shift/alt + tecla).

El escucha corre en su propio hilo y nunca toca la interfaz directamente: las
acciones se entregan mediante la función ``dispatch`` que recibe al crearse,
que es la encargada de volver al hilo de Tk.
"""

import threading

from pynput import keyboard

from .constants import MODIFIER_NAMES
from .keys import key_to_text, normalize_combo


class HotkeyManager:
    """Escucha el teclado y dispara acciones cuando coincide una combinación."""

    def __init__(self, dispatch, should_ignore_plain=None):
        self._dispatch = dispatch
        self._should_ignore_plain = should_ignore_plain or (lambda: False)

        # Mientras está en pausa no dispara nada: se usa al capturar una
        # combinación nueva, para que la tecla pulsada no ejecute la acción.
        self.paused = False

        self._bindings = {}
        self._lock = threading.Lock()
        self._held_modifiers = set()
        self._listener = None

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
        listener, self._listener = self._listener, None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass

    def _on_press(self, key):
        try:
            name = key_to_text(key)
            if name in MODIFIER_NAMES:
                self._held_modifiers.add(name)
                return
            if self.paused:
                return
            self._fire(self._current_combo(name))
        except Exception:
            pass

    def _on_release(self, key):
        try:
            name = key_to_text(key)
            self._held_modifiers.discard(name)
        except Exception:
            pass

    def _current_combo(self, key_name):
        mods = [m for m in MODIFIER_NAMES if m in self._held_modifiers]
        return normalize_combo("+".join(mods + [key_name]))

    def _fire(self, combo):
        # Una hotkey de una sola tecla imprimible no debe dispararse mientras
        # se escribe en un campo de la propia ventana.
        plain = "+" not in combo and len(combo) == 1
        if plain and self._should_ignore_plain():
            return
        with self._lock:
            actions = [a for a, assigned in self._bindings.items() if assigned == combo]
        for action in actions:
            self._dispatch(action)
