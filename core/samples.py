"""Exemples affichés sur la page Briques pour les représentations du catalogue élargi.

Ils viennent des études de démonstration (données fictives) : mêmes définitions, mêmes cas,
validés par le même chemin qu'un dépôt par l'API.
"""

from __future__ import annotations

from functools import cache

from . import casemodel, extensions
from .demo import elargi

# Cas montré pour chaque représentation (rang dans l'étude de démonstration) et étape affichée
SHOWN = {
    "matrice-croisee": (4, 2),
    "calcul-pas-a-pas": (2, 2),
    "axe-a-bandes": (2, 1),
    "avant-apres": (1, 2),
    "table-regles": (3, 1),
    "arbre-decision": (2, 2),
    "table-etats": (1, 3),
    "diagramme-etats": (1, 3),
    "diagramme-sequence": (2, 3),
}


# Démonstration de l'accueil : le cycle de vie d'une commande, en un seul parcours qui passe par presque tous
# les états (la boucle du paiement refusé, la livraison, le retour, le remboursement).
HOME_CASE = {
    "key": "accueil",
    "family": "Parcours d'une commande",
    "kind": "workflow",
    "title": "Une commande, du panier au remboursement",
    "summary": "Paiement refusé une fois, puis accepté ; la commande est livrée, retournée et remboursée.",
    "rules": ["O1", "O2"],
    "dimensions": {"issue": "remboursee"},
    "entities": [{"id": "commande", "label": "Commande n° 1042", "type": "commande"}],
    "initial": {"commande": "PANIER"},
    "steps": elargi._walk(
        [
            ("Le client valide son panier", "PAIEMENT", ""),
            ("La banque refuse le paiement", "PAIEMENT", "La commande reste en attente : c'est une boucle."),
            ("Le deuxième essai est accepté", "PAYEE", ""),
            ("Le colis part de l'entrepôt", "EXPEDIEE", ""),
            ("Le colis est remis au client", "LIVREE", ""),
            ("Le client demande un retour", "RETOUR", ""),
            ("Le produit revient : le client est remboursé", "REMBOURSEE", ""),
        ],
        "commande",
    ),
    "outcome": {"label": "Commande remboursée", "status": "REMBOURSEE"},
}


def home_sample() -> dict:
    """L'exemple du diagramme d'états, sur le parcours de l'accueil, montré depuis la première étape."""
    return extended_sample("diagramme-etats", home=True)


@cache
def extended_sample(slug: str, home: bool = False) -> dict | None:
    entry = next((item for item in elargi.STUDIES if item[0] == slug), None)
    if entry is None:
        return None
    _, definition, build = entry
    report = casemodel.Report()
    statuses = casemodel.normalize_statuses(definition["statuses"], report)
    dimensions = casemodel.normalize_dimensions(definition.get("dimensions"), report)
    keys = {s["key"] for s in statuses}
    ruleset = extensions.normalize_ruleset(definition.get("ruleset"), keys, report)
    lifecycles = extensions.normalize_lifecycles(definition.get("lifecycles"), keys, report)
    ctx = casemodel.StudyContext(
        statuses=statuses,
        dimensions=dimensions,
        rules=casemodel.normalize_rules(definition.get("rules"), report),
        kind=definition["kind"],
        ruleset=ruleset,
        lifecycles=lifecycles,
    )
    cases = []
    for number, raw in enumerate([HOME_CASE] if home else build(), start=1):
        case, case_report = casemodel.normalize_case(raw, ctx)
        if case is None:
            raise ValueError(f"Exemple « {slug} » invalide : {[i.as_dict() for i in case_report.errors][:2]}")
        case["number"] = number
        cases.append(case)
    index, step = (0, 0) if home else SHOWN[slug]
    siblings = [
        {
            "key": c["key"],
            "number": c["number"],
            "label": "",
            "title": c["title"],
            "family": c["family"],
            "dimensions": c["dimensions"],
            "outcome": (c.get("outcome") or {}).get("label"),
            "outcome_status": (c.get("outcome") or {}).get("status"),
            "measures": c.get("measures") or {},
        }
        for c in cases
    ]
    return {
        "title": definition["title"],
        "statuses": statuses,
        "dimensions": dimensions,
        "ruleset": ruleset,
        "lifecycles": lifecycles,
        "case": cases[min(index, len(cases) - 1)],
        "siblings": siblings,
        "step": step,
    }
