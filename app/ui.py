from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, colorchooser, simpledialog
from datetime import datetime
from typing import Callable, List, Optional, Dict, Tuple

from .models import Note, Reminder, AppSettings
from .utils import parse_date_time


# -------------------- helpers --------------------

def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join([c * 2 for c in h])
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

def _lerp_color(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    r = int(_lerp(r1, r2, t))
    g = int(_lerp(g1, g2, t))
    b = int(_lerp(b1, b2, t))
    return _rgb_to_hex(r, g, b)


class RoundedCard(tk.Canvas):
    """
    Canvas con rectángulo redondeado y un Frame interno.
    Permite "bordes redondos" sin librerías externas.
    """
    def __init__(self, master, radius=14, padding=12, **kwargs):
        super().__init__(master, highlightthickness=0, bd=0, **kwargs)
        self.radius = radius
        self.padding = padding
        self._bg = "#FFFFFF"
        self._border = "#E5E7EE"
        self._fill_id = None
        self._border_id = None
        self.inner = tk.Frame(self, bd=0, highlightthickness=0)
        self._win_id = self.create_window((padding, padding), window=self.inner, anchor="nw")
        self.bind("<Configure>", self._on_resize)

    def set_colors(self, bg: str, border: str):
        self._bg = bg
        self._border = border
        self._redraw()

    def _on_resize(self, _e=None):
        self._redraw()

    def _rounded_rect_points(self, x1, y1, x2, y2, r):
        # genera puntos para polygon smooth (aprox)
        # simplificado pero se ve bien
        return [
            x1+r, y1,
            x2-r, y1,
            x2, y1,
            x2, y1+r,
            x2, y2-r,
            x2, y2,
            x2-r, y2,
            x1+r, y2,
            x1, y2,
            x1, y2-r,
            x1, y1+r,
            x1, y1
        ]

    def _redraw(self):
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 2 or h <= 2:
            return

        pad = 2
        r = min(self.radius, (w - 2*pad)//3, (h - 2*pad)//3)
        x1, y1 = pad, pad
        x2, y2 = w - pad, h - pad

        # Fondo redondeado (smooth polygon)
        pts = self._rounded_rect_points(x1, y1, x2, y2, r)
        if self._fill_id is None:
            self._fill_id = self.create_polygon(pts, smooth=True, fill=self._bg, outline="")
        else:
            self.coords(self._fill_id, *pts)
            self.itemconfig(self._fill_id, fill=self._bg)

        # Borde
        if self._border_id is None:
            self._border_id = self.create_polygon(pts, smooth=True, fill="", outline=self._border, width=1)
        else:
            self.coords(self._border_id, *pts)
            self.itemconfig(self._border_id, outline=self._border, width=1)

        # resize frame interno
        inner_w = max(10, w - self.padding*2)
        inner_h = max(10, h - self.padding*2)
        self.itemconfig(self._win_id, width=inner_w, height=inner_h)
        self.coords(self._win_id, self.padding, self.padding)


# -------------------- Dialogs --------------------

class ReminderDialog(tk.Toplevel):
    def __init__(self, master: tk.Tk, note_title: str, palette: Dict[str, str]):
        super().__init__(master)
        self.title("Nuevo recordatorio")
        self.resizable(False, False)
        self.grab_set()
        self.result = None  # (message, due_at, days_before)

        frm = ttk.Frame(self, padding=14)
        frm.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frm, text="Nuevo recordatorio", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )
        ttk.Label(frm, text=f"Nota: {note_title}", foreground=palette["muted"]).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )

        ttk.Label(frm, text="Mensaje:").grid(row=2, column=0, sticky="w")
        self.msg_var = tk.StringVar(value=note_title)
        ttk.Entry(frm, textvariable=self.msg_var, width=44).grid(row=2, column=1, sticky="we", pady=4)

        ttk.Label(frm, text="Fecha (YYYY-MM-DD):").grid(row=3, column=0, sticky="w")
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(frm, textvariable=self.date_var, width=20).grid(row=3, column=1, sticky="w", pady=4)

        ttk.Label(frm, text="Hora (HH:MM):").grid(row=4, column=0, sticky="w")
        self.time_var = tk.StringVar(value="09:00")
        ttk.Entry(frm, textvariable=self.time_var, width=20).grid(row=4, column=1, sticky="w", pady=4)

        ttk.Label(frm, text="Avisar X días antes:").grid(row=5, column=0, sticky="w")
        self.days_var = tk.IntVar(value=2)
        ttk.Spinbox(frm, from_=0, to=365, textvariable=self.days_var, width=6).grid(row=5, column=1, sticky="w", pady=4)

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=2, sticky="e", pady=(14, 0))

        ttk.Button(btns, text="Cancelar", command=self._cancel).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btns, text="Guardar", command=self._ok).grid(row=0, column=1)

        self.bind("<Escape>", lambda e: self._cancel())
        self.bind("<Return>", lambda e: self._ok())

    def _cancel(self):
        self.result = None
        self.destroy()

    def _ok(self):
        msg = self.msg_var.get().strip()
        dt = parse_date_time(self.date_var.get(), self.time_var.get())
        if not msg:
            messagebox.showerror("Error", "El mensaje no puede estar vacío.")
            return
        if dt is None:
            messagebox.showerror("Error", "Fecha/Hora inválida. Usa YYYY-MM-DD y HH:MM.")
            return
        days = int(self.days_var.get())
        if days < 0:
            days = 0
        self.result = (msg, dt, days)
        self.destroy()


