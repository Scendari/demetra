"""Étude de démonstration : circuit de validation d'un document, avec ses règles d'atelier.

L'étude déclare ses briques (relecture, signature, publication), le lien qui les enchaîne et la table de
règles qui dit quand une étape démarre, aboutit ou est abandonnée. L'atelier s'en sert tel quel : rien, dans
le site, ne connaît ce circuit. Données fictives.
"""

from __future__ import annotations

TITLE = "Circuit de validation d'un document"

_ABOUTI = ["APPROUVE", "RESERVE", "SANS_OBJET"]

WORKSHOP = {
    "title": "Composer un circuit de validation",
    "bricks": [
        {
            "type": "relecture",
            "label": "Relecture",
            "options": [{"key": "obligatoire", "label": "Obligatoire", "values": [True, False]}],
            "events": [{"key": "refus", "label": "Refuse le document"}],
        },
        {
            "type": "signature",
            "label": "Signature",
            "options": [
                {
                    "key": "attend",
                    "label": "Attend",
                    "values": ["toutes les étapes précédentes", "une seule étape précédente"],
                }
            ],
            "events": [{"key": "refus", "label": "Refuse de signer"}],
        },
        {"type": "publication", "label": "Publication"},
    ],
    "links": [
        {
            "type": "puis",
            "label": "puis",
            "reverse": "après",
            "from": ["relecture", "signature"],
            "to": ["relecture", "signature", "publication"],
        }
    ],
    "settings": [{"key": "procedure", "label": "Procédure", "values": ["normale", "urgente"]}],
    "rules": [
        {
            "key": "V1",
            "title": "En procédure urgente, une relecture facultative est sans objet",
            "on": "relecture",
            "when": {
                "status": "A_FAIRE",
                "option": {"obligatoire": False},
                "setting": {"procedure": "urgente"},
            },
            "then": "SANS_OBJET",
        },
        {
            "key": "V2",
            "title": "Une étape est abandonnée dès qu'une étape en amont a refusé",
            "when": {"status": "A_FAIRE", "upstream": {"any": {"status": "REFUSE"}}},
            "then": "ABANDONNE",
        },
        {
            "key": "V3",
            "title": "Une signature qui n'attend qu'une étape démarre dès que l'une d'elles a abouti",
            "on": "signature",
            "when": {
                "status": "A_FAIRE",
                "option": {"attend": "une seule étape précédente"},
                "incoming": {"any": {"status": _ABOUTI}},
            },
            "then": "EN_COURS",
        },
        {
            "key": "V4",
            "title": "Une étape démarre quand toutes les étapes précédentes ont abouti",
            "when": {"status": "A_FAIRE", "incoming": {"all": {"status": _ABOUTI}}},
            "then": "EN_COURS",
        },
        {
            "key": "V5",
            "title": "Une relecture facultative qui refuse ne laisse qu'un avis réservé",
            "on": "relecture",
            "when": {"status": "EN_COURS", "event": "refus", "option": {"obligatoire": False}},
            "then": "RESERVE",
        },
        {
            "key": "V6",
            "title": "Un refus arrête le circuit",
            "on": ["relecture", "signature"],
            "when": {"status": "EN_COURS", "event": "refus"},
            "then": "REFUSE",
        },
        {
            "key": "V7",
            "title": "Le document est publié",
            "on": "publication",
            "when": {"status": "EN_COURS"},
            "then": "PUBLIE",
        },
        {
            "key": "V8",
            "title": "Une étape sans refus approuve le document",
            "on": ["relecture", "signature"],
            "when": {"status": "EN_COURS"},
            "then": "APPROUVE",
        },
    ],
    "outcome": [
        {
            "when": {"elements": {"any": {"status": "REFUSE"}}},
            "label": "Document refusé",
            "status": "REFUSE",
        },
        {
            "when": {
                "all": [
                    {"elements": {"type": "publication", "any": {"status": "PUBLIE"}}},
                    {"elements": {"any": {"status": "RESERVE"}}},
                ]
            },
            "label": "Document publié malgré un avis réservé",
            "status": "RESERVE",
        },
        {
            "when": {"elements": {"type": "publication", "any": {"status": "PUBLIE"}}},
            "label": "Document publié",
            "status": "PUBLIE",
        },
        {"label": "Circuit terminé sans publication", "status": "A_FAIRE"},
    ],
}

