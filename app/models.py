from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Note:
    id: Optional[int]
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
    sort_index: int

    # Estilos por nota
    text_color: str = "#0A0A0A"
    bg_color: str = "#FFFFFF"
    font_family: str = "Consolas"
    font_size: int = 12


@dataclass
class Reminder:
    id: Optional[int]
    note_id: int
    message: str
    due_at: datetime
    remind_days_before: int
    enabled: bool
    fired_at: Optional[datetime] = None


@dataclass
class AppSettings:
    # Transparencia de ventana eliminada (compat backup viejo si existe)
    window_alpha: float = 1.0

    topmost: bool = False
    always_save: bool = True
    word_wrap: bool = True
    zoom_percent: int = 100
    show_statusbar: bool = True

    # NUEVO: modo de tema persistente
    theme_mode: str = "light"  # "light" | "dark"