class ReminderManager(tk.Toplevel):
    def __init__(
        self,
        master: tk.Tk,
        note_title: str,
        reminders: List[Reminder],
        palette: Dict[str, str],
        on_add: Callable[[], None],
        on_toggle: Callable[[int, bool], None],
        on_delete: Callable[[int], None],
        on_reset: Callable[[int], None],
        on_refresh: Callable[[], List[Reminder]],
    ):
        super().__init__(master)
        self.title(f"Recordatorios — {note_title}")
        self.geometry("760x380")
        self.minsize(680, 320)

        self.on_add = on_add
        self.on_toggle = on_toggle
        self.on_delete = on_delete
        self.on_reset = on_reset
        self.on_refresh = on_refresh

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(1, weight=1)

        top = ttk.Frame(frm)
        top.grid(row=0, column=0, sticky="we")
        ttk.Label(top, text="Recordatorios", font=("Segoe UI", 12, "bold")).pack(side="left")
        ttk.Button(top, text="⏰ Agregar", command=self._add).pack(side="right")

        self.tree = ttk.Treeview(frm, columns=("due", "before", "enabled", "fired", "msg"), show="headings")
        self.tree.grid(row=1, column=0, sticky="nsew", pady=(10, 10))

        self.tree.heading("due", text="Vence")
        self.tree.heading("before", text="Aviso (días)")
        self.tree.heading("enabled", text="Activo")
        self.tree.heading("fired", text="Notificado")
        self.tree.heading("msg", text="Mensaje")

        self.tree.column("due", width=160, anchor="w")
        self.tree.column("before", width=90, anchor="center")
        self.tree.column("enabled", width=70, anchor="center")
        self.tree.column("fired", width=80, anchor="center")
        self.tree.column("msg", width=340, anchor="w")

        bottom = ttk.Frame(frm)
        bottom.grid(row=2, column=0, sticky="e")

        ttk.Button(bottom, text="Activar/Desactivar", command=self._toggle).pack(side="left", padx=4)
        ttk.Button(bottom, text="Reiniciar (volver a notificar)", command=self._reset).pack(side="left", padx=4)
        ttk.Button(bottom, text="Eliminar", command=self._delete).pack(side="left", padx=4)

        self.refresh(reminders)
        self.bind("<FocusIn>", lambda e: self.refresh(self.on_refresh()))

    def refresh(self, reminders: List[Reminder]):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in reminders:
            rid = str(r.id)
            due = r.due_at.strftime("%Y-%m-%d %H:%M")
            enabled = "Sí" if r.enabled else "No"
            fired = "Sí" if r.fired_at else "No"
            self.tree.insert("", "end", iid=rid, values=(due, r.remind_days_before, enabled, fired, r.message))

    def _selected_id(self) -> Optional[int]:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def _add(self):
        self.on_add()
        self.refresh(self.on_refresh())

    def _toggle(self):
        rid = self._selected_id()
        if rid is None:
            return
        values = self.tree.item(str(rid), "values")
        enabled_now = (values[2] == "Sí")
        self.on_toggle(rid, not enabled_now)
        self.refresh(self.on_refresh())

    def _delete(self):
        rid = self._selected_id()
        if rid is None:
            return
        if messagebox.askyesno("Eliminar", "¿Eliminar este recordatorio?"):
            self.on_delete(rid)
            self.refresh(self.on_refresh())

    def _reset(self):
        rid = self._selected_id()
        if rid is None:
            return
        self.on_reset(rid)
        self.refresh(self.on_refresh())


# -------------------- UI --------------------

