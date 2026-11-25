"""Atelier, famille « périodes » : des périodes posées, combinées par le site comme l'étude le déclare.

L'étude d'essai (le tarif d'un contrat) n'a rien à voir avec les études de démonstration : tout ce que
l'atelier en sait vient de sa déclaration."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core import families, periods
from core import services as svc
from core.casemodel import Report

from .conftest import STUDY as BUILDING
from .conftest import Api
from .test_atelier import WORKSHOP as LINKED

STUDY = {
    "title": "Tarif d'un contrat",
    "kind": "temporal",
    "statuses": [
        {"key": "A_VENIR", "label": "À venir", "role": "waiting", "default": True},
        {"key": "ACTIVE", "label": "En cours", "role": "active"},
        {"key": "FINIE", "label": "Finie", "role": "neutral"},
        {"key": "DEVANCEE", "label": "Devancée", "role": "disabled"},
        {"key": "INVALIDE", "label": "Invalide", "role": "error"},
        {"key": "BLOQUEE", "label": "Bloquée", "role": "blocked"},
        {"key": "REMISE", "label": "Tarif remisé", "role": "success"},
        {"key": "PLEIN", "label": "Plein tarif", "role": "info"},
    ],
}
STATUSES = {s["key"] for s in STUDY["statuses"]}
WORKSHOP = {
    "family": "periods",
    "title": "Composer un tarif",
    "axis": {"label": "Mois", "min": 1, "max": 13, "grain": 1, "step": 0.5},
    "bricks": [
        {
            "type": "contrat",
            "label": "Contrat",
            "options": [
                {"key": "offre", "label": "Offre", "values": ["Base", "Plus"]},
                {"key": "note", "label": "Note interne", "values": ["x", "y"]},
            ],
        },
        {"type": "remise", "label": "Remise", "options": [{"key": "code", "values": ["R1", "R2"]}]},
        {
            "type": "bareme",
            "label": "Barème",
            "options": [{"key": "code", "values": ["R1", "R2"]}, {"key": "taux", "values": [10, 20]}],
        },
    ],
    "settings": [{"key": "sans_remise", "label": "Mois sans remise", "values": ["gardés", "retirés"]}],
    "image": {
        "sources": [
            {"brick": "contrat"},
            {"brick": "remise", "mode": {"setting": "sans_remise", "inner": ["retirés"]}},
            {"brick": "bareme", "match": {"code": "remise.code"}},
        ],
        "fields": [
            {"key": "offre", "label": "Offre", "from": "contrat.offre"},
            {"key": "taux", "label": "Taux", "from": "bareme.taux"},
        ],
        "status": [{"when": {"missing": ["remise", "bareme"]}, "then": "PLEIN"}, {"then": "REMISE"}],
    },
    "states": {
        "active": "ACTIVE",
        "past": "FINIE",
        "ignored": "DEVANCEE",
        "invalid": "INVALIDE",
        "blocked": "BLOQUEE",
    },
    "outcome": [
        {"when": {"blocked": True}, "label": "Tarif non publié", "status": "BLOQUEE"},
        {"when": {"empty": True}, "label": "Aucun tarif"},
        {"when": {"status": "REMISE"}, "label": "Tarif avec remise", "status": "REMISE"},
        {"label": "Plein tarif", "status": "PLEIN"},
    ],
}


def contrat(key, start, end, offre="Base", note="x"):
    return {
        "id": key,
        "type": "contrat",
        "start": start,
        "end": end,
        "options": {"offre": offre, "note": note},
    }


def remise(key, start, end, code="R1"):
    return {"id": key, "type": "remise", "start": start, "end": end, "options": {"code": code}}


def bareme(key, start, end, code="R1", taux=10):
    return {"id": key, "type": "bareme", "start": start, "end": end, "options": {"code": code, "taux": taux}}


def declaration(**changes) -> dict:
    report = Report()
    decl = families.normalize({**WORKSHOP, **changes}, STATUSES, report)
    assert report.ok, [(i.path, i.code) for i in report.errors]
    return decl


def history(elements: list, decl: dict | None = None, **settings) -> tuple[list, list]:
    """Les périodes obtenues — (début, fin, offre, taux, statut) — et ce qui bloque."""
    decl = decl or declaration()
    report = Report()
    sit = periods.situation(decl, {"elements": elements, "settings": settings}, report)
    assert report.ok, [(i.path, i.code) for i in report.errors]
    result = periods.run(decl, sit, "A_VENIR")
    rows = [(i["start"], i["end"], *i["fields"].values(), i["status"]) for i in result["images"]]
    return rows, result["blocking"]


@pytest.fixture
def atelier(api):
    status, data = api.post("/studies", {**STUDY, "workshop": WORKSHOP})
    assert status == 201, data
    return data["id"]


# ---------------------------------------------------------------------------
# Déclaration
# ---------------------------------------------------------------------------


def test_the_declaration_is_a_closed_vocabulary():
    def codes(**changes) -> set:
        report = Report()
        families.normalize({**WORKSHOP, **changes}, STATUSES, report)
        return {(i.path, i.code) for i in report.errors}

    image = WORKSHOP["image"]
    assert codes() == set()
    assert codes(family="calcul") == {("workshop.family", "enum")}
    assert codes(script="print(1)") == {("workshop", "unknown_field")}
    assert codes(rules=[]) == {("workshop", "unknown_field")}  # les règles viennent de la déclaration
    assert codes(axis={"min": 1, "max": 1}) == {("workshop.axis", "type")}
    assert codes(axis={"min": 0, "max": 5000, "grain": 1}) == {("workshop.axis", "type")}
    assert codes(merge="oui") == {("workshop.merge", "type")}
    assert codes(invalid={"zero": "explode"}) == {("workshop.invalid", "enum")}
    assert codes(states={"active": "ACTIVE"}) == {("workshop.states", "unknown_status")}
    assert codes(image={**image, "sources": [{"brick": "facture"}]}) >= {
        ("workshop.image.sources[0].brick", "unknown_brick")
    }
    bad = [{"brick": "contrat"}, {"brick": "bareme", "match": {"code": "remise.code"}}]
    assert ("workshop.image.sources[1].match.code", "unknown_option") in codes(
        image={**image, "sources": bad}
    )
    bad = [image["sources"][0], {"brick": "remise", "mode": {"setting": "sans_remise", "inner": ["jamais"]}}]
    assert ("workshop.image.sources[1].mode", "type") in codes(image={**image, "sources": bad})
    bad = [{"key": "offre", "from": "contrat.prix"}]
    assert codes(image={**image, "fields": bad}) == {("workshop.image.fields[0].from", "unknown_option")}
    bad = [{"when": {"import": "os"}, "then": "PLEIN"}]
    assert codes(image={**image, "status": bad}) == {("workshop.image.status[0].when", "unknown_test")}
    bad = [{"then": "GRATUIT"}]
    assert codes(image={**image, "status": bad}) == {("workshop.image.status[0].then", "unknown_status")}
    events = [
        {**WORKSHOP["bricks"][0], "events": [{"key": "panne", "label": "Panne"}]},
        *WORKSHOP["bricks"][1:],
    ]
    assert ("workshop.bricks[0]", "unknown_field") in codes(bricks=events)


def test_the_declaration_reads_as_rules():
    """Ce que le relecteur lit à côté du résultat est écrit par le site à partir de la déclaration."""
    rules = declaration()["rules"]
    assert [r["key"] for r in rules] == ["P1", "P2", "P3", "P4", "P5", "P6", "P7"]
    text = " ".join(r["title"] for r in rules)
    assert "Une image par pas de 1 sur l'axe « Mois »" in text
    assert "de son début inclus à sa fin exclue" in text
    assert "sauf quand « Mois sans remise » vaut « retirés » : alors aucune image" in text
    assert "« code » vaut « code » de « Remise »" in text
    assert "Champs restitués : « Offre » et « Taux »" in text and "Note interne" not in text


def test_a_study_without_family_keeps_linked_elements(api):
    status, data = api.post("/studies", {**BUILDING, "workshop": {**LINKED, "family": "linked"}})
    assert status == 201, data
    status, data = api.get(f"/studies/{data['id']}/workshop")
    assert status == 200 and data["family"] == "linked" and data["workshop"]["links"]
    assert families.of({}) is families.FAMILIES["linked"]


# ---------------------------------------------------------------------------
# Moteur
# ---------------------------------------------------------------------------


def test_a_period_counts_from_its_start_to_just_before_its_end():
    rows, blocking = history([contrat("A", 2, 3), contrat("B", 3, 4, "Plus")])
    assert rows == [(2, 3, "Base", None, "PLEIN"), (3, 4, "Plus", None, "PLEIN")] and not blocking


def test_a_change_inside_a_step_creates_no_image():
    rows, _ = history([contrat("A", 1, 1.5), contrat("B", 1.5, 2.5, "Plus"), contrat("C", 2.5, 4)])
    # Le mois 1 finit sur « Plus », le mois 2 sur « Base » : un passage de mi-mois se voit en fin de mois.
    assert [(r[0], r[1], r[2]) for r in rows] == [(1, 2, "Plus"), (2, 4, "Base")]
    rows, _ = history([contrat("A", 1, 1.5), contrat("B", 1.5, 1.5 + 0.25, "Plus"), contrat("C", 1.75, 3)])
    assert [(r[0], r[1], r[2]) for r in rows] == [(1, 3, "Base")]


def test_identical_images_that_touch_merge_and_others_do_not():
    rows, _ = history(
        [contrat("A", 1, 3), contrat("B", 3, 4), contrat("C", 4, 6, "Plus"), contrat("D", 6, 7)]
    )
    assert [(r[0], r[1], r[2]) for r in rows] == [(1, 4, "Base"), (4, 6, "Plus"), (6, 7, "Base")]
    rows, _ = history([contrat("A", 1, 3), contrat("B", 5, 7)])
    assert [(r[0], r[1]) for r in rows] == [(1, 3), (5, 7)]  # un trou sépare
    # Un champ qui n'est pas restitué ne crée pas de période.
    rows, _ = history([contrat("A", 1, 3, note="x"), contrat("B", 3, 5, note="y")])
    assert [(r[0], r[1]) for r in rows] == [(1, 5)]
    rows, _ = history([contrat("A", 1, 3, note="x"), contrat("B", 3, 5, note="y")], declaration(merge=False))
    assert [(r[0], r[1]) for r in rows] == [(1, 3), (3, 5)]


def test_a_missing_source_keeps_or_removes_the_image_as_declared():
    placed = [contrat("A", 1, 10), remise("B", 2, 4), remise("C", 6, 8), bareme("D", 1, 10)]
    rows, _ = history(placed)
    assert [(r[0], r[1], r[3], r[4]) for r in rows] == [
        (1, 2, None, "PLEIN"),
        (2, 4, 10, "REMISE"),
        (4, 6, None, "PLEIN"),
        (6, 8, 10, "REMISE"),
        (8, 10, None, "PLEIN"),
    ]
    rows, _ = history(placed, sans_remise="retirés")
    assert [(r[0], r[1], r[3]) for r in rows] == [(2, 4, 10), (6, 8, 10)]
    # Sans la source de base, rien ne sort.
    assert history([remise("B", 2, 4), bareme("D", 1, 10)]) == ([], [])


def test_a_joined_source_is_matched_on_the_declared_field():
    placed = [contrat("A", 1, 5), remise("B", 1, 3, "R1"), remise("C", 3, 5, "R2")]
    placed += [bareme("D", 1, 5, "R1", 10), bareme("E", 1, 5, "R2", 20)]
    rows, blocking = history(placed)
    assert [(r[0], r[1], r[3]) for r in rows] == [(1, 3, 10), (3, 5, 20)] and not blocking


def test_several_periods_in_force_are_settled_as_declared():
    base = [contrat("A", 1, 5), bareme("D", 1, 5, "R1", 10), bareme("E", 1, 5, "R2", 20)]
    rows, blocking = history([*base, remise("B", 1, 5, "R1"), remise("C", 2, 5, "R2")])
    assert [(r[0], r[1], r[3]) for r in rows] == [(1, 2, 10), (2, 5, 20)] and not blocking
    # Même début : rien ne départage, le traitement est bloqué et l'image ne se confond pas avec la veille.
    rows, blocking = history([*base, remise("B", 2, 5, "R1"), remise("C", 2, 5, "R2")])
    assert [(r[0], r[1], r[4]) for r in rows] == [(1, 2, "BLOQUEE"), (2, 5, "BLOQUEE")]
    assert blocking == ["Mois 2 : plusieurs « Remise » en vigueur, à égalité"]
    first = declaration(
        image={
            **WORKSHOP["image"],
            "sources": [
                {"brick": "contrat"},
                {"brick": "remise", "several": "earliest_start", "tie": "first"},
                WORKSHOP["image"]["sources"][2],
            ],
        }
    )
    rows, blocking = history([*base, remise("B", 2, 5, "R2"), remise("C", 2, 5, "R1")], first)
    assert [(r[0], r[1], r[3]) for r in rows] == [(1, 2, None), (2, 5, 20)] and not blocking


def test_invalid_periods_are_ignored_or_block_as_declared():
    rows, blocking = history([contrat("A", 1, 4), contrat("B", 2, 2, "Plus")])
    assert [(r[0], r[1], r[2]) for r in rows] == [(1, 4, "Base")] and not blocking
    rows, blocking = history([contrat("A", 1, 4), contrat("B", 3, 2, "Plus")])
    assert blocking == ["Contrat B : une période qui finit avant de commencer"] and rows[0][-1] == "BLOQUEE"
    rows, blocking = history([contrat("A", 1, 4), contrat("B", 2, None, "Plus")])
    assert blocking == ["Contrat B : une période dont une borne manque"]
    lenient = declaration(invalid={"missing": "ignore", "inverted": "ignore"})
    assert history([contrat("A", 1, 4), contrat("B", 2, None, "Plus")], lenient)[1] == []


def test_the_walk_tells_each_period_what_it_becomes():
    decl = declaration()
    placed = [contrat("A", 1, 3), remise("B", 1, 3, "R1"), remise("C", 2, 3, "R2"), contrat("Z", 2, 2)]
    sit = periods.situation(decl, {"elements": placed}, Report())
    result = periods.run(decl, sit, "A_VENIR")
    case = periods.to_case(decl, sit, result, "A_VENIR")
    assert [s["title"] for s in case["steps"]] == [
        "Périodes posées",
        "Contrôle des périodes posées",
        "Mois 1 : Base · ∅",
        "Mois 2 : Base · ∅ — même image, d'autres périodes",
        "Mois 3 : aucune image",
    ]
    assert case["steps"][1]["changes"] == {"Z": "DEVANCEE"} and "ne comptent pas" in case["steps"][1]["note"]
    assert case["steps"][2]["changes"] == {"A": "ACTIVE", "B": "ACTIVE", "I1": "PLEIN"}
    # L'image ne change pas au mois 2, mais la remise C, plus récente, devance B : le déroulé le montre.
    assert case["steps"][3]["changes"] == {"B": "DEVANCEE", "C": "ACTIVE"}
    assert "Remise : Remise C, retenue parmi plusieurs" in case["steps"][3]["note"]
    assert [i["end"] for i in result["images"]] == [3]
    groups = {e["id"]: e["group"] for e in case["entities"]}
    assert groups["A"] == "Périodes posées" and groups["I1"] == "Historique obtenu"
    assert result["steps"][3]["changes"][0]["rule"] == "P5"  # la règle de la source « Remise »
    # Le déroulé va au bout de l'axe : après la dernière image, les périodes finies le sont, l'image reste.
    assert case["steps"][4]["changes"] == {"A": "FINIE", "B": "FINIE", "C": "FINIE"}
    assert case["steps"][4]["note"] == "Aucune période « Contrat » en vigueur."
    assert result["steps"][-1]["states"]["I1"] == "PLEIN"
    # Une période qui court jusqu'au bout de l'axe y est encore en vigueur.
    sit = periods.situation(decl, {"elements": [contrat("A", 1, 13)]}, Report())
    assert periods.run(decl, sit, "A_VENIR")["steps"][-1]["states"] == {"A": "ACTIVE", "I1": "PLEIN"}
    # Un trou dans l'historique est un pas, la fin de la dernière image aussi.
    sit = periods.situation(decl, {"elements": [contrat("A", 1, 2), contrat("B", 4, 5)]}, Report())
    case = periods.to_case(decl, sit, periods.run(decl, sit, "A_VENIR"), "A_VENIR")
    assert [s["title"] for s in case["steps"][1:]] == [
        "Mois 1 : Base · ∅",
        "Mois 2 : aucune image",
        "Mois 4 : Base · ∅",
        "Mois 5 : aucune image",
    ]


def test_an_address_holds_the_whole_situation():
    decl = declaration()
    raw = {
        "elements": [
            {**contrat("A", 1.5, 4, "Plus"), "label": "Contrat d'origine"},
            remise("B", 2, None, "R2"),
        ],
        "settings": {"sans_remise": "retirés"},
    }
    sit = periods.situation(decl, raw, Report())
    query = periods.to_query(decl, sit)
    assert ("de.A", "1.5") in query and ("a.B", "") in query and ("r.sans_remise", "retirés") in query
    packed: dict[str, list[str]] = {}
    for name, value in query:
        packed.setdefault(name, []).append(value)
    assert periods.situation(decl, periods.from_query(decl, packed), Report()) == sit
    # Ce que l'adresse contient d'inconnu est ignoré ; une borne hors de l'axe est ramenée dedans.
    odd = {"e": ["A:contrat", "B:facture", "A:remise"], "de.A": ["-4"], "a.A": ["99"], "o.A.offre": ["Luxe"]}
    read = periods.from_query(decl, odd)
    assert read["elements"] == [{"id": "A", "type": "contrat", "options": {}, "start": 1, "end": 13}]


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def test_the_api_describes_and_runs_a_periods_workshop(api, atelier):
    study = svc.Study.objects.get(public_id=atelier)
    revision = study.revision
    status, data = api.get(f"/studies/{atelier}/workshop")
    assert status == 200 and data["declared"] and data["family"] == "periods"
    assert data["limits"]["links"] == 0 and len(data["workshop"]["rules"]) == 7
    placed = [contrat("A", 1, 6), remise("B", 3, 5), bareme("C", 1, 6, taux=20)]
    status, data = api.post(f"/studies/{atelier}/workshop/run", {"situation": {"elements": placed}})
    assert status == 200, data
    assert data["family"] == "periods" and data["blocking"] == []
    assert data["images"] == [
        {
            "id": "I1",
            "start": 1,
            "end": 3,
            "fields": {"offre": "Base", "taux": None},
            "status": "PLEIN",
            "from": {"contrat": "A", "remise": None, "bareme": None},
        },
        {
            "id": "I2",
            "start": 3,
            "end": 5,
            "fields": {"offre": "Base", "taux": 20},
            "status": "REMISE",
            "from": {"contrat": "A", "remise": "B", "bareme": "C"},
        },
        {
            "id": "I3",
            "start": 5,
            "end": 6,
            "fields": {"offre": "Base", "taux": None},
            "status": "PLEIN",
            "from": {"contrat": "A", "remise": None, "bareme": None},
        },
    ]
    assert data["outcome"] == {"label": "Tarif avec remise", "status": "REMISE"}
    # Au bout de l'axe, les trois périodes sont finies.
    assert data["final"] == {"A": "FINIE", "B": "FINIE", "C": "FINIE"}
    assert data["steps"][1]["at"] == 1 and "at" not in data["steps"][0]
    assert {r["key"] for r in data["rules_applied"]} >= {"P1", "P2", "P7"}
    assert data["case"]["kind"] == "temporal" and len(data["case"]["entities"]) == 6
    assert data["web_url"].startswith(f"/etudes/{atelier}/atelier/?e=A%3Acontrat")
    study.refresh_from_db()
    assert study.revision == revision and not study.cases.exists()


def test_the_api_refuses_what_the_study_does_not_declare(api, atelier):
    bad = {
        "elements": [contrat("A", 1, 99), {"id": "B", "type": "facture"}],
        "links": [{"from": "A", "to": "B", "type": "puis"}],
    }
    status, data = api.post(f"/studies/{atelier}/workshop/run", {"situation": bad})
    assert status == 422
    assert {(d["path"], d["code"]) for d in data["error"]["details"]} == {
        ("situation.links", "unknown_field"),
        ("situation.elements[0].end", "out_of_range"),
        ("situation.elements[1].type", "unknown_brick"),
    }
    status, data = api.patch(f"/studies/{atelier}", {"workshop": {**WORKSHOP, "merge": 3}})
    assert status == 422 and data["error"]["details"][0]["path"] == "workshop.merge"
    # Un statut ne se retire pas sous une déclaration qui le nomme.
    status, data = api.patch(f"/studies/{atelier}", {"statuses": STUDY["statuses"][:7]})
    assert status == 422 and any(d["path"].startswith("workshop.") for d in data["error"]["details"])


def test_a_read_only_token_runs_it_and_nobody_saves_through_the_api(atelier, token_for, users):
    reader = Api(token_for("ana", scopes=["studies:read"]))
    situation = {"elements": [contrat("A", 1, 3)]}
    status, data = reader.post(f"/studies/{atelier}/workshop/run", {"situation": situation})
    assert status == 200 and data["outcome"]["label"] == "Plein tarif"
    study = svc.Study.objects.get(public_id=atelier)
    study.my_role = "owner"
    token, _ = svc.create_token(users["ana"], "jeton", list(svc.SCOPES))
    sit = periods.situation(study.workshop, situation, Report())
    with pytest.raises(svc.ServiceError) as caught:
        svc.save_built_case(svc.Actor(users["ana"], token), study, sit, "x")
    assert caught.value.code == "human_only" and not study.cases.exists()


# ---------------------------------------------------------------------------
# Écran
# ---------------------------------------------------------------------------


def rows_of(page: str) -> list[list[str]]:
    """Les lignes du tableau « Historique obtenu »."""
    table = re.search(r'<table class="at-history">(.*?)</table>', page, flags=re.DOTALL)
    assert table, "pas de tableau d'historique"
    body = table.group(1).split("<tbody>")[1]
    return [
        [
            re.sub(r"<[^>]+>", "", cell).strip()
            for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.DOTALL)
        ]
        for row in re.findall(r"<tr>(.*?)</tr>", body, flags=re.DOTALL)
    ]


def test_the_page_starts_empty_and_places_periods_one_after_the_other(atelier, web):
    client = web("ana")
    page = client.get(f"/etudes/{atelier}/atelier/").content.decode()
    assert "Composer un tarif" in page and "Sources de l&#x27;étude" in page
    assert "data-brick=" not in page and "at-history" not in page
    assert len(re.findall(r'name="add" value="(\w+)"', page)) == 3
    # Poser un contrat : deux pas à partir du début de l'axe ; le suivant commence où finit le premier.
    response = client.get(f"/etudes/{atelier}/atelier/?add=contrat")
    assert response.status_code == 302 and response["Location"].endswith("?e=A%3Acontrat&de.A=1&a.A=3")
    response = client.get(response["Location"] + "&add=contrat")
    assert response["Location"].endswith("e=A%3Acontrat&e=B%3Acontrat&de.A=1&a.A=3&de.B=3&a.B=5")
    response = client.get(response["Location"] + "&add=remise")
    assert response["Location"].endswith("&de.C=1&a.C=3")
    page = client.get(response["Location"]).content.decode()
    assert 'name="de.A" value="1"' in page and 'name="a.B" value="5"' in page and 'step="0.5"' in page
    assert rows_of(page) == [["1", "5", "Base", "vide", "Plein tarif"]]
    assert "Relier à" not in page and 'name="ev"' not in page  # des périodes ne se relient pas


def test_the_page_shows_the_history_and_follows_every_change(atelier, web):
    client = web("ana")
    state = "e=A%3Acontrat&e=B%3Aremise&e=C%3Abareme&de.A=1&a.A=6&de.B=3&a.B=5&de.C=1&a.C=6&o.C.taux=20"
    page = client.get(f"/etudes/{atelier}/atelier/?{state}").content.decode()
    assert rows_of(page) == [
        ["1", "3", "Base", "vide", "Plein tarif"],
        ["3", "5", "Base", "20", "Tarif remisé"],
        ["5", "6", "Base", "vide", "Plein tarif"],
    ]
    assert "Tarif avec remise" in page and "Les 7 règles" in page and "rep-view" in page
    # Un réglage change le résultat ; l'adresse le garde.
    page = client.get(f"/etudes/{atelier}/atelier/?{state}&r.sans_remise=retir%C3%A9s").content.decode()
    assert rows_of(page) == [["3", "5", "Base", "20", "Tarif remisé"]]
    # Une borne vidée reste vide : la période bloque le traitement, l'écran le dit.
    blank = state.replace("a.B=5", "a.B=")
    response = client.get(f"/etudes/{atelier}/atelier/?{blank}")
    assert response.status_code == 200
    page = response.content.decode()
    assert "Le traitement est bloqué" in page and "une période dont une borne manque" in page
    assert 'name="a.B" value=""' in page and "Tarif non publié" in page
    # Le fragment redessiné sur place porte le même résultat.
    part = client.get(f"/etudes/{atelier}/atelier/?{state}", headers={"X-Requested-With": "fetch"})
    assert "<html" not in part.content.decode() and len(rows_of(part.content.decode())) == 3


def test_a_human_saves_the_built_history_as_a_case(atelier, web):
    client = web("ana")
    state = "e=A%3Acontrat&e=B%3Aremise&e=C%3Abareme&de.A=1&a.A=4&de.B=2&a.B=3&de.C=1&a.C=4"
    response = client.post(f"/etudes/{atelier}/atelier/", {"etat": state, "title": "Remise d'un mois"})
    assert response.status_code == 302
    case = svc.Study.objects.get(public_id=atelier).cases.get()
    assert case.title == "Remise d'un mois" and case.content["kind"] == "temporal"
    groups = [e["group"] for e in case.content["entities"]]
    assert groups.count("Périodes posées") == 3 and groups.count("Historique obtenu") == 3
    assert [s.get("at") for s in case.content["steps"]] == [None, 1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Mode d'emploi
# ---------------------------------------------------------------------------


def test_the_guide_example_is_valid_and_gives_what_the_guide_says(api):
    text = (Path(svc.__file__).parent / "guide" / "atelier.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)```", text, flags=re.DOTALL)
    decl = json.loads("{" + next(b for b in blocks if b.startswith('"workshop"') and '"periods"' in b) + "}")
    situation = json.loads(next(b for b in blocks if b.startswith('{"situation"') and '"start"' in b))
    statuses = [
        {"key": "A_VENIR", "label": "À venir", "role": "waiting", "default": True},
        {"key": "EN_COURS", "label": "En cours", "role": "active"},
        {"key": "FINIE", "label": "Finie", "role": "neutral"},
        {"key": "IGNOREE", "label": "Ignorée", "role": "disabled"},
        {"key": "KO", "label": "Invalide", "role": "error"},
        {"key": "REMISE", "label": "Avec remise", "role": "success"},
        {"key": "SANS_REMISE", "label": "Sans remise", "role": "info"},
    ]
    study = {"title": "Exemple du guide", "kind": "temporal", "statuses": statuses, **decl}
    status, data = api.post("/studies", study)
    assert status == 201, data
    status, data = api.post(f"/studies/{data['id']}/workshop/run", situation)
    assert status == 200, data
    assert [(i["start"], i["end"], i["fields"], i["status"]) for i in data["images"]] == [
        (1, 3, {"offre": "A", "taux": None}, "SANS_REMISE"),
        (3, 5, {"offre": "A", "taux": 10}, "REMISE"),
        (5, 6, {"offre": "A", "taux": None}, "SANS_REMISE"),
    ]
    assert data["blocking"] == [] and data["final"] == {"A": "FINIE", "B": "FINIE"}
    # Chaque mot du vocabulaire de la famille est nommé dans le chapitre.
    words = (*periods.SEVERAL, *periods.TIES, *periods.STATES, *periods.INVALID, *periods.FIELDS)
    for word in (*words, "missing", "present", "blocked", "empty", "out_of_range", "images", "blocking"):
        assert f"`{word}`" in text or f'"{word}"' in text, word
