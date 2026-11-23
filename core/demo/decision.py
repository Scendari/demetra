"""Étude de démonstration : règles de décision (remboursement d'une commande)."""

from __future__ import annotations

TITLE = "Remboursement d'une commande"

DELAIS = [("j14", "≤ 14 jours"), ("j30", "15 à 30 jours"), ("j31", "> 30 jours")]
ETATS = [("intact", "Intact"), ("ouvert", "Ouvert"), ("defaut", "Défectueux")]
CLIENTS = [("standard", "Standard"), ("premium", "Premium")]

DEFINITION = {
    "title": TITLE,
    "description": "Ce que le service client accorde quand une commande est retournée, selon le délai, l'état du produit et le type de client.",
    "kind": "decision",
    "statuses": [
        {"key": "A_EVALUER", "label": "À évaluer", "short": "À évaluer", "role": "waiting", "default": True},
        {"key": "FAVORABLE", "label": "Favorable", "short": "Favorable", "role": "success"},
        {"key": "LIMITE", "label": "Restrictif", "short": "Restrictif", "role": "warning"},
        {"key": "DEFAVORABLE", "label": "Défavorable", "short": "Défavor.", "role": "error"},
        {"key": "SANS_EFFET", "label": "Sans effet", "short": "Sans effet", "role": "disabled"},
        {"key": "REMBOURSE", "label": "Remboursement intégral", "short": "Remboursé", "role": "success"},
        {"key": "AVOIR", "label": "Avoir", "short": "Avoir", "role": "warning"},
        {"key": "ECHANGE", "label": "Échange ou réparation", "short": "Échange", "role": "info"},
        {"key": "REFUSE", "label": "Refus", "short": "Refus", "role": "error"},
    ],
    "dimensions": [
        {"key": "delai", "label": "Délai depuis la livraison", "values": [{"value": k, "label": v} for k, v in DELAIS]},
        {"key": "etat", "label": "État du produit", "values": [{"value": k, "label": v} for k, v in ETATS]},
        {"key": "client", "label": "Type de client", "values": [{"value": k, "label": v} for k, v in CLIENTS]},
    ],
    "rules": [
        {"key": "R1", "title": "Rétractation sous 14 jours",
         "text": "Jusqu'à 14 jours après la livraison, un produit intact est remboursé intégralement, quel que soit le client."},
        {"key": "R2", "title": "Produit ouvert",
         "text": "Un produit ouvert n'est plus remboursé : il donne droit à un avoir sous 14 jours, et à rien au-delà. Un client Premium garde un cran d'avantage : remboursement sous 14 jours, avoir jusqu'à 30 jours."},
        {"key": "R3", "title": "Retour tardif",
         "text": "Entre 15 et 30 jours, un produit intact donne droit à un avoir (remboursement pour un client Premium). Au-delà de 30 jours, aucun retour n'est accepté."},
        {"key": "R4", "title": "Garantie sur défaut",
         "text": "Un produit défectueux est remboursé intégralement jusqu'à 30 jours ; au-delà, il est échangé ou réparé au titre de la garantie."},
    ],
    "exclusions": [
        {"when": {"delai": "j31", "etat": "ouvert"}, "reason": "Au-delà de 30 jours, un produit ouvert est traité comme un produit intact : seul le défaut est examiné."},
    ],
}

# Combinaisons volontairement absentes, pour que la couverture ait quelque chose à signaler.
OMITTED = {("j30", "defaut", "standard"), ("j30", "defaut", "premium"), ("j31", "intact", "premium"), ("j31", "defaut", "premium")}


def decide(delai: str, etat: str, client: str) -> tuple[str, list[str], str]:
    """Renvoie (statut du résultat, règles appliquées, motif)."""
    premium = client == "premium"
    if etat == "defaut":
        if delai in ("j14", "j30"):
            return "REMBOURSE", ["R4"], "Défaut constaté dans les 30 jours : remboursement intégral."
        return "ECHANGE", ["R4"], "Défaut constaté après 30 jours : la garantie prévoit l'échange ou la réparation."
    if delai == "j31":
        return "REFUSE", ["R3"], "Plus de 30 jours après la livraison : aucun retour n'est accepté."
    if etat == "intact":
        if delai == "j14":
            return "REMBOURSE", ["R1"], "Produit intact retourné sous 14 jours : droit de rétractation."
        if premium:
            return "REMBOURSE", ["R3"], "Retour tardif d'un produit intact : le client Premium reste remboursé."
        return "AVOIR", ["R3"], "Retour tardif d'un produit intact : un avoir remplace le remboursement."
    if delai == "j14":
        if premium:
            return "REMBOURSE", ["R2"], "Produit ouvert sous 14 jours : le client Premium reste remboursé."
        return "AVOIR", ["R2"], "Produit ouvert sous 14 jours : un avoir remplace le remboursement."
    if premium:
        return "AVOIR", ["R2"], "Produit ouvert entre 15 et 30 jours : avoir réservé aux clients Premium."
    return "REFUSE", ["R2"], "Produit ouvert retourné après 14 jours : aucun droit."


