"""Étude de démonstration : la facture d'une librairie, avec son atelier de calcul.

On pose des livres, de la papeterie, des coupons ; l'étude déclare les lignes de la facture (totaux, remise
adhérent, coupons, port, plancher, arrondi) et l'atelier les applique dans l'ordre. Rien, dans le site, ne
connaît cette librairie : tout tient dans la déclaration. Données fictives.

Les cas sont ceux que l'atelier enregistre pour les situations décrites ici : le moteur les écrit, ils se
relisent comme n'importe quel cas.
"""

from __future__ import annotations

from core import calc
from core.casemodel import Report

TITLE = "Facture d'une librairie"


def _price(label: str, high: float, default: float) -> dict:
    return {
        "key": "prix",
        "label": label,
        "number": {"min": 0, "max": high, "step": 0.01},
        "default": default,
        "unit": "€",
    }


QUANTITE = {"key": "quantite", "label": "Quantité", "number": {"min": 1, "max": 10, "step": 1}, "default": 1}


def _each(kind: str) -> dict:
    return {"sum": {"type": kind, "of": {"mul": [{"option": "prix"}, {"option": "quantite"}]}}}


WORKSHOP = {
    "family": "calc",
    "title": "Composer une facture",
    "bricks": [
        {"type": "livre", "label": "Livre", "options": [_price("Prix", 200, 15), QUANTITE]},
        {"type": "papeterie", "label": "Papeterie", "options": [_price("Prix", 50, 4), QUANTITE]},
        {
            "type": "coupon",
            "label": "Coupon",
            "options": [
                {
                    "key": "valeur",
                    "label": "Valeur",
                    "number": {"min": 1, "max": 50, "step": 1},
                    "default": 5,
                    "unit": "€",
                }
            ],
        },
    ],
    "settings": [
        {
            "key": "client",
            "label": "Client",
            "values": ["particulier", "adhérent"],
            "dimension": {"key": "client", "values": {"particulier": "particulier", "adherent": "adhérent"}},
        },
        {
            "key": "livraison",
            "label": "Livraison",
            "values": ["retrait", "domicile"],
            "dimension": {"key": "livraison", "values": {"retrait": "retrait", "domicile": "domicile"}},
        },
    ],
    "lines": [
        {"key": "livres", "label": "Livres", "op": "=", "value": _each("livre"), "unit": "€"},
        {"key": "papeterie", "label": "Papeterie", "op": "+", "value": _each("papeterie"), "unit": "€"},
        {
            "key": "adherent",
            "label": "Remise adhérent : 5 % des livres",
            "when": {"setting": {"client": "adhérent"}},
            "op": "-",
            "value": {"pct": [{"line": "livres"}, 5]},
            "unit": "€",
        },
        {
            "key": "coupons",
            "label": "Coupons, sans dépasser le montant dû",
            "when": {"elements": {"type": "coupon", "count": {"gte": 1}}},
            "op": "-",
            "value": {"min": [{"sum": {"type": "coupon", "of": {"option": "valeur"}}}, {"total": True}]},
            "unit": "€",
        },
        {
            "key": "port",
            "label": "Port à domicile sous 35 €, par paliers",
            "when": {"setting": {"livraison": "domicile"}, "total": {"lt": 35}},
            "op": "+",
            "value": {
                "scale": {"of": {"total": True}, "brackets": [{"upto": 15, "amount": 6.9}, {"amount": 4.9}]}
            },
            "unit": "€",
        },
        {"key": "arrondi", "label": "Arrondi au centime", "op": "arrondi", "value": 0.01},
    ],
    "result": {"label": "Montant à payer", "unit": "€"},
    "states": {"applied": "APPLIQUEE", "skipped": "SANS_OBJET", "blocked": "BLOQUEE"},
    "outcome": [
        {"when": {"total": {"gt": 0}}, "label": "Facture à régler", "status": "A_REGLER"},
        {"label": "Rien à régler", "status": "REGLEE"},
    ],
}

DEFINITION = {
    "title": TITLE,
    "description": "Le montant d'une facture de librairie se construit ligne après ligne : livres, "
    "papeterie, remise adhérent, coupons, port, arrondi. Exemple d'étude qui déclare un atelier de calcul : "
    "on y pose ses propres articles et on voit chaque ligne et le cumul.",
    "kind": "decision",
    "statuses": [
        {"key": "A_CALCULER", "label": "À calculer", "role": "waiting", "default": True},
        {"key": "APPLIQUEE", "label": "Appliquée", "role": "success"},
        {"key": "SANS_OBJET", "label": "Sans objet", "role": "disabled"},
        {"key": "BLOQUEE", "label": "Bloquée", "role": "error"},
        {"key": "A_REGLER", "label": "À régler", "role": "active"},
        {"key": "REGLEE", "label": "Rien à régler", "role": "neutral"},
    ],
    "dimensions": [
        {
            "key": "client",
            "label": "Client",
            "values": [
                {"value": "particulier", "label": "Particulier"},
                {"value": "adherent", "label": "Adhérent"},
            ],
        },
        {
            "key": "livraison",
            "label": "Livraison",
            "values": [
                {"value": "retrait", "label": "Retrait en librairie"},
                {"value": "domicile", "label": "À domicile"},
            ],
        },
        {
            "key": "coupon",
            "label": "Coupon",
            "values": [
                {"value": "aucun", "label": "Aucun coupon"},
                {"value": "partiel", "label": "Coupon plus petit que le montant"},
                {"value": "couvre", "label": "Coupon qui couvre tout"},
            ],
        },
    ],
    "rules": [
        {
            "key": "F1",
            "title": "Le total",
            "text": "Les livres puis la papeterie : prix unitaire × quantité.",
        },
        {
            "key": "F2",
            "title": "Remise adhérent",
            "text": "Un adhérent a 5 % de remise sur les livres seulement.",
        },
        {
            "key": "F3",
            "title": "Coupons",
            "text": "Les coupons se déduisent ensemble, sans rendre de monnaie : au plus le montant dû.",
        },
        {
            "key": "F4",
            "title": "Port",
            "text": "La livraison à domicile coûte 4,90 € quand la facture fait moins de 35 €, et 6,90 € "
            "sous 15 €.",
        },
    ],
    "attributes": [
        {"key": "prix", "label": "Prix unitaire", "text": "Le prix d'un exemplaire, en euros."},
        {"key": "quantite", "label": "Quantité", "text": "Le nombre d'exemplaires."},
        {"key": "valeur", "label": "Valeur du coupon", "text": "Ce que le coupon déduit, en euros."},
    ],
    "workshop": WORKSHOP,
}


