"""Étude de démonstration : les guichets d'une mairie, avec un atelier à places limitées.

Des demandes attendent dans la file ; un nombre réglable de guichets les reçoit, au plus un guichet par
demande et une demande par guichet. Une demande peut être retirée, un dossier incomplet est renvoyé. Rien,
dans le site, ne connaît cette mairie : tout tient dans la déclaration (une ressource à places, des règles).
Données fictives.

Les cas sont ceux que l'atelier enregistre pour les situations décrites ici : le moteur les écrit, ils se
relisent comme n'importe quel cas.
"""

from __future__ import annotations

from core import workshop
from core.casemodel import Report

TITLE = "Guichets d'une mairie"

WORKSHOP = {
    "title": "Composer une matinée au guichet",
    "bricks": [
        {
            "type": "demande",
            "label": "Demande",
            "options": [{"key": "complet", "label": "Dossier complet", "values": [True, False]}],
            "events": [{"key": "retrait", "label": "Retirée par l'usager"}],
        }
    ],
    "settings": [
        {
            "key": "guichets",
            "label": "Guichets ouverts",
            "values": [1, 2, 3],
            "dimension": {"key": "guichets", "values": {"1": 1, "2": 2, "3": 3}},
        }
    ],
    "resources": [
        {"key": "guichet", "label": "Guichets", "places": {"setting": "guichets"}, "held": ["AU_GUICHET"]}
    ],
    "rules": [
        {
            "key": "M1",
            "title": "Une demande retirée quitte la file",
            "when": {"status": "EN_FILE", "event": "retrait"},
            "then": "ANNULEE",
        },
        {
            "key": "M2",
            "title": "Un dossier incomplet est renvoyé sans passer au guichet",
            "when": {"status": "EN_FILE", "option": {"complet": False}},
            "then": "RENVOYEE",
        },
        {
            "key": "M3",
            "title": "Une demande passe au premier guichet libre",
            "when": {"status": "EN_FILE"},
            "then": "AU_GUICHET",
            "takes": "guichet",
        },
        {
            "key": "M4",
            "title": "Une demande traitée libère son guichet",
            "when": {"status": "AU_GUICHET"},
            "then": "TRAITEE",
        },
    ],
    "outcome": [
        {
            "when": {"elements": {"any": {"status": "RENVOYEE"}}},
            "label": "Des dossiers sont renvoyés",
            "status": "RENVOYEE",
        },
        {"label": "Toutes les demandes sont closes", "status": "TRAITEE"},
    ],
}

DEFINITION = {
    "title": TITLE,
    "description": "Des demandes attendent qu'un guichet se libère ; on règle le nombre de guichets ouverts "
    "et on voit qui passe, qui attend, qui repart. Exemple d'étude qui déclare une ressource à places "
    "limitées : jamais plus de demandes au guichet que de guichets ouverts.",
    "kind": "workflow",
    "statuses": [
        {"key": "EN_FILE", "label": "En file", "role": "waiting", "default": True},
        {"key": "AU_GUICHET", "label": "Au guichet", "role": "active"},
        {"key": "TRAITEE", "label": "Traitée", "role": "success"},
        {"key": "RENVOYEE", "label": "Renvoyée", "role": "warning"},
        {"key": "ANNULEE", "label": "Retirée", "role": "disabled"},
    ],
    "dimensions": [
        {
            "key": "guichets",
            "label": "Guichets ouverts",
            "values": [
                {"value": "1", "label": "Un"},
                {"value": "2", "label": "Deux"},
                {"value": "3", "label": "Trois"},
            ],
        },
        {
            "key": "affluence",
            "label": "Affluence",
            "values": [
                {"value": "sous", "label": "Pas plus de demandes que de guichets"},
                {"value": "au-dela", "label": "Plus de demandes que de guichets"},
            ],
        },
        {
            "key": "incident",
            "label": "Incident",
            "values": [
                {"value": "aucun", "label": "Aucun"},
                {"value": "retrait", "label": "Une demande retirée"},
                {"value": "incomplet", "label": "Un dossier incomplet"},
            ],
        },
    ],
    "rules": [
        {
            "key": "M1",
            "title": "Retrait",
            "text": "Une demande retirée quitte la file sans prendre de guichet.",
        },
        {
            "key": "M2",
            "title": "Dossier incomplet",
            "text": "Un dossier incomplet est renvoyé avant le guichet.",
        },
        {
            "key": "M3",
            "title": "Un guichet par demande",
            "text": "Une demande passe au guichet dès qu'il y en a un de libre ; jamais plus de demandes au "
            "guichet que de guichets ouverts. Les premières arrivées passent d'abord.",
        },
        {"key": "M4", "title": "Fin de traitement", "text": "Une demande traitée libère son guichet."},
    ],
    "attributes": [
        {"key": "complet", "label": "Dossier complet", "text": "Toutes les pièces sont fournies."}
    ],
    "workshop": WORKSHOP,
}