DEFINITION = {
    "title": TITLE,
    "description": "Un document passe par des relectures et des signatures avant d'être publié. Exemple "
    "d'étude qui déclare ses règles : l'atelier permet de composer son propre circuit et de voir ce qu'il "
    "devient.",
    "kind": "workflow",
    "statuses": [
        {"key": "A_FAIRE", "label": "À faire", "role": "waiting", "default": True},
        {"key": "EN_COURS", "label": "En cours", "role": "active"},
        {"key": "APPROUVE", "label": "Approuvé", "role": "success"},
        {"key": "RESERVE", "label": "Avis réservé", "short": "Réservé", "role": "warning"},
        {"key": "REFUSE", "label": "Refusé", "role": "error"},
        {"key": "ABANDONNE", "label": "Abandonné", "role": "blocked"},
        {"key": "SANS_OBJET", "label": "Sans objet", "role": "disabled"},
        {"key": "PUBLIE", "label": "Publié", "role": "success"},
    ],
    "dimensions": [
        {
            "key": "procedure",
            "label": "Procédure",
            "values": [{"value": "normale", "label": "Normale"}, {"value": "urgente", "label": "Urgente"}],
        },
        {
            "key": "refus",
            "label": "Qui refuse",
            "values": [
                {"value": "personne", "label": "Personne"},
                {"value": "obligatoire", "label": "Une relecture obligatoire"},
                {"value": "facultative", "label": "Une relecture facultative"},
            ],
        },
    ],
    "rules": [
        {
            "key": "C1",
            "title": "Enchaînement des étapes",
            "text": "Une étape ne commence que lorsque les étapes qui la précèdent ont abouti.",
        },
        {
            "key": "C2",
            "title": "Portée d'un refus",
            "text": "Le refus d'une relecture obligatoire ou d'une signature arrête le circuit ; celui d'une "
            "relecture facultative ne laisse qu'un avis réservé.",
        },
        {
            "key": "C3",
            "title": "Procédure urgente",
            "text": "En procédure urgente, les relectures facultatives sont sautées.",
        },
    ],
    "exclusions": [
        {
            "when": {"procedure": "urgente", "refus": "facultative"},
            "reason": "En procédure urgente, une relecture facultative n'a pas lieu : elle ne refuse rien.",
        }
    ],
    "attributes": [
        {
            "key": "obligatoire",
            "label": "Obligatoire",
            "text": "Une relecture obligatoire qui refuse arrête le circuit.",
        },
        {"key": "attend", "label": "Attend", "text": "Ce qu'une signature attend avant de commencer."},
    ],
    "workshop": WORKSHOP,
}

_ALL = "toutes les étapes précédentes"
_ENTITIES = [
    {"id": "J", "label": "Relecture juridique", "type": "relecture", "attrs": {"obligatoire": True}},
    {"id": "S", "label": "Relecture de style", "type": "relecture", "attrs": {"obligatoire": False}},
    {"id": "D", "label": "Signature de la direction", "type": "signature", "attrs": {"attend": _ALL}},
    {"id": "P", "label": "Publication", "type": "publication"},
]
_LINKS = [
    {"from": "J", "to": "D", "type": "puis"},
    {"from": "S", "to": "D", "type": "puis"},
    {"from": "D", "to": "P", "type": "puis"},
]


