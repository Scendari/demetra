"""Étude de démonstration : le responsable d'un magasin au fil du temps, avec son atelier de périodes.

Trois sources datées se combinent : le magasin (son enseigne change), la nomination qui le rattache à un
agent, et la fiche de cet agent (son nom change). L'étude déclare comment une image se compose à chaque jour ;
l'atelier s'en sert tel quel : rien, dans le site, ne connaît ces magasins. Données fictives.

Les cas sont ceux que l'atelier enregistre pour les situations décrites ici : le moteur les écrit, ils se
relisent comme n'importe quel cas.
"""

from __future__ import annotations

from core import periods
from core.casemodel import Report

TITLE = "Responsable d'un magasin au fil du temps"

GARDES, RETIRES = "gardés", "retirés"

WORKSHOP = {
    "family": "periods",
    "title": "Composer l'historique d'un magasin",
    "axis": {"label": "Jour", "min": 1, "max": 10, "grain": 1, "step": 0.25},
    "bricks": [
        {
            "type": "magasin",
            "label": "Magasin",
            "options": [
                {"key": "enseigne", "label": "Enseigne", "values": ["Halle du Port", "Halle du Phare"]},
                {"key": "caisse", "label": "Logiciel de caisse, non restitué", "values": ["v1", "v2"]},
            ],
        },
        {
            "type": "nomination",
            "label": "Nomination",
            "options": [{"key": "agent", "label": "Agent nommé", "values": ["A1", "A2"]}],
        },
        {
            "type": "agent",
            "label": "Fiche d'agent",
            "options": [
                {"key": "matricule", "label": "Matricule", "values": ["A1", "A2"]},
                {"key": "nom", "label": "Nom", "values": ["Alice", "Bruno", "A. Morel"]},
            ],
        },
    ],
    "settings": [{"key": "sans_responsable", "label": "Jours sans responsable", "values": [GARDES, RETIRES]}],
    "image": {
        "sources": [
            {"brick": "magasin"},
            {
                "brick": "nomination",
                "mode": {"setting": "sans_responsable", "inner": [RETIRES]},
                "several": "latest_start",
                "tie": "block",
            },
            {"brick": "agent", "match": {"matricule": "nomination.agent"}, "mode": "left"},
        ],
        "fields": [
            {"key": "enseigne", "label": "Enseigne", "from": "magasin.enseigne"},
            {"key": "responsable", "label": "Responsable", "from": "agent.nom"},
        ],
        "status": [
            {"when": {"missing": ["nomination", "agent"]}, "then": "SANS_RESPONSABLE"},
            {"then": "PUBLIEE"},
        ],
    },
    "merge": True,
    "invalid": {"zero": "ignore", "missing": "block", "inverted": "block"},
    "states": {
        "active": "EN_VIGUEUR",
        "past": "TERMINEE",
        "ignored": "ECARTEE",
        "invalid": "INVALIDE",
        "blocked": "BLOQUEE",
    },
    "outcome": [
        {"when": {"blocked": True}, "label": "Publication bloquée", "status": "BLOQUEE"},
        {"when": {"empty": True}, "label": "Aucune ligne publiée", "status": "ECARTEE"},
        {
            "when": {"status": "SANS_RESPONSABLE"},
            "label": "Historique publié, avec des jours sans responsable",
            "status": "SANS_RESPONSABLE",
        },
        {"label": "Historique publié", "status": "PUBLIEE"},
    ],
}

