"""Études de démonstration du catalogue élargi : une par représentation nouvelle.

Toutes les données sont fictives. Chaque étude est petite et choisie pour que la représentation
qu'elle illustre soit la mieux adaptée : c'est aussi ce que vérifie le test du conseil.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. Matrice croisée — droits d'accès selon le rôle et la sensibilité
# ---------------------------------------------------------------------------

ROLES = [
    ("lecteur", "Lecteur"),
    ("contributeur", "Contributeur"),
    ("responsable", "Responsable"),
    ("admin", "Administrateur"),
]
SENSIBILITES = [("public", "Public"), ("interne", "Interne"), ("confidentiel", "Confidentiel")]
ACCES = {
    ("lecteur", "public"): "LECTURE",
    ("lecteur", "interne"): "LECTURE",
    ("lecteur", "confidentiel"): "REFUSE",
    ("contributeur", "public"): "MODIFICATION",
    ("contributeur", "interne"): "MODIFICATION",
    ("contributeur", "confidentiel"): "REFUSE",
    ("responsable", "public"): "MODIFICATION",
    ("responsable", "interne"): "MODIFICATION",
    ("responsable", "confidentiel"): "LECTURE",
    ("admin", "public"): "MODIFICATION",
    ("admin", "interne"): "MODIFICATION",
    # (admin, confidentiel) volontairement absent : la matrice montre le trou.
}
ACCES_LABELS = {
    "LECTURE": "Lecture seule",
    "MODIFICATION": "Lecture et modification",
    "REFUSE": "Accès refusé",
}

MATRICE = {
    "title": "Droits d'accès aux documents",
    "description": "Ce qu'une personne peut faire d'un document, selon son rôle et la sensibilité du "
    "document. Exemple pour la matrice croisée.",
    "kind": "decision",
    "statuses": [
        {"key": "A_EVALUER", "label": "À évaluer", "role": "waiting", "default": True},
        {"key": "PRIS_EN_COMPTE", "label": "Pris en compte", "short": "Pris", "role": "info"},
        {"key": "LECTURE", "label": "Lecture seule", "short": "Lecture", "role": "warning"},
        {"key": "MODIFICATION", "label": "Lecture et modification", "short": "Modif.", "role": "success"},
        {"key": "REFUSE", "label": "Accès refusé", "short": "Refusé", "role": "error"},
    ],
    "dimensions": [
        {
            "key": "role",
            "label": "Rôle de la personne",
            "values": [{"value": k, "label": v} for k, v in ROLES],
        },
        {
            "key": "sensibilite",
            "label": "Sensibilité du document",
            "values": [{"value": k, "label": v} for k, v in SENSIBILITES],
        },
    ],
    "rules": [
        {
            "key": "A1",
            "title": "Document confidentiel",
            "text": "Un document confidentiel n'est visible qu'à partir du rôle Responsable, et en lecture "
            "seule.",
        },
        {
            "key": "A2",
            "title": "Modification",
            "text": "Modifier un document public ou interne demande au moins le rôle Contributeur.",
        },
    ],
}


def matrice_cases() -> list[dict]:
    cases = []
    for (role, sens), acces in ACCES.items():
        role_label, sens_label = dict(ROLES)[role], dict(SENSIBILITES)[sens]
        cases.append(
            {
                "key": f"{role}-{sens}",
                "family": role_label,
                "kind": "decision",
                "title": f"{role_label} devant un document {sens_label.lower()}",
                "summary": f"Rôle {role_label}, document {sens_label.lower()} : "
                f"{ACCES_LABELS[acces].lower()}.",
                "rules": ["A1"] if sens == "confidentiel" else ["A2"],
                "dimensions": {"role": role, "sensibilite": sens},
                "entities": [
                    {"id": "role", "label": "Rôle", "type": "condition", "attrs": {"value": role_label}},
                    {
                        "id": "sensibilite",
                        "label": "Sensibilité",
                        "type": "condition",
                        "attrs": {"value": sens_label},
                    },
                    {"id": "acces", "label": "Accès accordé", "type": "resultat"},
                ],
                "steps": [
                    {
                        "title": "Le rôle est lu",
                        "changes": {"role": "PRIS_EN_COMPTE"},
                        "annotations": {"role": role_label},
                    },
                    {
                        "title": "La sensibilité est lue",
                        "changes": {"sensibilite": "PRIS_EN_COMPTE"},
                        "annotations": {"sensibilite": sens_label},
                    },
                    {
                        "title": "L'accès est décidé",
                        "changes": {"acces": acces},
                        "global": acces,
                        "note": "Document confidentiel : la règle A1 s'applique."
                        if sens == "confidentiel"
                        else "Document non confidentiel : la règle A2 s'applique.",
                    },
                ],
                "outcome": {"label": ACCES_LABELS[acces], "status": acces},
            }
        )
    return cases


# ---------------------------------------------------------------------------
# 2. Calcul pas à pas — prix d'une commande
# ---------------------------------------------------------------------------

CALCUL = {
    "title": "Prix à payer d'une commande",
    "description": "Comment le montant d'une commande se construit : sous-total, remise de fidélité, code "
    "promotionnel, frais de port. Exemple pour le calcul pas à pas.",
    "kind": "decision",
    "statuses": [
        {"key": "A_CALCULER", "label": "À calculer", "role": "waiting", "default": True},
        {"key": "EN_COURS", "label": "Calcul en cours", "short": "En cours", "role": "active"},
        {"key": "CALCULE", "label": "Montant arrêté", "short": "Arrêté", "role": "success"},
    ],
    "dimensions": [
        {
            "key": "client",
            "label": "Client",
            "values": [{"value": "standard", "label": "Standard"}, {"value": "fidele", "label": "Fidèle"}],
        },
        {
            "key": "code",
            "label": "Code promotionnel",
            "values": [{"value": "sans", "label": "Sans code"}, {"value": "avec", "label": "Code de 10 €"}],
        },
        {
            "key": "port",
            "label": "Frais de port",
            "values": [{"value": "payant", "label": "Payants"}, {"value": "offert", "label": "Offerts"}],
        },
    ],
    "rules": [
        {
            "key": "P1",
            "title": "Remise de fidélité",
            "text": "Un client fidèle a 10 % de remise sur le sous-total.",
        },
        {
            "key": "P2",
            "title": "Code promotionnel",
            "text": "Le code retire 10 € après la remise de fidélité, sans jamais rendre le montant négatif.",
        },
        {
            "key": "P3",
            "title": "Frais de port",
            "text": "Les frais de port sont de 6,90 € ; ils sont offerts à partir de 80 € après remises.",
        },
    ],
}


def _eur(value: float) -> str:
    return (f"{value:.2f}".replace(".", ",").removesuffix(",00")) + " €"


# (clé, titre, sous-total, client fidèle, code promotionnel)
_PANIERS = [
    ("standard-sans-code", "Client standard, sans code, petit panier", 54.00, False, False),
    ("fidele-sans-code", "Client fidèle, sans code", 120.00, True, False),
    ("fidele-avec-code", "Client fidèle avec un code de 10 €", 85.00, True, True),
    ("standard-avec-code", "Client standard avec un code de 10 €", 95.00, False, True),
    (
        "fidele-seuil-port",
        "Client fidèle : la remise fait repasser sous le seuil du port offert",
        88.00,
        True,
        False,
    ),
]


def _ligne(label: str, op: str, value, result, note: str | None = None) -> dict:
    """Une ligne de calcul en euros."""
    row = {"label": label, "op": op, "value": value, "unit": "€", "result": result}
    if note is not None:
        row["note"] = note
    return row


def _calcul_steps(subtotal: float, fidele: bool, code: bool) -> tuple[list[dict], float, bool]:
    """Les étapes du calcul d'un panier ; rend (étapes, montant à payer, port offert)."""
    total = subtotal
    steps = [
        {
            "title": "Sous-total des articles",
            "changes": {"commande": "EN_COURS"},
            "values": [_ligne("Sous-total des articles", "=", subtotal, subtotal)],
        }
    ]
    if fidele:
        remise = round(total * 0.10, 2)
        total = round(total - remise, 2)
        steps.append(
            {
                "title": "Remise de fidélité",
                "note": "10 % du sous-total (règle P1).",
                "values": [_ligne("Remise de fidélité", "-", remise, total, "10 % du sous-total")],
            }
        )
    if code:
        total = round(max(0, total - 10), 2)
        steps.append(
            {
                "title": "Code promotionnel",
                "note": "Le code s'applique après la remise de fidélité (règle P2).",
                "values": [_ligne("Code promotionnel", "-", 10, total, "après la remise de fidélité")],
            }
        )
    offert = total >= 80
    port = 0 if offert else 6.90
    total = round(total + port, 2)
    steps.append(
        {
            "title": "Frais de port",
            "note": "Offerts à partir de 80 € après remises (règle P3)."
            if offert
            else "Moins de 80 € après remises : le port est dû (règle P3).",
            "values": [
                _ligne(
                    "Frais de port",
                    "+",
                    port,
                    total,
                    "offerts dès 80 €" if offert else "moins de 80 € après remises",
                )
            ],
        }
    )
    steps.append(
        {
            "title": "Montant à payer",
            "changes": {"commande": "CALCULE"},
            "global": "CALCULE",
            "values": [_ligne("Montant à payer", "=", total, total)],
        }
    )
    return steps, total, offert


