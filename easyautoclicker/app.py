"""Ventana principal de Easy Autoclicker: construcción de la UI y la lógica."""

import os
import queue
import random
import re
import sys
import threading
import time
import tkinter as tk
from collections import deque
from tkinter import ttk, messagebox, filedialog, simpledialog

from pynput import keyboard, mouse

from . import tray
from .constants import CLICK_COUNTS, COMMON_KEY_NAMES, DEFAULT_HOTKEYS, HOTKEY_LABELS, MOUSE_BUTTONS
from .hotkeys import HotkeyManager
from .key_row import KeyRow
from .keys import combo_label, normalize_combo
from .macro import MacroRecorder
from .paths import (
    CONFIG_DIR,
    CONFIG_PATH,
    MACROS_DIR,
    PRESETS_PATH,
    SEQUENCES_DIR,
    ensure_dirs,
    json_path,
    list_json_names,
    load_json,
    save_json,
)
from .sequence import SequenceRunner
from .step_row import StepRow
from .widgets import (
    CaptureDialog,
    ScrollableFrame,
    attach_number_check,
    set_capture_guard,
    setup_styles,
    tooltip,
)

MACRO_SPEEDS = ["0.25", "0.5", "1", "1.5", "2", "3", "4"]


class AutoClickerApp:
    """Pega la interfaz con los motores de clics, teclas, macros y secuencias."""

    UI_TICK_MS = 200

    def __init__(self, root):
        self.root = root
        self.root.title("Easy Autoclicker")
        self.root.minsize(700, 580)
        self._icon_photo = tray.apply_window_icon(self.root)
        setup_styles(self.root)

        self.mouse_controller = mouse.Controller()
        self.keyboard_controller = keyboard.Controller()

        self.running = False
        self._clicks = 0
        self._run_started_at = 0.0
        self._cps_samples = deque(maxlen=40)
        self._click_stop_event = threading.Event()
        self._click_thread = None
        self._stop_after_id = None
        self._tick_id = None
        self._closing = False

        # Los hilos de trabajo nunca tocan Tk: dejan el trabajo en esta cola y
        # el ticker de la interfaz la vacía desde el hilo principal.
        self._ui_queue = queue.SimpleQueue()
        self._main_thread = threading.main_thread()

        self.key_rows = []
        self.step_rows = []
        self.hotkeys = dict(DEFAULT_HOTKEYS)
        self._typing = False
        self._capturing_hotkey = False

        self.hotkey_manager = HotkeyManager(
            dispatch=self._dispatch_hotkey, should_ignore_plain=lambda: self._typing
        )
        # Mientras cualquier diálogo de captura esté abierto, las hotkeys se
        # callan: capturar F6 no debe arrancar el autoclicker al mismo tiempo.
        set_capture_guard(self._set_capture_mode)

        self.macro = MacroRecorder(
            self.mouse_controller,
            self.keyboard_controller,
            on_status=self._set_macro_status,
            should_ignore_key=self.hotkey_manager.uses_key,
        )

        self.sequence = SequenceRunner(
            self.keyboard_controller,
            self.mouse_controller,
            on_status=self._set_sequence_status,
            on_step=self._highlight_step,
        )

        self.tray_icon = None
        self._closing_to_tray = False

        self._build_ui()
        self._track_typing_focus()
        self._load_config()
        self.hotkey_manager.set_bindings(self.hotkeys)
        self.hotkey_manager.start()
        self._schedule_tick()

    # ---------------------------------------------------------------- UI --
    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, **pad)

        tabs = {}
        for key, title in (
            ("mouse", "Mouse"),
            ("keys", "Teclas"),
            ("macro", "Macros"),
            ("sequence", "Secuencia"),
            ("settings", "Ajustes"),
            ("help", "Ayuda"),
        ):
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=title)
            tabs[key] = frame

        self._build_mouse_tab(tabs["mouse"])
        self._build_keys_tab(tabs["keys"])
        self._build_macro_tab(tabs["macro"])
        self._build_sequence_tab(tabs["sequence"])
        self._build_settings_tab(tabs["settings"])
        self._build_help_tab(tabs["help"])

        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill="x", **pad)

        self.status_var = tk.StringVar(value="Detenido")
        self.status_label = ttk.Label(control_frame, textvariable=self.status_var, foreground="red")
        self.status_label.pack(side="left")

        self.stats_var = tk.StringVar(value="Clics: 0")
        ttk.Label(control_frame, textvariable=self.stats_var).pack(side="left", padx=(12, 0))

        self.toggle_button = ttk.Button(control_frame, text="Iniciar", command=self.toggle_running)
        self.toggle_button.pack(side="right")

        hint_frame = ttk.Frame(self.root)
        hint_frame.pack(fill="x", padx=10, pady=(0, 8))
        self.hotkey_hint_var = tk.StringVar()
        ttk.Label(hint_frame, textvariable=self.hotkey_hint_var, foreground="gray").pack(side="left")
        self._refresh_hotkey_hint()

    # -------------------------------------------------------- tab Mouse --
    def _build_mouse_tab(self, parent):
        frame = ttk.LabelFrame(parent, text="Clic del mouse")
        frame.pack(fill="x", padx=8, pady=6)

        self.mouse_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame, text="Habilitar clic automático", variable=self.mouse_enabled
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=6, pady=4)

        ttk.Label(frame, text="Botón:").grid(row=1, column=0, sticky="w", padx=6)
        self.mouse_button_var = tk.StringVar(value="Izquierdo")
        ttk.Combobox(
            frame, textvariable=self.mouse_button_var, values=list(MOUSE_BUTTONS.keys()),
            state="readonly", width=10,
        ).grid(row=1, column=1, sticky="w")

        ttk.Label(frame, text="Tipo de clic:").grid(row=1, column=2, sticky="w", padx=(12, 0))
        self.click_type_var = tk.StringVar(value="Simple")
        ttk.Combobox(
            frame, textvariable=self.click_type_var, values=list(CLICK_COUNTS.keys()),
            state="readonly", width=8,
        ).grid(row=1, column=3, sticky="w")

        ttk.Label(frame, text="Intervalo (ms):").grid(row=2, column=0, sticky="w", padx=6)
        self.mouse_interval_var = tk.StringVar(value="100")
        interval_entry = ttk.Entry(frame, textvariable=self.mouse_interval_var, width=8)
        interval_entry.grid(row=2, column=1, sticky="w")
        attach_number_check(interval_entry, self.mouse_interval_var, minimum=1)

        self.cps_hint_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.cps_hint_var, foreground="gray").grid(
            row=2, column=2, columnspan=2, sticky="w", padx=(12, 0)
        )
        self.mouse_interval_var.trace_add("write", lambda *_: self._refresh_cps_hint())
        self._refresh_cps_hint()

        ttk.Label(frame, text="Retraso inicial (ms):").grid(row=3, column=0, sticky="w", padx=6)
        self.mouse_delay_var = tk.StringVar(value="0")
        delay_entry = ttk.Entry(frame, textvariable=self.mouse_delay_var, width=8)
        delay_entry.grid(row=3, column=1, sticky="w")
        attach_number_check(delay_entry, self.mouse_delay_var, minimum=0)

        self.mouse_random_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame, text="Variar intervalo (aleatorio)", variable=self.mouse_random_var
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=6, pady=(6, 0))

        ttk.Label(frame, text="Mín (ms):").grid(row=4, column=2, sticky="e")
        self.mouse_min_var = tk.StringVar(value="80")
        min_entry = ttk.Entry(frame, textvariable=self.mouse_min_var, width=6)
        min_entry.grid(row=4, column=3, sticky="w")
        attach_number_check(min_entry, self.mouse_min_var, minimum=1)

        ttk.Label(frame, text="Máx (ms):").grid(row=5, column=2, sticky="e")
        self.mouse_max_var = tk.StringVar(value="150")
        max_entry = ttk.Entry(frame, textvariable=self.mouse_max_var, width=6)
        max_entry.grid(row=5, column=3, sticky="w")
        attach_number_check(max_entry, self.mouse_max_var, minimum=1)

        self.mouse_repeat_mode = tk.StringVar(value="infinito")
        ttk.Radiobutton(
            frame, text="Repetir sin límite", variable=self.mouse_repeat_mode, value="infinito"
        ).grid(row=6, column=0, columnspan=2, sticky="w", padx=6, pady=(6, 0))
        ttk.Radiobutton(
            frame, text="Repetir:", variable=self.mouse_repeat_mode, value="contado"
        ).grid(row=7, column=0, sticky="w", padx=6)
        self.mouse_repeat_count_var = tk.StringVar(value="10")
        repeat_entry = ttk.Entry(frame, textvariable=self.mouse_repeat_count_var, width=6)
        repeat_entry.grid(row=7, column=1, sticky="w")
        attach_number_check(repeat_entry, self.mouse_repeat_count_var, allow_float=False, minimum=1)
        ttk.Label(frame, text="veces").grid(row=7, column=2, sticky="w")

        pos_frame = ttk.LabelFrame(parent, text="Posición del clic")
        pos_frame.pack(fill="x", padx=8, pady=6)

        self.fixed_position = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            pos_frame, text="Usar posición fija", variable=self.fixed_position,
            command=self._toggle_position_fields,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=(6, 4))

        ttk.Label(pos_frame, text="X:").grid(row=0, column=2, sticky="e")
        self.pos_x_var = tk.StringVar(value="0")
        self.pos_x_entry = ttk.Entry(pos_frame, textvariable=self.pos_x_var, width=7, state="disabled")
        self.pos_x_entry.grid(row=0, column=3, sticky="w")

        ttk.Label(pos_frame, text="Y:").grid(row=1, column=2, sticky="e")
        self.pos_y_var = tk.StringVar(value="0")
        self.pos_y_entry = ttk.Entry(pos_frame, textvariable=self.pos_y_var, width=7, state="disabled")
        self.pos_y_entry.grid(row=1, column=3, sticky="w")

        ttk.Label(pos_frame, text="Variar ± px:").grid(row=2, column=2, sticky="e")
        self.pos_jitter_var = tk.StringVar(value="0")
        self.pos_jitter_entry = ttk.Entry(
            pos_frame, textvariable=self.pos_jitter_var, width=7, state="disabled"
        )
        self.pos_jitter_entry.grid(row=2, column=3, sticky="w")
        attach_number_check(self.pos_jitter_entry, self.pos_jitter_var, allow_float=False, minimum=0)
        tooltip(
            self.pos_jitter_entry,
            "Desplaza cada clic unos píxeles al azar alrededor de la posición "
            "fija, para que no caiga siempre en el mismo punto exacto.",
        )

        ttk.Button(
            pos_frame, text="Capturar posición actual", command=self._capture_position
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=6)
        self.capture_delayed_button = ttk.Button(
            pos_frame, text="Capturar en 3s", command=self._capture_position_delayed
        )
        self.capture_delayed_button.grid(row=2, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 6))
        tooltip(self.capture_delayed_button, "Mueve el mouse al lugar deseado antes de que termine.")

    def _build_keys_tab(self, parent):
        frame = ttk.LabelFrame(parent, text="Teclas simultáneas")
        frame.pack(fill="both", expand=True, padx=8, pady=6)

        ttk.Label(
            frame,
            text="Cada tecla corre en su propio hilo, así que pueden pulsarse todas al "
            "mismo tiempo. Acepta combinaciones como ctrl+shift+a.",
            wraplength=560,
            justify="left",
        ).pack(anchor="w", padx=6, pady=(4, 0))

        self.keys_scroll = ScrollableFrame(frame, height=240).pack(
            fill="both", expand=True, padx=6, pady=4
        )
        self.keys_container = self.keys_scroll.inner

        btns = ttk.Frame(frame)
        btns.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(btns, text="Agregar tecla", command=lambda: self._add_key_row()).pack(side="left")
        ttk.Button(btns, text="Quitar todas", command=self._clear_key_rows_confirm).pack(
            side="left", padx=(6, 0)
        )

    # -------------------------------------------------------- tab Macros --
    def _build_macro_tab(self, parent):
        frame = ttk.LabelFrame(parent, text="Grabar y reproducir macro (mouse + teclado)")
        frame.pack(fill="x", padx=8, pady=6)

        btns = ttk.Frame(frame)
        btns.pack(fill="x", padx=6, pady=6)

        self.record_button = ttk.Button(btns, text="Grabar", command=self._toggle_recording)
        self.record_button.pack(side="left")
        self.play_button = ttk.Button(btns, text="Reproducir", command=self._toggle_playback)
        self.play_button.pack(side="left", padx=(6, 0))
        ttk.Button(btns, text="Borrar", command=self._clear_macro).pack(side="left", padx=(6, 0))

        opts = ttk.Frame(frame)
        opts.pack(fill="x", padx=6, pady=(0, 4))

        self.macro_record_moves_var = tk.BooleanVar(value=True)
        tooltip(
            ttk.Checkbutton(
                opts, text="Grabar movimientos del mouse", variable=self.macro_record_moves_var,
                command=self._apply_macro_record_moves,
            ),
            "Desactívalo para grabar sólo clics, rueda y teclas: la macro queda "
            "mucho más chica y el cursor no se mueve al reproducirla.",
        ).pack(side="left")

        ttk.Label(opts, text="Velocidad:").pack(side="left", padx=(16, 2))
        self.macro_speed_var = tk.StringVar(value="1")
        speed_combo = ttk.Combobox(
            opts, textvariable=self.macro_speed_var, values=MACRO_SPEEDS, width=6
        )
        speed_combo.pack(side="left")
        ttk.Label(opts, text="x").pack(side="left", padx=(2, 0))
        tooltip(speed_combo, "2 reproduce al doble de velocidad; 0.5 a la mitad.")

        loop_frame = ttk.Frame(frame)
        loop_frame.pack(fill="x", padx=6, pady=(0, 6))

        self.macro_loop_forever = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            loop_frame, text="Repetir sin límite", variable=self.macro_loop_forever,
            command=self._toggle_macro_repeat_field,
        ).pack(side="left")

        ttk.Label(loop_frame, text="Repeticiones:").pack(side="left", padx=(12, 2))
        self.macro_repeat_var = tk.StringVar(value="1")
        self.macro_repeat_entry = ttk.Entry(
            loop_frame, textvariable=self.macro_repeat_var, width=6, state="disabled"
        )
        self.macro_repeat_entry.pack(side="left")
        attach_number_check(self.macro_repeat_entry, self.macro_repeat_var, allow_float=False, minimum=1)

        self.macro_status_var = tk.StringVar(value="Sin macro grabada")
        ttk.Label(frame, textvariable=self.macro_status_var).pack(anchor="w", padx=6, pady=(0, 6))

        saved = ttk.LabelFrame(parent, text="Macros guardadas")
        saved.pack(fill="x", padx=8, pady=6)
        self.macro_name_var = tk.StringVar(value="")
        self.macro_combo = ttk.Combobox(saved, textvariable=self.macro_name_var, width=28)
        self.macro_combo.grid(row=0, column=0, columnspan=4, sticky="w", padx=6, pady=(6, 4))

        ttk.Button(saved, text="Guardar", command=self._save_macro).grid(row=1, column=0, padx=(6, 4), pady=(0, 6))
        ttk.Button(saved, text="Cargar", command=self._load_macro).grid(row=1, column=1, padx=4, pady=(0, 6))
        ttk.Button(saved, text="Eliminar", command=self._delete_macro).grid(row=1, column=2, padx=4, pady=(0, 6))
        ttk.Button(saved, text="Importar/Exportar...", command=self._macro_file_dialog).grid(
            row=1, column=3, padx=4, pady=(0, 6)
        )
        self._refresh_macro_list()

    # ------------------------------------------------------ tab Secuencia --
    def _build_sequence_tab(self, parent):
        frame = ttk.LabelFrame(parent, text="Secuencia de pasos (se ejecutan en orden)")
        frame.pack(fill="both", expand=True, padx=8, pady=6)

        ttk.Label(
            frame,
            text="Los pasos corren uno tras otro: pulsar teclas, mantenerlas, hacer "
            "clic, mover el mouse, usar la rueda, escribir texto o esperar.",
            wraplength=560,
            justify="left",
        ).pack(anchor="w", padx=6, pady=(4, 0))

        self.steps_scroll = ScrollableFrame(frame, height=220).pack(
            fill="both", expand=True, padx=6, pady=4
        )
        self.steps_container = self.steps_scroll.inner

        add_btns = ttk.Frame(frame)
        add_btns.pack(fill="x", padx=6, pady=(0, 4))
        ttk.Button(add_btns, text="Agregar paso", command=lambda: self._add_step_row()).pack(side="left")
        ttk.Button(add_btns, text="Quitar todos", command=self._clear_step_rows_confirm).pack(
            side="left", padx=(6, 0)
        )

        self.sequence_run_button = ttk.Button(
            add_btns, text="Ejecutar secuencia", command=self._toggle_sequence
        )
        self.sequence_run_button.pack(side="right")

        loop_frame = ttk.Frame(frame)
        loop_frame.pack(fill="x", padx=6, pady=(0, 4))

        self.sequence_loop_forever = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            loop_frame, text="Repetir sin límite", variable=self.sequence_loop_forever,
            command=self._toggle_sequence_repeat_field,
        ).pack(side="left")

        ttk.Label(loop_frame, text="Repeticiones:").pack(side="left", padx=(12, 2))
        self.sequence_repeat_var = tk.StringVar(value="1")
        self.sequence_repeat_entry = ttk.Entry(
            loop_frame, textvariable=self.sequence_repeat_var, width=6, state="disabled"
        )
        self.sequence_repeat_entry.pack(side="left")
        attach_number_check(
            self.sequence_repeat_entry, self.sequence_repeat_var, allow_float=False, minimum=1
        )

        self.sequence_in_toggle_var = tk.BooleanVar(value=True)
        tooltip(
            ttk.Checkbutton(
                loop_frame,
                text="Arrancar también con Iniciar/Detener",
                variable=self.sequence_in_toggle_var,
            ),
            "Si lo desactivas, la secuencia sólo corre con su propio botón o su "
            "hotkey, y el botón Iniciar no la toca.",
        ).pack(side="left", padx=(16, 0))

        self.sequence_status_var = tk.StringVar(value="Sin pasos agregados")
        ttk.Label(frame, textvariable=self.sequence_status_var).pack(anchor="w", padx=6, pady=(0, 6))

        saved = ttk.LabelFrame(parent, text="Secuencias guardadas")
        saved.pack(fill="x", padx=8, pady=6)
        self.sequence_name_var = tk.StringVar(value="")
        self.sequence_combo = ttk.Combobox(saved, textvariable=self.sequence_name_var, width=28)
        self.sequence_combo.grid(row=0, column=0, columnspan=4, sticky="w", padx=6, pady=(6, 4))

        ttk.Button(saved, text="Guardar", command=self._save_sequence).grid(
            row=1, column=0, padx=(6, 4), pady=(0, 6)
        )
        ttk.Button(saved, text="Cargar", command=self._load_sequence).grid(row=1, column=1, padx=4, pady=(0, 6))
        ttk.Button(saved, text="Eliminar", command=self._delete_sequence).grid(
            row=1, column=2, padx=4, pady=(0, 6)
        )
        ttk.Button(saved, text="Importar/Exportar...", command=self._sequence_file_dialog).grid(
            row=1, column=3, padx=4, pady=(0, 6)
        )
        self._refresh_sequence_list()

    # -------------------------------------------------------- tab Ajustes --
    def _build_settings_tab(self, parent):
        scroll = ScrollableFrame(parent, height=380).pack(fill="both", expand=True, padx=4, pady=4)
        container = scroll.inner

        hk_frame = ttk.LabelFrame(container, text="Hotkeys globales")
        hk_frame.pack(fill="x", padx=8, pady=6)

        self.hotkey_vars = {}
        for row, (action, label) in enumerate(HOTKEY_LABELS.items()):
            ttk.Label(hk_frame, text=f"{label}:").grid(row=row, column=0, sticky="w", padx=6, pady=3)
            var = tk.StringVar(value=combo_label(self.hotkeys.get(action, "")))
            self.hotkey_vars[action] = var
            ttk.Label(hk_frame, textvariable=var, width=18).grid(row=row, column=1, sticky="w")
            ttk.Button(
                hk_frame, text="Asignar", width=9,
                command=lambda a=action: self._assign_hotkey(a),
            ).grid(row=row, column=2, padx=(6, 2))
            ttk.Button(
                hk_frame, text="Quitar", width=8,
                command=lambda a=action: self._clear_hotkey(a),
            ).grid(row=row, column=3)

        self.assign_status_var = tk.StringVar(value="")
        ttk.Label(hk_frame, textvariable=self.assign_status_var, foreground="blue").grid(
            row=len(HOTKEY_LABELS), column=0, columnspan=4, sticky="w", padx=6, pady=(2, 6)
        )

        limit_frame = ttk.LabelFrame(container, text="Límite de tiempo")
        limit_frame.pack(fill="x", padx=8, pady=6)

        self.stop_after_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            limit_frame, text="Detener todo después de", variable=self.stop_after_enabled,
            command=self._toggle_stop_after_field,
        ).grid(row=0, column=0, sticky="w", padx=6, pady=6)

        self.stop_after_var = tk.StringVar(value="60")
        self.stop_after_entry = ttk.Entry(
            limit_frame, textvariable=self.stop_after_var, width=8, state="disabled"
        )
        self.stop_after_entry.grid(row=0, column=1, sticky="w")
        attach_number_check(self.stop_after_entry, self.stop_after_var, minimum=1)
        ttk.Label(limit_frame, text="segundos").grid(row=0, column=2, sticky="w", padx=(4, 6))

        window_frame = ttk.LabelFrame(container, text="Ventana")
        window_frame.pack(fill="x", padx=8, pady=6)

        self.always_on_top_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            window_frame, text="Siempre visible (always on top)", variable=self.always_on_top_var,
            command=self._apply_always_on_top,
        ).pack(anchor="w", padx=6, pady=4)

        self.minimize_to_tray_var = tk.BooleanVar(value=tray.TRAY_DISPONIBLE)
        if tray.TRAY_DISPONIBLE:
            ttk.Checkbutton(
                window_frame, text="Minimizar a la bandeja al cerrar la ventana",
                variable=self.minimize_to_tray_var,
            ).pack(anchor="w", padx=6, pady=(0, 4))
        else:
            self.minimize_to_tray_var.set(False)
            ttk.Label(
                window_frame,
                text="(Bandeja del sistema no disponible: instala pystray y Pillow para activarla)",
                foreground="gray",
            ).pack(anchor="w", padx=6, pady=(0, 4))

        preset_frame = ttk.LabelFrame(container, text="Perfiles guardados")
        preset_frame.pack(fill="x", padx=8, pady=6)

        self.preset_var = tk.StringVar(value="")
        self.preset_combo = ttk.Combobox(
            preset_frame, textvariable=self.preset_var, state="readonly", width=28
        )
        self.preset_combo.grid(row=0, column=0, columnspan=3, sticky="w", padx=6, pady=(6, 4))
        self._refresh_preset_list()

        ttk.Button(preset_frame, text="Cargar", command=self._load_preset).grid(
            row=1, column=0, padx=(6, 4), pady=(0, 6)
        )
        ttk.Button(preset_frame, text="Guardar como...", command=self._save_preset_dialog).grid(
            row=1, column=1, padx=4, pady=(0, 6)
        )
        ttk.Button(preset_frame, text="Eliminar", command=self._delete_preset).grid(
            row=1, column=2, padx=4, pady=(0, 6)
        )
        ttk.Label(
            preset_frame,
            text="Un perfil guarda todo junto: mouse, teclas, pasos de la secuencia y hotkeys.",
            foreground="gray",
            wraplength=420,
            justify="left",
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 6))

        data_frame = ttk.LabelFrame(container, text="Datos")
        data_frame.pack(fill="x", padx=8, pady=6)
        ttk.Button(
            data_frame, text="Abrir carpeta de configuración", command=self._open_config_dir
        ).pack(anchor="w", padx=6, pady=6)
        ttk.Label(data_frame, text=CONFIG_DIR, foreground="gray", wraplength=420).pack(
            anchor="w", padx=6, pady=(0, 6)
        )

        about_frame = ttk.LabelFrame(container, text="Acerca de")
        about_frame.pack(fill="x", padx=8, pady=6)
        ttk.Label(
            about_frame,
            text="Easy Autoclicker es software libre y gratuito: nace como una "
            "alternativa a los programas tradicionales y del rechazo que me "
            "genera que haya gente que se atreva a cobrar por esto.",
            wraplength=440,
            justify="left",
        ).pack(anchor="w", padx=6, pady=6)

    # ---------------------------------------------------------- tab Ayuda --
    def _build_help_tab(self, parent):
        scroll = ScrollableFrame(parent, height=400).pack(fill="both", expand=True, padx=4, pady=4)
        container = scroll.inner

        texto = (
            "Cómo se escriben las teclas\n"
            "  Una letra o número se escribe tal cual: a, 7, ñ.\n"
            "  Las teclas con nombre se pueden escribir en español o en inglés:\n"
            "  espacio, enter, tabulador, retroceso, suprimir, esc, arriba, abajo,\n"
            "  izquierda, derecha, inicio, fin, página arriba, página abajo, f1 a f12.\n"
            "  Las combinaciones se escriben con +: ctrl+c, ctrl+shift+a, alt+tab.\n"
            "  Si no te acuerdas del nombre, usa el botón Capturar y presiona la tecla.\n"
            "  Para capturar ctrl, shift o alt a secas, presiónala y suéltala.\n"
            "  Si el campo de la tecla se pone rojo, ese nombre no existe.\n\n"
            "Modos de la pestaña Teclas\n"
            "  Pulsar: toca la tecla una y otra vez con el intervalo indicado.\n"
            "  Mantener: deja la tecla presionada hasta que detengas (correr en un juego).\n"
            "  El campo ± agrega variación aleatoria al intervalo, para un ritmo\n"
            "  menos robótico.\n\n"
            "Macros\n"
            "  Grabar guarda movimientos, clics, rueda y teclas con sus tiempos reales.\n"
            "  Las hotkeys del programa no se graban, así que puedes usarlas para\n"
            "  arrancar y cortar la grabación sin que queden dentro de la macro.\n"
            "  La velocidad multiplica el ritmo de reproducción.\n\n"
            "Secuencia\n"
            "  Los pasos corren en orden, no al mismo tiempo. Sirve para rutinas como\n"
            "  'mantener W 3 segundos, esperar 1, clic derecho, escribir texto'.\n"
            "  Cada paso se puede desmarcar para saltearlo sin borrarlo.\n\n"
            "Seguridad\n"
            "  El hotkey de pánico detiene todo de golpe: clics, teclas, macros y\n"
            "  secuencia, y suelta cualquier tecla o botón que haya quedado apretado.\n"
            "  También puedes poner un límite de tiempo en Ajustes para que todo se\n"
            "  detenga solo.\n"
        )
        ttk.Label(container, text=texto, justify="left", wraplength=580).pack(
            anchor="w", padx=10, pady=10
        )

        keys_frame = ttk.LabelFrame(container, text="Nombres de tecla reconocidos")
        keys_frame.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Label(
            keys_frame, text=", ".join(COMMON_KEY_NAMES), wraplength=560, justify="left",
            foreground="gray",
        ).pack(anchor="w", padx=6, pady=6)

    # ------------------------------------------------------------ avisos --
    # Todos los diálogos cuelgan de la ventana principal: así salen centrados
    # sobre ella y no se esconden detrás cuando está en "siempre visible".
    def _info(self, title, message):
        messagebox.showinfo(title, message, parent=self.root)

    def _ask(self, title, message):
        return messagebox.askyesno(title, message, parent=self.root)

    def _ask_three(self, title, message):
        return messagebox.askyesnocancel(title, message, parent=self.root)

    # ------------------------------------------------------ campos auxiliares --
    def _toggle_position_fields(self):
        state = "normal" if self.fixed_position.get() else "disabled"
        for entry in (self.pos_x_entry, self.pos_y_entry, self.pos_jitter_entry):
            entry.configure(state=state)

    def _toggle_macro_repeat_field(self):
        self.macro_repeat_entry.configure(
            state="disabled" if self.macro_loop_forever.get() else "normal"
        )

    def _toggle_sequence_repeat_field(self):
        self.sequence_repeat_entry.configure(
            state="disabled" if self.sequence_loop_forever.get() else "normal"
        )

    def _toggle_stop_after_field(self):
        self.stop_after_entry.configure(
            state="normal" if self.stop_after_enabled.get() else "disabled"
        )

    def _refresh_cps_hint(self):
        try:
            ms = float(self.mouse_interval_var.get())
        except (TypeError, ValueError):
            self.cps_hint_var.set("")
            return
        if ms <= 0:
            self.cps_hint_var.set("")
            return
        self.cps_hint_var.set(f"≈ {1000.0 / ms:.1f} clics/s")

    def _capture_position(self):
        x, y = self.mouse_controller.position
        self.pos_x_var.set(str(int(x)))
        self.pos_y_var.set(str(int(y)))

    def _capture_position_delayed(self, remaining=3):
        if remaining <= 0:
            self.capture_delayed_button.configure(text="Capturar en 3s", state="normal")
            self._capture_position()
            return
        self.capture_delayed_button.configure(text=f"{remaining}...", state="disabled")
        self.root.after(1000, lambda: self._capture_position_delayed(remaining - 1))

    def _open_config_dir(self):
        ensure_dirs()
        try:
            if sys.platform == "win32":
                os.startfile(CONFIG_DIR)  # noqa: S606 - ruta propia de la app
            elif sys.platform == "darwin":
                os.system(f'open "{CONFIG_DIR}"')
            else:
                os.system(f'xdg-open "{CONFIG_DIR}"')
        except Exception:
            self._info("Carpeta", CONFIG_DIR)

    # -------------------------------------------------------- filas Teclas --
    def _add_key_row(self, data=None):
        row = KeyRow(self.keys_container, self._on_key_action, data)
        self.key_rows.append(row)
        return row

    def _on_key_action(self, row, action):
        if action == "delete":
            row.destroy()
            if row in self.key_rows:
                self.key_rows.remove(row)
            if not self.key_rows:
                self._add_key_row()
        elif action == "duplicate":
            data = row.to_dict()
            new_row = self._add_key_row(data)
            if self.running:
                new_row.start(self.keyboard_controller)
            self.keys_scroll.scroll_to_bottom()

    def _clear_key_rows_confirm(self):
        if not self.key_rows:
            return
        if len(self.key_rows) == 1 and not self.key_rows[0].key_var.get().strip():
            return
        if not self._ask("Teclas", "¿Quitar todas las teclas configuradas?"):
            return
        for row in list(self.key_rows):
            row.destroy()
        self.key_rows = []
        self._add_key_row()

    # ----------------------------------------------------- filas Secuencia --
    def _add_step_row(self, data=None):
        row = StepRow(
            self.steps_container, self._on_step_action, data,
            get_position=lambda: self.mouse_controller.position,
        )
        self.step_rows.append(row)
        self._renumber_steps()
        return row

    def _on_step_action(self, row, action):
        if action == "changed":
            self._update_sequence_status_idle()
            return
        if self.sequence.is_running and action in ("delete", "up", "down", "duplicate"):
            self._info("Secuencia", "Detén la secuencia antes de modificar los pasos.")
            return
        if action == "delete":
            row.destroy()
            if row in self.step_rows:
                self.step_rows.remove(row)
            self._renumber_steps()
            return
        if action == "duplicate":
            index = self.step_rows.index(row)
            new_row = StepRow(
                self.steps_container, self._on_step_action, row.to_dict(),
                get_position=lambda: self.mouse_controller.position,
            )
            self.step_rows.insert(index + 1, new_row)
            self._reflow_step_rows()
            return
        index = self.step_rows.index(row)
        if action == "up" and index > 0:
            self.step_rows[index - 1], self.step_rows[index] = (
                self.step_rows[index], self.step_rows[index - 1],
            )
            self._reflow_step_rows()
        elif action == "down" and index < len(self.step_rows) - 1:
            self.step_rows[index + 1], self.step_rows[index] = (
                self.step_rows[index], self.step_rows[index + 1],
            )
            self._reflow_step_rows()

    def _reflow_step_rows(self):
        for row in self.step_rows:
            row.frame.pack_forget()
        for row in self.step_rows:
            row.frame.pack(fill="x", pady=3, padx=2)
        self._renumber_steps()

    def _renumber_steps(self):
        for i, row in enumerate(self.step_rows, start=1):
            row.set_index_label(i)
        self._update_sequence_status_idle()

    def _update_sequence_status_idle(self):
        if self.sequence.is_running:
            return
        if not self.step_rows:
            self.sequence_status_var.set("Sin pasos agregados")
            return
        active = sum(1 for row in self.step_rows if row.enabled.get())
        total = len(self.step_rows)
        pasos = "paso" if total == 1 else "pasos"
        if active == total:
            listo = "listo" if total == 1 else "listos"
            self.sequence_status_var.set(f"{total} {pasos} {listo}")
        elif active == 0:
            self.sequence_status_var.set(f"Ningún paso habilitado (de {total})")
        else:
            self.sequence_status_var.set(f"{active} de {total} {pasos} habilitados")

    def _clear_step_rows(self):
        for row in list(self.step_rows):
            row.destroy()
        self.step_rows = []

    def _clear_step_rows_confirm(self):
        if not self.step_rows:
            return
        if self.sequence.is_running:
            self._info("Secuencia", "Detén la secuencia antes de modificar los pasos.")
            return
        if not self._ask("Secuencia", "¿Quitar todos los pasos?"):
            return
        self._clear_step_rows()
        self._renumber_steps()

    # ------------------------------------------------- secuencias guardadas --
    def _refresh_sequence_list(self):
        ensure_dirs()
        self.sequence_combo.configure(values=list_json_names(SEQUENCES_DIR))

    def _save_sequence(self):
        if not self.step_rows:
            self._info("Secuencia", "No hay pasos para guardar.")
            return
        name = self.sequence_name_var.get().strip()
        if not name:
            name = simpledialog.askstring("Guardar secuencia", "Nombre:", parent=self.root) or ""
            name = name.strip()
        path = json_path(SEQUENCES_DIR, name)
        if not path:
            return
        if os.path.exists(path) and not self._ask(
            "Secuencia", f"Ya existe «{name}». ¿Reemplazarla?"
        ):
            return
        save_json(path, {"version": 2, "steps": [row.to_dict() for row in self.step_rows]})
        self.sequence_name_var.set(name)
        self._refresh_sequence_list()
        self.sequence_status_var.set(f"Secuencia guardada: {name}")

    def _load_sequence(self):
        if self.sequence.is_running:
            self._info("Secuencia", "Detén la secuencia antes de cargar otra.")
            return
        name = self.sequence_name_var.get().strip()
        path = json_path(SEQUENCES_DIR, name)
        if not path or not os.path.exists(path):
            self._info("Secuencia", "Elige una secuencia guardada.")
            return
        self._apply_sequence_data(load_json(path, {"steps": []}), name)

    def _apply_sequence_data(self, data, name):
        self._clear_step_rows()
        for step_data in data.get("steps", []):
            self._add_step_row(step_data)
        self._renumber_steps()
        self.sequence_status_var.set(f"Secuencia cargada: {name} ({len(self.step_rows)} pasos)")

    def _delete_sequence(self):
        name = self.sequence_name_var.get().strip()
        path = json_path(SEQUENCES_DIR, name)
        if not path or not os.path.exists(path):
            return
        if not self._ask("Secuencia", f"¿Eliminar «{name}»?"):
            return
        try:
            os.remove(path)
        except OSError:
            pass
        self.sequence_name_var.set("")
        self._refresh_sequence_list()

    def _sequence_file_dialog(self):
        ensure_dirs()
        if self.sequence.is_running:
            self._info("Secuencia", "Detén la secuencia antes de importar o exportar.")
            return
        choice = self._ask_three(
            "Secuencia", "¿Exportar la secuencia actual a un archivo?\n\n"
            "Sí: exportar.  No: importar desde un archivo."
        )
        if choice is None:
            return
        if choice:
            if not self.step_rows:
                self._info("Secuencia", "No hay pasos para exportar.")
                return
            path = filedialog.asksaveasfilename(
                parent=self.root,
                initialdir=SEQUENCES_DIR, defaultextension=".json",
                filetypes=[("Secuencia JSON", "*.json")],
            )
            if path:
                save_json(path, {"version": 2, "steps": [r.to_dict() for r in self.step_rows]})
        else:
            path = filedialog.askopenfilename(
                parent=self.root,
                initialdir=SEQUENCES_DIR, filetypes=[("Secuencia JSON", "*.json")]
            )
            if path:
                self._apply_sequence_data(
                    load_json(path, {"steps": []}), os.path.splitext(os.path.basename(path))[0]
                )

    # ------------------------------------------------------ control Secuencia --
    def _set_sequence_status(self, text):
        self._ui(lambda: self.sequence_status_var.set(text))

    def _highlight_step(self, index):
        def apply():
            for i, row in enumerate(self.step_rows):
                row.set_highlight(i == index)
            if index == -1:
                self.sequence_run_button.configure(text="Ejecutar secuencia")
                self._cancel_stop_after()
        self._ui(apply)

    def _sequence_params(self):
        try:
            repeat = max(int(float(self.sequence_repeat_var.get())), 1)
        except (TypeError, ValueError):
            repeat = 1
        return self.sequence_loop_forever.get(), repeat

    def _start_sequence(self):
        if self.sequence.is_running or not self.step_rows:
            return
        loop_forever, repeat = self._sequence_params()
        steps = [row.to_dict() for row in self.step_rows]
        self.sequence.start(steps, loop_forever=loop_forever, repeat=repeat)
        if self.sequence.is_running:
            self.sequence_run_button.configure(text="Detener secuencia")
            self._schedule_stop_after()

    def _stop_sequence(self):
        if self.sequence.is_running:
            self.sequence.stop()
        self.sequence_run_button.configure(text="Ejecutar secuencia")
        self._cancel_stop_after()

    def _toggle_sequence(self):
        if self.sequence.is_running:
            self._stop_sequence()
            return
        if not self.step_rows:
            self._info("Secuencia", "Agrega al menos un paso primero.")
            return
        self._start_sequence()

    # --------------------------------------------------------- control Macro --
    def _set_macro_status(self, text):
        self._ui(lambda: self.macro_status_var.set(text))

    def _apply_macro_record_moves(self):
        self.macro.record_moves = self.macro_record_moves_var.get()

    def _macro_speed(self):
        try:
            return max(float(self.macro_speed_var.get()), 0.05)
        except (TypeError, ValueError):
            return 1.0

    def _toggle_recording(self):
        if self.macro.is_recording:
            self.macro.stop_recording()
            self.record_button.configure(text="Grabar")
            return
        if self.macro.is_playing:
            self._info("Macro", "Detén la reproducción antes de grabar.")
            return
        if self.macro.events and not self._ask(
            "Macro", "Ya hay una macro grabada. ¿Reemplazarla con una grabación nueva?"
        ):
            return
        self._apply_macro_record_moves()
        self.macro.start_recording()
        self.record_button.configure(text="Detener grabación")

    def _toggle_playback(self):
        if self.macro.is_playing:
            self._stop_playback()
            return
        if self.macro.is_recording:
            self._info("Macro", "Detén la grabación antes de reproducir.")
            return
        if not self.macro.events:
            self._info("Macro", "No hay nada grabado todavía.")
            return
        loop_forever = self.macro_loop_forever.get()
        try:
            repeat = max(int(float(self.macro_repeat_var.get())), 1)
        except (TypeError, ValueError):
            repeat = 1
        self.macro.play(loop_forever=loop_forever, repeat=repeat, speed=self._macro_speed())
        self.play_button.configure(text="Detener")
        self._schedule_stop_after()
        self.root.after(self.UI_TICK_MS, self._watch_playback)

    def _watch_playback(self):
        """Devuelve el botón a su estado normal cuando la macro termina sola."""
        if self.macro.is_playing:
            self.root.after(self.UI_TICK_MS, self._watch_playback)
        else:
            self.play_button.configure(text="Reproducir")
            self._cancel_stop_after()

    def _stop_playback(self):
        self.macro.stop_playback()
        self.play_button.configure(text="Reproducir")
        self._cancel_stop_after()

    def _clear_macro(self):
        if self.macro.is_recording or self.macro.is_playing:
            self._info("Macro", "Detén la grabación o la reproducción primero.")
            return
        if not self.macro.events:
            return
        if self._ask("Macro", "¿Borrar la macro en memoria?"):
            self.macro.clear()

    def _refresh_macro_list(self):
        ensure_dirs()
        self.macro_combo.configure(values=list_json_names(MACROS_DIR))

    def _save_macro(self):
        if not self.macro.events:
            self._info("Macro", "No hay nada grabado todavía.")
            return
        name = self.macro_name_var.get().strip()
        if not name:
            name = simpledialog.askstring("Guardar macro", "Nombre:", parent=self.root) or ""
            name = name.strip()
        path = json_path(MACROS_DIR, name)
        if not path:
            return
        if os.path.exists(path) and not self._ask(
            "Macro", f"Ya existe «{name}». ¿Reemplazarla?"
        ):
            return
        self.macro.name = name
        save_json(path, self.macro.to_dict())
        self.macro_name_var.set(name)
        self._refresh_macro_list()
        self.macro_status_var.set(f"Macro guardada: {name}")

    def _load_macro(self):
        if self.macro.is_recording or self.macro.is_playing:
            self._info("Macro", "Detén la grabación o la reproducción primero.")
            return
        name = self.macro_name_var.get().strip()
        path = json_path(MACROS_DIR, name)
        if not path or not os.path.exists(path):
            self._info("Macro", "Elige una macro guardada.")
            return
        self.macro.load_dict(load_json(path, {"events": []}), name=name)

    def _delete_macro(self):
        name = self.macro_name_var.get().strip()
        path = json_path(MACROS_DIR, name)
        if not path or not os.path.exists(path):
            return
        if not self._ask("Macro", f"¿Eliminar «{name}»?"):
            return
        try:
            os.remove(path)
        except OSError:
            pass
        self.macro_name_var.set("")
        self._refresh_macro_list()

    def _macro_file_dialog(self):
        ensure_dirs()
        if self.macro.is_recording or self.macro.is_playing:
            self._info("Macro", "Detén la grabación o la reproducción primero.")
            return
        choice = self._ask_three(
            "Macro", "¿Exportar la macro actual a un archivo?\n\n"
            "Sí: exportar.  No: importar desde un archivo."
        )
        if choice is None:
            return
        if choice:
            if not self.macro.events:
                self._info("Macro", "No hay nada grabado todavía.")
                return
            path = filedialog.asksaveasfilename(
                parent=self.root,
                initialdir=MACROS_DIR, defaultextension=".json",
                filetypes=[("Macro JSON", "*.json")],
            )
            if path:
                save_json(path, self.macro.to_dict())
        else:
            path = filedialog.askopenfilename(
                parent=self.root,
                initialdir=MACROS_DIR, filetypes=[("Macro JSON", "*.json")]
            )
            if path:
                self.macro.load_dict(
                    load_json(path, {"events": []}),
                    name=os.path.splitext(os.path.basename(path))[0],
                )

    # ------------------------------------------------------------- Lógica --
    def toggle_running(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def _has_work(self):
        """Indica si hay algo configurado para ejecutar al iniciar."""
        if self.mouse_enabled.get():
            return True
        if any(row.enabled.get() and row.key_var.get().strip() for row in self.key_rows):
            return True
        if self.sequence_in_toggle_var.get() and any(
            row.enabled.get() for row in self.step_rows
        ):
            return True
        return False

    def start(self):
        if self.running:
            return
        if not self._has_work():
            self._info(
                "Easy Autoclicker",
                "No hay nada configurado para ejecutar.\n\n"
                "Habilita el clic automático, agrega una tecla o arma una secuencia.",
            )
            return
        self.running = True
        self._clicks = 0
        self._run_started_at = time.perf_counter()
        self._cps_samples.clear()
        self._cps_samples.append((self._run_started_at, 0))
        self.status_var.set("Corriendo")
        self.status_label.configure(foreground="green")
        self.toggle_button.configure(text="Detener")

        if self.mouse_enabled.get():
            self._start_mouse_loop()

        for row in self.key_rows:
            row.start(self.keyboard_controller)

        if self.sequence_in_toggle_var.get():
            self._start_sequence()

        self._schedule_stop_after()

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.status_var.set("Detenido")
        self.status_label.configure(foreground="red")
        self.toggle_button.configure(text="Iniciar")

        self._click_stop_event.set()
        self._click_thread = None

        for row in self.key_rows:
            row.stop()

        if self.sequence_in_toggle_var.get():
            self._stop_sequence()

        self._cancel_stop_after()
        self._refresh_stats()

    def panic_stop(self):
        """Detiene absolutamente todo y suelta lo que esté presionado."""
        self.stop()
        for row in self.key_rows:
            row.stop()
        if self.macro.is_recording:
            self.macro.stop_recording()
            self.record_button.configure(text="Grabar")
        if self.macro.is_playing:
            self._stop_playback()
        self._stop_sequence()
        self.status_var.set("Detenido (pánico)")

    def _schedule_stop_after(self):
        if self._stop_after_id is not None:
            # Ya hay una cuenta en marcha: el límite es uno solo para todo.
            return
        if not self.stop_after_enabled.get():
            return
        try:
            seconds = max(float(self.stop_after_var.get()), 0.1)
        except (TypeError, ValueError):
            return
        self._stop_after_id = self.root.after(int(seconds * 1000), self._timed_stop)

    def _cancel_stop_after(self):
        # Sólo se cancela cuando ya no queda nada corriendo: el límite vale
        # también para la secuencia y la macro lanzadas por su cuenta.
        if self.running or self.sequence.is_running or self.macro.is_playing:
            return
        if self._stop_after_id is not None:
            try:
                self.root.after_cancel(self._stop_after_id)
            except Exception:
                pass
            self._stop_after_id = None

    def _timed_stop(self):
        self._stop_after_id = None
        self.panic_stop()
        self.status_var.set("Detenido (límite de tiempo)")

    # ------------------------------------------------------ bucle de clics --
    def _mouse_snapshot(self):
        """Lee los campos del mouse una sola vez, desde el hilo de la UI.

        El hilo de clics no debe tocar variables de Tk, así que se queda con
        esta copia: los cambios de ritmo se aplican al volver a iniciar.
        """
        def number(var, default, minimum=None):
            try:
                value = float(var.get())
            except (TypeError, ValueError):
                value = float(default)
            if minimum is not None:
                value = max(value, minimum)
            return value

        interval = number(self.mouse_interval_var, 100, 1.0) / 1000.0
        lo = number(self.mouse_min_var, 80, 1.0) / 1000.0
        hi = number(self.mouse_max_var, 150, 1.0) / 1000.0
        if hi < lo:
            lo, hi = hi, lo

        snapshot = {
            "button": MOUSE_BUTTONS.get(self.mouse_button_var.get(), mouse.Button.left),
            "clicks": CLICK_COUNTS.get(self.click_type_var.get(), 1),
            "delay": number(self.mouse_delay_var, 0, 0.0) / 1000.0,
            "interval": interval,
            "random": self.mouse_random_var.get(),
            "min": lo,
            "max": hi,
            "fixed": self.fixed_position.get(),
            "jitter": int(number(self.pos_jitter_var, 0, 0.0)),
            "repeat_mode": self.mouse_repeat_mode.get(),
            "repeat_limit": max(int(number(self.mouse_repeat_count_var, 10, 1.0)), 1),
        }
        if snapshot["fixed"]:
            snapshot["x"] = int(number(self.pos_x_var, self.mouse_controller.position[0]))
            snapshot["y"] = int(number(self.pos_y_var, self.mouse_controller.position[1]))
        return snapshot

    def _start_mouse_loop(self):
        self._click_stop_event.clear()
        cfg = self._mouse_snapshot()
        controller = self.mouse_controller
        stop_event = self._click_stop_event

        def next_wait():
            if cfg["random"]:
                return max(random.uniform(cfg["min"], cfg["max"]), 0.001)
            return cfg["interval"]

        def loop():
            if cfg["delay"] > 0 and stop_event.wait(cfg["delay"]):
                return
            count = 0
            jitter = cfg["jitter"]
            while not stop_event.is_set():
                if cfg["fixed"]:
                    x, y = cfg["x"], cfg["y"]
                    if jitter > 0:
                        x += random.randint(-jitter, jitter)
                        y += random.randint(-jitter, jitter)
                    controller.position = (x, y)
                try:
                    controller.click(cfg["button"], cfg["clicks"])
                except Exception:
                    pass
                count += 1
                # El contador lo lee el ticker de la UI: así no se inunda la
                # cola de eventos de Tk cuando el intervalo es muy chico.
                self._clicks += cfg["clicks"]
                if cfg["repeat_mode"] == "contado" and count >= cfg["repeat_limit"]:
                    self._ui(self.stop)
                    break
                if stop_event.wait(next_wait()):
                    break

        self._click_thread = threading.Thread(target=loop, daemon=True)
        self._click_thread.start()

    # ------------------------------------------------------ ticker de la UI --
    def _schedule_tick(self):
        if self._tick_id is None and not self._closing:
            self._tick_id = self.root.after(self.UI_TICK_MS, self._tick)

    def _tick(self):
        self._tick_id = None
        if self._closing:
            return
        self._drain_ui_queue()
        if self.running:
            self._refresh_stats()
        self._schedule_tick()

    def _drain_ui_queue(self):
        """Ejecuta en el hilo principal lo que dejaron los hilos de trabajo."""
        while True:
            try:
                callback = self._ui_queue.get_nowait()
            except queue.Empty:
                return
            try:
                callback()
            except tk.TclError:
                return

    def _refresh_stats(self):
        now = time.perf_counter()
        clicks = self._clicks
        parts = [f"Clics: {clicks}"]
        if self.running:
            self._cps_samples.append((now, clicks))
            elapsed = now - self._run_started_at
            parts.append(f"Tiempo: {self._format_time(elapsed)}")
            cps = self._current_cps(now, clicks)
            if cps is not None:
                parts.append(f"CPS: {cps:.1f}")
        self.stats_var.set("   ".join(parts))

    def _current_cps(self, now, clicks):
        """Clics por segundo del último segundo, según las muestras del ticker."""
        window_start = now - 1.0
        base = None
        for sample_time, sample_clicks in self._cps_samples:
            if sample_time <= window_start:
                base = (sample_time, sample_clicks)
            else:
                break
        if base is None:
            base = self._cps_samples[0]
        span = now - base[0]
        if span <= 0:
            return None
        return (clicks - base[1]) / span

    @staticmethod
    def _format_time(seconds):
        seconds = int(seconds)
        if seconds < 3600:
            return f"{seconds // 60:02d}:{seconds % 60:02d}"
        return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"

    # ------------------------------------------------------------- Hotkeys --
    def _ui(self, callback):
        """Ejecuta algo en el hilo de Tk, venga de donde venga la llamada.

        Desde el hilo principal corre al instante; desde un hilo de trabajo se
        encola, porque llamar a Tk desde otro hilo no es seguro.
        """
        if self._closing:
            return
        if threading.current_thread() is self._main_thread:
            try:
                callback()
            except tk.TclError:
                pass
            return
        self._ui_queue.put(callback)

    def _track_typing_focus(self):
        """Marca cuándo el foco está en un campo de texto de la ventana.

        Sirve para que una hotkey de una sola letra no se dispare mientras se
        escribe el nombre de una tecla o un intervalo.
        """
        def focus_in(_event=None):
            self._typing = True

        def focus_out(_event=None):
            self._typing = False

        for widget_class in ("TEntry", "TCombobox", "Entry"):
            self.root.bind_class(widget_class, "<FocusIn>", focus_in, add="+")
            self.root.bind_class(widget_class, "<FocusOut>", focus_out, add="+")

    def _refresh_hotkey_hint(self):
        parts = []
        for action, label in HOTKEY_LABELS.items():
            combo = self.hotkeys.get(action)
            if combo:
                short = label.split(" (")[0]
                parts.append(f"{short}: {combo_label(combo)}")
        self.hotkey_hint_var.set("   ".join(parts))

    def _dispatch_hotkey(self, action):
        if self._capturing_hotkey:
            return
        actions = {
            "toggle": self.toggle_running,
            "panic": self.panic_stop,
            "record": self._toggle_recording,
            "play": self._toggle_playback,
            "sequence": self._toggle_sequence,
        }
        callback = actions.get(action)
        if callback is not None:
            self._ui(callback)

    def _set_capture_mode(self, active):
        self._capturing_hotkey = active
        self.hotkey_manager.paused = active

    def _assign_hotkey(self, action):
        self.assign_status_var.set("Presiona la tecla o combinación...")

        def done(combo):
            if not combo:
                self.assign_status_var.set("Captura cancelada")
                return
            other = self.hotkey_manager.conflicting_action(combo, ignore_action=action)
            if other:
                self.assign_status_var.set(
                    f"{combo_label(combo)} ya está en «{HOTKEY_LABELS.get(other, other)}»"
                )
                return
            self.hotkeys[action] = normalize_combo(combo)
            self._apply_hotkeys()
            self.assign_status_var.set(f"Asignado: {combo_label(combo)}")

        CaptureDialog(
            self.root,
            done,
            title=HOTKEY_LABELS.get(action, "Hotkey"),
            on_cancel=lambda: self.assign_status_var.set("Captura cancelada"),
        )

    def _clear_hotkey(self, action):
        self.hotkeys[action] = ""
        self._apply_hotkeys()
        self.assign_status_var.set(f"«{HOTKEY_LABELS.get(action, action)}» sin hotkey")

    def _apply_hotkeys(self):
        self.hotkey_manager.set_bindings(self.hotkeys)
        for action, var in self.hotkey_vars.items():
            var.set(combo_label(self.hotkeys.get(action, "")))
        self._refresh_hotkey_hint()

    def _apply_always_on_top(self):
        self.root.attributes("-topmost", self.always_on_top_var.get())

    # --------------------------------------------------------- Config --
    def _collect_config(self):
        return {
            "version": 2,
            "mouse": {
                "enabled": self.mouse_enabled.get(),
                "button": self.mouse_button_var.get(),
                "click_type": self.click_type_var.get(),
                "interval_ms": self.mouse_interval_var.get(),
                "delay_ms": self.mouse_delay_var.get(),
                "random": self.mouse_random_var.get(),
                "min_ms": self.mouse_min_var.get(),
                "max_ms": self.mouse_max_var.get(),
                "repeat_mode": self.mouse_repeat_mode.get(),
                "repeat_count": self.mouse_repeat_count_var.get(),
                "fixed_position": self.fixed_position.get(),
                "pos_x": self.pos_x_var.get(),
                "pos_y": self.pos_y_var.get(),
                "pos_jitter": self.pos_jitter_var.get(),
            },
            "keys": [row.to_dict() for row in self.key_rows],
            "macro": {
                "loop_forever": self.macro_loop_forever.get(),
                "repeat": self.macro_repeat_var.get(),
                "speed": self.macro_speed_var.get(),
                "record_moves": self.macro_record_moves_var.get(),
                "last_name": self.macro_name_var.get(),
            },
            "sequence": {
                "steps": [row.to_dict() for row in self.step_rows],
                "loop_forever": self.sequence_loop_forever.get(),
                "repeat": self.sequence_repeat_var.get(),
                "include_in_toggle": self.sequence_in_toggle_var.get(),
                "last_name": self.sequence_name_var.get(),
            },
            "hotkeys": self.hotkeys,
            "limits": {
                "stop_after_enabled": self.stop_after_enabled.get(),
                "stop_after_seconds": self.stop_after_var.get(),
            },
            "window": {
                "always_on_top": self.always_on_top_var.get(),
                "minimize_to_tray": self.minimize_to_tray_var.get(),
                "geometry": self._current_geometry(),
            },
        }

    def _current_geometry(self):
        try:
            return self.root.winfo_geometry()
        except tk.TclError:
            return ""

    def _apply_config(self, cfg, restore_geometry=True):
        m = cfg.get("mouse", {})
        self.mouse_enabled.set(m.get("enabled", True))
        self.mouse_button_var.set(m.get("button", "Izquierdo"))
        self.click_type_var.set(m.get("click_type", "Simple"))
        self.mouse_interval_var.set(str(m.get("interval_ms", 100)))
        self.mouse_delay_var.set(str(m.get("delay_ms", 0)))
        self.mouse_random_var.set(m.get("random", False))
        self.mouse_min_var.set(str(m.get("min_ms", 80)))
        self.mouse_max_var.set(str(m.get("max_ms", 150)))
        self.mouse_repeat_mode.set(m.get("repeat_mode", "infinito"))
        self.mouse_repeat_count_var.set(str(m.get("repeat_count", 10)))
        self.fixed_position.set(m.get("fixed_position", False))
        self.pos_x_var.set(str(m.get("pos_x", 0)))
        self.pos_y_var.set(str(m.get("pos_y", 0)))
        self.pos_jitter_var.set(str(m.get("pos_jitter", 0)))
        self._toggle_position_fields()

        for row in list(self.key_rows):
            row.destroy()
        self.key_rows = []
        for key_data in cfg.get("keys", []):
            self._add_key_row(key_data)
        if not self.key_rows:
            self._add_key_row()

        macro_cfg = cfg.get("macro", {})
        self.macro_loop_forever.set(macro_cfg.get("loop_forever", True))
        self.macro_repeat_var.set(str(macro_cfg.get("repeat", 1)))
        self.macro_speed_var.set(str(macro_cfg.get("speed", "1")))
        self.macro_record_moves_var.set(macro_cfg.get("record_moves", True))
        self.macro_name_var.set(macro_cfg.get("last_name", ""))
        self._apply_macro_record_moves()
        self._toggle_macro_repeat_field()

        self._clear_step_rows()
        seq = cfg.get("sequence", {})
        for step_data in seq.get("steps", []):
            self._add_step_row(step_data)
        self.sequence_loop_forever.set(seq.get("loop_forever", True))
        self.sequence_repeat_var.set(str(seq.get("repeat", 1)))
        self.sequence_in_toggle_var.set(seq.get("include_in_toggle", True))
        self.sequence_name_var.set(seq.get("last_name", ""))
        self._toggle_sequence_repeat_field()
        self._renumber_steps()

        hotkeys = dict(DEFAULT_HOTKEYS)
        for action, combo in (cfg.get("hotkeys") or {}).items():
            if action in hotkeys:
                hotkeys[action] = normalize_combo(combo)
        self.hotkeys = hotkeys
        self._apply_hotkeys()

        limits = cfg.get("limits", {})
        self.stop_after_enabled.set(limits.get("stop_after_enabled", False))
        self.stop_after_var.set(str(limits.get("stop_after_seconds", 60)))
        self._toggle_stop_after_field()

        # "always_on_top" vivía en la raíz de la config antigua.
        window = cfg.get("window", {})
        self.always_on_top_var.set(
            window.get("always_on_top", cfg.get("always_on_top", False))
        )
        self._apply_always_on_top()
        if tray.TRAY_DISPONIBLE:
            self.minimize_to_tray_var.set(window.get("minimize_to_tray", True))
        if restore_geometry:
            self._apply_geometry(window.get("geometry", ""))

    def _apply_geometry(self, geometry):
        """Restaura tamaño y posición, sin dejar la ventana fuera de pantalla.

        Si se guardó en un monitor que ya no está, la posición se descarta y
        la ventana vuelve a abrirse donde el sistema decida.
        """
        match = re.match(r"^(\d+x\d+)((?:[+-]\d+){2})?$", geometry.strip())
        if not match:
            return
        size, position = match.group(1), match.group(2) or ""
        if position:
            x, y = (int(value) for value in re.findall(r"[+-]\d+", position))
            max_x = self.root.winfo_screenwidth() - 200
            max_y = self.root.winfo_screenheight() - 200
            if not (0 <= x <= max_x and 0 <= y <= max_y):
                position = ""
        try:
            self.root.geometry(size + position)
        except tk.TclError:
            pass

    def _load_config(self):
        ensure_dirs()
        cfg = load_json(CONFIG_PATH, None)
        if cfg:
            self._apply_config(cfg)
        else:
            self._add_key_row()
            self._apply_hotkeys()

    def _save_config(self):
        try:
            save_json(CONFIG_PATH, self._collect_config())
        except OSError:
            pass

    # --------------------------------------------------------- Presets --
    def _refresh_preset_list(self):
        presets = load_json(PRESETS_PATH, {})
        self.preset_combo.configure(values=list(presets.keys()))

    def _save_preset_dialog(self):
        name = simpledialog.askstring("Guardar perfil", "Nombre del perfil:", parent=self.root)
        if not name or not name.strip():
            return
        name = name.strip()
        presets = load_json(PRESETS_PATH, {})
        if name in presets and not self._ask(
            "Perfiles", f"Ya existe «{name}». ¿Reemplazarlo?"
        ):
            return
        config = self._collect_config()
        config["window"].pop("geometry", None)
        presets[name] = config
        save_json(PRESETS_PATH, presets)
        self._refresh_preset_list()
        self.preset_var.set(name)

    def _load_preset(self):
        name = self.preset_var.get()
        if not name:
            return
        if self.running:
            self.stop()
        presets = load_json(PRESETS_PATH, {})
        if name in presets:
            self._apply_config(presets[name], restore_geometry=False)

    def _delete_preset(self):
        name = self.preset_var.get()
        if not name:
            return
        if not self._ask("Perfiles", f"¿Eliminar el perfil «{name}»?"):
            return
        presets = load_json(PRESETS_PATH, {})
        if name in presets:
            del presets[name]
            save_json(PRESETS_PATH, presets)
            self._refresh_preset_list()
            self.preset_var.set("")

    # ------------------------------------------------------------ Tray --
    def _show_from_tray(self, icon=None, item=None):
        self._ui(self._restore_window)

    def _restore_window(self):
        self.root.deiconify()
        self.root.lift()
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None

    def _quit_from_tray(self, icon=None, item=None):
        self._ui(self._force_close)

    def _force_close(self):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self._closing_to_tray = True
        self.on_close()

    def _minimize_to_tray(self):
        self.root.withdraw()
        menu = tray.pystray.Menu(
            tray.pystray.MenuItem("Mostrar", self._show_from_tray, default=True),
            tray.pystray.MenuItem(
                "Iniciar/Detener", lambda icon, item: self._ui(self.toggle_running)
            ),
            tray.pystray.MenuItem("Detener todo", lambda icon, item: self._ui(self.panic_stop)),
            tray.pystray.MenuItem("Salir", self._quit_from_tray),
        )
        self.tray_icon = tray.pystray.Icon(
            "easy_autoclicker", tray.make_tray_image(), "Easy Autoclicker", menu
        )
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def on_close(self):
        if tray.TRAY_DISPONIBLE and self.minimize_to_tray_var.get() and not self._closing_to_tray:
            self._save_config()
            self._minimize_to_tray()
            return
        self._save_config()
        self.stop()
        self._closing = True
        for row in self.key_rows:
            row.stop()
        if self.macro.is_recording:
            self.macro.stop_recording()
        if self.macro.is_playing:
            self.macro.stop_playback()
        self.sequence.stop()
        self.hotkey_manager.stop()
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.destroy()


def main():
    root = tk.Tk()
    app = AutoClickerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
