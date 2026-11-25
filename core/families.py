"""Les familles d'atelier : ce qu'une étude peut déclarer pour qu'on y construise une situation.

Chaque famille est un module pur qui offre les mêmes fonctions — `normalize`, `declared`, `situation`,
`from_query`, `to_query`, `placed`, `run`, `outcome`, `extra`, `to_case` — : l'écran, l'API et la couche de
services ne connaissent que cette interface. Ajouter une famille, c'est ajouter un module ici.
"""

from __future__ import annotations

from typing import Any

from . import periods, workshop
from .casemodel import Report

FAMILIES = {"linked": workshop, "periods": periods}
LABELS = {"linked": "éléments reliés", "periods": "périodes"}


def name_of(decl: dict | None) -> str:
    return (decl or {}).get("family") or "linked"


def of(decl: dict | None):
    """Le module qui exécute cette déclaration."""
    return FAMILIES[name_of(decl)]


def normalize(raw: Any, status_keys: set[str], report: Report, path: str = "workshop") -> dict:
    """La déclaration d'atelier d'une étude, validée par sa famille ; {} quand l'étude n'en déclare pas."""
    if raw in (None, {}):
        return {}
    if not isinstance(raw, dict):
        return workshop.normalize(raw, status_keys, report, path)
    family = raw.get("family", "linked")
    if family not in FAMILIES:
        report.error(
            f"{path}.family", "enum", "Famille d'atelier inconnue.", received=family, expected=list(FAMILIES)
        )
        return {}
    return FAMILIES[family].normalize(raw, status_keys, report, path)


def declared(decl: dict | None) -> bool:
    return bool(decl) and name_of(decl) in FAMILIES and of(decl).declared(decl)