def calcul_cases() -> list[dict]:
    cases = []
    for key, title, subtotal, fidele, code in _PANIERS:
        steps, total, offert = _calcul_steps(subtotal, fidele, code)
        cases.append(
            {
                "key": key,
                "family": "Client fidèle" if fidele else "Client standard",
                "kind": "decision",
                "title": title,
                "summary": f"Sous-total de {_eur(subtotal)}, montant à payer {_eur(total)}.",
                "rules": [r for r, used in (("P1", fidele), ("P2", code), ("P3", True)) if used],
                "dimensions": {
                    "client": "fidele" if fidele else "standard",
                    "code": "avec" if code else "sans",
                    "port": "offert" if offert else "payant",
                },
                "entities": [{"id": "commande", "label": "Commande", "type": "commande"}],
                "steps": steps,
                "outcome": {"label": f"{_eur(total)} à payer", "status": "CALCULE"},
            }
        )
    return cases


# ---------------------------------------------------------------------------
# 3. Axe à bandes — circuit de validation d'une note de frais
# ---------------------------------------------------------------------------

BANDES = {
    "title": "Validation d'une note de frais",
    "description": "Qui valide une note de frais selon son montant. Les cas se placent juste sous, pile sur "
    "et juste au-dessus de chaque seuil. Exemple pour l'axe à bandes.",
    "kind": "decision",
    "statuses": [
        {"key": "DEPOSEE", "label": "Déposée", "role": "waiting", "default": True},
        {"key": "AUTO", "label": "Validée automatiquement", "short": "Auto", "role": "success"},
        {
            "key": "RESPONSABLE",
            "label": "À valider par le responsable",
            "short": "Responsable",
            "role": "info",
        },
        {"key": "DIRECTION", "label": "À valider par la direction", "short": "Direction", "role": "warning"},
    ],
    "dimensions": [
        {
            "key": "montant",
            "label": "Montant de la note",
            "unit": "€",
            "inclusive": "from",
            "highlight": True,
            "values": [
                {"value": "petit", "label": "Moins de 50 €"},
                {"value": "moyen", "label": "De 50 à 500 €"},
                {"value": "grand", "label": "500 € et plus"},
            ],
            "bands": [
                {"value": "petit", "to": 50, "result": "Validation automatique"},
                {"value": "moyen", "from": 50, "to": 500, "result": "Responsable"},
                {"value": "grand", "from": 500, "result": "Direction"},
            ],
        },
    ],
    "rules": [
        {
            "key": "N1",
            "title": "Petites dépenses",
            "text": "Une note de moins de 50 € est validée sans intervention.",
        },
        {
            "key": "N2",
            "title": "Dépenses courantes",
            "text": "De 50 € inclus à 500 € exclu, le responsable hiérarchique valide.",
        },
        {"key": "N3", "title": "Grosses dépenses", "text": "À partir de 500 €, la direction valide."},
    ],
}


def bandes_cases() -> list[dict]:
    cases = []
    for key, title, amount, band, status, rule in [
        ("montant-12", "Un ticket de parking", 12, "petit", "AUTO", "N1"),
        ("montant-49-99", "Un centime sous le premier seuil", 49.99, "petit", "AUTO", "N1"),
        ("montant-50", "Pile sur le premier seuil", 50, "moyen", "RESPONSABLE", "N2"),
        ("montant-50-01", "Un centime au-dessus du premier seuil", 50.01, "moyen", "RESPONSABLE", "N2"),
        ("montant-180", "Un billet de train", 180, "moyen", "RESPONSABLE", "N2"),
        ("montant-499-99", "Un centime sous le second seuil", 499.99, "moyen", "RESPONSABLE", "N2"),
        ("montant-500", "Pile sur le second seuil", 500, "grand", "DIRECTION", "N3"),
        ("montant-1240", "Un déplacement à l'étranger", 1240, "grand", "DIRECTION", "N3"),
    ]:
        label = next(s["label"] for s in BANDES["statuses"] if s["key"] == status)
        cases.append(
            {
                "key": key,
                "family": {v["value"]: v["label"] for v in BANDES["dimensions"][0]["values"]}[band],
                "kind": "decision",
                "title": title,
                "summary": f"Note de {str(amount).replace('.', ',')} € : {label.lower()}.",
                "rules": [rule],
                "dimensions": {"montant": band},
                "measures": {"montant": amount},
                "entities": [{"id": "note", "label": "Note de frais", "type": "note"}],
                "steps": [
                    {
                        "title": "La note est déposée",
                        "note": f"Montant déclaré : {str(amount).replace('.', ',')} €.",
                    },
                    {
                        "title": "Le montant est comparé aux seuils",
                        "changes": {"note": status},
                        "global": status,
                        "note": f"Règle {rule}.",
                    },
                ],
                "outcome": {"label": label, "status": status},
            }
        )
    return cases


