"""Conversión entre texto de tecla (en español o inglés) y objetos de pynput.

Además de teclas sueltas, aquí se interpretan combinaciones escritas como
``ctrl+shift+a``: se resuelven a una lista de teclas que se pulsan en orden y
se liberan al revés, igual que haría una persona.
"""

import sys

from pynput import keyboard

from .constants import KEY_ALIASES, MODIFIER_NAMES

# Códigos de tecla virtual de Windows para letras y dígitos. Con ctrl o altgr
# apretados, el carácter que informa el sistema es un carácter de control o
# directamente nada ("ctrl+c" llegaba como "ctrl+vk67"), así que para estas
# teclas conviene mirar el código y no el carácter. Los códigos siguen la
# distribución del teclado, así que la letra sale bien también en AZERTY.
_WINDOWS_VK_NAMES = {}
if sys.platform == "win32":
    _WINDOWS_VK_NAMES = {vk: chr(vk).lower() for vk in range(0x41, 0x5B)}  # A-Z
    _WINDOWS_VK_NAMES.update({vk: chr(vk) for vk in range(0x30, 0x3A)})  # 0-9


def normalize_key_name(name):
    """Devuelve el nombre canónico (en inglés, como pynput) de una tecla.

    Acepta alias en español, nombres de pynput con lado (``ctrl_l``) y
    caracteres sueltos. Devuelve cadena vacía si no hay nada que interpretar.
    """
    name = (name or "").strip().lower()
    if not name:
        return ""
    if len(name) == 1:
        return name
    # Normaliza separadores internos: "pagina_arriba" y "pagina arriba" valen.
    compact = name.replace("_", " ")
    for candidate in (name, compact, compact.replace(" ", "_")):
        if candidate in KEY_ALIASES:
            return KEY_ALIASES[candidate]
    return name.replace(" ", "_")


def is_modifier_name(name):
    """Indica si el nombre canónico corresponde a una tecla modificadora."""
    return normalize_key_name(name) in MODIFIER_NAMES


def key_to_text(key):
    """Convierte una tecla de pynput a su nombre canónico en texto."""
    if isinstance(key, keyboard.KeyCode):
        name = _WINDOWS_VK_NAMES.get(key.vk)
        if name:
            return name
        char = key.char
        if char and char.isprintable() and char.strip():
            return char.lower()
        if key.vk is not None:
            return f"vk{key.vk}"
        return str(key)
    name = str(key).replace("Key.", "")
    return normalize_key_name(name)


def resolve_key_name(name):
    """Convierte un texto de tecla a una tecla de pynput (o ``None``)."""
    canonical = normalize_key_name(name)
    if not canonical:
        return None
    if len(canonical) == 1:
        return canonical
    if canonical.startswith("vk") and canonical[2:].isdigit():
        return keyboard.KeyCode.from_vk(int(canonical[2:]))
    if hasattr(keyboard.Key, canonical):
        return getattr(keyboard.Key, canonical)
    return None


def split_combo(text):
    """Separa ``"ctrl+shift+a"`` en ``["ctrl", "shift", "a"]``.

    El ``+`` como tecla literal se respeta: ``"ctrl++"`` da ``["ctrl", "+"]``.
    """
    text = (text or "").strip().lower()
    if not text:
        return []
    if text == "+":
        return ["+"]
    parts = [raw.strip() for raw in text.split("+")]
    parts = [part for part in parts if part]
    if text.endswith("+"):
        # "ctrl++" significa "ctrl" más la tecla "+" literal.
        parts.append("+")
    return parts


def normalize_combo(text):
    """Devuelve la combinación en forma canónica (modificadores primero)."""
    names = [normalize_key_name(p) for p in split_combo(text)]
    names = [n for n in names if n]
    if not names:
        return ""
    mods = [n for n in names if n in MODIFIER_NAMES]
    rest = [n for n in names if n not in MODIFIER_NAMES]
    ordered = []
    for mod in MODIFIER_NAMES:
        if mod in mods and mod not in ordered:
            ordered.append(mod)
    return "+".join(ordered + rest)


def combo_label(text):
    """Texto de la combinación para mostrar en la interfaz."""
    combo = normalize_combo(text)
    if not combo:
        return "(sin asignar)"
    return "+".join(part.upper() for part in combo.split("+"))


def parse_combo(text):
    """Resuelve una combinación a la lista de teclas de pynput, en orden."""
    keys = []
    for name in normalize_combo(text).split("+"):
        key = resolve_key_name(name)
        if key is None:
            return []
        keys.append(key)
    return keys


def tap_combo(controller, keys):
    """Pulsa y libera una combinación completa, liberando al revés."""
    pressed = []
    try:
        for key in keys:
            controller.press(key)
            pressed.append(key)
    finally:
        for key in reversed(pressed):
            try:
                controller.release(key)
            except Exception:
                pass


def press_combo(controller, keys):
    """Mantiene pulsada una combinación y devuelve las teclas que quedaron."""
    pressed = []
    for key in keys:
        try:
            controller.press(key)
            pressed.append(key)
        except Exception:
            break
    return pressed


def release_combo(controller, keys):
    """Libera (al revés) una lista de teclas que estaban mantenidas."""
    for key in reversed(list(keys)):
        try:
            controller.release(key)
        except Exception:
            pass
