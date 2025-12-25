from __future__ import annotations

from datetime import datetime
from typing import Optional

DATE_FMT = "%Y-%m-%d"
TIME_FMT = "%H:%M"

def now_local() -> datetime:
    return datetime.now()

def parse_date_time(date_str: str, time_str: str) -> Optional[datetime]:
    """
    date_str: YYYY-MM-DD
    time_str: HH:MM
    """
    date_str = date_str.strip()
    time_str = time_str.strip()
    if not date_str:
        return None
    if not time_str:
        time_str = "09:00"

    try:
        dt = datetime.strptime(f"{date_str} {time_str}", f"{DATE_FMT} {TIME_FMT}")
        return dt
    except ValueError:
        return None

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