# ---------------------------------------------------------------------------
# 4. Avant / après — changement d'adresse
# ---------------------------------------------------------------------------

AVANT_APRES = {
    "title": "Changement d'adresse d'un assuré",
    "description": "Ce qu'un changement d'adresse modifie dans le dossier client et dans le contrat, champ "
    "par champ. Exemple pour la vue avant / après.",
    "kind": "workflow",
    "statuses": [
        {"key": "INCHANGE", "label": "Inchangé", "role": "neutral", "default": True},
        {"key": "A_JOUR", "label": "Mis à jour", "role": "success"},
        {"key": "REFUSE", "label": "Demande refusée", "short": "Refusée", "role": "error"},
    ],
    "dimensions": [
        {
            "key": "zone",
            "label": "Zone tarifaire",
            "values": [{"value": "meme", "label": "Même zone"}, {"value": "autre", "label": "Autre zone"}],
        },
        {
            "key": "adresse",
            "label": "Adresse saisie",
            "values": [
                {"value": "valide", "label": "Reconnue"},
                {"value": "inconnue", "label": "Non reconnue"},
            ],
        },
    ],
    "exclusions": [
        {
            "when": {"zone": "autre", "adresse": "inconnue"},
            "reason": "Une adresse non reconnue n'a pas de zone : la demande est refusée avant tout calcul.",
        }
    ],
    "rules": [
        {
            "key": "C1",
            "title": "Adresse reconnue",
            "text": "L'adresse saisie doit être reconnue par le référentiel ; sinon rien n'est modifié.",
        },
        {
            "key": "C2",
            "title": "Contrat aligné",
            "text": "L'adresse du risque suit celle du client ; la prime n'est recalculée que si la zone "
            "tarifaire change.",
        },
    ],
}

_CLIENT = {
    "Adresse": "12 rue des Lilas",
    "Code postal": "35000",
    "Ville": "Rennes",
    "Téléphone": "02 55 55 01 23",
}
_CONTRAT = {
    "Adresse du risque": "12 rue des Lilas, 35000 Rennes",
    "Zone tarifaire": "B",
    "Prime mensuelle": "38,50 €",
}


def _adresse_case(key, title, summary, dims, steps, outcome, status) -> dict:
    return {
        "key": key,
        "family": "Changement d'adresse",
        "kind": "workflow",
        "title": title,
        "summary": summary,
        "rules": ["C1", "C2"],
        "dimensions": dims,
        "entities": [
            {"id": "client", "label": "Client", "type": "dossier", "fields": dict(_CLIENT)},
            {"id": "contrat", "label": "Contrat habitation", "type": "contrat", "fields": dict(_CONTRAT)},
        ],
        "steps": steps,
        "outcome": {"label": outcome, "status": status},
    }


def _adresse_meme_zone() -> dict:
    return _adresse_case(
        "meme-zone",
        "Déménagement dans la même zone tarifaire",
        "Le client change de rue dans la même ville : l'adresse change partout, la prime ne bouge pas.",
        {"zone": "meme", "adresse": "valide"},
        [
            {
                "title": "La demande est reçue",
                "note": "Nouvelle adresse saisie : 4 quai Duguay-Trouin, 35000 Rennes.",
            },
            {
                "title": "Le dossier client est mis à jour",
                "changes": {"client": "A_JOUR"},
                "fields": {"client": {"Adresse": "4 quai Duguay-Trouin"}},
            },
            {
                "title": "Le contrat suit l'adresse",
                "changes": {"contrat": "A_JOUR"},
                "global": "A_JOUR",
                "fields": {"contrat": {"Adresse du risque": "4 quai Duguay-Trouin, 35000 Rennes"}},
                "note": "Même zone B : la prime n'est pas recalculée.",
            },
        ],
        "Dossier et contrat à jour, prime inchangée",
        "A_JOUR",
    )


def _adresse_autre_zone() -> dict:
    return _adresse_case(
        "autre-zone",
        "Déménagement dans une autre zone tarifaire",
        "Le client part dans une autre ville : adresse, zone et prime changent.",
        {"zone": "autre", "adresse": "valide"},
        [
            {
                "title": "La demande est reçue",
                "note": "Nouvelle adresse saisie : 27 cours Vitton, 69006 Lyon.",
            },
            {
                "title": "Le dossier client est mis à jour",
                "changes": {"client": "A_JOUR"},
                "fields": {"client": {"Adresse": "27 cours Vitton", "Code postal": "69006", "Ville": "Lyon"}},
            },
            {
                "title": "Le contrat suit l'adresse",
                "changes": {"contrat": "A_JOUR"},
                "fields": {
                    "contrat": {"Adresse du risque": "27 cours Vitton, 69006 Lyon", "Zone tarifaire": "A"}
                },
            },
            {
                "title": "La prime est recalculée",
                "global": "A_JOUR",
                "fields": {"contrat": {"Prime mensuelle": "44,90 €"}},
                "note": "Zone A : la prime passe de 38,50 € à 44,90 €.",
            },
        ],
        "Dossier et contrat à jour, prime recalculée",
        "A_JOUR",
    )


def _adresse_inconnue() -> dict:
    return _adresse_case(
        "adresse-inconnue",
        "Adresse non reconnue",
        "L'adresse saisie n'existe pas dans le référentiel : rien n'est modifié.",
        {"zone": "meme", "adresse": "inconnue"},
        [
            {
                "title": "La demande est reçue",
                "note": "Nouvelle adresse saisie : 999 rue Inexistante, 35000 Rennes.",
            },
            {
                "title": "L'adresse est refusée",
                "changes": {"client": "REFUSE"},
                "global": "REFUSE",
                "note": "Le référentiel ne connaît pas cette adresse : aucun champ n'est touché.",
            },
        ],
        "Demande refusée, aucun champ modifié",
        "REFUSE",
    )