class UI:
    def __init__(
        self,
        root: tk.Tk,
        settings: AppSettings,

        # notas
        on_new_note: Callable[[], None],
        on_delete_note: Callable[[], None],
        on_duplicate_note: Callable[[], None],
        on_select_note: Callable[[int], None],
        on_sort_title: Callable[[], None],
        on_sort_updated: Callable[[], None],

        # guardar / cambios
        on_note_changed: Callable[[str, str], None],   # title, content
        on_manual_save: Callable[[], None],
        on_save_all: Callable[[], None],

        # estilo
        on_style_changed: Callable[[dict], None],
        on_settings_changed: Callable[[dict], None],

        # recordatorios
        on_add_reminder: Callable[[], None],
        on_toggle_reminder: Callable[[int, bool], None],
        on_delete_reminder: Callable[[int], None],
        on_reset_reminder: Callable[[int], None],
        on_get_reminders: Callable[[], List[Reminder]],

        # backup
        on_export_backup: Callable[[], None],
        on_import_backup: Callable[[], None],
    ):
        self.root = root
        self.settings = settings

        self.on_new_note = on_new_note
        self.on_delete_note = on_delete_note
        self.on_duplicate_note = on_duplicate_note
        self.on_select_note = on_select_note
        self.on_sort_title = on_sort_title
        self.on_sort_updated = on_sort_updated

        self.on_note_changed = on_note_changed
        self.on_manual_save = on_manual_save
        self.on_save_all = on_save_all

        self.on_style_changed = on_style_changed
        self.on_settings_changed = on_settings_changed

        self.on_add_reminder = on_add_reminder
        self.on_toggle_reminder = on_toggle_reminder
        self.on_delete_reminder = on_delete_reminder
        self.on_reset_reminder = on_reset_reminder
        self.on_get_reminders = on_get_reminders

        self.on_export_backup = on_export_backup
        self.on_import_backup = on_import_backup

        self.notes: List[Note] = []
        self.current_note_id: Optional[int] = None

        self._autosave_after_id: Optional[str] = None
        self._ignore_text_event = False
        self._modified = False
        self._updating_list = False

        self._current_note_style: Optional[Note] = None

        # theme
        self._animating = False
        self.palette = self._get_palette(self.settings.theme_mode)

        self._build()

    # ---------------- theme ----------------

    def _get_palette(self, mode: str) -> Dict[str, str]:
        mode = (mode or "light").lower()
        if mode == "dark":
            return {
                "app_bg": "#0F1115",
                "card_bg": "#171A21",
                "border": "#2A2F3B",
                "text": "#F3F4F6",
                "muted": "#A7ABB4",
                "accent": "#6EA8FE",
                "entry_bg": "#12151B",
                "entry_fg": "#F3F4F6",
            }
        return {
            "app_bg": "#F6F7FB",
            "card_bg": "#FFFFFF",
            "border": "#E5E7EE",
            "text": "#101114",
            "muted": "#666A73",
            "accent": "#2F6FED",
            "entry_bg": "#FFFFFF",
            "entry_fg": "#101114",
        }

    def _apply_ttk_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        p = self.palette

        style.configure("App.TFrame", background=p["app_bg"])
        style.configure("Title.TLabel", background=p["app_bg"], foreground=p["text"], font=("Segoe UI", 13, "bold"))
        style.configure("Status.TFrame", background=p["app_bg"])
        style.configure("Status.TLabel", background=p["app_bg"], foreground=p["muted"], font=("Segoe UI", 9))

        style.configure("Card.TFrame", background=p["card_bg"])
        style.configure("TLabel", background=p["card_bg"], foreground=p["text"], font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=p["card_bg"], foreground=p["muted"], font=("Segoe UI", 9))

        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 6))
        style.map(
            "TButton",
            foreground=[("disabled", p["muted"]), ("!disabled", p["text"])],
        )

        style.configure("TEntry", padding=(8, 6), fieldbackground=p["entry_bg"], foreground=p["entry_fg"])
        style.configure("TCheckbutton", background=p["card_bg"], foreground=p["text"])

        style.configure("Notes.Treeview",
                        background=p["card_bg"],
                        fieldbackground=p["card_bg"],
                        foreground=p["text"],
                        rowheight=28,
                        bordercolor=p["border"],
                        borderwidth=1,
                        font=("Segoe UI", 10))
        style.configure("Notes.Treeview.Heading",
                        font=("Segoe UI", 10, "bold"),
                        background=p["card_bg"],
                        foreground=p["text"])

    def _animate_theme_to(self, new_mode: str):
        if self._animating:
            return

        new_mode = "dark" if new_mode == "dark" else "light"
        start = self.palette
        end = self._get_palette(new_mode)

        self._animating = True
        steps = 14
        delay_ms = 18

        def frame(i: int):
            t = i / float(steps)
            self.palette = {
                k: _lerp_color(start[k], end[k], t) if k in start and k in end else end.get(k, start.get(k, "#000000"))
                for k in end.keys()
            }
            self._apply_ttk_style()
            self._apply_theme_to_widgets()

            if i < steps:
                self.root.after(delay_ms, lambda: frame(i + 1))
            else:
                self.palette = end
                self._apply_ttk_style()
                self._apply_theme_to_widgets()
                self._animating = False

        frame(0)

        # persist
        self.settings.theme_mode = new_mode
        self.on_settings_changed({"theme_mode": new_mode})

    def _apply_theme_to_widgets(self):
        p = self.palette
        self.root.configure(bg=p["app_bg"])
        self.container.configure(style="App.TFrame")
        self.topbar.configure(style="App.TFrame")

        # rounded cards
        self.sidebar_card.set_colors(p["card_bg"], p["border"])
        self.editor_card.set_colors(p["card_bg"], p["border"])

        # entries and frames inside cards: set bg for inner frames
        for w in (self.sidebar_card.inner, self.editor_card.inner):
            w.configure(bg=p["card_bg"])

        # Search entry tweaks (ttk entry already)
        # Text editor border/backdrop: keep note background, but set highlight to theme border
        try:
            self.text.configure(highlightbackground=p["border"], highlightcolor=p["border"])
        except Exception:
            pass

        # status
        self.status.configure(style="Status.TFrame")
        self.status_label.configure(style="Status.TLabel")

    # ---------------- Build ----------------

    def _build(self):
        self._apply_ttk_style()

        self.root.title("Transparent Notepad")
        self.root.geometry("1160x740")
        self.root.minsize(980, 600)
        self.root.attributes("-topmost", bool(self.settings.topmost))

        self._build_menu()

        self.container = ttk.Frame(self.root, style="App.TFrame")
        self.container.pack(fill="both", expand=True)

        self._build_topbar(self.container)

        content = ttk.Frame(self.container, style="App.TFrame")
        content.pack(fill="both", expand=True, padx=12, pady=(10, 12))

        paned = ttk.Panedwindow(content, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # Sidebar card
        self.sidebar_card = RoundedCard(paned, radius=16, padding=12, bg=self.palette["app_bg"])
        paned.add(self.sidebar_card, weight=0)

        # Editor card
        self.editor_card = RoundedCard(paned, radius=16, padding=12, bg=self.palette["app_bg"])
        paned.add(self.editor_card, weight=1)

        self._build_sidebar(self.sidebar_card.inner)
        self._build_editor(self.editor_card.inner)

        # Status bar
        self.status = ttk.Frame(self.container, style="Status.TFrame")
        self.status.pack(fill="x")
        self.status_label = ttk.Label(self.status, text="", style="Status.TLabel", anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True, padx=12, pady=6)

        self._apply_statusbar_visibility()

        # Apply palette to cards (after widgets created)
        self.sidebar_card.set_colors(self.palette["card_bg"], self.palette["border"])
        self.editor_card.set_colors(self.palette["card_bg"], self.palette["border"])
        self._apply_theme_to_widgets()

        # Shortcuts
        self.root.bind("<Control-n>", lambda e: self._new_note())
        self.root.bind("<Control-s>", lambda e: self._manual_save())
        self.root.bind("<Control-Shift-S>", lambda e: self.on_save_all())
        self.root.bind("<Control-a>", lambda e: self._select_all())
        self.root.bind("<Control-f>", lambda e: self._find_text())
        self.root.bind("<Control-z>", lambda e: self._safe_event(self.text.edit_undo))
        self.root.bind("<Control-y>", lambda e: self._safe_event(self.text.edit_redo))

        self.root.protocol("WM_DELETE_WINDOW", self.request_exit)

        self._apply_zoom_to_text()
        self._update_statusbar()

    def _build_topbar(self, parent: ttk.Frame):
        self.topbar = ttk.Frame(parent, style="App.TFrame")
        self.topbar.pack(fill="x", padx=12, pady=(12, 0))

        ttk.Label(self.topbar, text="Transparent Notepad", style="Title.TLabel").pack(side="left")

        right = ttk.Frame(self.topbar, style="App.TFrame")
        right.pack(side="right")

        # Theme toggle button
        self.theme_btn = ttk.Button(right, text="🌙" if self.settings.theme_mode == "light" else "☀", command=self._toggle_theme)
        self.theme_btn.pack(side="right", padx=(8, 0))

        self.var_topmost = tk.BooleanVar(value=self.settings.topmost)
        chk = ttk.Checkbutton(right, text="Siempre arriba", variable=self.var_topmost, command=self._toggle_topmost)
        chk.pack(side="right")

    def _toggle_theme(self):
        new_mode = "dark" if self.settings.theme_mode == "light" else "light"
        # update icon immediately for responsiveness
        self.theme_btn.configure(text="☀" if new_mode == "dark" else "🌙")
        self._animate_theme_to(new_mode)

    def _build_sidebar(self, parent: tk.Frame):
        parent.configure(bg=self.palette["card_bg"])

        header = tk.Frame(parent, bg=self.palette["card_bg"])
        header.pack(fill="x")
        tk.Label(header, text="Notas", bg=self.palette["card_bg"], fg=self.palette["text"], font=("Segoe UI", 12, "bold")).pack(anchor="w")

        # Search
        search_row = tk.Frame(parent, bg=self.palette["card_bg"])
        search_row.pack(fill="x", pady=(10, 10))

        ttk.Label(search_row, text="Buscar", style="Muted.TLabel").pack(anchor="w")
        self.search_var = tk.StringVar()
        ent = ttk.Entry(search_row, textvariable=self.search_var)
        ent.pack(fill="x", pady=(6, 0))
        self.search_var.trace_add("write", lambda *_: self._render_note_list())

        # Notes list
        self.note_tree = ttk.Treeview(parent, style="Notes.Treeview", columns=("title",), show="tree", selectmode="browse")
        self.note_tree.pack(fill="both", expand=True)
        self.note_tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Buttons
        btns = tk.Frame(parent, bg=self.palette["card_bg"])
        btns.pack(fill="x", pady=(10, 0))

        ttk.Button(btns, text="＋ Nueva", command=self._new_note).pack(side="left")
        ttk.Button(btns, text="⧉", command=self._duplicate_note).pack(side="left", padx=8)
        ttk.Button(btns, text="🗑 Eliminar", command=self._request_delete_note).pack(side="right")

        sort_row = tk.Frame(parent, bg=self.palette["card_bg"])
        sort_row.pack(fill="x", pady=(10, 0))
        ttk.Button(sort_row, text="Ordenar A-Z", command=self.on_sort_title).pack(side="left")
        ttk.Button(sort_row, text="Recientes", command=self.on_sort_updated).pack(side="left", padx=8)

    def _build_editor(self, parent: tk.Frame):
        parent.configure(bg=self.palette["card_bg"])

        ttk.Label(parent, text="Título", style="Muted.TLabel").pack(anchor="w")
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(parent, textvariable=self.title_var)
        self.title_entry.pack(fill="x", pady=(6, 10))
        self.title_var.trace_add("write", lambda *_: self._mark_modified_and_schedule())

        # Toolbar
        tools = tk.Frame(parent, bg=self.palette["card_bg"])
        tools.pack(fill="x", pady=(0, 10))

        ttk.Button(tools, text="Guardar (Ctrl+S)", command=self._manual_save).pack(side="left")
        ttk.Button(tools, text="Recordatorios", command=self._open_reminders_manager).pack(side="left", padx=8)

        ttk.Button(tools, text="Fuente", command=self._font_dialog).pack(side="right")
        ttk.Button(tools, text="Fondo", command=self._bg_color_dialog).pack(side="right", padx=8)
        ttk.Button(tools, text="Texto", command=self._text_color_dialog).pack(side="right")

        # Rounded editor box
        self.editor_box = RoundedCard(parent, radius=14, padding=10, bg=self.palette["card_bg"])
        self.editor_box.pack(fill="both", expand=True)
        self.editor_box.set_colors(self.palette["entry_bg"], self.palette["border"])
        self.editor_box.inner.configure(bg=self.palette["entry_bg"])

        # Text widget inside rounded editor
        self.text = tk.Text(
            self.editor_box.inner,
            undo=True,
            wrap="word" if self.settings.word_wrap else "none",
            relief="flat",
            highlightthickness=0,
            bd=0,
            padx=10,
            pady=10,
        )
        self.text.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(self.editor_box.inner, orient="vertical", command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sb.set)

        self.text.bind("<<Modified>>", self._on_text_modified)
        self.text.bind("<KeyRelease>", lambda e: self._update_statusbar())
        self.text.bind("<ButtonRelease>", lambda e: self._update_statusbar())

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        m_file = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=m_file)
        m_file.add_command(label="Nueva nota\tCtrl+N", command=self._new_note)
        m_file.add_command(label="Guardar\tCtrl+S", command=self._manual_save)
        m_file.add_command(label="Guardar todo\tCtrl+Shift+S", command=self.on_save_all)
        m_file.add_separator()
        m_file.add_command(label="Exportar backup (.bplus)", command=self.on_export_backup)
        m_file.add_command(label="Importar backup (.bplus)", command=self.on_import_backup)
        m_file.add_separator()
        m_file.add_command(label="Salir", command=self.request_exit)

        m_edit = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edición", menu=m_edit)
        m_edit.add_command(label="Deshacer\tCtrl+Z", command=lambda: self._safe_event(self.text.edit_undo))
        m_edit.add_command(label="Rehacer\tCtrl+Y", command=lambda: self._safe_event(self.text.edit_redo))
        m_edit.add_separator()
        m_edit.add_command(label="Cortar\tCtrl+X", command=lambda: self._safe_event(lambda: self.root.focus_get().event_generate("<<Cut>>")))
        m_edit.add_command(label="Copiar\tCtrl+C", command=lambda: self._safe_event(lambda: self.root.focus_get().event_generate("<<Copy>>")))
        m_edit.add_command(label="Pegar\tCtrl+V", command=lambda: self._safe_event(lambda: self.root.focus_get().event_generate("<<Paste>>")))
        m_edit.add_separator()
        m_edit.add_command(label="Buscar...\tCtrl+F", command=self._find_text)
        m_edit.add_command(label="Seleccionar todo\tCtrl+A", command=self._select_all)

        m_view = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ver", menu=m_view)

        self.var_word_wrap = tk.BooleanVar(value=self.settings.word_wrap)
        self.var_statusbar = tk.BooleanVar(value=self.settings.show_statusbar)
        self.var_topmost_menu = tk.BooleanVar(value=self.settings.topmost)

        m_view.add_checkbutton(label="Ajuste de línea (Word Wrap)", variable=self.var_word_wrap, command=self._toggle_word_wrap)
        m_view.add_checkbutton(label="Barra de estado", variable=self.var_statusbar, command=self._toggle_statusbar)
        m_view.add_separator()
        m_view.add_checkbutton(label="Siempre arriba", variable=self.var_topmost_menu, command=self._toggle_topmost_from_menu)
        m_view.add_separator()
        m_view.add_command(label="Modo Oscuro/Claro", command=self._toggle_theme)
        m_view.add_separator()
        m_view.add_command(label="Zoom +", command=lambda: self._zoom_change(+10))
        m_view.add_command(label="Zoom -", command=lambda: self._zoom_change(-10))
        m_view.add_command(label="Zoom 100%", command=lambda: self._zoom_set(100))

        m_help = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=m_help)
        m_help.add_command(label="Acerca de", command=lambda: messagebox.showinfo("Acerca de", "Transparent Notepad\nModo claro/oscuro + UI pro (Tkinter)"))

    # ---------------- Public API ----------------

    def set_notes(self, notes: List[Note], select_note_id: Optional[int] = None):
        self.notes = notes
        self._render_note_list(select_note_id=select_note_id)

    def show_note(self, note: Note):
        self.current_note_id = note.id
        self._current_note_style = note

        self._ignore_text_event = True
        self.title_var.set(note.title)

        # IMPORTANTE: no recargar por autosave (esto se llama sólo en cambio real de nota)
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", note.content)

        self._apply_note_style(note)

        self.text.edit_modified(False)
        self._ignore_text_event = False

        self._modified = False
        self._update_window_title(note.title)
        self._update_statusbar()

    def show_info(self, msg: str):
        messagebox.showinfo("Info", msg)

    def show_error(self, msg: str):
        messagebox.showerror("Error", msg)

    def open_add_reminder_dialog(self, note_title: str):
        dlg = ReminderDialog(self.root, note_title, self.palette)
        self.root.wait_window(dlg)
        return dlg.result

    # ---------------- Confirmations ----------------

    def has_unsaved_changes(self) -> bool:
        return bool(self._modified)

    def request_exit(self):
        if self.has_unsaved_changes():
            ok = messagebox.askyesno("Salir", "Tienes cambios sin guardar.\n\n¿Seguro que deseas salir?")
            if not ok:
                return

        # guardado final si hay autosave pendiente
        try:
            if self._autosave_after_id:
                self.root.after_cancel(self._autosave_after_id)
                self._autosave_after_id = None
            if self.current_note_id is not None:
                self._do_autosave()
        except Exception:
            pass

        self.root.quit()

    def _request_delete_note(self):
        if self.current_note_id is None:
            return

        note = next((n for n in self.notes if n.id == self.current_note_id), None)
        title = (note.title if note else "esta nota")

        if self.has_unsaved_changes():
            res = messagebox.askyesnocancel(
                "Eliminar nota",
                f"Tienes cambios sin guardar en \"{title}\".\n\n¿Guardar antes de borrar?"
            )
            if res is None:
                return
            if res is True:
                self._manual_save()
                if self.has_unsaved_changes():
                    return
            # False -> borrar sin guardar
        else:
            ok = messagebox.askyesno("Eliminar nota", f"¿Seguro que deseas borrar \"{title}\"?")
            if not ok:
                return

        self.on_delete_note()

    def _confirm_before_switch_note(self) -> bool:
        if not self.has_unsaved_changes():
            return True

        res = messagebox.askyesnocancel(
            "Cambios sin guardar",
            "Tienes cambios sin guardar.\n\n¿Guardar antes de cambiar de nota?"
        )
        if res is None:
            return False
        if res is True:
            self._manual_save()
            return not self.has_unsaved_changes()

        # No -> descartar (al cambiar de nota se reemplaza contenido)
        self._modified = False
        self._update_window_title(self.title_var.get().strip() or "Sin título")
        self._update_statusbar()
        return True

    # ---------------- Sidebar render ----------------

    def _render_note_list(self, select_note_id: Optional[int] = None):
        if self._updating_list:
            return

        self._updating_list = True
        try:
            q = self.search_var.get().strip().lower()

            keep_id = select_note_id if select_note_id is not None else self.current_note_id

            for i in self.note_tree.get_children():
                self.note_tree.delete(i)

            for n in self.notes:
                if q and (q not in n.title.lower() and q not in n.content.lower()):
                    continue
                iid = str(n.id)
                display = n.title if n.title else "Sin título"
                self.note_tree.insert("", "end", iid=iid, text=display)

            if keep_id is not None:
                iid = str(keep_id)
                if iid in self.note_tree.get_children(""):
                    self.note_tree.selection_set(iid)
                    self.note_tree.see(iid)
        finally:
            self._updating_list = False

    # ---------------- Events ----------------

    def _on_tree_select(self, _evt):
        if self._updating_list:
            return
        sel = self.note_tree.selection()
        if not sel:
            return
        try:
            note_id = int(sel[0])
        except ValueError:
            return

        if self.current_note_id == note_id:
            return

        if not self._confirm_before_switch_note():
            if self.current_note_id is not None:
                self._updating_list = True
                try:
                    self.note_tree.selection_set(str(self.current_note_id))
                    self.note_tree.see(str(self.current_note_id))
                finally:
                    self._updating_list = False
            return

        self.on_select_note(note_id)

    # ---------------- Commands wrappers ----------------

    def _new_note(self):
        if not self._confirm_before_switch_note():
            return
        self.on_new_note()

    def _duplicate_note(self):
        if not self._confirm_before_switch_note():
            return
        self.on_duplicate_note()

    # ---------------- Settings ----------------

    def _toggle_topmost(self):
        self.settings.topmost = bool(self.var_topmost.get())
        self.root.attributes("-topmost", self.settings.topmost)
        self.var_topmost_menu.set(self.settings.topmost)
        self.on_settings_changed({"topmost": self.settings.topmost})

    def _toggle_topmost_from_menu(self):
        self.settings.topmost = bool(self.var_topmost_menu.get())
        self.root.attributes("-topmost", self.settings.topmost)
        self.var_topmost.set(self.settings.topmost)
        self.on_settings_changed({"topmost": self.settings.topmost})

    def _toggle_word_wrap(self):
        self.settings.word_wrap = bool(self.var_word_wrap.get())
        self.on_settings_changed({"word_wrap": self.settings.word_wrap})
        if self._current_note_style:
            self._apply_note_style(self._current_note_style)

    def _toggle_statusbar(self):
        self.settings.show_statusbar = bool(self.var_statusbar.get())
        self.on_settings_changed({"show_statusbar": self.settings.show_statusbar})
        self._apply_statusbar_visibility()

    def _zoom_change(self, delta: int):
        self._zoom_set(self.settings.zoom_percent + delta)

    def _zoom_set(self, value: int):
        value = int(max(50, min(500, value)))
        self.settings.zoom_percent = value
        self.on_settings_changed({"zoom_percent": value})
        self._apply_zoom_to_text()

    def _apply_zoom_to_text(self):
        if self._current_note_style:
            self._apply_note_style(self._current_note_style)
        self._update_statusbar()

    # ---------------- Note style ----------------

    def _apply_note_style(self, note: Note):
        self._current_note_style = note

        base = max(6, int(note.font_size))
        zoom = max(50, min(500, int(self.settings.zoom_percent)))
        size = int(base * (zoom / 100.0))

        # Fondo del texto (sin alpha real en Tk)
        self.text.configure(
            fg=note.text_color,
            bg=note.bg_color,
            insertbackground=note.text_color,
            font=(note.font_family, size),
            wrap="word" if self.settings.word_wrap else "none",
        )

    def _font_dialog(self):
        if self.current_note_id is None:
            return
        family = simpledialog.askstring("Fuente", "Familia de fuente (ej: Consolas, Arial):", initialvalue="Consolas")
        if not family:
            return
        size = simpledialog.askinteger("Tamaño", "Tamaño base (ej: 12):", initialvalue=12, minvalue=6, maxvalue=72)
        if not size:
            return
        self.on_style_changed({"font_family": family.strip(), "font_size": int(size)})
        self._mark_modified_and_schedule()

    def _text_color_dialog(self):
        c = colorchooser.askcolor(title="Color de texto")
        if c and c[1]:
            self.on_style_changed({"text_color": c[1]})
            self._mark_modified_and_schedule()

    def _bg_color_dialog(self):
        c = colorchooser.askcolor(title="Color de fondo")
        if c and c[1]:
            self.on_style_changed({"bg_color": c[1]})
            self._mark_modified_and_schedule()

    # ---------------- Saving + Text bugfix ----------------

    def _on_text_modified(self, _evt):
        if self._ignore_text_event:
            self.text.edit_modified(False)
            return
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self._mark_modified_and_schedule()
            self._update_statusbar()

    def _mark_modified_and_schedule(self):
        if self.current_note_id is None:
            return
        self._modified = True
        self._update_window_title(self.title_var.get().strip() or "Sin título")
        self._schedule_autosave()

    def _schedule_autosave(self):
        if not self.settings.always_save:
            return
        if self.current_note_id is None:
            return
        if self._autosave_after_id:
            try:
                self.root.after_cancel(self._autosave_after_id)
            except Exception:
                pass
        self._autosave_after_id = self.root.after(700, self._do_autosave)

    def _get_editor_text(self) -> str:
        # end-1c = no elimina espacios ni líneas extra del usuario, solo el newline final implícito
        return self.text.get("1.0", "end-1c")

    def _do_autosave(self):
        self._autosave_after_id = None
        if self.current_note_id is None:
            return
        title = self.title_var.get().strip() or "Sin título"
        content = self._get_editor_text()

        try:
            self.on_note_changed(title, content)
            self._modified = False
            self._update_window_title(title)
            self._update_statusbar()
        except Exception:
            self._modified = True
            self._update_window_title(title)
            self._update_statusbar()

    def _manual_save(self):
        if self.current_note_id is None:
            return

        if self._autosave_after_id:
            try:
                self.root.after_cancel(self._autosave_after_id)
            except Exception:
                pass
            self._autosave_after_id = None

        title = self.title_var.get().strip() or "Sin título"
        content = self._get_editor_text()

        try:
            self.on_note_changed(title, content)
            self.on_manual_save()
            self._modified = False
            self._update_window_title(title)
            self._update_statusbar()
        except Exception:
            self._modified = True
            self._update_window_title(title)
            self._update_statusbar()

    # ---------------- Reminders ----------------

    def _open_reminders_manager(self):
        if self.current_note_id is None:
            self.show_error("Selecciona una nota primero.")
            return
        note = next((n for n in self.notes if n.id == self.current_note_id), None)
        if not note:
            return

        ReminderManager(
            self.root,
            note_title=note.title,
            reminders=self.on_get_reminders(),
            palette=self.palette,
            on_add=self.on_add_reminder,
            on_toggle=self.on_toggle_reminder,
            on_delete=self.on_delete_reminder,
            on_reset=self.on_reset_reminder,
            on_refresh=self.on_get_reminders,
        )

    # ---------------- Statusbar & helpers ----------------

    def _apply_statusbar_visibility(self):
        if self.settings.show_statusbar:
            self.status.pack(fill="x")
        else:
            self.status.pack_forget()

    def _update_window_title(self, note_title: str):
        star = " •" if self._modified else ""
        self.root.title(f"{note_title}{star} — Transparent Notepad")

    def _update_statusbar(self):
        if not self.settings.show_statusbar:
            return
        try:
            index = self.text.index(tk.INSERT)
            line, col = index.split(".")
            zoom = self.settings.zoom_percent
            wrap = "Wrap" if self.settings.word_wrap else "No Wrap"
            mod = "Sin guardar" if self._modified else "Guardado"
            self.status_label.configure(text=f"Línea {line}, Col {int(col)+1}   |   {wrap}   |   Zoom {zoom}%   |   {mod}")
        except Exception:
            pass

    def _safe_event(self, fn):
        try:
            fn()
        except Exception:
            pass

    def _select_all(self):
        self.text.tag_add("sel", "1.0", "end")

    def _find_text(self):
        needle = simpledialog.askstring("Buscar", "Buscar:")
        if not needle:
            return
        self.text.tag_remove("found", "1.0", "end")
        start = "1.0"
        while True:
            pos = self.text.search(needle, start, stopindex="end", nocase=True)
            if not pos:
                break
            end = f"{pos}+{len(needle)}c"
            self.text.tag_add("found", pos, end)
            start = end
        self.text.tag_config("found", underline=True)
        first = self.text.search(needle, "1.0", stopindex="end", nocase=True)
        if first:
            self.text.mark_set(tk.INSERT, first)
            self.text.see(first)
