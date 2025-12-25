from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from .storage import Storage
from .utils import now_local

try:
    from winotify import Notification, audio
    _HAS_TOAST = True
except Exception:
    _HAS_TOAST = False

@dataclass
class ReminderFireEvent:
    reminder_id: int
    note_id: int
    message: str
    due_at: datetime
    notify_at: datetime

class ReminderService:
    """
    Revisa periódicamente la DB y dispara recordatorios pendientes.
    Se integra con Tkinter mediante callbacks (after()) desde la UI.
    """
    def __init__(self, storage: Storage, on_fire: Optional[Callable[[ReminderFireEvent], None]] = None):
        self.storage = storage
        self.on_fire = on_fire
        self._running = False
        self._interval_ms = 30_000  # 30s

    def start(self, tk_after: Callable[[int, Callable[[], None]], None]) -> None:
        self._running = True
        self._tick(tk_after)

    def stop(self) -> None:
        self._running = False

    def _tick(self, tk_after: Callable[[int, Callable[[], None]], None]) -> None:
        if not self._running:
            return

        now_dt = now_local()
        due = self.storage.list_due_reminders_to_fire(now_dt)

        for rem, notify_at in due:
            self._notify(rem.note_id, rem.message, rem.due_at, rem.remind_days_before)

            if rem.id is not None:
                self.storage.mark_reminder_fired(rem.id, now_dt)

                if self.on_fire:
                    self.on_fire(ReminderFireEvent(
                        reminder_id=rem.id,
                        note_id=rem.note_id,
                        message=rem.message,
                        due_at=rem.due_at,
                        notify_at=notify_at
                    ))

        tk_after(self._interval_ms, lambda: self._tick(tk_after))

    def _notify(self, note_id: int, message: str, due_at: datetime, days_before: int) -> None:
        title = "Recordatorio"
        body = f"{message}\nVence: {due_at.strftime('%Y-%m-%d %H:%M')} | Aviso: {days_before} día(s) antes"

        if _HAS_TOAST:
            try:
                toast = Notification(
                    app_id="Transparent Notepad",
                    title=title,
                    msg=body,
                    duration="short"
                )
                toast.set_audio(audio.Reminder, loop=False)
                toast.show()
                return
            except Exception:
                pass

        # fallback silencioso (no bloquea la app)
        return