def avant_apres_cases() -> list[dict]:
    return [_adresse_meme_zone(), _adresse_autre_zone(), _adresse_inconnue()]


# ---------------------------------------------------------------------------
# 5. Table de règles — priorité d'un ticket de support
# ---------------------------------------------------------------------------

REGLES_ROWS = [
    (
        "T1",
        {"client": "Premium", "gravite": "Bloquant", "environnement": "Production"},
        "Astreinte immédiate",
        "P1",
    ),
    ("T2", {"gravite": "Bloquant", "environnement": "Production"}, "Prise en charge sous 1 h", "P1"),
    ("T3", {"client": "Premium", "gravite": "Bloquant"}, "Prise en charge sous 4 h", "P2"),
    ("T4", {"gravite": "Bloquant"}, "Prise en charge sous 8 h", "P2"),
    (
        "T5",
        {"client": "Premium", "gravite": "Majeur", "horaire": "Heures ouvrées"},
        "Prise en charge sous 4 h",
        "P2",
    ),
    ("T6", {"gravite": "Majeur", "environnement": "Production"}, "Prise en charge le jour même", "P3"),
    ("T7", {"gravite": "Majeur"}, "Prise en charge sous 2 jours", "P3"),
    ("T8", {"client": "Premium"}, "Prise en charge sous 3 jours", "P4"),
    ("T9", {}, "File d'attente normale", "P4"),
]
REGLES_CONDITIONS = [
    ("client", "Client"),
    ("gravite", "Gravité"),
    ("environnement", "Environnement"),
    ("horaire", "Horaire"),
]

REGLES = {
    "title": "Priorité d'un ticket de support",
    "description": "Quel engagement de prise en charge s'applique à un ticket. Plusieurs lignes "
    "correspondent souvent : la plus haute dans la table l'emporte, les autres sont écartées. Exemple "
    "pour la table de règles.",
    "kind": "decision",
    "statuses": [
        {"key": "OUVERT", "label": "Ouvert", "role": "waiting", "default": True},
        {"key": "P1", "label": "Priorité 1", "short": "P1", "role": "error"},
        {"key": "P2", "label": "Priorité 2", "short": "P2", "role": "warning"},
        {"key": "P3", "label": "Priorité 3", "short": "P3", "role": "info"},
        {"key": "P4", "label": "Priorité 4", "short": "P4", "role": "neutral"},
    ],
    "dimensions": [
        {"key": "client", "label": "Client", "values": ["Premium", "Standard"]},
        {"key": "gravite", "label": "Gravité", "values": ["Bloquant", "Majeur", "Mineur"]},
        {"key": "environnement", "label": "Environnement", "values": ["Production", "Recette"]},
        {"key": "horaire", "label": "Horaire", "values": ["Heures ouvrées", "Nuit et week-end"]},
    ],
    "rules": [
        {
            "key": "S1",
            "title": "Une seule priorité par ticket",
            "text": "Quand plusieurs lignes correspondent, la plus haute dans la table décide ; les autres "
            "sont écartées.",
        }
    ],
    "ruleset": {
        "title": "Engagements de prise en charge",
        "policy": "priority",
        "conditions": [{"key": k, "label": v} for k, v in REGLES_CONDITIONS],
        "rows": [
            {"key": k, "when": when, "then": then, "status": status} for k, when, then, status in REGLES_ROWS
        ],
    },
}


def _rule_fate(values: dict) -> tuple[dict, str]:
    """Sort de chaque ligne pour un ticket, et clé de la ligne retenue."""
    fate, selected = {}, None
    for key, when, _, _ in REGLES_ROWS:
        miss = next(
            (cond for cond, _ in REGLES_CONDITIONS if cond in when and when[cond] != values[cond]), None
        )
        if miss:
            fate[key] = {"result": "failed", "on": miss}
        elif selected is None:
            fate[key], selected = {"result": "selected"}, key
        else:
            fate[key] = {"result": "discarded"}
    return fate, selected


# (clé, titre, valeurs du ticket pour chaque condition)
_TICKETS = [
    (
        "premium-bloquant-prod",
        "Client Premium, incident bloquant en production",
        {
            "client": "Premium",
            "gravite": "Bloquant",
            "environnement": "Production",
            "horaire": "Nuit et week-end",
        },
    ),
    (
        "standard-bloquant-prod",
        "Client standard, incident bloquant en production",
        {
            "client": "Standard",
            "gravite": "Bloquant",
            "environnement": "Production",
            "horaire": "Heures ouvrées",
        },
    ),
    (
        "premium-bloquant-recette",
        "Client Premium, incident bloquant en recette",
        {"client": "Premium", "gravite": "Bloquant", "environnement": "Recette", "horaire": "Heures ouvrées"},
    ),
    (
        "premium-majeur-nuit",
        "Client Premium, incident majeur en production, la nuit",
        {
            "client": "Premium",
            "gravite": "Majeur",
            "environnement": "Production",
            "horaire": "Nuit et week-end",
        },
    ),
    (
        "standard-majeur-recette",
        "Client standard, incident majeur en recette",
        {"client": "Standard", "gravite": "Majeur", "environnement": "Recette", "horaire": "Heures ouvrées"},
    ),
    (
        "premium-mineur",
        "Client Premium, incident mineur",
        {
            "client": "Premium",
            "gravite": "Mineur",
            "environnement": "Production",
            "horaire": "Heures ouvrées",
        },
    ),
    (
        "standard-mineur",
        "Client standard, incident mineur",
        {
            "client": "Standard",
            "gravite": "Mineur",
            "environnement": "Recette",
            "horaire": "Nuit et week-end",
        },
    ),
]


def _ticket_case(key: str, title: str, values: dict) -> dict:
    fate, selected = _rule_fate(values)
    row = next(r for r in REGLES_ROWS if r[0] == selected)
    failed = {k: v for k, v in fate.items() if v["result"] == "failed"}
    matched = {k: v for k, v in fate.items() if v["result"] != "failed"}
    discarded = [k for k, v in matched.items() if v["result"] == "discarded"]
    return {
        "key": key,
        "family": f"Gravité : {values['gravite']}",
        "kind": "decision",
        "title": title,
        "summary": f"Ligne {selected} retenue : {row[2].lower()}."
        + (f" {len(discarded)} autre(s) ligne(s) correspondaient aussi." if discarded else ""),
        "rules": ["S1"],
        "dimensions": values,
        "entities": [{"id": "ticket", "label": "Ticket", "type": "ticket"}],
        "steps": [
            {
                "title": "Les lignes qui ne correspondent pas sont écartées",
                "rows": failed,
                "note": f"{len(failed)} ligne(s) sur {len(REGLES_ROWS)} ont une condition qui diffère du "
                "ticket.",
            },
            {
                "title": "Parmi celles qui correspondent, la plus haute décide",
                "rows": matched,
                "changes": {"ticket": row[3]},
                "global": row[3],
                "note": (
                    f"{', '.join(discarded)} correspondaient aussi, mais sont plus bas dans la table."
                    if discarded
                    else "Une seule ligne correspond."
                ),
            },
        ],
        "outcome": {"label": row[2], "status": row[3]},
    }


