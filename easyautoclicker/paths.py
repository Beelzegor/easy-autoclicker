"""Rutas de la aplicación y persistencia en disco (config, perfiles, macros)."""

import json
import os
import sys


def resource_path(filename):
    """Resuelve una ruta junto al script, o dentro del bundle de PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, filename)


ICON_PATH = resource_path("icon.ico")

if sys.platform == "win32":
    CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "EasyAutoclicker")
else:
    CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".easyautoclicker")

CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
PRESETS_PATH = os.path.join(CONFIG_DIR, "presets.json")
MACROS_DIR = os.path.join(CONFIG_DIR, "macros")
SEQUENCES_DIR = os.path.join(CONFIG_DIR, "sequences")


def ensure_dirs():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(MACROS_DIR, exist_ok=True)
    os.makedirs(SEQUENCES_DIR, exist_ok=True)


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path, data):
    """Guarda en disco de forma atómica: si falla a mitad, no corrompe nada."""
    ensure_dirs()
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(temp_path, path)


def list_json_names(directory):
    """Nombres (sin extensión) de los .json guardados en una carpeta."""
    try:
        names = [f[:-5] for f in os.listdir(directory) if f.lower().endswith(".json")]
    except OSError:
        return []
    return sorted(names, key=str.lower)


def json_path(directory, name):
    """Ruta del .json con ese nombre dentro de la carpeta indicada."""
    safe = "".join(c for c in (name or "").strip() if c not in '\\/:*?"<>|')
    if not safe:
        return None
    return os.path.join(directory, f"{safe}.json")
