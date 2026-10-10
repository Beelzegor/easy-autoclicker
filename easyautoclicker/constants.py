"""Constantes compartidas: botones de mouse, tipos de clic, teclas especiales."""

from pynput import keyboard, mouse

MOUSE_BUTTONS = {
    "Izquierdo": mouse.Button.left,
    "Derecho": mouse.Button.right,
    "Medio": mouse.Button.middle,
}

CLICK_COUNTS = {
    "Simple": 1,
    "Doble": 2,
    "Triple": 3,
}

SPECIAL_KEYS = {
    "espacio": keyboard.Key.space,
    "space": keyboard.Key.space,
    "enter": keyboard.Key.enter,
    "tab": keyboard.Key.tab,
    "shift": keyboard.Key.shift,
    "ctrl": keyboard.Key.ctrl,
    "alt": keyboard.Key.alt,
    "arriba": keyboard.Key.up,
    "abajo": keyboard.Key.down,
    "izquierda": keyboard.Key.left,
    "derecha": keyboard.Key.right,
    "esc": keyboard.Key.esc,
}

DEFAULT_HOTKEYS = {"toggle": "f6", "panic": "esc"}
