"""Étude de démonstration : cas paramétrés (renouvellement d'un abonnement).

Deux cas sur trois déclarent des paramètres : le site les rejoue pour chaque combinaison, et le panneau du
cas, dans l'onglet « Cas », donne un lien vers chaque variante. Données fictives.
"""

from __future__ import annotations

TITLE = "Renouvellement d'un abonnement"

PAIEMENTS = [("accepte", "Accepté"), ("refuse", "Refusé")]
RELANCES = [("active", "Activée"), ("inactive", "Désactivée")]
ANCIENNETES = [("recent", "Moins d'un an"), ("ancien", "Un an ou plus")]

DEFINITION = {
    "title": TITLE,
    "description": "Ce qui arrive à un abonnement le jour de son échéance, selon que le prélèvement passe et "
    "que la relance automatique est activée. Exemple de cas paramétrés : un même cas décrit plusieurs "
    "situations.",
    "kind": "workflow",
    "statuses": [
        {"key": "A_VENIR", "label": "À venir", "role": "neutral", "default": True},
        {"key": "ECHEANCE", "label": "À l'échéance", "short": "Échéance", "role": "waiting"},
        {"key": "EN_COURS", "label": "En cours", "role": "active"},
        {"key": "ACCEPTE", "label": "Accepté", "role": "success"},
        {"key": "REFUSE", "label": "Refusé", "role": "error"},
        {"key": "ENVOYEE", "label": "Envoyée", "role": "info"},
        {"key": "REPORTE", "label": "Reporté", "role": "warning"},
        {"key": "RENOUVELE", "label": "Renouvelé", "role": "success"},
        {"key": "SUSPENDU", "label": "Suspendu", "role": "blocked"},
    ],
    "dimensions": [
        {
            "key": "paiement",
            "label": "Premier prélèvement",
            "values": [{"value": k, "label": v} for k, v in PAIEMENTS],
        },
        {
            "key": "relance",
            "label": "Relance automatique",
            "values": [{"value": k, "label": v} for k, v in RELANCES],
        },
        {
            "key": "anciennete",
            "label": "Ancienneté de l'abonné",
            "values": [{"value": k, "label": v} for k, v in ANCIENNETES],
        },
    ],
    "rules": [
        {
            "key": "A1",
            "title": "Prélèvement à l'échéance",
            "text": "À l'échéance, le prélèvement est tenté. S'il passe, l'abonnement est renouvelé.",
        },
        {
            "key": "A2",
            "title": "Relance après un refus",
            "text": "Après un refus, si la relance automatique est activée, un message part et un second "
            "prélèvement est tenté trois jours plus tard.",
        },
        {
            "key": "A3",
            "title": "Suspension",
            "text": "Sans relance, ou après un second refus, l'abonnement est suspendu. Un abonné d'un an "
            "ou plus garde l'accès sept jours de plus.",
        },
        {
            "key": "A4",
            "title": "Jour férié",
            "text": "Une échéance qui tombe un jour férié est prélevée le jour ouvré suivant.",
        },
    ],
}

_ENTITIES = [
    {"id": "abonnement", "label": "Abonnement", "type": "abonnement"},
    {"id": "prelevement", "label": "Prélèvement", "type": "paiement"},
    {"id": "relance", "label": "Message de relance", "type": "message"},
]
_REFUSE = {"paiement": "refuse"}
_RELANCE = {"all": [_REFUSE, {"relance": "active"}]}
_SANS_RELANCE = {"all": [_REFUSE, {"relance": "inactive"}]}


