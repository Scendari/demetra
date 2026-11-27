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
            "options": [
                {"key": "complet", "label": "Dossier complet", "values": [True, False]},
                {"key": "duree", "label": "Durée du traitement (pas)", "values": [1, 2, 3]},
            ],
            "events": [{"key": "retrait", "label": "Retirée par l'usager"}],
        }
    ],
    "links": [
        {
            "type": "remplace",
            "label": "remplace",
            "reverse": "remplacée par",
            "from": ["demande"],
            "to": ["demande"],
            "request": True,
            "options": [{"key": "immediat", "label": "Retrait immédiat", "values": [True, False]}],
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
            "key": "M5",
            "title": "Retrait immédiat : la demande remplacée part quand la nouvelle passe au guichet",
            "when": {
                "status": "EN_FILE",
                "incoming": {
                    "link": "remplace",
                    "any": {"status": "AU_GUICHET", "link_option": {"immediat": True}},
                },
            },
            "then": "ANNULEE",
        },
        {
            "key": "M6",
            "title": "Une demande remplacée est retirée quand la nouvelle est traitée",
            "when": {"status": "EN_FILE", "incoming": {"link": "remplace", "any": {"status": "TRAITEE"}}},
            "then": "ANNULEE",
        },
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
            "title": "Une demande traitée, au bout de sa durée, libère son guichet",
            "when": {"status": "AU_GUICHET", "since": {"gte": {"option": "duree"}}},
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
                {"value": "remplacement", "label": "Une demande en remplace une autre"},
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
        {
            "key": "M4",
            "title": "Fin de traitement",
            "text": "Une demande reste au guichet le temps de son traitement (un à trois pas), puis libère "
            "son guichet.",
        },
        {
            "key": "M5",
            "title": "Remplacement",
            "text": "Une demande peut en remplacer une autre encore en file : celle-ci est retirée, aussitôt "
            "que la nouvelle passe au guichet si le retrait est immédiat, sinon quand la nouvelle est "
            "traitée. Une demande déjà passée au guichet n'est plus retirée.",
        },
    ],
    "attributes": [
        {"key": "complet", "label": "Dossier complet", "text": "Toutes les pièces sont fournies."},
        {"key": "duree", "label": "Durée du traitement", "text": "Les pas que la demande passe au guichet."},
    ],
    "workshop": WORKSHOP,
}


def _replaces(new: str, old: str, immediat: bool = True) -> dict:
    return {"from": new, "to": old, "type": "remplace", "options": {"immediat": immediat}}


def _ask(key: str, *, complet: bool = True, retrait: bool = False, duree: int = 1) -> dict:
    options = {"complet": complet, "duree": duree}
    return {"id": key, "type": "demande", "options": options, "events": ["retrait"] if retrait else []}


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
        "un-long-traitement",
        "Un long traitement retient le guichet",
        "A reste trois pas au guichet : B attend tout ce temps, puis passe à son tour.",
        [_ask("A", duree=3), _ask("B")],
        1,
        "au-dela",
        "aucun",
        ["M3", "M4"],
    ),
    (
        "durees-differentes",
        "Deux guichets, des traitements de durées différentes",
        "Le guichet de B, au traitement court, se libère le premier : C y passe pendant que A est traitée.",
        [_ask("A", duree=3), _ask("B"), _ask("C", duree=2)],
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


# Remplacements : (clé, titre, résumé, demandes, liens, guichets, règles). La nouvelle demande est posée
# avant l'ancienne quand elle doit passer la première.
_REPLACEMENTS = [
    (
        "remplacement-immediat",
        "Une demande en remplace une autre, retrait immédiat",
        "B remplace A : dès que B passe au guichet, A est retirée de la file.",
        [_ask("B"), _ask("A")],
        [_replaces("B", "A")],
        1,
        ["M5", "M3", "M4"],
    ),
    (
        "remplacement-differe",
        "Une demande en remplace une autre, retrait à la fin",
        "B remplace A sans retrait immédiat : A attend dans la file et n'est retirée qu'une fois B traitée.",
        [_ask("B"), _ask("A")],
        [_replaces("B", "A", immediat=False)],
        1,
        ["M5", "M3", "M4"],
    ),
    (
        "remplacement-trop-tard",
        "Un remplacement qui arrive trop tard",
        "A est déjà passée au guichet quand B, qui la remplace, est traitée : la demande reste sans effet.",
        [_ask("A"), _ask("B")],
        [_replaces("B", "A", immediat=False)],
        1,
        ["M5", "M3", "M4"],
    ),
]


def declaration() -> dict:
    """La déclaration d'atelier, validée : c'est elle que le moteur lit."""
    return workshop.normalize(WORKSHOP, {s["key"] for s in DEFINITION["statuses"]}, Report())


def cases() -> list[dict]:
    decl = declaration()
    default = next(s["key"] for s in DEFINITION["statuses"] if s.get("default"))
    out = []
    rows = [(k, t, s, e, [], g, a, i, r) for k, t, s, e, g, a, i, r in _SITUATIONS]
    rows += [
        (k, t, s, e, links, g, "au-dela", "remplacement", r) for k, t, s, e, links, g, r in _REPLACEMENTS
    ]
    for key, title, summary, elements, links, guichets, affluence, incident, rules in rows:
        raw = {"elements": elements, "links": links, "settings": {"guichets": guichets}}
        situation = workshop.situation(decl, raw, Report())
        case = workshop.to_case(decl, situation, workshop.run(decl, situation, default), default)
        dims = {"guichets": str(guichets), "affluence": affluence, "incident": incident}
        family = "Remplacements" if links else "Matinées"
        case.update(key=key, family=family, title=title, summary=summary, rules=rules, dimensions=dims)
        out.append(case)
    return out
