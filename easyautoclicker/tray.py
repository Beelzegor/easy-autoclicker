"""Soporte opcional de bandeja del sistema e ícono de ventana.

pystray y Pillow son dependencias opcionales: si no están instaladas, la app
sigue funcionando igual, solo sin minimizar a la bandeja.
"""

import os

from .paths import ICON_PATH

try:
    import pystray
    from PIL import Image, ImageDraw

    TRAY_DISPONIBLE = True
except ImportError:
    pystray = None
    Image = None
    ImageDraw = None
    TRAY_DISPONIBLE = False

try:
    from PIL import Image as PILImage

    PIL_DISPONIBLE = True
except ImportError:
    PILImage = None
    PIL_DISPONIBLE = False


def make_tray_image():
    """Construye la imagen que se muestra en la bandeja del sistema."""
    if os.path.exists(ICON_PATH):
        try:
            return Image.open(ICON_PATH).convert("RGBA")
        except Exception:
            pass
    image = Image.new("RGB", (64, 64), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((4, 4, 60, 60), fill="#2d6cdf")
    draw.ellipse((24, 24, 40, 40), fill="white")
    return image


def apply_window_icon(root):
    """Aplica icon.ico a la ventana principal y a las que se abran después.

    El ``default=`` es lo que hace que los diálogos (capturar tecla, avisos,
    pedir un nombre) hereden el ícono en vez de salir con el de Tk.
    """
    if not os.path.exists(ICON_PATH):
        return None
    try:
        root.iconbitmap(default=ICON_PATH)
        return None
    except Exception:
        pass
    try:
        root.iconbitmap(ICON_PATH)
        return None
    except Exception:
        if not PIL_DISPONIBLE:
            return None
        try:
            from PIL import ImageTk

            image = PILImage.open(ICON_PATH)
            photo = ImageTk.PhotoImage(image)
            root.iconphoto(True, photo)
            return photo  # mantener referencia viva, Tk no la retiene
        except Exception:
            return None


def apply_dialog_icon(window):
    """Pone el ícono en una ventana secundaria.

    Con ``iconbitmap(default=...)`` en la raíz ya alcanzaría en Windows, pero
    no en todas las plataformas ni con todas las versiones de Tk, así que las
    ventanas propias lo piden igual.
    """
    if not os.path.exists(ICON_PATH):
        return
    try:
        window.iconbitmap(ICON_PATH)
    except Exception:
        pass