def cases() -> list[dict]:
    labels = {s["key"]: s["label"] for s in DEFINITION["statuses"]}
    out, number = [], 0
    for delai, delai_label in DELAIS:
        for etat, etat_label in ETATS:
            for client, client_label in CLIENTS:
                if (delai, etat, client) in OMITTED or (delai, etat) == ("j31", "ouvert"):
                    continue
                number += 1
                result, rules, reason = decide(delai, etat, client)
                delai_status = {"j14": "FAVORABLE", "j30": "LIMITE", "j31": "DEFAVORABLE"}[delai]
                etat_status = {"intact": "FAVORABLE", "ouvert": "LIMITE", "defaut": "FAVORABLE"}[etat]
                decided_same = decide(delai, etat, "standard")[0] == decide(delai, etat, "premium")[0]
                client_status = "SANS_EFFET" if decided_same else ("FAVORABLE" if client == "premium" else "LIMITE")
                client_note = "ne change rien ici" if decided_same else ("avantage Premium appliqué" if client == "premium" else "pas d'avantage")
                family = {"REMBOURSE": "Remboursements", "AVOIR": "Avoirs", "ECHANGE": "Garantie", "REFUSE": "Refus"}[result]
                # Quand le type de client change la décision, le cas jumeau (l'autre type de client) est proposé en comparaison,
                # et la question posée au relecteur porte sur cet écart.
                other = "standard" if client == "premium" else "premium"
                guide = {}
                if not decided_same and (delai, etat, other) not in OMITTED:
                    other_label = dict(CLIENTS)[other].lower()
                    guide = {"compare_with": [f"remb-{delai}-{etat}-{other}"],
                             "question": f"Un client {other_label} obtient « {labels[decide(delai, etat, other)[0]].lower()} » dans la même situation : "
                                         "cet écart est-il bien voulu ?"}
                out.append({
                    **guide,
                    "key": f"remb-{delai}-{etat}-{client}",
                    "number": number,
                    "family": family,
                    "title": f"{etat_label}, {delai_label.lower()}, client {client_label.lower()} : {labels[result].lower()}",
                    "summary": reason,
                    "kind": "decision",
                    "rules": rules,
                    "dimensions": {"delai": delai, "etat": etat, "client": client},
                    "entities": [
                        {"id": "delai", "label": "Délai depuis la livraison", "type": "condition", "group": "Conditions", "attrs": {"value": delai_label}},
                        {"id": "etat", "label": "État du produit", "type": "condition", "group": "Conditions", "attrs": {"value": etat_label}},
                        {"id": "client", "label": "Type de client", "type": "condition", "group": "Conditions", "attrs": {"value": client_label}},
                        {"id": "decision", "label": "Décision", "type": "résultat", "group": "Résultat", "attrs": {"value": labels[result]}},
                    ],
                    "links": [{"from": c, "to": "decision", "type": "determines", "label": ""} for c in ("delai", "etat", "client")],
                    "steps": [
                        {"title": "Le délai est examiné", "note": f"La demande arrive {delai_label.lower()} après la livraison.",
                         "changes": {"delai": delai_status},
                         "annotations": {"delai": {"j14": "dans le délai de rétractation", "j30": "hors rétractation, encore recevable", "j31": "hors de tout délai de retour"}[delai]}},
                        {"title": "L'état du produit est examiné", "note": f"Le produit est {etat_label.lower()}.",
                         "changes": {"etat": etat_status},
                         "annotations": {"etat": {"intact": "revendable en l'état", "ouvert": "ne peut plus être revendu neuf", "defaut": "la garantie s'applique"}[etat]}},
                        {"title": "Le type de client est pris en compte", "note": f"Client {client_label.lower()} : {client_note}.",
                         "changes": {"client": client_status}, "annotations": {"client": client_note}},
                        {"title": f"Décision : {labels[result].lower()}", "note": reason, "changes": {"decision": result},
                         "annotations": {"decision": "règle " + ", ".join(rules)}, "global": result},
                    ],
                    "outcome": {"label": labels[result], "status": result},
                    "references": [{"kind": "source", "label": "Conditions générales de vente, article « Retours »"}],
                    "proof": "asserted",
                })
    return out