def _ask(key: str, *, complet: bool = True, retrait: bool = False) -> dict:
    return {
        "id": key,
        "type": "demande",
        "options": {"complet": complet},
        "events": ["retrait"] if retrait else [],
    }


# (clé, titre, résumé, demandes, guichets, affluence, incident, règles)
_SITUATIONS = [
    (
        "une-demande",
        "Une demande, un guichet",
        "Le cas le plus simple.",
        [_ask("A")],
        1,
        "sous",
        "aucun",
        ["M3", "M4"],
    ),
    (
        "deux-guichets-deux-demandes",
        "Deux demandes, deux guichets",
        "Assez de guichets : les deux demandes passent en même temps.",
        [_ask("A"), _ask("B")],
        2,
        "sous",
        "aucun",
        ["M3", "M4"],
    ),
    (
        "file-a-un-guichet",
        "Trois demandes pour un guichet",
        "Un seul guichet : les demandes passent l'une après l'autre, dans leur ordre d'arrivée.",
        [_ask("A"), _ask("B"), _ask("C")],
        1,
        "au-dela",
        "aucun",
        ["M3", "M4"],
    ),
    (
        "la-troisieme-attend",
        "Trois demandes pour deux guichets",
        "Les deux premières passent ; la troisième attend qu'un guichet se libère.",
        [_ask("A"), _ask("B"), _ask("C")],
        2,
        "au-dela",
        "aucun",
        ["M3", "M4"],
    ),
    (
        "retrait-dans-la-file",
        "Une demande retirée pendant l'attente",
        "La demande retirée quitte la file sans occuper de guichet.",
        [_ask("A"), _ask("B", retrait=True), _ask("C")],
        1,
        "au-dela",
        "retrait",
        ["M1", "M3", "M4"],
    ),
    (
        "dossier-incomplet",
        "Un dossier incomplet",
        "Le dossier incomplet est renvoyé avant le guichet ; les autres passent.",
        [_ask("A", complet=False), _ask("B"), _ask("C")],
        2,
        "au-dela",
        "incomplet",
        ["M2", "M3", "M4"],
    ),
]


def declaration() -> dict:
    """La déclaration d'atelier, validée : c'est elle que le moteur lit."""
    return workshop.normalize(WORKSHOP, {s["key"] for s in DEFINITION["statuses"]}, Report())


def cases() -> list[dict]:
    decl = declaration()
    default = next(s["key"] for s in DEFINITION["statuses"] if s.get("default"))
    out = []
    for key, title, summary, elements, guichets, affluence, incident, rules in _SITUATIONS:
        raw = {"elements": elements, "settings": {"guichets": guichets}}
        situation = workshop.situation(decl, raw, Report())
        case = workshop.to_case(decl, situation, workshop.run(decl, situation, default), default)
        dims = {"guichets": str(guichets), "affluence": affluence, "incident": incident}
        case.update(key=key, family="Matinées", title=title, summary=summary, rules=rules, dimensions=dims)
        out.append(case)
    return out
