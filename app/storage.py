from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple

from .models import Note, Reminder, AppSettings

def _dt_to_str(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")

def _str_to_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)

class Storage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self._init_db()

    def close(self):
        self.conn.close()

    def _init_db(self):
        cur = self.conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            sort_index INTEGER NOT NULL,
            text_color TEXT NOT NULL,
            bg_color TEXT NOT NULL,
            font_family TEXT NOT NULL,
            font_size INTEGER NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            due_at TEXT NOT NULL,
            remind_days_before INTEGER NOT NULL,
            enabled INTEGER NOT NULL,
            fired_at TEXT,
            FOREIGN KEY(note_id) REFERENCES notes(id) ON DELETE CASCADE
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """)

        self.conn.commit()

    # -------------------- SETTINGS --------------------
    def load_settings(self) -> AppSettings:
        cur = self.conn.cursor()
        cur.execute("SELECT key, value FROM settings")
        rows = cur.fetchall()
        kv = {r["key"]: r["value"] for r in rows}

        def get_bool(key: str, default: bool) -> bool:
            v = kv.get(key)
            if v is None:
                return default
            return v.lower() in ("1", "true", "yes", "y", "on")

        def get_float(key: str, default: float) -> float:
            v = kv.get(key)
            if v is None:
                return default
            try:
                return float(v)
            except ValueError:
                return default

        def get_int(key: str, default: int) -> int:
            v = kv.get(key)
            if v is None:
                return default
            try:
                return int(v)
            except ValueError:
                return default

        theme_mode = kv.get("theme_mode", "light").strip().lower()
        if theme_mode not in ("light", "dark"):
            theme_mode = "light"

        return AppSettings(
            window_alpha=get_float("window_alpha", 1.0),  # compat
            topmost=get_bool("topmost", False),
            always_save=get_bool("always_save", True),
            word_wrap=get_bool("word_wrap", True),
            zoom_percent=get_int("zoom_percent", 100),
            show_statusbar=get_bool("show_statusbar", True),
            theme_mode=theme_mode,
        )

    def save_settings(self, settings: AppSettings) -> None:
        cur = self.conn.cursor()
        data = {
            "window_alpha": str(getattr(settings, "window_alpha", 1.0)),  # compat
            "topmost": "1" if settings.topmost else "0",
            "always_save": "1" if settings.always_save else "0",
            "word_wrap": "1" if settings.word_wrap else "0",
            "zoom_percent": str(int(settings.zoom_percent)),
            "show_statusbar": "1" if settings.show_statusbar else "0",
            "theme_mode": (settings.theme_mode or "light").strip().lower(),
        }
        if data["theme_mode"] not in ("light", "dark"):
            data["theme_mode"] = "light"

        for k, v in data.items():
            cur.execute("""
                INSERT INTO settings(key, value)
                VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """, (k, v))
        self.conn.commit()

    # -------------------- NOTES --------------------
    def list_notes(self) -> List[Note]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM notes ORDER BY sort_index ASC, updated_at DESC")
        rows = cur.fetchall()
        notes: List[Note] = []
        for r in rows:
            notes.append(Note(
                id=r["id"],
                title=r["title"],
                content=r["content"],
                created_at=_str_to_dt(r["created_at"]),
                updated_at=_str_to_dt(r["updated_at"]),
                sort_index=int(r["sort_index"]),
                text_color=r["text_color"],
                bg_color=r["bg_color"],
                font_family=r["font_family"],
                font_size=int(r["font_size"]),
            ))
        return notes

    def _next_sort_index(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COALESCE(MAX(sort_index), -1) AS m FROM notes")
        m = cur.fetchone()["m"]
        return int(m) + 1

    def create_note(self, title: str = "Nueva nota", content: str = "") -> Note:
        now = datetime.now()
        sort_index = self._next_sort_index()
        note = Note(
            id=None,
            title=title,
            content=content,
            created_at=now,
            updated_at=now,
            sort_index=sort_index
        )
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO notes(title, content, created_at, updated_at, sort_index, text_color, bg_color, font_family, font_size)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            note.title, note.content, _dt_to_str(note.created_at), _dt_to_str(note.updated_at),
            note.sort_index, note.text_color, note.bg_color, note.font_family, note.font_size
        ))
        note.id = cur.lastrowid
        self.conn.commit()
        return note

    def update_note(self, note: Note) -> None:
        if note.id is None:
            return
        note.updated_at = datetime.now()
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE notes
            SET title=?, content=?, updated_at=?, sort_index=?, text_color=?, bg_color=?, font_family=?, font_size=?
            WHERE id=?
        """, (
            note.title, note.content, _dt_to_str(note.updated_at), note.sort_index,
            note.text_color, note.bg_color, note.font_family, note.font_size,
            note.id
        ))
        self.conn.commit()

    def delete_note(self, note_id: int) -> None:
        cur = self.conn.cursor()
        cur.execute("DELETE FROM notes WHERE id=?", (note_id,))
        self.conn.commit()

    def duplicate_note(self, note_id: int) -> Optional[Note]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM notes WHERE id=?", (note_id,))
        r = cur.fetchone()
        if not r:
            return None
        now = datetime.now()
        sort_index = self._next_sort_index()
        title = f"{r['title']} (copia)"
        content = r["content"]
        cur.execute("""
            INSERT INTO notes(title, content, created_at, updated_at, sort_index, text_color, bg_color, font_family, font_size)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title, content, _dt_to_str(now), _dt_to_str(now), sort_index,
            r["text_color"], r["bg_color"], r["font_family"], int(r["font_size"])
        ))
        new_id = cur.lastrowid
        self.conn.commit()
        return Note(
            id=new_id,
            title=title,
            content=content,
            created_at=now,
            updated_at=now,
            sort_index=sort_index,
            text_color=r["text_color"],
            bg_color=r["bg_color"],
            font_family=r["font_family"],
            font_size=int(r["font_size"]),
        )

    def reorder_by_title(self) -> None:
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM notes ORDER BY LOWER(title) ASC")
        ids = [r["id"] for r in cur.fetchall()]
        for i, nid in enumerate(ids):
            cur.execute("UPDATE notes SET sort_index=? WHERE id=?", (i, nid))
        self.conn.commit()

    def reorder_by_updated(self) -> None:
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM notes ORDER BY updated_at DESC")
        ids = [r["id"] for r in cur.fetchall()]
        for i, nid in enumerate(ids):
            cur.execute("UPDATE notes SET sort_index=? WHERE id=?", (i, nid))
        self.conn.commit()

    # -------------------- REMINDERS --------------------
    def list_reminders_for_note(self, note_id: int) -> List[Reminder]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM reminders WHERE note_id=? ORDER BY due_at ASC", (note_id,))
        rows = cur.fetchall()
        out: List[Reminder] = []
        for r in rows:
            out.append(Reminder(
                id=r["id"],
                note_id=r["note_id"],
                message=r["message"],
                due_at=_str_to_dt(r["due_at"]),
                remind_days_before=int(r["remind_days_before"]),
                enabled=bool(int(r["enabled"])),
                fired_at=_str_to_dt(r["fired_at"]) if r["fired_at"] else None,
            ))
        return out

    def list_all_reminders(self) -> List[Reminder]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM reminders ORDER BY due_at ASC")
        rows = cur.fetchall()
        out: List[Reminder] = []
        for r in rows:
            out.append(Reminder(
                id=r["id"],
                note_id=r["note_id"],
                message=r["message"],
                due_at=_str_to_dt(r["due_at"]),
                remind_days_before=int(r["remind_days_before"]),
                enabled=bool(int(r["enabled"])),
                fired_at=_str_to_dt(r["fired_at"]) if r["fired_at"] else None,
            ))
        return out

    def create_reminder(self, note_id: int, message: str, due_at: datetime, remind_days_before: int) -> Reminder:
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO reminders(note_id, message, due_at, remind_days_before, enabled, fired_at)
            VALUES(?, ?, ?, ?, 1, NULL)
        """, (note_id, message, _dt_to_str(due_at), int(remind_days_before)))
        rid = cur.lastrowid
        self.conn.commit()
        return Reminder(
            id=rid, note_id=note_id, message=message, due_at=due_at,
            remind_days_before=int(remind_days_before), enabled=True, fired_at=None
        )

    def set_reminder_enabled(self, reminder_id: int, enabled: bool) -> None:
        cur = self.conn.cursor()
        cur.execute("UPDATE reminders SET enabled=? WHERE id=?", ("1" if enabled else "0", reminder_id))
        self.conn.commit()

    def delete_reminder(self, reminder_id: int) -> None:
        cur = self.conn.cursor()
        cur.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
        self.conn.commit()

    def mark_reminder_fired(self, reminder_id: int, fired_at: datetime) -> None:
        cur = self.conn.cursor()
        cur.execute("UPDATE reminders SET fired_at=? WHERE id=?", (_dt_to_str(fired_at), reminder_id))
        self.conn.commit()

    def reset_reminder_fired(self, reminder_id: int) -> None:
        cur = self.conn.cursor()
        cur.execute("UPDATE reminders SET fired_at=NULL WHERE id=?", (reminder_id,))
        self.conn.commit()

    def list_due_reminders_to_fire(self, now_dt: datetime) -> List[Tuple[Reminder, datetime]]:
        from datetime import timedelta
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM reminders WHERE enabled=1 AND fired_at IS NULL")
        rows = cur.fetchall()

        due_list: List[Tuple[Reminder, datetime]] = []
        for r in rows:
            rem = Reminder(
                id=r["id"],
                note_id=r["note_id"],
                message=r["message"],
                due_at=_str_to_dt(r["due_at"]),
                remind_days_before=int(r["remind_days_before"]),
                enabled=True,
                fired_at=None,
            )
            notify_at = rem.due_at - timedelta(days=rem.remind_days_before)
            if now_dt >= notify_at:
                due_list.append((rem, notify_at))
        return due_list

    # -------------------- EXPORT/IMPORT SNAPSHOT --------------------
    def export_snapshot(self) -> tuple[AppSettings, List[Note], List[Reminder]]:
        settings = self.load_settings()
        notes = self.list_notes()
        reminders = self.list_all_reminders()
        return settings, notes, reminders

    def import_snapshot_replace(self, settings: AppSettings, notes: List[Note], reminders: List[Reminder]) -> None:
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")

            cur.execute("DELETE FROM reminders")
            cur.execute("DELETE FROM notes")
            cur.execute("DELETE FROM settings")

            settings_kv = {
                "window_alpha": str(getattr(settings, "window_alpha", 1.0)),  # compat
                "topmost": "1" if settings.topmost else "0",
                "always_save": "1" if settings.always_save else "0",
                "word_wrap": "1" if settings.word_wrap else "0",
                "zoom_percent": str(int(settings.zoom_percent)),
                "show_statusbar": "1" if settings.show_statusbar else "0",
                "theme_mode": (settings.theme_mode or "light").strip().lower(),
            }
            if settings_kv["theme_mode"] not in ("light", "dark"):
                settings_kv["theme_mode"] = "light"

            for k, v in settings_kv.items():
                cur.execute("INSERT INTO settings(key, value) VALUES(?, ?)", (k, v))

            for n in notes:
                cur.execute("""
                    INSERT INTO notes(id, title, content, created_at, updated_at, sort_index, text_color, bg_color, font_family, font_size)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    n.id, n.title, n.content, _dt_to_str(n.created_at), _dt_to_str(n.updated_at),
                    int(n.sort_index), n.text_color, n.bg_color, n.font_family, int(n.font_size)
                ))

            for r in reminders:
                cur.execute("""
                    INSERT INTO reminders(id, note_id, message, due_at, remind_days_before, enabled, fired_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.id, int(r.note_id), r.message, _dt_to_str(r.due_at), int(r.remind_days_before),
                    1 if r.enabled else 0,
                    _dt_to_str(r.fired_at) if r.fired_at else None
                ))

            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
