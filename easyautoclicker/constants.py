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

# Modificadores: se normalizan sin lado (ctrl_l y ctrl_r son "ctrl") para que
# una combinación funcione con cualquiera de las dos teclas del teclado.
MODIFIER_NAMES = ("ctrl", "shift", "alt", "alt_gr", "cmd")

# Alias en español e inglés hacia el nombre canónico de pynput.
KEY_ALIASES = {
    # Edición y navegación
    "espacio": "space",
    "barra espaciadora": "space",
    "intro": "enter",
    "entrar": "enter",
    "return": "enter",
    "tabulador": "tab",
    "tabulación": "tab",
    "retroceso": "backspace",
    "borrar": "backspace",
    "suprimir": "delete",
    "supr": "delete",
    "del": "delete",
    "escape": "esc",
    "insertar": "insert",
    "ins": "insert",
    "inicio": "home",
    "fin": "end",
    "pagina arriba": "page_up",
    "página arriba": "page_up",
    "pagarriba": "page_up",
    "pageup": "page_up",
    "pgup": "page_up",
    "pagina abajo": "page_down",
    "página abajo": "page_down",
    "pagabajo": "page_down",
    "pagedown": "page_down",
    "pgdn": "page_down",
    # Flechas
    "arriba": "up",
    "abajo": "down",
    "izquierda": "left",
    "derecha": "right",
    "flecha arriba": "up",
    "flecha abajo": "down",
    "flecha izquierda": "left",
    "flecha derecha": "right",
    # Modificadores
    "control": "ctrl",
    "mayus": "shift",
    "mayús": "shift",
    "mayusculas": "shift",
    "mayúsculas": "shift",
    "ctrl_l": "ctrl",
    "ctrl_r": "ctrl",
    "shift_l": "shift",
    "shift_r": "shift",
    "alt_l": "alt",
    "alt_r": "alt_gr",
    "altgr": "alt_gr",
    "alt gr": "alt_gr",
    "win": "cmd",
    "windows": "cmd",
    "super": "cmd",
    "cmd_l": "cmd",
    "cmd_r": "cmd",
    # Bloqueos y especiales
    "bloq mayus": "caps_lock",
    "bloqmayus": "caps_lock",
    "capslock": "caps_lock",
    "bloq num": "num_lock",
    "numlock": "num_lock",
    "bloq despl": "scroll_lock",
    "scrolllock": "scroll_lock",
    "impr pant": "print_screen",
    "imprpant": "print_screen",
    "printscreen": "print_screen",
    "pausa": "pause",
    "menú": "menu",
    "menu contextual": "menu",
}

# Nombres canónicos que la interfaz ofrece como sugerencia.
COMMON_KEY_NAMES = [
    "space",
    "enter",
    "tab",
    "backspace",
    "delete",
    "esc",
    "up",
    "down",
    "left",
    "right",
    "home",
    "end",
    "page_up",
    "page_down",
    "insert",
    "ctrl",
    "shift",
    "alt",
    "cmd",
] + [f"f{n}" for n in range(1, 13)]

DEFAULT_HOTKEYS = {
    "toggle": "f6",
    "panic": "esc",
    "record": "f7",
    "play": "f8",
    "sequence": "f9",
}

# Orden y nombre visible de cada acción con hotkey.
HOTKEY_LABELS = {
    "toggle": "Iniciar / Detener",
    "panic": "Pánico (detener todo)",
    "record": "Grabar / detener macro",
    "play": "Reproducir / detener macro",
    "sequence": "Ejecutar / detener secuencia",
}