DEFINITION = {
    "title": TITLE,
    "description": "L'historique publié d'un magasin dit, jour par jour, son enseigne et son responsable. Il "
    "se compose de trois sources datées. Exemple d'étude qui déclare un atelier de périodes : on y pose ses "
    "propres périodes et on voit l'historique obtenu.",
    "kind": "temporal",
    "statuses": [
        {"key": "A_VENIR", "label": "À venir", "role": "waiting", "default": True},
        {"key": "EN_VIGUEUR", "label": "En vigueur", "role": "active"},
        {"key": "TERMINEE", "label": "Terminée", "role": "neutral"},
        {"key": "PUBLIEE", "label": "Publiée", "role": "success"},
        {
            "key": "SANS_RESPONSABLE",
            "label": "Publiée sans responsable",
            "short": "Sans resp.",
            "role": "info",
        },
        {"key": "ECARTEE", "label": "Écartée", "role": "disabled"},
        {"key": "BLOQUEE", "label": "Publication bloquée", "short": "Bloquée", "role": "blocked"},
        {"key": "INVALIDE", "label": "Invalide", "role": "error"},
    ],
    "dimensions": [
        {
            "key": "sans_responsable",
            "label": "Jours sans responsable",
            "values": [
                {"value": "gardes", "label": "Gardés : le magasin reste publié"},
                {"value": "retires", "label": "Retirés de l'historique"},
            ],
        },
        {
            "key": "nominations",
            "label": "Nominations",
            "values": [
                {"value": "continue", "label": "Une nomination à tout moment"},
                {"value": "trou", "label": "Des jours sans nomination"},
                {"value": "chevauchement", "label": "Deux en vigueur, débuts distincts"},
                {"value": "egalite", "label": "Deux en vigueur, même début"},
            ],
        },
    ],
    "rules": [
        {
            "key": "M1",
            "title": "Une image par jour",
            "text": "L'historique donne l'état du magasin à la fin de chaque jour. Deux jours de suite aux "
            "mêmes valeurs forment une seule période.",
        },
        {
            "key": "M2",
            "title": "Jours sans responsable",
            "text": "Un jour sans nomination en vigueur est publié sans responsable, ou retiré de "
            "l'historique, selon le réglage.",
        },
        {
            "key": "M3",
            "title": "Deux nominations en vigueur",
            "text": "La nomination la plus récente l'emporte. Si deux nominations ont commencé le même jour, "
            "rien n'est publié.",
        },
        {
            "key": "M4",
            "title": "Périodes invalides",
            "text": "Une période de durée nulle est ignorée. Une période sans borne, ou qui finit avant de "
            "commencer, bloque la publication.",
        },
    ],
    "attributes": [
        {"key": "enseigne", "label": "Enseigne", "text": "Le nom affiché du magasin sur la période."},
        {
            "key": "agent",
            "label": "Agent nommé",
            "text": "Le matricule de l'agent que la nomination désigne.",
        },
        {"key": "matricule", "label": "Matricule", "text": "Le matricule que porte la fiche d'agent."},
        {"key": "nom", "label": "Nom", "text": "Le nom de l'agent sur la période."},
    ],
    "workshop": WORKSHOP,
}


def _magasin(key: str, start, end, enseigne: str = "Halle du Port", caisse: str = "v1") -> dict:
    options = {"enseigne": enseigne, "caisse": caisse}
    return {"id": key, "type": "magasin", "start": start, "end": end, "options": options}


def _nomination(key: str, start, end, agent: str = "A1") -> dict:
    return {"id": key, "type": "nomination", "start": start, "end": end, "options": {"agent": agent}}


def _agent(key: str, start, end, matricule: str = "A1", nom: str = "Alice") -> dict:
    options = {"matricule": matricule, "nom": nom}
    return {"id": key, "type": "agent", "start": start, "end": end, "options": options}


_FICHES = [_agent("E", 1, 7, "A1", "Alice"), _agent("F", 1, 7, "A2", "Bruno")]
# (valeur de la dimension « nominations », titre, résumé, périodes posées, règles citées)
_SITUATIONS = [
    (
        "continue",
        "Deux nominations qui se suivent",
        "Alice puis Bruno : le responsable et l'enseigne changent chacun à leur date.",
        [
            _magasin("A", 1, 3),
            _magasin("B", 3, 7, "Halle du Phare"),
            _nomination("C", 1, 5, "A1"),
            _nomination("D", 5, 7, "A2"),
            *_FICHES,
        ],
        ["M1"],
    ),
    (
        "trou",
        "Deux jours sans nomination",
        "Entre deux nominations, le magasin n'a pas de responsable pendant deux jours.",
        [_magasin("A", 1, 7), _nomination("C", 1, 3, "A1"), _nomination("D", 5, 7, "A2"), *_FICHES],
        ["M1", "M2"],
    ),
    (
        "chevauchement",
        "Une nomination en recouvre une autre",
        "La nomination de Bruno commence alors que celle d'Alice court encore : la plus récente l'emporte.",
        [_magasin("A", 1, 7), _nomination("C", 1, 7, "A1"), _nomination("D", 4, 7, "A2"), *_FICHES],
        ["M1", "M3"],
    ),
    (
        "egalite",
        "Deux nominations commencent le même jour",
        "Rien ne départage deux nominations qui commencent le même jour : la publication est bloquée.",
        [_magasin("A", 1, 7), _nomination("C", 3, 7, "A1"), _nomination("D", 3, 7, "A2"), *_FICHES],
        ["M3"],
    ),
]
_REGLAGES = [("gardes", GARDES, "jours sans responsable gardés"), ("retires", RETIRES, "jours retirés")]


def declaration() -> dict:
    """La déclaration d'atelier, validée : c'est elle que le moteur lit."""
    return periods.normalize(WORKSHOP, {s["key"] for s in DEFINITION["statuses"]}, Report())


def cases() -> list[dict]:
    decl = declaration()
    default = next(s["key"] for s in DEFINITION["statuses"] if s.get("default"))
    out = []
    for value, title, summary, elements, rules in _SITUATIONS:
        for dim, setting, words in _REGLAGES:
            raw = {"elements": elements, "settings": {"sans_responsable": setting}}
            situation = periods.situation(decl, raw, Report())
            case = periods.to_case(decl, situation, periods.run(decl, situation, default), default)
            case.update(
                key=f"{value}-{dim}",
                family=title,
                title=f"{title}, {words}",
                summary=summary,
                rules=rules,
                dimensions={"sans_responsable": dim, "nominations": value},
            )
            out.append(case)
    return out
