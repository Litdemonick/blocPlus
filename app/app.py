from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from typing import Optional, List

from .models import Note, Reminder
from .storage import Storage
from .reminders import ReminderService
from .ui import UI
from .backup import build_backup_payload, write_bplus, read_bplus, payload_to_objects


class TransparentNotepadApp:
    def __init__(self):
        self.root = tk.Tk()

        data_dir = Path.home() / ".transparent_notepad"
        data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = data_dir / "notes.db"

        self.storage = Storage(self.db_path)
        self.settings = self.storage.load_settings()

        self.current_note: Optional[Note] = None

        self.ui = UI(
            root=self.root,
            settings=self.settings,

            # notas
            on_new_note=self.new_note,
            on_delete_note=self.delete_note,
            on_duplicate_note=self.duplicate_note,
            on_select_note=self.select_note,
            on_sort_title=self.sort_title,
            on_sort_updated=self.sort_updated,

            # guardar / cambios
            on_note_changed=self.note_changed,
            on_manual_save=self.manual_save_hook,
            on_save_all=self.save_all,

            # estilo
            on_style_changed=self.style_changed,
            on_settings_changed=self.settings_changed,

            # recordatorios
            on_add_reminder=self.add_reminder,
            on_toggle_reminder=self.toggle_reminder,
            on_delete_reminder=self.delete_reminder,
            on_reset_reminder=self.reset_reminder,
            on_get_reminders=self.get_current_note_reminders,

            # backup
            on_export_backup=self.export_backup,
            on_import_backup=self.import_backup,
        )

        self.reminder_service = ReminderService(self.storage, on_fire=None)
        self.refresh_notes(select_first=True)
        self.reminder_service.start(self.root.after)

    def run(self):
        self.root.mainloop()
        self.on_close()

    def on_close(self):
        try:
            self.storage.save_settings(self.settings)
        finally:
            self.storage.close()
            try:
                self.root.destroy()
            except Exception:
                pass

    # -------------------- Notes --------------------
    def refresh_notes(self, select_first: bool = False, select_note_id: Optional[int] = None):
        notes = self.storage.list_notes()

        if select_note_id is None and select_first and notes:
            select_note_id = notes[0].id

        self.ui.set_notes(notes, select_note_id=select_note_id)

        if select_note_id is not None:
            self.select_note(select_note_id)
        elif not notes:
            self.current_note = None

    def new_note(self):
        n = self.storage.create_note("Nueva nota", "")
        self.refresh_notes(select_note_id=n.id)

    def delete_note(self):
        # UI ya confirmó
        if not self.current_note or self.current_note.id is None:
            return
        self.storage.delete_note(self.current_note.id)
        self.refresh_notes(select_first=True)

    def duplicate_note(self):
        if not self.current_note or self.current_note.id is None:
            return
        new_note = self.storage.duplicate_note(self.current_note.id)
        if new_note:
            self.refresh_notes(select_note_id=new_note.id)

    def sort_title(self):
        self.storage.reorder_by_title()
        nid = self.current_note.id if self.current_note else None
        self.refresh_notes(select_note_id=nid)

    def sort_updated(self):
        self.storage.reorder_by_updated()
        nid = self.current_note.id if self.current_note else None
        self.refresh_notes(select_note_id=nid)

    def select_note(self, note_id: int):
        notes = self.storage.list_notes()
        note = next((n for n in notes if n.id == note_id), None)
        if not note:
            return
        self.current_note = note
        self.ui.show_note(note)

    def note_changed(self, title: str, content: str):
        """
        BUGFIX CLAVE:
        Antes refrescabas y volvías a cargar la nota -> movía el cursor.
        Ahora: actualiza DB y refresca SOLO la lista, sin recargar el editor.
        """
        if not self.current_note or self.current_note.id is None:
            return

        self.current_note.title = title.strip() if title.strip() else "Sin título"
        self.current_note.content = content
        self.storage.update_note(self.current_note)

        # refrescar lista sin re-cargar editor:
        notes = self.storage.list_notes()
        self.ui.set_notes(notes, select_note_id=self.current_note.id)

    def manual_save_hook(self):
        return

    def save_all(self):
        if self.current_note and self.current_note.id is not None:
            self.storage.update_note(self.current_note)
        self.ui.show_info("Guardar todo ✅")

    # -------------------- Style & Settings --------------------
    def style_changed(self, style: dict):
        if not self.current_note or self.current_note.id is None:
            return
        if "text_color" in style:
            self.current_note.text_color = style["text_color"]
        if "bg_color" in style:
            self.current_note.bg_color = style["bg_color"]
        if "font_family" in style:
            self.current_note.font_family = style["font_family"]
        if "font_size" in style:
            self.current_note.font_size = int(style["font_size"])

        self.storage.update_note(self.current_note)
        # re-aplica estilos en editor sin re-cargar (safe)
        self.select_note(self.current_note.id)

    def settings_changed(self, changes: dict):
        if "topmost" in changes:
            self.settings.topmost = bool(changes["topmost"])
        if "word_wrap" in changes:
            self.settings.word_wrap = bool(changes["word_wrap"])
        if "zoom_percent" in changes:
            self.settings.zoom_percent = int(changes["zoom_percent"])
        if "show_statusbar" in changes:
            self.settings.show_statusbar = bool(changes["show_statusbar"])
        if "theme_mode" in changes:
            self.settings.theme_mode = str(changes["theme_mode"]).strip().lower()

        self.storage.save_settings(self.settings)

        if self.current_note and self.current_note.id is not None:
            # no recargar si no hace falta, pero sí re-aplicar wrap/zoom:
            self.select_note(self.current_note.id)

    # -------------------- Reminders --------------------
    def get_current_note_reminders(self) -> List[Reminder]:
        if not self.current_note or self.current_note.id is None:
            return []
        return self.storage.list_reminders_for_note(self.current_note.id)

    def add_reminder(self):
        if not self.current_note or self.current_note.id is None:
            return
        res = self.ui.open_add_reminder_dialog(self.current_note.title)
        if res is None:
            return
        msg, due_at, days_before = res
        self.storage.create_reminder(self.current_note.id, msg, due_at, days_before)

    def toggle_reminder(self, reminder_id: int, enabled: bool):
        self.storage.set_reminder_enabled(reminder_id, enabled)

    def delete_reminder(self, reminder_id: int):
        self.storage.delete_reminder(reminder_id)

    def reset_reminder(self, reminder_id: int):
        self.storage.reset_reminder_fired(reminder_id)

    # -------------------- Backup (.bplus) --------------------
    def export_backup(self):
        path = filedialog.asksaveasfilename(
            title="Exportar backup",
            defaultextension=".bplus",
            filetypes=[("Backup Plus", "*.bplus")]
        )
        if not path:
            return

        settings, notes, reminders = self.storage.export_snapshot()
        payload = build_backup_payload(settings, notes, reminders)
        write_bplus(Path(path), payload)
        self.ui.show_info("Backup exportado correctamente ✅")

    def import_backup(self):
        path = filedialog.askopenfilename(
            title="Importar backup",
            filetypes=[("Backup Plus", "*.bplus")]
        )
        if not path:
            return

        if not messagebox.askyesno(
            "Importar backup",
            "Esto REEMPLAZARÁ todas tus notas actuales.\n\n¿Seguro que deseas continuar?"
        ):
            return

        payload = read_bplus(Path(path))
        settings, notes, reminders = payload_to_objects(payload)

        self.storage.import_snapshot_replace(settings, notes, reminders)
        self.settings = self.storage.load_settings()
        self.root.attributes("-topmost", bool(self.settings.topmost))

        self.refresh_notes(select_first=True)
        self.ui.show_info("Backup importado correctamente ✅")