def _abonne_recent() -> dict:
    """Un cas, quatre situations : le prélèvement passe ou non, la relance est activée ou non."""
    return {
        "key": "abonne-recent",
        "family": "Abonné de moins d'un an",
        "kind": "workflow",
        "title": "Échéance d'un abonné récent",
        "summary": "Le cas déclare deux paramètres. Les étapes après le prélèvement dépendent de leurs "
        "valeurs ; le site rejoue le cas pour les quatre combinaisons.",
        "rules": ["A1", "A2", "A3"],
        "dimensions": {"anciennete": "recent"},
        "params": [
            {"key": "paiement", "label": "Premier prélèvement", "values": ["accepte", "refuse"]},
            {"key": "relance", "label": "Relance automatique", "values": ["active", "inactive"]},
        ],
        "entities": _ENTITIES,
        "steps": [
            {"title": "L'échéance arrive", "changes": {"abonnement": "ECHEANCE"}},
            {"title": "Le prélèvement est tenté", "changes": {"prelevement": "EN_COURS"}},
            {
                "when": {"paiement": "accepte"},
                "title": "Le prélèvement est accepté",
                "changes": {"prelevement": "ACCEPTE", "abonnement": "RENOUVELE"},
            },
            {
                "when": _REFUSE,
                "title": "Le prélèvement est refusé",
                "note": "La banque refuse le prélèvement : rien n'est encaissé.",
                "changes": {"prelevement": "REFUSE"},
            },
            {
                "when": _RELANCE,
                "title": "Un message de relance part",
                "note": "La relance automatique est activée : l'abonné est prévenu (règle A2).",
                "changes": {"relance": "ENVOYEE"},
            },
            {
                "when": _RELANCE,
                "title": "Le second prélèvement passe, trois jours plus tard",
                "changes": {"prelevement": "ACCEPTE", "abonnement": "RENOUVELE"},
            },
            {
                "when": _SANS_RELANCE,
                "title": "L'abonnement est suspendu",
                "note": "Aucune relance n'est prévue : l'accès est coupé le jour même (règle A3).",
                "changes": {"abonnement": "SUSPENDU"},
            },
        ],
        "outcome": [
            {"when": {"paiement": "accepte"}, "label": "Abonnement renouvelé", "status": "RENOUVELE"},
            {"when": _RELANCE, "label": "Abonnement renouvelé après relance", "status": "RENOUVELE"},
            {"label": "Abonnement suspendu", "status": "SUSPENDU"},
        ],
    }


def _abonne_ancien_accepte() -> dict:
    """Un paramètre qui n'est pas une dimension de l'étude : il devient un réglage du cas."""
    return {
        "key": "abonne-ancien-accepte",
        "family": "Abonné d'un an ou plus",
        "kind": "workflow",
        "title": "Échéance d'un abonné ancien, prélèvement accepté",
        "summary": "Le paramètre « échéance un jour férié » ajoute une étape de report quand il est vrai.",
        "rules": ["A1", "A4"],
        "dimensions": {"anciennete": "ancien", "paiement": "accepte", "relance": "active"},
        "params": [
            {
                "key": "jour_ferie",
                "label": "Échéance un jour férié",
                "values": [False, True],
                "default": False,
            }
        ],
        "entities": _ENTITIES[:2],
        "steps": [
            {"title": "L'échéance arrive", "changes": {"abonnement": "ECHEANCE"}},
            {
                "when": {"jour_ferie": True},
                "title": "Le prélèvement est reporté au jour ouvré suivant",
                "note": "La banque ne traite rien un jour férié (règle A4).",
                "changes": {"prelevement": "REPORTE"},
            },
            {"title": "Le prélèvement est tenté", "changes": {"prelevement": "EN_COURS"}},
            {
                "title": "Le prélèvement est accepté",
                "changes": {"prelevement": "ACCEPTE", "abonnement": "RENOUVELE"},
            },
        ],
        "outcome": {"label": "Abonnement renouvelé", "status": "RENOUVELE"},
    }


def _abonne_ancien_grace() -> dict:
    """Un cas ordinaire, sans paramètre : il côtoie les cas paramétrés."""
    return {
        "key": "abonne-ancien-grace",
        "family": "Abonné d'un an ou plus",
        "kind": "workflow",
        "title": "Abonné ancien, refus sans relance : sept jours de grâce",
        "summary": "Le prélèvement est refusé et aucune relance n'est prévue. L'abonné garde l'accès sept "
        "jours avant la suspension.",
        "rules": ["A1", "A3"],
        "dimensions": {"anciennete": "ancien", "paiement": "refuse", "relance": "inactive"},
        "entities": _ENTITIES[:2],
        "steps": [
            {"title": "L'échéance arrive", "changes": {"abonnement": "ECHEANCE"}},
            {"title": "Le prélèvement est tenté", "changes": {"prelevement": "EN_COURS"}},
            {"title": "Le prélèvement est refusé", "changes": {"prelevement": "REFUSE"}},
            {
                "title": "L'accès est maintenu sept jours",
                "note": "L'abonné a plus d'un an d'ancienneté : la suspension est différée (règle A3).",
                "changes": {},
            },
            {"title": "L'abonnement est suspendu", "changes": {"abonnement": "SUSPENDU"}},
        ],
        "outcome": {"label": "Abonnement suspendu après sept jours", "status": "SUSPENDU"},
    }


def cases() -> list[dict]:
    return [_abonne_recent(), _abonne_ancien_accepte(), _abonne_ancien_grace()]
