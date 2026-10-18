"""Decide qué combinación eligió el usuario a partir de presiones y sueltas.

La regla difícil es el modificador suelto: cuando baja ctrl todavía no se sabe
si el usuario quiere "ctrl" o está armando "ctrl+c", así que la decisión se
toma al soltarlo. Esta clase no sabe nada de pynput ni de Tk, para poder
probarse sola; la usan tanto el diálogo de captura como las hotkeys globales.
"""

from .constants import MODIFIER_NAMES
from .keys import normalize_combo


class ComboCapture:
    """Máquina de estados de una captura de tecla o combinación."""

    def __init__(self, allow_combo=True):
        self.allow_combo = allow_combo
        self._held = []
        # Teclas normales que siguen apretadas, para ignorar la autorrepetición.
        self._down = set()
        # Se enciende cuando ya hubo algo más que un único modificador: a
        # partir de ahí, soltarlo no confirma nada.
        self._dirty = False

    def reset(self):
        """Olvida lo apretado (al perder el foco, por ejemplo)."""
        self._held = []
        self._down = set()
        self._dirty = False

    @property
    def held(self):
        return tuple(self._held)

    def press(self, name):
        """Procesa una tecla que baja. Devuelve la combinación si ya está."""
        if not name:
            return None
        if name in MODIFIER_NAMES:
            if not self.allow_combo:
                return None
            # Se compara ignorando esta misma tecla: el teclado puede repetir
            # el evento de una tecla que sigue apretada.
            self._dirty = bool(set(self._held) - {name})
            if name not in self._held:
                self._held.append(name)
            return None
        if name in self._down:
            return None
        self._down.add(name)
        self._dirty = True
        mods = list(self._held) if self.allow_combo else []
        return normalize_combo("+".join(mods + [name]))

    def release(self, name):
        """Procesa una tecla que sube. Devuelve el modificador si quedó solo."""
        if not name:
            return None
        self._down.discard(name)
        was_held = name in self._held
        if was_held:
            self._held.remove(name)
        if name not in MODIFIER_NAMES or not self.allow_combo:
            return None
        if was_held and not self._dirty and not self._held:
            return name
        if not self._held:
            # Soltó todo sin elegir nada: queda listo para volver a intentar.
            self._dirty = False
        return None

    def preview(self):
        """Texto de lo que está apretado ahora, o cadena vacía."""
        mods = [m for m in MODIFIER_NAMES if m in self._held]
        if not mods:
            return ""
        return "+".join(m.upper() for m in mods) + "+..."
