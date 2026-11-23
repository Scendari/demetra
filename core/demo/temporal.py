"""Étude de démonstration : règles temporelles (relances d'une facture impayée).

Le temps est compté en jours par rapport à l'échéance de la facture (J+0).
"""

from __future__ import annotations

TITLE = "Relances d'une facture impayée"

PAIEMENTS = [
    ("avant_echeance", "Avant l'échéance", -8),
    ("avant_relance", "Avant la 1re relance", 4),
    ("entre_relances", "Entre les deux relances", 11),
    ("apres_demeure", "Après la mise en demeure", 38),
    ("jamais", "Jamais", None),
]
CLIENTS = [("particulier", "Particulier"), ("professionnel", "Professionnel")]
LITIGES = [("non", "Non"), ("oui", "Oui")]

DEFINITION = {
    "title": TITLE,
    "description": "Calendrier des relances après l'échéance d'une facture : ce qui part, quand, et ce qu'un "
    "paiement ou un litige arrête.",
    "kind": "temporal",
    "statuses": [
        {"key": "A_VENIR", "label": "À venir", "short": "À venir", "role": "waiting", "default": True},
        {"key": "EN_COURS", "label": "En cours", "short": "En cours", "role": "active"},
        {"key": "TERMINEE", "label": "Terminée", "short": "Terminée", "role": "success"},
        {"key": "ENVOYEE", "label": "Envoyée", "short": "Envoyée", "role": "info"},
        {"key": "PAYEE", "label": "Payée", "short": "Payée", "role": "success"},
        {"key": "DEPASSEE", "label": "Dépassée", "short": "Dépassée", "role": "error"},
        {"key": "SUSPENDUE", "label": "Suspendue", "short": "Suspendue", "role": "blocked"},
        {"key": "ANNULEE", "label": "Annulée", "short": "Annulée", "role": "disabled"},
        {"key": "DECLARE", "label": "Déclaré", "short": "Déclaré", "role": "warning"},
    ],
    "dimensions": [
        {
            "key": "paiement",
            "label": "Moment du paiement",
            "values": [{"value": k, "label": v} for k, v, _ in PAIEMENTS],
        },
        {
            "key": "client",
            "label": "Type de client",
            "values": [{"value": k, "label": v} for k, v in CLIENTS],
        },
        {
            "key": "litige",
            "label": "Litige déclaré",
            "values": [{"value": k, "label": v} for k, v in LITIGES],
        },
    ],
    "rules": [
        {
            "key": "T1",
            "title": "Première relance à J+7",
            "text": "Sept jours après l'échéance, une première relance amiable est envoyée si la facture "
            "n'est pas payée.",
        },
        {
            "key": "T2",
            "title": "Seconde relance à J+15",
            "text": "Quinze jours après l'échéance, une seconde relance part. Pour un client professionnel, "
            "elle annonce les pénalités de retard.",
        },
        {
            "key": "T3",
            "title": "Mise en demeure à J+30",
            "text": "Trente jours après l'échéance, la phase amiable se termine par une mise en demeure.",
        },
        {
            "key": "T4",
            "title": "Contentieux à J+45",
            "text": "Quinze jours après la mise en demeure, le dossier est transmis au contentieux.",
        },
        {
            "key": "T5",
            "title": "Le paiement arrête tout",
            "text": "Dès que la facture est payée, toutes les relances à venir sont annulées.",
        },
        {
            "key": "T6",
            "title": "Un litige suspend les relances",
            "text": "Un litige déclaré par le client suspend les relances à venir tant qu'il n'est pas "
            "tranché.",
        },
    ],
    "exclusions": [
        {
            "when": {"paiement": "avant_echeance", "litige": "oui"},
            "reason": "Un litige n'est déclaré qu'en réponse à une relance : il n'existe pas si la facture "
            "est payée avant.",
        },
        {
            "when": {"paiement": "avant_relance", "litige": "oui"},
            "reason": "Un litige n'est déclaré qu'en réponse à une relance : il n'existe pas si la facture "
            "est payée avant.",
        },
    ],
}

SCHEDULE = [
    ("r1", 7, "1re relance", "T1"),
    ("r2", 15, "2e relance", "T2"),
    ("demeure", 30, "Mise en demeure", "T3"),
    ("contentieux", 45, "Transmission au contentieux", "T4"),
]
LITIGE_AT = 9