def regles_cases() -> list[dict]:
    return [_ticket_case(key, title, dict(values)) for key, title, values in _TICKETS]


# ---------------------------------------------------------------------------
# 6. Arbre de décision — mode de livraison proposé
# ---------------------------------------------------------------------------

ARBRE_ROWS = [
    ("M1", {"destination": "Étranger"}, "Transporteur international", "INTERNATIONAL"),
    ("M2", {"destination": "France", "poids": "Plus de 30 kg"}, "Livraison sur palette", "PALETTE"),
    (
        "M3",
        {"destination": "France", "poids": "De 2 à 30 kg", "urgence": "Urgent"},
        "Colis express",
        "EXPRESS",
    ),
    ("M4", {"destination": "France", "poids": "De 2 à 30 kg"}, "Colis standard", "COLIS"),
    (
        "M5",
        {"destination": "France", "poids": "Moins de 2 kg", "urgence": "Urgent"},
        "Lettre suivie prioritaire",
        "EXPRESS",
    ),
    ("M6", {"destination": "France", "poids": "Moins de 2 kg"}, "Lettre suivie", "LETTRE"),
]

ARBRE = {
    "title": "Mode de livraison proposé",
    "description": "Quel mode de livraison est proposé pour un envoi, question après question : destination, "
    "poids, urgence. Exemple pour l'arbre de décision.",
    "kind": "decision",
    "statuses": [
        {"key": "A_CHOISIR", "label": "À choisir", "role": "waiting", "default": True},
        {"key": "LETTRE", "label": "Lettre suivie", "short": "Lettre", "role": "success"},
        {"key": "COLIS", "label": "Colis standard", "short": "Colis", "role": "success"},
        {"key": "EXPRESS", "label": "Envoi express", "short": "Express", "role": "info"},
        {"key": "PALETTE", "label": "Palette", "role": "warning"},
        {"key": "INTERNATIONAL", "label": "International", "short": "Internat.", "role": "active"},
    ],
    "dimensions": [
        {"key": "destination", "label": "Destination", "values": ["France", "Étranger"]},
        {"key": "poids", "label": "Poids", "values": ["Moins de 2 kg", "De 2 à 30 kg", "Plus de 30 kg"]},
        {"key": "urgence", "label": "Urgence", "values": ["Normal", "Urgent"]},
    ],
    "rules": [
        {
            "key": "L1",
            "title": "Première ligne qui correspond",
            "text": "Les lignes sont lues dans l'ordre ; la première qui correspond donne le mode de "
            "livraison.",
        }
    ],
    "ruleset": {
        "title": "Choix du mode de livraison",
        "policy": "first",
        "conditions": [
            {"key": "destination", "label": "Destination"},
            {"key": "poids", "label": "Poids"},
            {"key": "urgence", "label": "Urgence"},
        ],
        "rows": [
            {"key": k, "when": when, "then": then, "status": status} for k, when, then, status in ARBRE_ROWS
        ],
    },
}


def arbre_cases() -> list[dict]:
    cases = []
    for key, title, values in [
        (
            "etranger",
            "Un colis pour l'étranger",
            {"destination": "Étranger", "poids": "De 2 à 30 kg", "urgence": "Normal"},
        ),
        (
            "palette",
            "Un envoi de 45 kg en France",
            {"destination": "France", "poids": "Plus de 30 kg", "urgence": "Urgent"},
        ),
        (
            "colis-urgent",
            "Un colis de 5 kg, urgent",
            {"destination": "France", "poids": "De 2 à 30 kg", "urgence": "Urgent"},
        ),
        (
            "colis-normal",
            "Un colis de 5 kg, sans urgence",
            {"destination": "France", "poids": "De 2 à 30 kg", "urgence": "Normal"},
        ),
        (
            "lettre-urgente",
            "Un pli de 300 g, urgent",
            {"destination": "France", "poids": "Moins de 2 kg", "urgence": "Urgent"},
        ),
        (
            "lettre-normale",
            "Un pli de 300 g, sans urgence",
            {"destination": "France", "poids": "Moins de 2 kg", "urgence": "Normal"},
        ),
    ]:
        steps, chosen = [], None
        for row_key, when, then, status in ARBRE_ROWS:
            miss = next(
                (c for c in ("destination", "poids", "urgence") if c in when and when[c] != values[c]), None
            )
            if miss:
                steps.append(
                    {
                        "title": f"Ligne {row_key} : ne correspond pas",
                        "rows": {row_key: {"result": "failed", "on": miss}},
                        "note": f"La ligne attend « {when[miss]} » ; l'envoi a « {values[miss]} ».",
                    }
                )
            else:
                chosen = (row_key, then, status)
                steps.append(
                    {
                        "title": f"Ligne {row_key} : correspond, la lecture s'arrête",
                        "rows": {row_key: "selected"},
                        "changes": {"envoi": status},
                        "global": status,
                        "note": f"Mode proposé : {then.lower()}.",
                    }
                )
                break
        cases.append(
            {
                "key": key,
                "family": values["destination"],
                "kind": "decision",
                "title": title,
                "summary": f"Ligne {chosen[0]} : {chosen[1].lower()}.",
                "rules": ["L1"],
                "dimensions": values,
                "entities": [{"id": "envoi", "label": "Envoi", "type": "envoi"}],
                "steps": steps,
                "outcome": {"label": chosen[1], "status": chosen[2]},
            }
        )
    return cases


# ---------------------------------------------------------------------------
# 7. Table d'états — document soumis à validation (cycle dense)
# ---------------------------------------------------------------------------

DOC_TRANSITIONS = [
    ("BROUILLON", "BROUILLON", "modifier"),
    ("BROUILLON", "RELECTURE", "soumettre"),
    ("BROUILLON", "ARCHIVE", "archiver"),
    ("RELECTURE", "CORRECTION", "demander des corrections"),
    ("RELECTURE", "APPROUVE", "approuver"),
    ("RELECTURE", "BROUILLON", "retirer"),
    ("CORRECTION", "CORRECTION", "modifier"),
    ("CORRECTION", "RELECTURE", "soumettre"),
    ("CORRECTION", "ARCHIVE", "archiver"),
    ("APPROUVE", "PUBLIE", "publier"),
    ("APPROUVE", "CORRECTION", "demander des corrections"),
    ("APPROUVE", "ARCHIVE", "archiver"),
    ("PUBLIE", "APPROUVE", "retirer"),
    ("PUBLIE", "ARCHIVE", "archiver"),
    ("ARCHIVE", "BROUILLON", "restaurer"),
]