def _case(
    key: str, title: str, summary: str, dims: dict, steps: list[tuple], outcome: tuple, rules: list
) -> dict:
    return {
        "key": key,
        "family": "Circuit à deux relectures",
        "title": title,
        "summary": summary,
        "kind": "workflow",
        "rules": rules,
        "dimensions": dims,
        "config": {"procedure": dims["procedure"]},
        "entities": _ENTITIES,
        "links": _LINKS,
        "steps": [{"title": t, "note": note, "changes": changes} for t, note, changes in steps],
        "outcome": {"label": outcome[0], "status": outcome[1]},
    }


_START = (
    "Le document entre dans le circuit",
    "Les deux relectures commencent.",
    {"J": "EN_COURS", "S": "EN_COURS"},
)
# Chaque cas : clé, titre, résumé, dimensions, étapes (titre, note, changements), issue, règles citées.
_CASES = [
    (
        "tout-approuve",
        "Personne ne refuse : le document est publié",
        "Les deux relectures approuvent, la direction signe, le document est publié.",
        {"procedure": "normale", "refus": "personne"},
        [
            _START,
            ("Les relectures approuvent", "", {"J": "APPROUVE", "S": "APPROUVE"}),
            ("La direction signe", "Les deux relectures ont abouti.", {"D": "EN_COURS"}),
            ("Signature accordée", "", {"D": "APPROUVE"}),
            ("Publication", "", {"P": "EN_COURS"}),
            ("Le document est publié", "", {"P": "PUBLIE"}),
        ],
        ("Document publié", "PUBLIE"),
        ["C1"],
    ),
    (
        "refus-juridique",
        "La relecture juridique refuse : le circuit s'arrête",
        "La relecture juridique est obligatoire. Son refus abandonne la signature et la publication.",
        {"procedure": "normale", "refus": "obligatoire"},
        [
            _START,
            (
                "La relecture juridique refuse",
                "La relecture de style approuve.",
                {"J": "REFUSE", "S": "APPROUVE"},
            ),
            (
                "La suite est abandonnée",
                "Un refus en amont arrête le circuit.",
                {"D": "ABANDONNE", "P": "ABANDONNE"},
            ),
        ],
        ("Document refusé", "REFUSE"),
        ["C1", "C2"],
    ),
    (
        "reserve-style",
        "La relecture de style refuse : simple avis réservé",
        (
            "La relecture de style est facultative. Son refus ne bloque rien : le document est publié "
            "avec un avis réservé."
        ),
        {"procedure": "normale", "refus": "facultative"},
        [
            _START,
            ("La relecture de style émet une réserve", "", {"J": "APPROUVE", "S": "RESERVE"}),
            ("La direction signe", "Un avis réservé compte comme une étape aboutie.", {"D": "EN_COURS"}),
            ("Signature accordée", "", {"D": "APPROUVE"}),
            ("Publication", "", {"P": "EN_COURS"}),
            ("Le document est publié", "", {"P": "PUBLIE"}),
        ],
        ("Document publié malgré un avis réservé", "RESERVE"),
        ["C2"],
    ),
    (
        "urgence",
        "Procédure urgente : la relecture de style est sautée",
        (
            "En procédure urgente, la relecture facultative n'a pas lieu. La direction signe après la seule "
            "relecture juridique."
        ),
        {"procedure": "urgente", "refus": "personne"},
        [
            (
                "Le document entre dans le circuit",
                "La relecture de style est sans objet.",
                {"J": "EN_COURS", "S": "SANS_OBJET"},
            ),
            ("La relecture juridique approuve", "", {"J": "APPROUVE"}),
            ("La direction signe", "", {"D": "EN_COURS"}),
            ("Signature accordée", "", {"D": "APPROUVE"}),
            ("Publication", "", {"P": "EN_COURS"}),
            ("Le document est publié", "", {"P": "PUBLIE"}),
        ],
        ("Document publié", "PUBLIE"),
        ["C3"],
    ),
]


def cases() -> list[dict]:
    return [_case(*described) for described in _CASES]