COMBINATIONS = [(p, c, "non") for p, _, _ in PAIEMENTS for c, _ in CLIENTS] + [
    ("jamais", "professionnel", "oui"),
    ("entre_relances", "particulier", "oui"),
]


def _temporal_entities(pro: bool, has_litige: bool, paid_at) -> list[dict]:
    """Périodes et échéances du calendrier de recouvrement, plus le litige et le paiement s'ils ont lieu."""
    entities = [
        {
            "id": "delai",
            "label": "Délai de paiement",
            "type": "période",
            "group": "Périodes",
            "attrs": {"start": -30, "end": 0},
        },
        {
            "id": "amiable",
            "label": "Phase amiable",
            "type": "période",
            "group": "Périodes",
            "attrs": {"start": 0, "end": 30},
        },
        {
            "id": "contentieuse",
            "label": "Phase contentieuse",
            "type": "période",
            "group": "Périodes",
            "attrs": {"start": 30, "end": 60},
        },
        {
            "id": "echeance",
            "label": "Échéance de la facture",
            "type": "échéance",
            "group": "Échéances",
            "attrs": {"at": 0},
        },
        {"id": "r1", "label": "1re relance", "type": "échéance", "group": "Échéances", "attrs": {"at": 7}},
        {
            "id": "r2",
            "label": "2e relance" + (" (pénalités annoncées)" if pro else ""),
            "type": "échéance",
            "group": "Échéances",
            "attrs": {"at": 15},
        },
        {
            "id": "demeure",
            "label": "Mise en demeure",
            "type": "échéance",
            "group": "Échéances",
            "attrs": {"at": 30},
        },
        {
            "id": "contentieux",
            "label": "Transmission au contentieux",
            "type": "échéance",
            "group": "Échéances",
            "attrs": {"at": 45},
        },
    ]
    if has_litige:
        entities.append(
            {
                "id": "litige",
                "label": "Litige déclaré par le client",
                "type": "événement",
                "group": "Événements",
                "attrs": {"at": LITIGE_AT},
            }
        )
    if paid_at is not None:
        entities.append(
            {
                "id": "paiement",
                "label": "Paiement reçu",
                "type": "événement",
                "group": "Événements",
                "attrs": {"at": paid_at},
            }
        )
    return entities


def _payment_step(t: int, rules: set[str]) -> dict:
    """Le client paie : tout ce qui restait à envoyer est annulé."""
    changes = {"paiement": "PAYEE"}
    annotations = {}
    if t < 0:
        changes.update(delai="TERMINEE", echeance="ANNULEE", amiable="ANNULEE", contentieuse="ANNULEE")
    else:
        changes["amiable" if t < 30 else "contentieuse"] = "TERMINEE"
        if t < 30:
            changes["contentieuse"] = "ANNULEE"
    for key, when, _, _ in SCHEDULE:
        if when > t:
            changes[key] = "ANNULEE"
            annotations[key] = "annulée par le paiement"
    rules.add("T5")
    return {
        "title": f"Le client paie à J{t:+d}",
        "note": "La facture est soldée : tout ce qui restait à envoyer est annulé.",
        "at": t,
        "changes": changes,
        "annotations": annotations,
        "global": "PAYEE",
    }


def _litige_step(t: int, rules: set[str]) -> dict:
    """Le client déclare un litige : les relances à venir sont suspendues."""
    changes, annotations = {"litige": "DECLARE", "amiable": "SUSPENDUE"}, {}
    for key, when, _, _ in SCHEDULE:
        if when > t:
            changes[key] = "SUSPENDUE"
            annotations[key] = "suspendue par le litige"
    rules.add("T6")
    return {
        "title": f"Le client déclare un litige à J+{t}",
        "note": "Les relances à venir sont suspendues tant que le litige n'est pas tranché.",
        "at": t,
        "changes": changes,
        "annotations": annotations,
        "global": "SUSPENDUE",
    }