TABLE_ETATS = {
    "title": "Validation d'un document",
    "description": "Ce qu'on peut faire d'un document selon son état : six états, huit évènements, et "
    "beaucoup de combinaisons interdites. Exemple pour la table d'états.",
    "kind": "workflow",
    "statuses": [
        {"key": "BROUILLON", "label": "Brouillon", "role": "neutral", "default": True},
        {"key": "RELECTURE", "label": "En relecture", "short": "Relecture", "role": "active"},
        {"key": "CORRECTION", "label": "À corriger", "role": "warning"},
        {"key": "APPROUVE", "label": "Approuvé", "role": "info"},
        {"key": "PUBLIE", "label": "Publié", "role": "success"},
        {"key": "ARCHIVE", "label": "Archivé", "role": "disabled"},
    ],
    "dimensions": [
        {
            "key": "parcours",
            "label": "Parcours",
            "values": [
                {"value": "direct", "label": "Sans correction"},
                {"value": "corrections", "label": "Avec corrections"},
                {"value": "retrait", "label": "Retrait après publication"},
            ],
        },
    ],
    "rules": [
        {
            "key": "D1",
            "title": "Relecture obligatoire",
            "text": "Un document n'est publié qu'après avoir été approuvé en relecture.",
        },
        {
            "key": "D2",
            "title": "Un document publié ne se modifie pas",
            "text": "Pour corriger un document publié, il faut d'abord le retirer.",
        },
    ],
    "lifecycles": [
        {
            "type": "document",
            "title": "Cycle de vie d'un document",
            "initial": "BROUILLON",
            "transitions": [{"from": a, "to": b, "label": label} for a, b, label in DOC_TRANSITIONS],
        }
    ],
}


def _walk(steps: list[tuple[str, str, str]], entity: str) -> list[dict]:
    return [
        {"title": title, "changes": {entity: status}, "global": status, **({"note": note} if note else {})}
        for title, status, note in steps
    ]


def _document_case(key, title, summary, parcours, steps, final, label) -> dict:
    return {
        "key": key,
        "family": "Parcours d'un document",
        "kind": "workflow",
        "title": title,
        "summary": summary,
        "rules": ["D1", "D2"],
        "dimensions": {"parcours": parcours},
        "entities": [{"id": "doc", "label": "Procédure qualité", "type": "document"}],
        "initial": {"doc": "BROUILLON"},
        "steps": _walk(steps, "doc"),
        "outcome": {"label": label, "status": final},
    }


# (clé, titre, résumé, dimension « parcours », étapes (titre, état, note), état final, libellé du résultat)
_DOCUMENTS = [
    (
        "publication-directe",
        "Publication sans correction",
        "Le document est soumis, approuvé puis publié.",
        "direct",
        [
            (
                "L'auteur complète le brouillon",
                "BROUILLON",
                "L'évènement « modifier » laisse le document en brouillon.",
            ),
            ("L'auteur soumet le document", "RELECTURE", ""),
            ("Le relecteur approuve", "APPROUVE", ""),
            ("Le document est publié", "PUBLIE", ""),
        ],
        "PUBLIE",
        "Document publié",
    ),
    (
        "aller-retour-corrections",
        "Deux allers-retours de correction",
        "Le relecteur demande des corrections à deux reprises avant d'approuver.",
        "corrections",
        [
            ("L'auteur soumet le document", "RELECTURE", ""),
            ("Le relecteur demande des corrections", "CORRECTION", ""),
            ("L'auteur corrige", "CORRECTION", "« modifier » ne change pas l'état."),
            ("L'auteur soumet à nouveau", "RELECTURE", ""),
            ("Le relecteur demande encore des corrections", "CORRECTION", ""),
            ("L'auteur soumet une troisième fois", "RELECTURE", ""),
            ("Le relecteur approuve", "APPROUVE", ""),
            ("Le document est publié", "PUBLIE", ""),
        ],
        "PUBLIE",
        "Document publié après corrections",
    ),
    (
        "retrait-apres-publication",
        "Retrait d'un document publié",
        "Une erreur est trouvée après publication : le document est retiré, corrigé, puis republié.",
        "retrait",
        [
            ("L'auteur soumet le document", "RELECTURE", ""),
            ("Le relecteur approuve", "APPROUVE", ""),
            ("Le document est publié", "PUBLIE", ""),
            (
                "Une erreur est signalée : le document est retiré",
                "APPROUVE",
                "Un document publié ne se modifie pas : il repasse d'abord à « Approuvé ».",
            ),
            ("Des corrections sont demandées", "CORRECTION", ""),
            ("L'auteur soumet la version corrigée", "RELECTURE", ""),
            ("Le relecteur approuve", "APPROUVE", ""),
            ("Le document est republié", "PUBLIE", ""),
        ],
        "PUBLIE",
        "Document republié",
    ),
    (
        "abandon-et-restauration",
        "Archivage puis restauration",
        "Un brouillon abandonné est archivé, puis restauré pour être repris.",
        "direct",
        [
            ("Le brouillon est archivé", "ARCHIVE", ""),
            (
                "Le document est restauré",
                "BROUILLON",
                "Depuis « Archivé », seul « restaurer » est permis.",
            ),
            ("L'auteur soumet le document", "RELECTURE", ""),
        ],
        "RELECTURE",
        "Document en relecture",
    ),
]


def table_etats_cases() -> list[dict]:
    return [_document_case(*row) for row in _DOCUMENTS]


# ---------------------------------------------------------------------------
# 8. Diagramme d'états — commande en ligne (cycle clairsemé, boucle et retour)
# ---------------------------------------------------------------------------

CMD_TRANSITIONS = [
    ("PANIER", "PAIEMENT", "valider le panier"),
    ("PAIEMENT", "PAIEMENT", "paiement refusé"),
    ("PAIEMENT", "PANIER", "abandonner"),
    ("PAIEMENT", "PAYEE", "paiement accepté"),
    ("PAYEE", "EXPEDIEE", "expédier"),
    ("PAYEE", "ANNULEE", "annuler"),
    ("EXPEDIEE", "LIVREE", "livrer"),
    ("LIVREE", "RETOUR", "demander un retour"),
    ("RETOUR", "REMBOURSEE", "rembourser"),
]

