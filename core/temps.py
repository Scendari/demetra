"""Un axe du temps en dates réelles : un rang (0, 1, 2…) compté en jours ou en mois depuis une date d'origine.

Les moteurs et le dessin calculent sur des rangs, comme sur tout axe numérique ; ce module passe d'un rang à
une date (ISO pour les champs et les adresses, en toutes lettres pour l'écran) et choisit des graduations
qui tombent sur des débuts de mois ou d'année. Pur : aucun accès à la base.
"""

from __future__ import annotations

import datetime as dt

UNITS = ("day", "month")
MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def parse(unit: str, text) -> dt.date | None:
    """Une date écrite en ISO : « 2026-03-15 » pour un axe en jours, « 2026-03 » (ou un jour) en mois."""
    if not isinstance(text, str):
        return None
    try:
        if unit == "month" and len(text) == 7:
            return dt.date.fromisoformat(text + "-01")
        day = dt.date.fromisoformat(text)
    except ValueError:
        return None
    return day.replace(day=1) if unit == "month" else day


def index(unit: str, origin: dt.date, day: dt.date) -> int:
    """Le rang d'une date sur l'axe."""
    if unit == "month":
        return (day.year - origin.year) * 12 + day.month - origin.month
    return (day - origin).days


def date_at(unit: str, origin: dt.date, rank: float) -> dt.date:
    """La date d'un rang (arrondi à l'unité)."""
    rank = round(rank)
    if unit == "month":
        months = origin.month - 1 + rank
        return dt.date(origin.year + months // 12, months % 12 + 1, 1)
    return origin + dt.timedelta(days=rank)


def iso(unit: str, origin: dt.date, rank: float) -> str:
    """Le rang écrit en ISO, pour un champ de saisie ou une adresse."""
    day = date_at(unit, origin, rank)
    return day.isoformat()[:7] if unit == "month" else day.isoformat()


def label(unit: str, origin: dt.date, rank: float) -> str:
    """Le rang écrit pour l'écran : « 3 mars 2026 », ou « mars 2026 » pour un axe en mois."""
    day = date_at(unit, origin, rank)
    month = f"{MONTHS[day.month - 1]} {day.year}"
    return month if unit == "month" else f"{day.day} {month}"


def ticks(unit: str, origin: dt.date, low: float, high: float, most: int = 9) -> list[tuple[int, str]]:
    """Des graduations lisibles entre deux rangs : débuts de mois, de trimestre ou d'année, au plus `most`."""
    first, last = date_at(unit, origin, low), date_at(unit, origin, high)
    span_months = (last.year - first.year) * 12 + last.month - first.month
    if unit == "day" and span_months < 2:
        step = max(1, int(high - low) // most + 1)
        out = []
        rank = int(low)
        while rank <= high:
            out.append((rank, label(unit, origin, rank)))
            rank += step
        return out
    for every in (1, 2, 3, 6, 12, 24, 60):
        if span_months // every + 1 <= most:
            break
    out = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        if (month - 1) % every == 0 or every >= 12 and month == 1:
            day = dt.date(year, month, 1)
            rank = index(unit, origin, day)
            if low <= rank <= high and (every < 12 or month == 1):
                text = str(year) if every >= 12 else f"{MONTHS[month - 1]} {year}"
                out.append((rank, text))
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return out
