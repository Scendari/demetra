"""Étude de démonstration : les garanties d'un contrat, avec un atelier de périodes qui les combine.

Un contrat court sur trois ans ; des garanties s'y ajoutent, chacune avec sa surprime. Quand plusieurs
garanties sont en vigueur en même temps, leurs surprimes s'additionnent et leurs noms se lisent ensemble :
le site combine les périodes au lieu d'en garder une. Rien, dans le site, ne connaît ce contrat : tout tient
dans la déclaration. Données fictives.

Les cas sont ceux que l'atelier enregistre pour les situations décrites ici.
"""

from __future__ import annotations

from core import periods
from core.casemodel import Report

TITLE = "Garanties d'un contrat"

WORKSHOP = {
    "family": "periods",
    "title": "Composer les garanties d'un contrat",
    "axis": {"label": "Date", "calendar": "day", "from": "2025-01-01", "to": "2028-01-01"},
    "bricks": [
        {
            "type": "contrat",
            "label": "Contrat",
            "options": [{"key": "formule", "label": "Formule", "values": ["Essentielle", "Confort"]}],
        },
        {
            "type": "garantie",
            "label": "Garantie",
            "options": [
                {"key": "nom", "label": "Garantie", "values": ["Bris de glace", "Vol", "Assistance"]},
                {"key": "surprime", "label": "Surprime (€/mois)", "values": [3, 5, 8]},
            ],
        },
    ],
    "image": {
        "sources": [
            {"brick": "contrat"},
            {
                "brick": "garantie",
                "mode": "left",
                "several": "combine",
                "combine": {"surprime": "sum", "nom": "list"},
            },
        ],
        "fields": [
            {"key": "formule", "label": "Formule", "from": "contrat.formule"},
            {"key": "garanties", "label": "Garanties", "from": "garantie.nom"},
            {"key": "surprime", "label": "Surprime", "from": "garantie.surprime"},
        ],
        "status": [{"when": {"missing": ["garantie"]}, "then": "SANS_GARANTIE"}, {"then": "GARANTI"}],
    },
    "states": {
        "active": "EN_VIGUEUR",
        "past": "TERMINEE",
        "ignored": "ECARTEE",
        "invalid": "INVALIDE",
        "blocked": "BLOQUEE",
    },
    "outcome": [
        {"when": {"blocked": True}, "label": "Calendrier bloqué", "status": "BLOQUEE"},
        {"when": {"status": "GARANTI"}, "label": "Des garanties s'ajoutent au contrat", "status": "GARANTI"},
        {"label": "Contrat seul", "status": "SANS_GARANTIE"},
    ],
}

DEFINITION = {
    "title": TITLE,
    "description": "Un contrat et ses garanties, jour par jour sur trois ans. Quand deux garanties se "
    "chevauchent, leurs surprimes s'additionnent. Exemple d'étude qui déclare un atelier de périodes "
    "combinées, sur un axe en dates.",
    "kind": "temporal",
    "statuses": [
        {"key": "A_VENIR", "label": "À venir", "role": "waiting", "default": True},
        {"key": "EN_VIGUEUR", "label": "En vigueur", "role": "active"},
        {"key": "TERMINEE", "label": "Terminée", "role": "neutral"},
        {"key": "ECARTEE", "label": "Écartée", "role": "disabled"},
        {"key": "INVALIDE", "label": "Invalide", "role": "warning"},
        {"key": "BLOQUEE", "label": "Bloquée", "role": "error"},
        {"key": "GARANTI", "label": "Garanti", "role": "success"},
        {"key": "SANS_GARANTIE", "label": "Sans garantie", "role": "info"},
    ],
    "dimensions": [
        {
            "key": "chevauchement",
            "label": "Garanties en même temps",
            "values": [
                {"value": "aucune", "label": "Aucune garantie"},
                {"value": "une", "label": "Une à la fois"},
                {"value": "plusieurs", "label": "Plusieurs à la fois"},
            ],
        }
    ],
    "rules": [
        {
            "key": "G1",
            "title": "Surprimes cumulées",
            "text": "Les garanties en vigueur le même jour s'ajoutent : leurs surprimes s'additionnent.",
        },
        {
            "key": "G2",
            "title": "Contrat seul",
            "text": "Hors garantie, le contrat se lit seul, sans surprime.",
        },
    ],
    "workshop": WORKSHOP,
}


def _contrat(start: str, end: str, formule: str = "Essentielle") -> dict:
    return {"id": "A", "type": "contrat", "start": start, "end": end, "options": {"formule": formule}}


def _garantie(key: str, start: str, end: str, nom: str, surprime: int) -> dict:
    options = {"nom": nom, "surprime": surprime}
    return {"id": key, "type": "garantie", "start": start, "end": end, "options": options}


# (clé, titre, résumé, périodes, chevauchement, règles)
_SITUATIONS = [
    (
        "contrat-seul",
        "Un contrat sans garantie",
        "Rien ne s'ajoute.",
        [_contrat("2025-01-01", "2028-01-01")],
        "aucune",
        ["G2"],
    ),
    (
        "une-garantie",
        "Une garantie de quelques mois",
        "La surprime ne court que pendant la garantie.",
        [_contrat("2025-01-01", "2028-01-01"), _garantie("B", "2025-10-01", "2026-10-01", "Vol", 5)],
        "une",
        ["G1", "G2"],
    ),
    (
        "deux-garanties-qui-se-chevauchent",
        "Deux garanties qui se chevauchent",
        "Pendant le chevauchement, les deux garanties se lisent ensemble et leurs surprimes s'additionnent.",
        [
            _contrat("2025-01-01", "2028-01-01"),
            _garantie("B", "2025-04-01", "2026-10-01", "Vol", 5),
            _garantie("C", "2026-04-01", "2027-06-01", "Bris de glace", 3),
        ],
        "plusieurs",
        ["G1", "G2"],
    ),
    (
        "trois-garanties",
        "Trois garanties en même temps",
        "Quand les trois se croisent, la surprime vaut leur somme.",
        [
            _contrat("2025-01-01", "2028-01-01", "Confort"),
            _garantie("B", "2025-01-01", "2026-07-01", "Vol", 5),
            _garantie("C", "2025-07-01", "2027-01-01", "Bris de glace", 3),
            _garantie("D", "2026-01-01", "2026-04-01", "Assistance", 8),
        ],
        "plusieurs",
        ["G1", "G2"],
    ),
]


def declaration() -> dict:
    """La déclaration d'atelier, validée : c'est elle que le moteur lit."""
    return periods.normalize(WORKSHOP, {s["key"] for s in DEFINITION["statuses"]}, Report())


def cases() -> list[dict]:
    decl = declaration()
    default = next(s["key"] for s in DEFINITION["statuses"] if s.get("default"))
    out = []
    for key, title, summary, elements, overlap, rules in _SITUATIONS:
        situation = periods.situation(decl, {"elements": elements}, Report())
        case = periods.to_case(decl, situation, periods.run(decl, situation, default), default)
        dims = {"chevauchement": overlap}
        case.update(key=key, family="Garanties", title=title, summary=summary, rules=rules, dimensions=dims)
        out.append(case)
    return out