DIAGRAMME_ETATS = {
    "title": "Cycle de vie d'une commande en ligne",
    "description": "Le parcours d'une commande, du panier à la livraison, avec le paiement refusé qui boucle "
    "et l'abandon qui ramène au panier. Exemple pour le diagramme d'états.",
    "kind": "workflow",
    "statuses": [
        {"key": "PANIER", "label": "Panier", "role": "neutral", "default": True},
        {"key": "PAIEMENT", "label": "Paiement en attente", "short": "Paiement", "role": "waiting"},
        {"key": "PAYEE", "label": "Payée", "role": "info"},
        {"key": "EXPEDIEE", "label": "Expédiée", "role": "active"},
        {"key": "LIVREE", "label": "Livrée", "role": "success"},
        {"key": "RETOUR", "label": "Retour demandé", "short": "Retour", "role": "warning"},
        {"key": "REMBOURSEE", "label": "Remboursée", "short": "Rembours.", "role": "blocked"},
        {"key": "ANNULEE", "label": "Annulée", "role": "error"},
    ],
    "dimensions": [
        {
            "key": "issue",
            "label": "Issue",
            "values": [
                {"value": "livree", "label": "Livrée"},
                {"value": "annulee", "label": "Annulée"},
                {"value": "remboursee", "label": "Remboursée"},
                {"value": "abandonnee", "label": "Abandonnée"},
            ],
        },
    ],
    "rules": [
        {
            "key": "O1",
            "title": "Paiement avant expédition",
            "text": "Une commande n'est expédiée qu'une fois payée.",
        },
        {
            "key": "O2",
            "title": "Annulation",
            "text": "Une commande payée peut être annulée tant qu'elle n'est pas expédiée.",
        },
    ],
    "lifecycles": [
        {
            "type": "commande",
            "title": "Cycle de vie d'une commande",
            "initial": "PANIER",
            "transitions": [{"from": a, "to": b, "label": label} for a, b, label in CMD_TRANSITIONS],
        }
    ],
}


def _commande_case(key, title, summary, issue, steps, final, label) -> dict:
    return {
        "key": key,
        "family": "Parcours d'une commande",
        "kind": "workflow",
        "title": title,
        "summary": summary,
        "rules": ["O1", "O2"],
        "dimensions": {"issue": issue},
        "entities": [{"id": "commande", "label": "Commande n° 1042", "type": "commande"}],
        "initial": {"commande": "PANIER"},
        "steps": _walk(steps, "commande"),
        "outcome": {"label": label, "status": final},
    }


# (clé, titre, résumé, dimension « issue », étapes (titre, état, note), état final, libellé du résultat)
_COMMANDES = [
    (
        "livraison-nominale",
        "Commande payée du premier coup et livrée",
        "Le parcours sans incident.",
        "livree",
        [
            ("Le client valide son panier", "PAIEMENT", ""),
            ("Le paiement est accepté", "PAYEE", ""),
            ("Le colis part de l'entrepôt", "EXPEDIEE", ""),
            ("Le colis est remis au client", "LIVREE", ""),
        ],
        "LIVREE",
        "Commande livrée",
    ),
    (
        "paiement-refuse-puis-accepte",
        "Paiement refusé deux fois, puis accepté",
        (
            "La carte est refusée à deux reprises : la commande reste en attente de paiement, "
            "puis le troisième essai passe."
        ),
        "livree",
        [
            ("Le client valide son panier", "PAIEMENT", ""),
            (
                "Premier paiement refusé",
                "PAIEMENT",
                "La commande reste dans le même état : c'est une boucle.",
            ),
            ("Deuxième paiement refusé", "PAIEMENT", ""),
            ("Le troisième paiement est accepté", "PAYEE", ""),
            ("Le colis part de l'entrepôt", "EXPEDIEE", ""),
            ("Le colis est remis au client", "LIVREE", ""),
        ],
        "LIVREE",
        "Commande livrée",
    ),
    (
        "abandon-puis-reprise",
        "Paiement abandonné, panier repris",
        "Le client abandonne au moment de payer, revient au panier, puis valide de nouveau.",
        "abandonnee",
        [
            ("Le client valide son panier", "PAIEMENT", ""),
            ("Le client abandonne le paiement", "PANIER", "Retour en arrière : le panier est conservé."),
            ("Le client valide de nouveau son panier", "PAIEMENT", ""),
        ],
        "PAIEMENT",
        "Paiement en attente",
    ),
    (
        "annulation-avant-expedition",
        "Commande annulée avant l'expédition",
        "Le client annule une commande payée qui n'est pas encore partie.",
        "annulee",
        [
            ("Le client valide son panier", "PAIEMENT", ""),
            ("Le paiement est accepté", "PAYEE", ""),
            (
                "Le client annule la commande",
                "ANNULEE",
                "Permis parce que le colis n'est pas parti (règle O2).",
            ),
        ],
        "ANNULEE",
        "Commande annulée",
    ),
    (
        "retour-et-remboursement",
        "Commande livrée, retournée et remboursée",
        "Le client renvoie le produit après livraison.",
        "remboursee",
        [
            ("Le client valide son panier", "PAIEMENT", ""),
            ("Le paiement est accepté", "PAYEE", ""),
            ("Le colis part de l'entrepôt", "EXPEDIEE", ""),
            ("Le colis est remis au client", "LIVREE", ""),
            ("Le client demande un retour", "RETOUR", ""),
            ("Le produit est reçu : le client est remboursé", "REMBOURSEE", ""),
        ],
        "REMBOURSEE",
        "Commande remboursée",
    ),
]


def diagramme_etats_cases() -> list[dict]:
    return [_commande_case(*row) for row in _COMMANDES]


# ---------------------------------------------------------------------------
# 9. Diagramme de séquence — paiement par carte
# ---------------------------------------------------------------------------

SEQUENCE = {
    "title": "Paiement par carte d'une commande",
    "description": "Les échanges entre le client, la boutique, le prestataire de paiement et la banque, dans "
    "l'ordre, y compris quand une réponse se perd. Exemple pour le diagramme de séquence.",
    "kind": "workflow",
    "statuses": [
        {"key": "ATTEND", "label": "En attente", "role": "waiting", "default": True},
        {"key": "TRAITE", "label": "Traite la demande", "short": "Traite", "role": "active"},
        {"key": "TERMINE", "label": "A répondu", "role": "success"},
        {"key": "REFUSE", "label": "A refusé", "role": "error"},
        {"key": "SANS_REPONSE", "label": "Sans réponse", "short": "Muet", "role": "warning"},
    ],
    "dimensions": [
        {
            "key": "issue",
            "label": "Issue du paiement",
            "values": [
                {"value": "accepte", "label": "Accepté"},
                {"value": "refuse", "label": "Refusé"},
                {"value": "relance", "label": "Accepté après relance"},
            ],
        },
    ],
    "rules": [
        {
            "key": "Q1",
            "title": "Autorisation avant confirmation",
            "text": "La boutique ne confirme la commande qu'après l'accord de la banque, transmis par le "
            "prestataire.",
        },
        {
            "key": "Q2",
            "title": "Relance",
            "text": "Sans réponse du prestataire sous 30 secondes, la boutique relance une fois la même "
            "demande.",
        },
    ],
}

