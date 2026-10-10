"""Ventana principal de Easy Autoclicker: construcción de la UI y la lógica."""

import random
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from pynput import keyboard, mouse

from . import tray
from .constants import CLICK_COUNTS, DEFAULT_HOTKEYS, MOUSE_BUTTONS
from .key_row import KeyRow
from .keys import key_to_text
from .macro import MacroRecorder
from .paths import CONFIG_PATH, MACROS_DIR, PRESETS_PATH, ensure_dirs, load_json, save_json


class AutoClickerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Easy Autoclicker")
        self.root.resizable(False, False)
        self._icon_photo = tray.apply_window_icon(self.root)

        self.mouse_controller = mouse.Controller()
        self.keyboard_controller = keyboard.Controller()

        self.running = False
        self.click_count = 0
        self._click_stop_event = threading.Event()
        self._click_thread = None

        self.key_rows = []
        self.hotkeys = dict(DEFAULT_HOTKEYS)
        self._listening_for_hotkey = None

        self.macro = MacroRecorder(
            self.mouse_controller, self.keyboard_controller, on_status=self._set_macro_status
        )

        self.tray_icon = None
        self._closing_to_tray = False

        self._build_ui()
        self._load_config()
        self._start_hotkey_listener()

    # ---------------------------------------------------------------- UI --
    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, **pad)

        mouse_tab = ttk.Frame(notebook)
        keys_tab = ttk.Frame(notebook)
        macro_tab = ttk.Frame(notebook)
        settings_tab = ttk.Frame(notebook)
        notebook.add(mouse_tab, text="Mouse")
        notebook.add(keys_tab, text="Teclas")
        notebook.add(macro_tab, text="Macros")
        notebook.add(settings_tab, text="Ajustes")

        self._build_mouse_tab(mouse_tab)
        self._build_keys_tab(keys_tab)
        self._build_macro_tab(macro_tab)
        self._build_settings_tab(settings_tab)

        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill="x", **pad)

        self.status_var = tk.StringVar(value="Detenido")
        ttk.Label(control_frame, textvariable=self.status_var, foreground="red").pack(side="left")

        self.count_var = tk.StringVar(value="Clics: 0")
        ttk.Label(control_frame, textvariable=self.count_var).pack(side="left", padx=(12, 0))

        self.hotkey_hint_var = tk.StringVar()
        ttk.Label(control_frame, textvariable=self.hotkey_hint_var).pack(side="left", padx=(12, 0))
        self._refresh_hotkey_hint()

        self.toggle_button = ttk.Button(control_frame, text="Iniciar", command=self.toggle_running)
        self.toggle_button.pack(side="right")

    def _build_mouse_tab(self, parent):
        mouse_frame = ttk.LabelFrame(parent, text="Clic del mouse")
        mouse_frame.pack(fill="x", padx=8, pady=6)

        self.mouse_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            mouse_frame, text="Habilitar clic automático", variable=self.mouse_enabled
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=6, pady=4)

        ttk.Label(mouse_frame, text="Botón:").grid(row=1, column=0, sticky="w", padx=6)
        self.mouse_button_var = tk.StringVar(value="Izquierdo")
        ttk.Combobox(
            mouse_frame, textvariable=self.mouse_button_var, values=list(MOUSE_BUTTONS.keys()),
            state="readonly", width=10,
        ).grid(row=1, column=1, sticky="w")

        ttk.Label(mouse_frame, text="Tipo de clic:").grid(row=1, column=2, sticky="w", padx=(12, 0))
        self.click_type_var = tk.StringVar(value="Simple")
        ttk.Combobox(
            mouse_frame, textvariable=self.click_type_var, values=list(CLICK_COUNTS.keys()),
            state="readonly", width=8,
        ).grid(row=1, column=3, sticky="w")

        ttk.Label(mouse_frame, text="Intervalo (ms):").grid(row=2, column=0, sticky="w", padx=6)
        self.mouse_interval_var = tk.StringVar(value="100")
        ttk.Entry(mouse_frame, textvariable=self.mouse_interval_var, width=8).grid(row=2, column=1, sticky="w")

        ttk.Label(mouse_frame, text="Retraso inicial (ms):").grid(row=2, column=2, sticky="w", padx=(12, 0))
        self.mouse_delay_var = tk.StringVar(value="0")
        ttk.Entry(mouse_frame, textvariable=self.mouse_delay_var, width=8).grid(row=2, column=3, sticky="w")

        self.mouse_random_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            mouse_frame, text="Variar intervalo (aleatorio)", variable=self.mouse_random_var
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=6, pady=(4, 0))

        ttk.Label(mouse_frame, text="Mín (ms):").grid(row=3, column=2, sticky="e")
        self.mouse_min_var = tk.StringVar(value="80")
        ttk.Entry(mouse_frame, textvariable=self.mouse_min_var, width=6).grid(row=3, column=3, sticky="w")

        ttk.Label(mouse_frame, text="Máx (ms):").grid(row=4, column=2, sticky="e")
        self.mouse_max_var = tk.StringVar(value="150")
        ttk.Entry(mouse_frame, textvariable=self.mouse_max_var, width=6).grid(row=4, column=3, sticky="w")

        self.mouse_repeat_mode = tk.StringVar(value="infinito")
        ttk.Radiobutton(
            mouse_frame, text="Repetir sin límite", variable=self.mouse_repeat_mode, value="infinito"
        ).grid(row=5, column=0, columnspan=2, sticky="w", padx=6, pady=(4, 0))
        ttk.Radiobutton(
            mouse_frame, text="Repetir:", variable=self.mouse_repeat_mode, value="contado"
        ).grid(row=6, column=0, sticky="w", padx=6)
        self.mouse_repeat_count_var = tk.StringVar(value="10")
        ttk.Entry(mouse_frame, textvariable=self.mouse_repeat_count_var, width=6).grid(
            row=6, column=1, sticky="w"
        )
        ttk.Label(mouse_frame, text="veces").grid(row=6, column=2, sticky="w")

        self.fixed_position = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            mouse_frame, text="Usar posición fija", variable=self.fixed_position,
            command=self._toggle_position_fields,
        ).grid(row=7, column=0, columnspan=2, sticky="w", padx=6, pady=(8, 4))

        ttk.Label(mouse_frame, text="X:").grid(row=7, column=2, sticky="e")
        self.pos_x_var = tk.StringVar(value="0")
        self.pos_x_entry = ttk.Entry(mouse_frame, textvariable=self.pos_x_var, width=6, state="disabled")
        self.pos_x_entry.grid(row=7, column=3, sticky="w")

        ttk.Label(mouse_frame, text="Y:").grid(row=8, column=2, sticky="e")
        self.pos_y_var = tk.StringVar(value="0")
        self.pos_y_entry = ttk.Entry(mouse_frame, textvariable=self.pos_y_var, width=6, state="disabled")
        self.pos_y_entry.grid(row=8, column=3, sticky="w")

        ttk.Button(
            mouse_frame, text="Capturar posición actual", command=self._capture_position
        ).grid(row=8, column=0, columnspan=2, sticky="w", padx=6)
        ttk.Button(
            mouse_frame, text="Capturar en 3s (mueve el mouse)", command=self._capture_position_delayed
        ).grid(row=9, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 6))

    def _build_keys_tab(self, parent):
        keys_frame = ttk.LabelFrame(parent, text="Teclas simultáneas")
        keys_frame.pack(fill="x", padx=8, pady=6)

        ttk.Label(
            keys_frame,
            text="Cada tecla corre en su propio hilo: pueden pulsarse todas al mismo tiempo.",
        ).pack(anchor="w", padx=6, pady=(4, 0))

        self.keys_container = ttk.Frame(keys_frame)
        self.keys_container.pack(fill="x", padx=6, pady=4)

        ttk.Button(keys_frame, text="Agregar tecla", command=lambda: self._add_key_row()).pack(
            anchor="w", padx=6, pady=(0, 6)
        )

    def _build_macro_tab(self, parent):
        macro_frame = ttk.LabelFrame(parent, text="Grabar y reproducir macro (mouse + teclado)")
        macro_frame.pack(fill="x", padx=8, pady=6)

        btns = ttk.Frame(macro_frame)
        btns.pack(fill="x", padx=6, pady=6)

        self.record_button = ttk.Button(btns, text="Grabar", command=self._toggle_recording)
        self.record_button.pack(side="left")

        self.play_button = ttk.Button(btns, text="Reproducir", command=self._toggle_playback)
        self.play_button.pack(side="left", padx=(6, 0))

        ttk.Button(btns, text="Guardar macro...", command=self._save_macro_dialog).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(btns, text="Cargar macro...", command=self._load_macro_dialog).pack(
            side="left", padx=(6, 0)
        )

        loop_frame = ttk.Frame(macro_frame)
        loop_frame.pack(fill="x", padx=6, pady=(0, 6))

        self.macro_loop_forever = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            loop_frame, text="Repetir sin límite", variable=self.macro_loop_forever,
            command=self._toggle_macro_repeat_field,
        ).pack(side="left")

        ttk.Label(loop_frame, text="Repeticiones:").pack(side="left", padx=(12, 2))
        self.macro_repeat_var = tk.StringVar(value="1")
        self.macro_repeat_entry = ttk.Entry(loop_frame, textvariable=self.macro_repeat_var, width=6, state="disabled")
        self.macro_repeat_entry.pack(side="left")

        self.macro_status_var = tk.StringVar(value="Sin macro grabada")
        ttk.Label(macro_frame, textvariable=self.macro_status_var).pack(anchor="w", padx=6, pady=(0, 6))

    def _build_settings_tab(self, parent):
        hk_frame = ttk.LabelFrame(parent, text="Hotkeys globales")
        hk_frame.pack(fill="x", padx=8, pady=6)

        ttk.Label(hk_frame, text="Iniciar / Detener:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.toggle_hotkey_var = tk.StringVar(value=self.hotkeys["toggle"])
        ttk.Label(hk_frame, textvariable=self.toggle_hotkey_var, width=10).grid(row=0, column=1, sticky="w")
        ttk.Button(
            hk_frame, text="Asignar", command=lambda: self._begin_assign_hotkey("toggle")
        ).grid(row=0, column=2, padx=6)

        ttk.Label(hk_frame, text="Pánico (detener todo):").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.panic_hotkey_var = tk.StringVar(value=self.hotkeys["panic"])
        ttk.Label(hk_frame, textvariable=self.panic_hotkey_var, width=10).grid(row=1, column=1, sticky="w")
        ttk.Button(
            hk_frame, text="Asignar", command=lambda: self._begin_assign_hotkey("panic")
        ).grid(row=1, column=2, padx=6)

        self.assign_status_var = tk.StringVar(value="")
        ttk.Label(hk_frame, textvariable=self.assign_status_var, foreground="blue").grid(
            row=2, column=0, columnspan=3, sticky="w", padx=6
        )

        window_frame = ttk.LabelFrame(parent, text="Ventana")
        window_frame.pack(fill="x", padx=8, pady=6)

        self.always_on_top_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            window_frame, text="Siempre visible (always on top)", variable=self.always_on_top_var,
            command=self._apply_always_on_top,
        ).pack(anchor="w", padx=6, pady=4)

        if tray.TRAY_DISPONIBLE:
            self.minimize_to_tray_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(
                window_frame, text="Minimizar a la bandeja al cerrar la ventana",
                variable=self.minimize_to_tray_var,
            ).pack(anchor="w", padx=6, pady=(0, 4))
        else:
            self.minimize_to_tray_var = tk.BooleanVar(value=False)
            ttk.Label(
                window_frame,
                text="(Bandeja del sistema no disponible: instala pystray y Pillow para activarla)",
                foreground="gray",
            ).pack(anchor="w", padx=6, pady=(0, 4))

        preset_frame = ttk.LabelFrame(parent, text="Perfiles guardados")
        preset_frame.pack(fill="x", padx=8, pady=6)

        self.preset_var = tk.StringVar(value="")
        self.preset_combo = ttk.Combobox(preset_frame, textvariable=self.preset_var, state="readonly", width=24)
        self.preset_combo.grid(row=0, column=0, columnspan=3, sticky="w", padx=6, pady=4)
        self._refresh_preset_list()

        ttk.Button(preset_frame, text="Cargar", command=self._load_preset).grid(row=1, column=0, padx=6, pady=(0, 6))
        ttk.Button(preset_frame, text="Guardar como...", command=self._save_preset_dialog).grid(
            row=1, column=1, padx=6, pady=(0, 6)
        )
        ttk.Button(preset_frame, text="Eliminar", command=self._delete_preset).grid(
            row=1, column=2, padx=6, pady=(0, 6)
        )

        about_frame = ttk.LabelFrame(parent, text="Acerca de")
        about_frame.pack(fill="x", padx=8, pady=6)
        ttk.Label(
            about_frame,
            text="Easy Autoclicker es software libre y gratuito: nace como una "
            "alternativa a los programas tradicionales y del rechazo que me "
            "genera que haya gente que se atreva a cobrar por esto.",
            wraplength=420,
            justify="left",
        ).pack(anchor="w", padx=6, pady=6)

    def _toggle_position_fields(self):
        state = "normal" if self.fixed_position.get() else "disabled"
        self.pos_x_entry.configure(state=state)
        self.pos_y_entry.configure(state=state)

    def _toggle_macro_repeat_field(self):
        state = "disabled" if self.macro_loop_forever.get() else "normal"
        self.macro_repeat_entry.configure(state=state)

    def _capture_position(self):
        x, y = self.mouse_controller.position
        self.pos_x_var.set(str(x))
        self.pos_y_var.set(str(y))

    def _capture_position_delayed(self):
        def worker():
            time.sleep(3)
            x, y = self.mouse_controller.position
            self.root.after(0, lambda: (self.pos_x_var.set(str(x)), self.pos_y_var.set(str(y))))

        threading.Thread(target=worker, daemon=True).start()

    def _add_key_row(self, data=None):
        row = KeyRow(self.keys_container, self._remove_key_row, data)
        self.key_rows.append(row)

    def _remove_key_row(self, row):
        row.destroy()
        self.key_rows.remove(row)

    # ------------------------------------------------------- Macro UI --
    def _set_macro_status(self, text):
        self.root.after(0, lambda: self.macro_status_var.set(text))

    def _toggle_recording(self):
        if self.macro.is_recording:
            self.macro.stop_recording()
            self.record_button.configure(text="Grabar")
        else:
            if self.macro.is_playing:
                return
            self.macro.start_recording()
            self.record_button.configure(text="Detener grabación")

    def _toggle_playback(self):
        if self.macro.is_playing:
            self.macro.stop_playback()
            self.play_button.configure(text="Reproducir")
        else:
            if self.macro.is_recording or not self.macro.events:
                return
            loop_forever = self.macro_loop_forever.get()
            try:
                repeat = max(int(self.macro_repeat_var.get()), 1)
            except ValueError:
                repeat = 1
            self.macro.play(loop_forever=loop_forever, repeat=repeat)
            self.play_button.configure(text="Detener")

    def _save_macro_dialog(self):
        ensure_dirs()
        if not self.macro.events:
            messagebox.showinfo("Macro", "No hay nada grabado todavía.")
            return
        path = filedialog.asksaveasfilename(
            initialdir=MACROS_DIR, defaultextension=".json", filetypes=[("Macro JSON", "*.json")]
        )
        if path:
            save_json(path, self.macro.to_dict())

    def _load_macro_dialog(self):
        ensure_dirs()
        path = filedialog.askopenfilename(initialdir=MACROS_DIR, filetypes=[("Macro JSON", "*.json")])
        if path:
            data = load_json(path, {"events": []})
            self.macro.load_dict(data)
            self.macro_status_var.set(f"Macro cargada ({len(self.macro.events)} eventos)")

    # ----------------------------------------------------------- Lógica --
    def toggle_running(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self):
        if self.running:
            return
        self.running = True
        self.click_count = 0
        self.count_var.set("Clics: 0")
        self.status_var.set("Corriendo")
        self.toggle_button.configure(text="Detener")

        if self.mouse_enabled.get():
            self._start_mouse_loop()

        for row in self.key_rows:
            row.start(self.keyboard_controller)

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.status_var.set("Detenido")
        self.toggle_button.configure(text="Iniciar")

        self._click_stop_event.set()
        self._click_thread = None

        for row in self.key_rows:
            row.stop()

    def panic_stop(self):
        self.stop()
        if self.macro.is_recording:
            self.macro.stop_recording()
            self.record_button.configure(text="Grabar")
        if self.macro.is_playing:
            self.macro.stop_playback()
            self.play_button.configure(text="Reproducir")

    def _get_mouse_interval_seconds(self):
        try:
            ms = float(self.mouse_interval_var.get())
        except ValueError:
            ms = 100.0
        return max(ms, 1.0) / 1000.0

    def _get_mouse_delay_seconds(self):
        try:
            ms = float(self.mouse_delay_var.get())
        except ValueError:
            ms = 0.0
        return max(ms, 0.0) / 1000.0

    def _next_mouse_interval(self):
        if self.mouse_random_var.get():
            try:
                lo = float(self.mouse_min_var.get())
                hi = float(self.mouse_max_var.get())
            except ValueError:
                lo, hi = 80.0, 150.0
            if hi < lo:
                lo, hi = hi, lo
            return max(random.uniform(lo, hi), 1.0) / 1000.0
        return self._get_mouse_interval_seconds()

    def _start_mouse_loop(self):
        self._click_stop_event.clear()
        button = MOUSE_BUTTONS.get(self.mouse_button_var.get(), mouse.Button.left)
        click_count = CLICK_COUNTS.get(self.click_type_var.get(), 1)
        delay = self._get_mouse_delay_seconds()
        use_fixed = self.fixed_position.get()
        repeat_mode = self.mouse_repeat_mode.get()
        try:
            repeat_limit = max(int(self.mouse_repeat_count_var.get()), 1)
        except ValueError:
            repeat_limit = 10

        if use_fixed:
            try:
                fixed_x = int(float(self.pos_x_var.get()))
                fixed_y = int(float(self.pos_y_var.get()))
            except ValueError:
                fixed_x, fixed_y = self.mouse_controller.position
        else:
            fixed_x = fixed_y = None

        def loop():
            if delay > 0 and self._click_stop_event.wait(delay):
                return
            count = 0
            while not self._click_stop_event.is_set():
                if use_fixed:
                    self.mouse_controller.position = (fixed_x, fixed_y)
                self.mouse_controller.click(button, click_count)
                count += 1
                self.click_count += 1
                self.root.after(0, lambda c=self.click_count: self.count_var.set(f"Clics: {c}"))
                if repeat_mode == "contado" and count >= repeat_limit:
                    self.root.after(0, self.stop)
                    break
                if self._click_stop_event.wait(self._next_mouse_interval()):
                    break

        self._click_thread = threading.Thread(target=loop, daemon=True)
        self._click_thread.start()

    # ------------------------------------------------------- Hotkeys --
    def _refresh_hotkey_hint(self):
        self.hotkey_hint_var.set(
            f"  Iniciar/Detener: {self.hotkeys['toggle'].upper()}   Pánico: {self.hotkeys['panic'].upper()}"
        )

    def _begin_assign_hotkey(self, which):
        self._listening_for_hotkey = which
        self.assign_status_var.set("Presiona la tecla que quieras asignar...")

    def _start_hotkey_listener(self):
        def on_press(key):
            try:
                name = key_to_text(key)
                if self._listening_for_hotkey:
                    which = self._listening_for_hotkey
                    self._listening_for_hotkey = None
                    self.hotkeys[which] = name
                    self.root.after(0, lambda: self._on_hotkey_assigned(which, name))
                    return
                if name == self.hotkeys.get("toggle"):
                    self.root.after(0, self.toggle_running)
                elif name == self.hotkeys.get("panic"):
                    self.root.after(0, self.panic_stop)
            except Exception:
                pass

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.daemon = True
        self._listener.start()

    def _on_hotkey_assigned(self, which, name):
        if which == "toggle":
            self.toggle_hotkey_var.set(name)
        else:
            self.panic_hotkey_var.set(name)
        self.assign_status_var.set(f"Asignado: {name.upper()}")
        self._refresh_hotkey_hint()

    def _apply_always_on_top(self):
        self.root.attributes("-topmost", self.always_on_top_var.get())

    # --------------------------------------------------------- Config --
    def _collect_config(self):
        return {
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
            },
            "keys": [row.to_dict() for row in self.key_rows],
            "hotkeys": self.hotkeys,
            "always_on_top": self.always_on_top_var.get(),
        }

    def _apply_config(self, cfg):
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
        self._toggle_position_fields()

        for row in list(self.key_rows):
            self._remove_key_row(row)
        for key_data in cfg.get("keys", []):
            self._add_key_row(key_data)
        if not self.key_rows:
            self._add_key_row()

        self.hotkeys = dict(cfg.get("hotkeys", DEFAULT_HOTKEYS))
        self.toggle_hotkey_var.set(self.hotkeys.get("toggle", "f6"))
        self.panic_hotkey_var.set(self.hotkeys.get("panic", "esc"))
        self._refresh_hotkey_hint()

        self.always_on_top_var.set(cfg.get("always_on_top", False))
        self._apply_always_on_top()

    def _load_config(self):
        ensure_dirs()
        cfg = load_json(CONFIG_PATH, None)
        if cfg:
            self._apply_config(cfg)
        else:
            self._add_key_row()

    def _save_config(self):
        save_json(CONFIG_PATH, self._collect_config())

    # --------------------------------------------------------- Presets --
    def _refresh_preset_list(self):
        presets = load_json(PRESETS_PATH, {})
        self.preset_combo.configure(values=list(presets.keys()))

    def _save_preset_dialog(self):
        name = simpledialog.askstring("Guardar perfil", "Nombre del perfil:", parent=self.root)
        if not name:
            return
        presets = load_json(PRESETS_PATH, {})
        presets[name] = self._collect_config()
        save_json(PRESETS_PATH, presets)
        self._refresh_preset_list()
        self.preset_var.set(name)

    def _load_preset(self):
        name = self.preset_var.get()
        if not name:
            return
        presets = load_json(PRESETS_PATH, {})
        if name in presets:
            self._apply_config(presets[name])

    def _delete_preset(self):
        name = self.preset_var.get()
        if not name:
            return
        presets = load_json(PRESETS_PATH, {})
        if name in presets:
            del presets[name]
            save_json(PRESETS_PATH, presets)
            self._refresh_preset_list()
            self.preset_var.set("")

    # ------------------------------------------------------------ Tray --
    def _show_from_tray(self, icon=None, item=None):
        self.root.after(0, self._restore_window)

    def _restore_window(self):
        self.root.deiconify()
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None

    def _quit_from_tray(self, icon=None, item=None):
        self.root.after(0, self._force_close)

    def _force_close(self):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self._closing_to_tray = False
        self.on_close()

    def _minimize_to_tray(self):
        self.root.withdraw()
        menu = tray.pystray.Menu(
            tray.pystray.MenuItem("Mostrar", self._show_from_tray),
            tray.pystray.MenuItem(
                "Iniciar/Detener", lambda icon, item: self.root.after(0, self.toggle_running)
            ),
            tray.pystray.MenuItem("Salir", self._quit_from_tray),
        )
        self.tray_icon = tray.pystray.Icon(
            "easy_autoclicker", tray.make_tray_image(), "Easy Autoclicker", menu
        )
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def on_close(self):
        if tray.TRAY_DISPONIBLE and self.minimize_to_tray_var.get() and not self._closing_to_tray:
            self._minimize_to_tray()
            return
        self._save_config()
        self.stop()
        if self.macro.is_recording:
            self.macro.stop_recording()
        if self.macro.is_playing:
            self.macro.stop_playback()
        try:
            self._listener.stop()
        except Exception:
            pass
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = AutoClickerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