def _book(key: str, prix: float, quantite: int = 1) -> dict:
    return {"id": key, "type": "livre", "options": {"prix": prix, "quantite": quantite}}


# (clé, titre, résumé, briques, réglages, dimensions, règles)
_SITUATIONS = [
    (
        "un-livre-retrait",
        "Un livre retiré en librairie",
        "Le cas le plus simple : une ligne, l'arrondi.",
        [_book("A", 18.5)],
        {},
        {"client": "particulier", "livraison": "retrait", "coupon": "aucun"},
        ["F1"],
    ),
    (
        "port-sous-seuil",
        "Petite commande livrée",
        "Sous 35 €, la livraison à domicile ajoute le port.",
        [_book("A", 12), {"id": "B", "type": "papeterie", "options": {"prix": 3.5, "quantite": 2}}],
        {"livraison": "domicile"},
        {"client": "particulier", "livraison": "domicile", "coupon": "aucun"},
        ["F1", "F4"],
    ),
    (
        "port-petite-commande",
        "Très petite commande livrée",
        "Sous 15 €, le port passe au palier le plus haut.",
        [_book("A", 9)],
        {"livraison": "domicile"},
        {"client": "particulier", "livraison": "domicile", "coupon": "aucun"},
        ["F1", "F4"],
    ),
    (
        "port-offert",
        "Grosse commande livrée",
        "À 35 € ou plus, le port n'est pas dû.",
        [_book("A", 22, 2)],
        {"livraison": "domicile"},
        {"client": "particulier", "livraison": "domicile", "coupon": "aucun"},
        ["F1", "F4"],
    ),
    (
        "adherent-livres",
        "Un adhérent achète des livres et un carnet",
        "La remise ne porte que sur les livres, pas sur la papeterie.",
        [_book("A", 20), {"id": "B", "type": "papeterie", "options": {"prix": 6, "quantite": 1}}],
        {"client": "adhérent"},
        {"client": "adherent", "livraison": "retrait", "coupon": "aucun"},
        ["F1", "F2"],
    ),
    (
        "coupon-partiel",
        "Un coupon plus petit que la facture",
        "Le coupon se déduit en entier.",
        [_book("A", 16), {"id": "B", "type": "coupon", "options": {"valeur": 5}}],
        {},
        {"client": "particulier", "livraison": "retrait", "coupon": "partiel"},
        ["F1", "F3"],
    ),
    (
        "coupon-couvre-tout",
        "Un coupon qui couvre tout",
        "Le coupon s'arrête au montant dû : rien à régler.",
        [_book("A", 7.5), {"id": "B", "type": "coupon", "options": {"valeur": 10}}],
        {},
        {"client": "particulier", "livraison": "retrait", "coupon": "couvre"},
        ["F1", "F3"],
    ),
    (
        "coupon-puis-port",
        "Un coupon fait passer la commande sous le seuil du port",
        "Le port se décide après les coupons : la facture repasse sous 35 €.",
        [_book("A", 38), {"id": "B", "type": "coupon", "options": {"valeur": 5}}],
        {"livraison": "domicile"},
        {"client": "particulier", "livraison": "domicile", "coupon": "partiel"},
        ["F1", "F3", "F4"],
    ),
]


def declaration() -> dict:
    """La déclaration d'atelier, validée : c'est elle que le moteur lit."""
    return calc.normalize(WORKSHOP, {s["key"] for s in DEFINITION["statuses"]}, Report())


def cases() -> list[dict]:
    decl = declaration()
    default = next(s["key"] for s in DEFINITION["statuses"] if s.get("default"))
    out = []
    for key, title, summary, elements, settings, dimensions, rules in _SITUATIONS:
        situation = calc.situation(decl, {"elements": elements, "settings": settings}, Report())
        case = calc.to_case(decl, situation, calc.run(decl, situation, default), default)
        case.update(
            key=key, family="Factures", title=title, summary=summary, rules=rules, dimensions=dimensions
        )
        out.append(case)
    return out
