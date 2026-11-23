#!/usr/bin/env python3
"""Joue le rôle d'une IA externe face à Demetra, avec un jeton personnel et rien d'autre.

    uv run python scripts/ia_externe.py --base http://127.0.0.1:8000 --token dmt_xxx

Le script n'emploie que la bibliothèque standard. Il suit le parcours décrit par le mode d'emploi :
lire le mode d'emploi, créer une étude, valider puis déposer des cas, lire la couverture, assembler une
représentation par briques, en demander l'aperçu, la proposer, puis lire les avis. Il vérifie aussi ce
qu'un jeton ne doit pas pouvoir faire. Il dépose ensuite une seconde étude au format étendu (montants,
champs, messages, tranches, jeu de règles, cycle de vie) et choisit sa représentation. Il s'arrête avec
un code non nul au premier écart.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request


class Client:
    def __init__(self, base: str, token: str | None):
        self.base, self.token = base.rstrip("/"), token

    def call(self, method: str, path: str, body=None, headers: dict | None = None, auth: bool = True):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method)
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        if auth and self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        for name, value in (headers or {}).items():
            request.add_header(name, value)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                status, raw, kind = response.status, response.read(), response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as error:
            status, raw, kind = error.code, error.read(), error.headers.get("Content-Type", "")
        if "json" in kind:
            return status, json.loads(raw.decode() or "null")
        return status, raw.decode()


STEP = 0


def step(title: str):
    global STEP
    STEP += 1
    print(f"\n{STEP:>2}. {title}")


def check(condition: bool, message: str):
    print(f"    {'ok ' if condition else 'KO '} {message}")
    if not condition:
        sys.exit(1)


STUDY = {
    "title": "Notes de frais : circuit de validation",
    "description": "Qui valide une note de frais, selon son montant et la présence d'un justificatif.",
    "kind": "decision",
    "statuses": [
        {"key": "A_EVALUER", "label": "À évaluer", "role": "waiting", "default": True},
        {"key": "REMPLIE", "label": "Remplie", "role": "success"},
        {"key": "NON_REMPLIE", "label": "Non remplie", "role": "error"},
        {"key": "ACCEPTEE", "label": "Acceptée", "role": "success"},
        {"key": "A_VALIDER", "label": "Validation du responsable", "short": "Responsable", "role": "warning"},
        {"key": "REJETEE", "label": "Rejetée", "role": "error"},
    ],
    "dimensions": [
        {"key": "montant", "label": "Montant", "values": ["≤ 50 €", "51 à 500 €", "> 500 €"]},
        {"key": "justificatif", "label": "Justificatif", "values": ["présent", "absent"]},
    ],
    "rules": [
        {
            "key": "R1",
            "title": "Petits montants",
            "text": "Jusqu'à 50 €, la note est acceptée sans validation si le justificatif est joint.",
        },
        {
            "key": "R2",
            "title": "Justificatif obligatoire",
            "text": "Sans justificatif, la note est rejetée, quel que soit le montant.",
        },
        {
            "key": "R3",
            "title": "Validation hiérarchique",
            "text": "Au-delà de 50 €, le responsable valide ; au-delà de 500 €, la direction aussi.",
        },
    ],
}


def case(
    key: str, number: int, montant: str, justificatif: str, outcome: str, rules: list[str], title: str
) -> dict:
    """Un cas de décision : deux conditions évaluées l'une après l'autre, puis le résultat."""
    ok_justif = justificatif == "présent"
    steps = [
        {
            "title": "Le justificatif est contrôlé",
            "changes": {
                "justificatif": {
                    "status": "REMPLIE" if ok_justif else "NON_REMPLIE",
                    "note": f"justificatif {justificatif}",
                }
            },
        },
        {
            "title": "Le montant est examiné",
            "changes": {"montant": "REMPLIE" if montant == "≤ 50 €" else "NON_REMPLIE"},
            "annotations": {"montant": montant},
        },
        {"title": "La décision est rendue", "changes": {"decision": outcome}, "global": outcome},
    ]
    labels = {
        "ACCEPTEE": "Acceptée sans validation",
        "A_VALIDER": "Validation du responsable",
        "REJETEE": "Rejetée",
    }
    return {
        "key": key,
        "number": number,
        "family": "Notes de frais",
        "title": title,
        "kind": "decision",
        "rules": rules,
        "dimensions": {"montant": montant, "justificatif": justificatif},
        "entities": [
            {
                "id": "justificatif",
                "label": "Justificatif joint",
                "type": "condition",
                "attrs": {"value": justificatif},
            },
            {"id": "montant", "label": "Montant ≤ 50 €", "type": "condition", "attrs": {"value": montant}},
            {"id": "decision", "label": "Décision", "type": "result", "attrs": {"value": labels[outcome]}},
        ],
        "links": [
            {"from": "justificatif", "to": "decision", "type": "condition"},
            {"from": "montant", "to": "decision", "type": "condition"},
        ],
        "steps": steps,
        "outcome": {"label": labels[outcome], "status": outcome},
        "proof": "asserted",
    }


CASES = [
    case(
        "petit-avec-justificatif",
        1,
        "≤ 50 €",
        "présent",
        "ACCEPTEE",
        ["R1"],
        "Petit montant, justificatif joint : acceptée",
    ),
    case(
        "petit-sans-justificatif",
        2,
        "≤ 50 €",
        "absent",
        "REJETEE",
        ["R2"],
        "Petit montant sans justificatif : rejetée",
    ),
    case(
        "moyen-avec-justificatif",
        3,
        "51 à 500 €",
        "présent",
        "A_VALIDER",
        ["R3"],
        "Montant moyen : le responsable valide",
    ),
    case(
        "moyen-sans-justificatif",
        4,
        "51 à 500 €",
        "absent",
        "REJETEE",
        ["R2"],
        "Montant moyen sans justificatif : rejetée",
    ),
    case(
        "gros-avec-justificatif",
        5,
        "> 500 €",
        "présent",
        "A_VALIDER",
        ["R3"],
        "Gros montant : responsable puis direction",
    ),
]

REPRESENTATION = {
    "schema": "demetra.representation/1",
    "compose": {"brick": "compose.columns", "ratio": [2, 3]},
    "tokens": {"density": "compact", "status_label": "full", "canvas": "plain"},
    "views": [
        {
            "id": "conditions",
            "title": "Conditions du cas",
            "layout": {"brick": "layout.grid", "rows": "entities"},
            "marks": [
                {"brick": "mark.cell", "header": "Élément", "text": "{label}", "weight": "strong"},
                {"brick": "mark.cell", "header": "Valeur", "text": "{attr.value}"},
                {"brick": "mark.cell", "header": "État", "content": "status"},
            ],
            "time": {"brick": "time.stepper", "highlight_changes": True},
        },
        {
            "id": "deroule",
            "title": "Déroulé",
            "layout": {"brick": "layout.grid", "rows": "entities"},
            "marks": [
                {"brick": "mark.cell", "header": "Élément", "text": "{label}"},
                {"brick": "mark.cells_per_step", "header": "{n}", "label": "icon"},
            ],
            "time": {"brick": "time.stepper"},
        },
    ],
}


# ---------------------------------------------------------------------------
# Seconde étude, au format étendu. Données fictives.
# ---------------------------------------------------------------------------

RICH_STUDY = {
    "title": "Abonnement : prix, règles et cycle de vie",
    "description": "Prix d'un abonnement selon l'ancienneté et la formule, et ce que devient l'abonnement "
    "quand un paiement passe ou échoue.",
    "kind": "decision",
    "statuses": [
        {"key": "EN_ATTENTE", "label": "En attente", "role": "waiting", "default": True},
        {"key": "ESSAI", "label": "Essai gratuit", "short": "Essai", "role": "info"},
        {"key": "ACTIF", "label": "Actif", "role": "success"},
        {"key": "SUSPENDU", "label": "Suspendu", "role": "warning"},
        {"key": "RESILIE", "label": "Résilié", "role": "error"},
    ],
    "dimensions": [
        # Une dimension numérique : ses tranches, la borne qui appartient à chacune, et le résultat de chaque
        # tranche.
        {
            "key": "anciennete",
            "label": "Ancienneté",
            "unit": "mois",
            "inclusive": "from",
            "values": [
                {"value": "nouveau", "label": "Moins de 12 mois"},
                {"value": "fidele", "label": "12 mois et plus"},
            ],
            "bands": [
                {"value": "nouveau", "to": 12, "result": "Plein tarif"},
                {"value": "fidele", "from": 12, "result": "Remise de 10 %"},
            ],
        },
        {"key": "formule", "label": "Formule", "values": ["Mensuelle", "Annuelle"]},
    ],
    "rules": [
        {
            "key": "A1",
            "title": "Prix",
            "text": "La formule annuelle offre deux mois ; sinon, 10 % de remise à partir de 12 mois "
            "d'ancienneté.",
        },
        {
            "key": "A2",
            "title": "Impayé",
            "text": "Un paiement refusé suspend l'abonnement ; il redevient actif à la régularisation.",
        },
    ],
    # Un jeu de règles partagé par les cas : conditions, conclusion, et la politique qui départage plusieurs
    # lignes.
    "ruleset": {
        "title": "Prix de l'abonnement",
        "policy": "first",
        "conditions": [{"key": "formule", "label": "Formule"}, {"key": "anciennete", "label": "Ancienneté"}],
        "rows": [
            {"key": "P1", "when": {"formule": "Annuelle"}, "then": "Deux mois offerts"},
            {"key": "P2", "when": {"anciennete": "12 mois et plus"}, "then": "Remise de 10 %"},
            {"key": "P3", "when": {}, "then": "Plein tarif"},
        ],
    },
    # Un cycle de vie par type d'entité : les seules transitions permises.
    "lifecycles": [
        {
            "type": "abonnement",
            "title": "Vie d'un abonnement",
            "initial": "ESSAI",
            "transitions": [
                {"from": "ESSAI", "to": "ACTIF", "label": "premier paiement"},
                {"from": "ACTIF", "to": "ACTIF", "label": "renouvellement"},
                {"from": "ACTIF", "to": "SUSPENDU", "label": "paiement refusé"},
                {"from": "SUSPENDU", "to": "ACTIF", "label": "régularisation"},
                {
                    "from": "SUSPENDU",
                    "to": "RESILIE",
                    "label": "résiliation automatique",
                    "guard": "après 30 jours",
                },
                {"from": "ACTIF", "to": "RESILIE", "label": "résilier"},
            ],
        }
    ],
}

_ACTORS = [
    {"id": "service", "label": "Service d'abonnement", "type": "acteur"},
    {"id": "banque", "label": "Banque", "type": "acteur"},
    {"id": "client", "label": "Client", "type": "acteur"},
]


def rich_case(
    key, title, months, band, formule, start, price_rows, values, fields_before, steps, outcome, status
) -> dict:
    return {
        "key": key,
        "title": title,
        "family": f"Formule {formule.lower()}",
        "rules": ["A1", "A2"],
        "dimensions": {"anciennete": band, "formule": formule},
        "measures": {"anciennete": months},
        "entities": [
            {"id": "abo", "label": "Abonnement", "type": "abonnement", "fields": fields_before},
            *_ACTORS,
        ],
        "initial": {"abo": start},
        "steps": [
            {"title": "Les règles de prix sont examinées dans l'ordre", "rows": price_rows, "values": values},
            *steps,
        ],
        "outcome": {"label": outcome, "status": status},
    }


RICH_CASES = [
    rich_case(
        "fidele-mensuel",
        "18 mois d'ancienneté, formule mensuelle",
        18,
        "fidele",
        "Mensuelle",
        "ACTIF",
        {"P1": {"result": "failed", "on": "formule"}, "P2": "selected"},
        [
            {"label": "Prix catalogue", "op": "=", "value": 20, "unit": "€", "result": 20},
            {"label": "Remise de 10 %", "op": "-", "value": 2, "unit": "€", "result": 18},
        ],
        {"Prix du mois": "20 €", "Remise": "aucune"},
        [
            {
                "title": "Le renouvellement est prélevé",
                "changes": {"abo": "ACTIF"},
                "fields": {"abo": {"Prix du mois": "18 €", "Remise": "10 %"}},
                "messages": [
                    {"from": "service", "to": "banque", "label": "Prélever 18 €"},
                    {"from": "banque", "to": "service", "label": "Accepté"},
                ],
            },
            {
                "title": "Le client reçoit sa facture",
                "global": "ACTIF",
                "messages": [{"from": "service", "to": "client", "label": "Facture de 18 €"}],
            },
        ],
        "Remise de 10 %",
        "ACTIF",
    ),
    rich_case(
        "nouveau-annuel",
        "3 mois d'ancienneté, formule annuelle",
        3,
        "nouveau",
        "Annuelle",
        "ESSAI",
        {"P1": "selected"},
        [
            {"label": "Prix catalogue", "op": "=", "value": 240, "unit": "€", "result": 240},
            {"label": "Deux mois offerts", "op": "-", "value": 40, "unit": "€", "result": 200},
        ],
        {"Prix de l'année": "240 €", "Remise": "aucune"},
        [
            {
                "title": "Le premier paiement passe",
                "changes": {"abo": "ACTIF"},
                "global": "ACTIF",
                "fields": {"abo": {"Prix de l'année": "200 €", "Remise": "2 mois offerts"}},
                "messages": [
                    {"from": "service", "to": "banque", "label": "Prélever 200 €"},
                    {"from": "banque", "to": "service", "label": "Accepté"},
                ],
            }
        ],
        "Deux mois offerts",
        "ACTIF",
    ),
    rich_case(
        "seuil-12-mois-impaye",
        "Pile 12 mois d'ancienneté, paiement refusé puis régularisé",
        12,
        "fidele",
        "Mensuelle",
        "ACTIF",
        {"P1": {"result": "failed", "on": "formule"}, "P2": "selected"},
        [
            {"label": "Prix catalogue", "op": "=", "value": 20, "unit": "€", "result": 20},
            {"label": "Remise de 10 %", "op": "-", "value": 2, "unit": "€", "result": 18},
        ],
        {"Prix du mois": "20 €", "Remise": "aucune"},
        [
            {
                "title": "Le prélèvement est refusé",
                "changes": {"abo": "SUSPENDU"},
                "fields": {"abo": {"Prix du mois": "18 €", "Remise": "10 %"}},
                "messages": [
                    {"from": "service", "to": "banque", "label": "Prélever 18 €"},
                    {"from": "banque", "to": "service", "label": "Refusé"},
                    {"from": "service", "to": "client", "label": "Paiement à régulariser", "status": "lost"},
                ],
            },
            {
                "title": "Le client régularise",
                "changes": {"abo": "ACTIF"},
                "global": "ACTIF",
                "messages": [{"from": "client", "to": "service", "label": "Payer 18 €"}],
            },
        ],
        "Remise de 10 %",
        "ACTIF",
    ),
]

NEW_REPRESENTATIONS = [
    "matrice-croisee",
    "calcul-pas-a-pas",
    "axe-a-bandes",
    "avant-apres",
    "table-regles",
    "arbre-decision",
    "table-etats",
    "diagramme-etats",
    "diagramme-sequence",
]


def extended_format(api: Client, args) -> str:
    step("Lire dans le mode d'emploi le format étendu et les nouvelles briques")
    status, chapter = api.call("GET", "/api/v1/guide/cases", auth=False)
    text = chapter.get("markdown", "")
    check(
        status == 200 and all(word in text for word in ("measures", "values", "fields", "messages", "rows")),
        "chapitre « cases » : measures, values, fields, messages, rows",
    )
    status, chapter = api.call("GET", "/api/v1/guide/studies", auth=False)
    text = chapter.get("markdown", "")
    check(
        status == 200 and all(word in text for word in ("bands", "ruleset", "lifecycles")),
        "chapitre « studies » : bands, ruleset, lifecycles",
    )
    status, chapter = api.call("GET", "/api/v1/guide/representations", auth=False)
    text = chapter.get("markdown", "")
    check(
        status == 200
        and all(
            word in text
            for word in (
                "layout.matrix",
                "layout.scale",
                "layout.tree",
                "layout.states",
                "layout.lifelines",
                "PUT /api/v1/studies/{id}/representation",
            )
        ),
        "chapitre « representations » : nouvelles dispositions et choix de la représentation",
    )
    status, bricks = api.call("GET", "/api/v1/bricks", auth=False)
    names = [b["brick"] for family in bricks.get("families", []) for b in family.get("bricks", [])]
    check(
        all(
            n in names
            for n in (
                "layout.matrix",
                "layout.scale",
                "layout.tree",
                "layout.states",
                "layout.lifelines",
                "mark.message",
                "mark.band",
            )
        ),
        f"catalogue : {len(names)} briques, dont les nouvelles dispositions",
    )

    step("Créer une étude au format étendu : tranches, jeu de règles, cycle de vie")
    wrong = json.loads(json.dumps(RICH_STUDY))
    wrong["dimensions"][0]["bands"][1]["from"] = 24
    status, refused = api.call("POST", "/api/v1/studies", wrong)
    gap = next((d for d in refused.get("error", {}).get("details", []) if d["code"] == "gap"), None)
    check(
        status == 422 and gap and gap["path"] == "dimensions[0].bands[1].from",
        f"tranches qui ne se suivent pas : refus à {gap and gap['path']}",
    )
    status, study = api.call("POST", "/api/v1/studies", RICH_STUDY)
    check(
        status in (200, 201)
        and study.get("ruleset", {}).get("policy") == "first"
        and study["lifecycles"][0]["states"],
        f"étude créée : {study.get('id')}",
    )
    sid = study["id"]

    step("Les contrôles de cohérence donnent le chemin exact de l'erreur")
    faults = [
        (
            "mesure hors de sa tranche",
            lambda c: c["measures"].update(anciennete=11.5),
            "out_of_band",
            "cases[0].measures.anciennete",
        ),
        (
            "ligne de règle inexistante",
            lambda c: c["steps"][0]["rows"].update(P9="selected"),
            "unknown_rule",
            "cases[0].steps[0].rows.P9",
        ),
        (
            "message vers une entité non déclarée",
            lambda c: c["steps"][1]["messages"][0].update(to="tresorerie"),
            "unknown_entity",
            "cases[0].steps[1].messages[0].to",
        ),
        (
            "transition absente du cycle de vie",
            lambda c: c["steps"][1]["changes"].update(abo="ESSAI"),
            "forbidden_transition",
            "cases[0].steps[1].changes.abo",
        ),
    ]
    for label, mutate, code, path in faults:
        broken = json.loads(json.dumps(RICH_CASES[0]))
        mutate(broken)
        status, report = api.call("POST", f"/api/v1/studies/{sid}/cases/validate", {"cases": [broken]})
        found = next((e for e in report["results"][0].get("errors", []) if e["code"] == code), None)
        check(bool(found) and found["path"] == path, f"{label} : {code} à {path}")

    step("Déposer les cas au format étendu, puis rejouer le lot")
    status, deposit = api.call("POST", f"/api/v1/studies/{sid}/cases/batch", {"cases": RICH_CASES})
    check(
        status == 200 and deposit["counts"].get("created") == len(RICH_CASES),
        f"{len(RICH_CASES)} cas créés (montants, champs, messages, lignes de règles, mesures)",
    )
    status, again = api.call("POST", f"/api/v1/studies/{sid}/cases/batch", {"cases": RICH_CASES})
    check(
        status == 200 and again["counts"] == {"unchanged": len(RICH_CASES)},
        "même lot rejoué : tout est « unchanged »",
    )
    status, read = api.call("GET", f"/api/v1/studies/{sid}/cases/seuil-12-mois-impaye")
    back = read["case"]
    check(
        status == 200
        and back["measures"] == {"anciennete": 12}
        and back["steps"][1]["messages"][2]["status"] == "lost",
        "un cas relu rend ses champs étendus",
    )

    step("Choisir la représentation de l'étude : une étude = une représentation")
    status, recommended = api.call("GET", f"/api/v1/studies/{sid}/representations/recommended")
    slugs = [r["slug"] for r in recommended["recommended"]]
    check(
        status == 200 and set(slugs) & set(NEW_REPRESENTATIONS),
        "conseillées pour cette étude : " + ", ".join(slugs),
    )
    chosen = "table-regles" if "table-regles" in slugs else next(s for s in slugs if s in NEW_REPRESENTATIONS)
    status, choice = api.call(
        "PUT", f"/api/v1/studies/{sid}/representation", {"representation": chosen, "level": "study"}
    )
    check(
        status == 200 and choice["study"]["slug"] == chosen and choice["study_chosen_by"] == "ai",
        f"représentation de l'étude : {choice['study']['name']} (choisie par l'IA)",
    )
    status, choice = api.call(
        "PUT",
        f"/api/v1/studies/{sid}/representation",
        {"representation": "diagramme-sequence", "level": "case", "case": "seuil-12-mois-impaye"},
    )
    check(
        status == 200 and [c["case"] for c in choice["cases"]] == ["seuil-12-mois-impaye"],
        "un seul cas montré autrement : diagramme de séquence pour le cas à message perdu",
    )
    status, choice = api.call(
        "PUT", f"/api/v1/studies/{sid}/representation", {"representation": "diagramme-etats", "level": "me"}
    )
    check(
        status == 200 and choice["me"]["slug"] == "diagramme-etats" and choice["study"]["slug"] == chosen,
        "choix personnel : l'étude garde la sienne",
    )
    status, choice = api.call(
        "PUT", f"/api/v1/studies/{sid}/representation", {"representation": None, "level": "me"}
    )
    status, choice = api.call("GET", f"/api/v1/studies/{sid}/representation")
    check(
        status == 200 and choice["me"] is None and choice["effective"]["slug"] == chosen,
        "retour au choix de l'étude",
    )
    status, refused = api.call(
        "PUT", f"/api/v1/studies/{sid}/representation", {"representation": chosen, "level": "partout"}
    )
    check(status == 422, "niveau inconnu : 422")

    step("Regarder chaque nouvelle représentation sur un cas de l'étude")
    for slug in NEW_REPRESENTATIONS:
        status, preview = api.call(
            "POST",
            f"/api/v1/studies/{sid}/cases/seuil-12-mois-impaye/preview",
            {"representation": slug, "step": 2, "image": False},
        )
        lines = preview.get("summary", {}).get("text", "").splitlines()
        detail = next(
            (line.strip() for line in lines if line.startswith("  ")),
            lines[2].strip() if len(lines) > 2 else "",
        )
        check(status == 200 and len(lines) >= 3, f"{slug} : {detail[:110]}")
    status, preview = api.call(
        "POST", f"/api/v1/studies/{sid}/cases/seuil-12-mois-impaye/preview", {"step": 2, "image": True}
    )
    check(
        status == 200 and preview["representation"] == "Diagramme de séquence",
        "sans représentation nommée, l'aperçu suit le choix fait pour ce cas",
    )
    if preview.get("image"):
        png = base64.b64decode(preview["image"]["data"])
        check(
            png[:8] == b"\x89PNG\r\n\x1a\n", f"aperçu image du diagramme de séquence reçu ({len(png)} octets)"
        )
        if args.image:
            root, ext = os.path.splitext(args.image)
            with open(f"{root}-sequence{ext or '.png'}", "wb") as handle:
                handle.write(png)
    else:
        print(f"    --   pas d'image : {preview.get('image_unavailable')}")
    return sid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base", default=os.environ.get("DEMETRA_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.environ.get("DEMETRA_TOKEN"))
    parser.add_argument(
        "--share-with", default="lea", help="Compte pour lequel demander un partage (demande en attente)."
    )
    parser.add_argument("--image", default="", help="Chemin où écrire l'aperçu PNG, s'il est disponible.")
    args = parser.parse_args()
    if not args.token:
        parser.error("Un jeton est nécessaire : --token ou la variable DEMETRA_TOKEN.")
    api = Client(args.base, args.token)

    step("Lire le mode d'emploi, sans jeton")
    status, llms = api.call("GET", "/llms.txt", auth=False)
    check(status == 200 and "/api/v1/guide" in llms, "/llms.txt indique où lire le mode d'emploi")
    status, guide = api.call("GET", "/api/v1/guide", auth=False)
    check(
        status == 200 and guide.get("topics"),
        f"mode d'emploi version {guide.get('version')}, {len(guide.get('topics', []))} chapitres",
    )
    for topic in ("cases", "representations"):
        status, chapter = api.call("GET", f"/api/v1/guide/{topic}", auth=False)
        check(
            status == 200 and len(chapter.get("markdown", "")) > 500,
            f"chapitre « {topic} » lu ({len(chapter.get('markdown', ''))} caractères)",
        )

    step("Vérifier son identité et ses droits")
    status, _ = api.call("GET", "/api/v1/me", auth=False)
    check(status == 401, "sans jeton : 401")
    status, me = api.call("GET", "/api/v1/me")
    check(
        status == 200,
        f"jeton « {me['token']['name']} » de {me['user']}, portées : {', '.join(me['token']['scopes'])}",
    )

    step("Créer une étude")
    status, study = api.call("POST", "/api/v1/studies", STUDY)
    check(status in (200, 201), f"étude créée : {study.get('id')}")
    sid = study["id"]

    step("Valider à blanc un lot qui contient une faute, puis la corriger")
    faulty = json.loads(json.dumps(CASES))
    faulty[2]["steps"][2]["changes"]["decision"] = "A_VALIDE"
    status, report = api.call("POST", f"/api/v1/studies/{sid}/cases/validate", {"cases": faulty})
    errors = [d for result in report.get("results", []) for d in result.get("errors", [])]
    check(
        status in (200, 422) and report.get("dry_run") and errors,
        f"faute repérée sans rien écrire : {errors[0]['path']} — {errors[0]['message']}",
    )
    check(
        "A_VALIDER" in (errors[0].get("expected") or []),
        "l'erreur donne les valeurs attendues, dont la bonne",
    )
    status, listing = api.call("GET", f"/api/v1/studies/{sid}/cases")
    check(status == 200 and listing.get("total") == 0, "toujours aucun cas dans l'étude")

    step("Déposer les cas, puis rejouer le même lot")
    status, deposit = api.call(
        "POST", f"/api/v1/studies/{sid}/cases/batch", {"cases": CASES}, {"Idempotency-Key": "lot-1"}
    )
    check(status == 200 and deposit["counts"].get("created") == len(CASES), f"{len(CASES)} cas créés")
    status, again = api.call(
        "POST", f"/api/v1/studies/{sid}/cases/batch", {"cases": CASES}, {"Idempotency-Key": "lot-1"}
    )
    check(
        status == 200 and again.get("replayed") is True,
        "même clé d'idempotence : réponse enregistrée renvoyée",
    )
    status, again = api.call("POST", f"/api/v1/studies/{sid}/cases/batch", {"cases": CASES})
    check(
        status == 200 and again["counts"].get("unchanged") == len(CASES),
        "même lot sans clé : tout est « unchanged »",
    )

    step("Lire la couverture")
    status, coverage = api.call("GET", f"/api/v1/studies/{sid}/coverage")
    check(
        status == 200 and coverage["missing_count"] == 1,
        f"{coverage['covered']} combinaisons sur {coverage['total']} ; manque : {coverage['missing'][0]}",
    )
    extra = case(
        "gros-sans-justificatif",
        6,
        "> 500 €",
        "absent",
        "REJETEE",
        ["R2"],
        "Gros montant sans justificatif : rejetée",
    )
    status, deposit = api.call("POST", f"/api/v1/studies/{sid}/cases/batch", {"cases": [extra]})
    check(
        status == 200 and deposit["coverage"]["missing_count"] == 0,
        "cas manquant ajouté : couverture complète",
    )

    step("Assembler une représentation avec les briques du site")
    status, bricks = api.call("GET", "/api/v1/bricks", auth=False)
    names = [b["brick"] for family in bricks.get("families", []) for b in family.get("bricks", [])]
    check(status == 200 and "layout.grid" in names, f"{len(names)} briques au catalogue")
    status, recommended = api.call("GET", f"/api/v1/studies/{sid}/representations/recommended")
    check(
        status == 200 and recommended["recommended"],
        "recommandées pour cette étude : " + ", ".join(r["slug"] for r in recommended["recommended"]),
    )
    broken = json.loads(json.dumps(REPRESENTATION))
    broken["views"][0]["marks"].append({"brick": "mark.script", "code": "alert(1)"})
    status, verdict = api.call("POST", "/api/v1/representations/validate", {"spec": broken})
    check(
        status in (200, 422) and not verdict.get("valid", False),
        "une brique inconnue est refusée (aucun code n'est exécuté)",
    )
    status, verdict = api.call("POST", "/api/v1/representations/validate", {"spec": REPRESENTATION})
    check(status == 200 and verdict.get("valid"), "le document assemblé est valide")
    status, rep = api.call(
        "POST",
        "/api/v1/representations",
        {
            "name": "Conditions et déroulé",
            "description": "Les conditions du cas à gauche, leur évolution étape par étape à droite.",
            "spec": REPRESENTATION,
        },
    )
    check(status in (200, 201), f"représentation créée : {rep.get('id')}")
    rid = rep["id"]
    status, adjusted = api.call(
        "POST",
        "/api/v1/representations",
        {"mode": "adjustment", "parent": "table-decision", "overrides": {"tokens": {"density": "spacious"}}},
    )
    check(
        status in (200, 201) and adjusted.get("scope") == "adjustment",
        "ajustement personnel d'une représentation système créé",
    )
    status, copy = api.call(
        "POST", f"/api/v1/representations/{rid}/duplicate", {"name": "Conditions et déroulé (copie)"}
    )
    check(status in (200, 201) and copy.get("id") != rid, "représentation dupliquée")

    step("Regarder le rendu avant de le proposer")
    status, preview = api.call(
        "POST",
        f"/api/v1/studies/{sid}/cases/moyen-avec-justificatif/preview",
        {"representation": rid, "step": 2, "image": True},
    )
    check(
        status == 200 and preview["summary"]["text"],
        "résumé textuel : " + preview["summary"]["text"].splitlines()[0],
    )
    if preview.get("image"):
        png = base64.b64decode(preview["image"]["data"])
        check(png[:8] == b"\x89PNG\r\n\x1a\n", f"aperçu image reçu ({len(png)} octets)")
        if args.image:
            with open(args.image, "wb") as handle:
                handle.write(png)
    else:
        print(f"    --   pas d'image : {preview.get('image_unavailable')}")
    status, proposal = api.call(
        "POST",
        f"/api/v1/studies/{sid}/representations/proposals",
        {
            "representation": rid,
            "reason": "Deux conditions et un résultat : une table se lit mieux qu'un graphe.",
        },
    )
    check(status in (200, 201), "représentation proposée à l'utilisateur, qui choisira dans l'interface")
    status, request = api.call(
        "POST",
        "/api/v1/bricks/requests",
        {
            "title": "Arbre de décision",
            "need": "Montrer les conditions comme des embranchements successifs.",
            "family": "disposition",
            "study": sid,
        },
    )
    check(status in (200, 201), "brique manquante signalée")

    step("Ce qu'un jeton ne peut pas faire")
    status, refused = api.call(
        "POST", f"/api/v1/studies/{sid}/cases/petit-avec-justificatif/verdict", {"decision": "accepted"}
    )
    check(status == 403 and refused["error"]["code"] == "human_only", "rendre un avis : 403 human_only")
    status, pending = api.call(
        "POST",
        f"/api/v1/studies/{sid}/share-requests",
        {"user": args.share_with, "role": "commenter", "message": "Relecture des cas de notes de frais."},
    )
    check(
        status == 202 and pending.get("status") == "pending",
        "partage : demande en attente de confirmation dans l'interface",
    )
    status, members = api.call("GET", f"/api/v1/studies/{sid}/members")
    check(
        status == 200 and all(m["user"] != args.share_with for m in members["items"]),
        "le partage n'a pas pris effet",
    )

    step("Lire les avis et la liste de travail")
    status, verdicts = api.call("GET", f"/api/v1/studies/{sid}/verdicts")
    check(
        status == 200 and "items" in verdicts,
        f"{len(verdicts['items'])} avis lus (les humains n'ont pas encore relu) ; état : "
        f"{verdicts['summary']}",
    )
    status, worklist = api.call("GET", f"/api/v1/studies/{sid}/worklist")
    check(
        status == 200 and worklist["review"]["cases"] == 6,
        f"liste de travail : {worklist['review']['cases']} cas, {len(worklist['rejected'])} refusé, "
        f"{worklist['coverage']['missing_count']} combinaison manquante",
    )
    status, audit = api.call("GET", f"/api/v1/studies/{sid}/audit")
    entries = audit.get("items", [])
    check(
        status == 200 and entries and all(e["actor_kind"] == "jeton" and e["token"] for e in entries),
        f"journal : {len(entries)} actions, toutes inscrites au nom du jeton",
    )

    rich = extended_format(api, args)

    print(f"\nTerminé. Études à relire : {args.base}/etudes/{sid}/ et {args.base}/etudes/{rich}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