def _schedule_step(t: int, pro: bool, rules: set[str]) -> dict:
    """Une relance du calendrier : première, seconde, mise en demeure, transmission au contentieux."""
    key, _, label, rule = next(s for s in SCHEDULE if s[1] == t)
    rules.add(rule)
    changes = {key: "ENVOYEE"}
    note = {
        "r1": "Première relance amiable, sans frais.",
        "r2": "Seconde relance"
        + (
            " : elle annonce les pénalités de retard dues par un professionnel."
            if pro
            else ", toujours amiable."
        ),
        "demeure": "La phase amiable est close : le dossier entre en phase contentieuse.",
        "contentieux": "Le dossier quitte le service comptable.",
    }[key]
    if key == "demeure":
        changes.update(amiable="TERMINEE", contentieuse="EN_COURS")
    return {
        "title": f"J+{t} : {label.lower()}",
        "note": note,
        "at": t,
        "changes": changes,
        "global": "DEPASSEE",
    }


def _temporal_steps(paid_at, has_litige: bool, pro: bool) -> tuple[list[dict], set[str], bool, bool]:
    """Le déroulé du dossier, moment par moment. Rend (étapes, règles illustrées, payé, suspendu)."""
    steps = [
        {
            "title": "La facture est émise",
            "note": "Le client a 30 jours pour payer.",
            "at": -30,
            "changes": {"delai": "EN_COURS"},
            "global": "EN_COURS",
        }
    ]
    rules: set[str] = set()
    moments = sorted(
        {
            0,
            *(t for _, t, _, _ in SCHEDULE),
            *([paid_at] if paid_at is not None else []),
            *([LITIGE_AT] if has_litige else []),
        }
    )
    paid = suspended = False
    for t in moments:
        if paid:
            break
        if paid_at is not None and t == paid_at:
            paid = True
            steps.append(_payment_step(t, rules))
            continue
        if has_litige and t == LITIGE_AT:
            suspended = True
            steps.append(_litige_step(t, rules))
            continue
        if t == 0:
            steps.append(
                {
                    "title": "L'échéance passe sans paiement",
                    "note": "La phase amiable commence ; rien ne part avant sept jours.",
                    "at": 0,
                    "changes": {"delai": "TERMINEE", "echeance": "DEPASSEE", "amiable": "EN_COURS"},
                    "global": "DEPASSEE",
                }
            )
            continue
        if suspended:
            if t == 45:
                steps.append(
                    {
                        "title": "J+45 : le dossier reste suspendu",
                        "note": "Sans décision sur le litige, rien n'est envoyé et le dossier n'est pas "
                        "transmis.",
                        "at": 45,
                        "changes": {},
                        "global": "SUSPENDUE",
                    }
                )
            continue
        steps.append(_schedule_step(t, pro, rules))
    return steps, rules, paid, suspended


def build(paiement: str, client: str, litige: str, number: int) -> dict:
    labels = {k: v for k, v, _ in PAIEMENTS}
    paid_at = next(t for k, _, t in PAIEMENTS if k == paiement)
    pro = client == "professionnel"
    has_litige = litige == "oui"
    entities = _temporal_entities(pro, has_litige, paid_at)
    steps, rules, paid, suspended = _temporal_steps(paid_at, has_litige, pro)
    outcome = (
        ("PAYEE", "Facture payée")
        if paid
        else (("SUSPENDUE", "Dossier suspendu") if suspended else ("DEPASSEE", "Dossier au contentieux"))
    )
    litige_text = ", litige déclaré" if has_litige else ""
    family = (
        "Paiement avant relance"
        if paiement in ("avant_echeance", "avant_relance")
        else (
            "Litige" if has_litige else ("Paiement après relance" if paid_at is not None else "Sans paiement")
        )
    )
    return {
        "key": f"facture-{paiement.replace('_', '-')}-{client[:4]}{'-litige' if has_litige else ''}",
        "number": number,
        "family": family,
        "title": f"Paiement : {labels[paiement].lower()} — client {client}{litige_text}",
        "summary": {
            "PAYEE": "Le paiement arrête les relances qui restaient à envoyer.",
            "SUSPENDUE": "Le litige gèle le calendrier : plus rien ne part.",
            "DEPASSEE": "Aucun paiement : le calendrier va jusqu'au contentieux.",
        }[outcome[0]],
        "kind": "temporal",
        "rules": sorted(rules),
        "dimensions": {"paiement": paiement, "client": client, "litige": litige},
        "entities": entities,
        "links": [],
        "steps": steps,
        "outcome": {"label": outcome[1], "status": outcome[0]},
        "references": [{"kind": "source", "label": "Procédure de recouvrement, version 3"}],
        "proof": "asserted",
    }


def cases() -> list[dict]:
    return [build(p, c, l, i + 1) for i, (p, c, l) in enumerate(COMBINATIONS)]
