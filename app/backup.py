from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .models import Note, Reminder, AppSettings

SCHEMA_VERSION = 1

def _dt_to_iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")

def _iso_to_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)

def build_backup_payload(settings: AppSettings, notes: List[Note], reminders: List[Reminder]) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": _dt_to_iso(datetime.now()),
        "app": "Transparent Notepad",
        "settings": {
            "window_alpha": settings.window_alpha,
            "topmost": settings.topmost,
            "always_save": settings.always_save,
        },
        "notes": [
            {
                "id": n.id,
                "title": n.title,
                "content": n.content,
                "created_at": _dt_to_iso(n.created_at),
                "updated_at": _dt_to_iso(n.updated_at),
                "sort_index": n.sort_index,
                "text_color": n.text_color,
                "bg_color": n.bg_color,
                "font_family": n.font_family,
                "font_size": n.font_size,
            }
            for n in notes
        ],
        "reminders": [
            {
                "id": r.id,
                "note_id": r.note_id,
                "message": r.message,
                "due_at": _dt_to_iso(r.due_at),
                "remind_days_before": r.remind_days_before,
                "enabled": r.enabled,
                "fired_at": _dt_to_iso(r.fired_at) if r.fired_at else None,
            }
            for r in reminders
        ],
    }

def write_bplus(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("data.json", data)

def read_bplus(path: Path) -> Dict[str, Any]:
    with zipfile.ZipFile(path, "r") as z:
        if "data.json" not in z.namelist():
            raise ValueError("El archivo .bplus no contiene data.json")
        raw = z.read("data.json").decode("utf-8")
        payload = json.loads(raw)

    if "schema_version" not in payload:
        raise ValueError("Backup inválido: falta schema_version")

    if int(payload["schema_version"]) != SCHEMA_VERSION:
        raise ValueError(
            f"Backup incompatible. schema_version={payload['schema_version']} (se esperaba {SCHEMA_VERSION})."
        )

    return payload

def payload_to_objects(payload: Dict[str, Any]) -> Tuple[AppSettings, List[Note], List[Reminder]]:
    s = payload.get("settings", {})
    settings = AppSettings(
        window_alpha=float(s.get("window_alpha", 0.88)),
        topmost=bool(s.get("topmost", False)),
        always_save=bool(s.get("always_save", True)),
    )

    notes: List[Note] = []
    for n in payload.get("notes", []):
        notes.append(Note(
            id=n.get("id"),
            title=n.get("title", "Sin título"),
            content=n.get("content", ""),
            created_at=_iso_to_dt(n["created_at"]),
            updated_at=_iso_to_dt(n["updated_at"]),
            sort_index=int(n.get("sort_index", 0)),
            text_color=n.get("text_color", "#FFFFFF"),
            bg_color=n.get("bg_color", "#1E1E1E"),
            font_family=n.get("font_family", "Consolas"),
            font_size=int(n.get("font_size", 12)),
        ))

    reminders: List[Reminder] = []
    for r in payload.get("reminders", []):
        reminders.append(Reminder(
            id=r.get("id"),
            note_id=int(r["note_id"]),
            message=r.get("message", ""),
            due_at=_iso_to_dt(r["due_at"]),
            remind_days_before=int(r.get("remind_days_before", 0)),
            enabled=bool(r.get("enabled", True)),
            fired_at=_iso_to_dt(r["fired_at"]) if r.get("fired_at") else None,
        ))

    return settings, notes, reminders