_ACTEURS = [
    {"id": "client", "label": "Client", "type": "acteur"},
    {"id": "boutique", "label": "Boutique en ligne", "type": "acteur"},
    {"id": "psp", "label": "Prestataire de paiement", "type": "acteur"},
    {"id": "banque", "label": "Banque du client", "type": "acteur"},
]


def _paiement_case(key, title, summary, issue, steps, label, status) -> dict:
    return {
        "key": key,
        "family": "Paiement",
        "kind": "workflow",
        "title": title,
        "summary": summary,
        "rules": ["Q1", "Q2"],
        "dimensions": {"issue": issue},
        "entities": [dict(a) for a in _ACTEURS],
        "steps": steps,
        "outcome": {"label": label, "status": status},
    }


def _paiement_debut() -> list[dict]:
    """Les deux premières étapes, communes aux trois cas."""
    return [
        {
            "title": "Le client valide sa commande",
            "changes": {"boutique": "TRAITE"},
            "messages": [{"from": "client", "to": "boutique", "label": "Valider la commande"}],
        },
        {
            "title": "La boutique demande l'autorisation",
            "changes": {"psp": "TRAITE"},
            "messages": [{"from": "boutique", "to": "psp", "label": "Demande d'autorisation"}],
        },
    ]


def _paiement_accepte(debut: list[dict]) -> dict:
    return _paiement_case(
        "paiement-accepte",
        "Paiement accepté",
        "La banque autorise : la commande est confirmée.",
        "accepte",
        [
            *debut,
            {
                "title": "Le prestataire interroge la banque",
                "changes": {"banque": "TRAITE"},
                "messages": [
                    {"from": "psp", "to": "banque", "label": "Autoriser 86,40 € ?"},
                    {"from": "banque", "to": "banque", "label": "Vérifie le solde"},
                ],
            },
            {
                "title": "La banque autorise",
                "changes": {"banque": "TERMINE", "psp": "TERMINE"},
                "messages": [
                    {"from": "banque", "to": "psp", "label": "Autorisé"},
                    {"from": "psp", "to": "boutique", "label": "Paiement accepté"},
                ],
            },
            {
                "title": "La boutique confirme la commande",
                "changes": {"boutique": "TERMINE", "client": "TERMINE"},
                "global": "TERMINE",
                "messages": [{"from": "boutique", "to": "client", "label": "Commande confirmée"}],
            },
        ],
        "Commande confirmée",
        "TERMINE",
    )


def _paiement_refuse(debut: list[dict]) -> dict:
    return _paiement_case(
        "paiement-refuse",
        "Paiement refusé par la banque",
        "La banque refuse : la boutique propose un autre moyen de paiement.",
        "refuse",
        [
            *debut,
            {
                "title": "Le prestataire interroge la banque",
                "changes": {"banque": "TRAITE"},
                "messages": [{"from": "psp", "to": "banque", "label": "Autoriser 86,40 € ?"}],
            },
            {
                "title": "La banque refuse",
                "changes": {"banque": "REFUSE", "psp": "TERMINE"},
                "messages": [
                    {"from": "banque", "to": "psp", "label": "Refusé : plafond atteint"},
                    {"from": "psp", "to": "boutique", "label": "Paiement refusé"},
                ],
            },
            {
                "title": "La boutique propose un autre moyen",
                "changes": {"boutique": "TERMINE"},
                "global": "REFUSE",
                "messages": [
                    {"from": "boutique", "to": "client", "label": "Choisir un autre moyen de paiement"}
                ],
            },
        ],
        "Paiement refusé",
        "REFUSE",
    )


def _paiement_relance(debut: list[dict]) -> dict:
    return _paiement_case(
        "reponse-perdue-puis-relance",
        "Réponse perdue, puis relance",
        "La réponse du prestataire n'arrive pas : la boutique relance une fois et obtient l'accord.",
        "relance",
        [
            *debut,
            {
                "title": "Le prestataire interroge la banque, qui autorise",
                "changes": {"banque": "TERMINE"},
                "messages": [
                    {"from": "psp", "to": "banque", "label": "Autoriser 86,40 € ?"},
                    {"from": "banque", "to": "psp", "label": "Autorisé"},
                ],
            },
            {
                "title": "La réponse du prestataire se perd",
                "changes": {"psp": "SANS_REPONSE"},
                "note": "La boutique attend 30 secondes sans rien recevoir (règle Q2).",
                "messages": [
                    {"from": "psp", "to": "boutique", "label": "Paiement accepté", "status": "lost"}
                ],
            },
            {
                "title": "La boutique relance la même demande",
                "changes": {"psp": "TRAITE"},
                "messages": [{"from": "boutique", "to": "psp", "label": "Demande d'autorisation (relance)"}],
            },
            {
                "title": "Le prestataire répond sans réinterroger la banque",
                "changes": {"psp": "TERMINE"},
                "note": "La demande porte le même identifiant : le prestataire renvoie sa première réponse.",
                "messages": [{"from": "psp", "to": "boutique", "label": "Paiement accepté"}],
            },
            {
                "title": "La boutique confirme la commande",
                "changes": {"boutique": "TERMINE", "client": "TERMINE"},
                "global": "TERMINE",
                "messages": [{"from": "boutique", "to": "client", "label": "Commande confirmée"}],
            },
        ],
        "Commande confirmée après relance",
        "TERMINE",
    )


def sequence_cases() -> list[dict]:
    debut = _paiement_debut()
    return [_paiement_accepte(debut), _paiement_refuse(debut), _paiement_relance(debut)]


# (slug de la représentation illustrée, définition de l'étude, cas)
STUDIES = [
    ("matrice-croisee", MATRICE, matrice_cases),
    ("calcul-pas-a-pas", CALCUL, calcul_cases),
    ("axe-a-bandes", BANDES, bandes_cases),
    ("avant-apres", AVANT_APRES, avant_apres_cases),
    ("table-regles", REGLES, regles_cases),
    ("arbre-decision", ARBRE, arbre_cases),
    ("table-etats", TABLE_ETATS, table_etats_cases),
    ("diagramme-etats", DIAGRAMME_ETATS, diagramme_etats_cases),
    ("diagramme-sequence", SEQUENCE, sequence_cases),
]
