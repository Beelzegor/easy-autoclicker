"""Conversión entre texto de tecla (en español) y objetos de pynput."""

from pynput import keyboard

from .constants import SPECIAL_KEYS


def key_to_text(key):
    """Convierte una tecla de pynput a su representación en texto."""
    if isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char.lower()
        return str(key)
    name = str(key).replace("Key.", "")
    return name


def resolve_key_name(name):
    """Convierte un texto de tecla (español incluido) a una tecla de pynput."""
    name = (name or "").strip().lower()
    if not name:
        return None
    if name in SPECIAL_KEYS:
        return SPECIAL_KEYS[name]
    if len(name) == 1:
        return name
    if hasattr(keyboard.Key, name):
        return getattr(keyboard.Key, name)
    return name
