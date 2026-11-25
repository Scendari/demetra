"""Atelier : règles déclarées par l'étude, situation construite, déroulé pas à pas, API, écran."""

from __future__ import annotations

import json
import re
from html import escape, unescape
from pathlib import Path
from urllib.parse import urlencode

import pytest

from core import services as svc
from core import workshop
from core.casemodel import Report
from core.demo import catalogue, circuit

from .conftest import STUDY, Api, make_case

STATUSES = {s["key"] for s in STUDY["statuses"]}
WORKSHOP = {
    "title": "Composer un parcours",
    "bricks": [
        {
            "type": "porte",
            "label": "Porte",
            "options": [
                {"key": "active", "label": "En service", "values": [True, False]},
                {"key": "niveau", "label": "Niveau", "values": ["bas", "haut"]},
            ],
            "events": [{"key": "panne", "label": "Tombe en panne"}],
        },
        {"type": "sas", "label": "Sas"},
    ],
    "links": [
        {
            "type": "mene",
            "label": "mène à",
            "reverse": "accessible depuis",
            "from": ["porte"],
            "to": ["porte", "sas"],
        }
    ],
    "settings": [{"key": "alerte", "label": "Alerte", "values": [False, True]}],
    "rules": [
        {
            "key": "P1",
            "title": "Une porte hors service ne s'ouvre pas",
            "on": "porte",
            "when": {"status": "ATTENTE", "option": {"active": False}},
            "then": "BLOQUE",
        },
        {
            "key": "P2",
            "title": "En alerte, les portes du niveau haut restent fermées",
            "on": "porte",
            "when": {"status": "ATTENTE", "setting": {"alerte": True}, "option": {"niveau": "haut"}},
            "then": "BLOQUE",
        },
        {
            "key": "P3",
            "title": "Rien ne s'ouvre derrière une porte en panne",
            "when": {"status": "ATTENTE", "upstream": {"any": {"status": ["KO", "BLOQUE"]}}},
            "then": "BLOQUE",
        },
        {
            "key": "P4",
            "title": "Un passage s'ouvre quand tout ce qui y mène est ouvert",
            "when": {"status": "ATTENTE", "incoming": {"all": {"status": "OK"}}},
            "then": "EN_COURS",
        },
        {
            "key": "P5",
            "title": "Une porte en panne reste fermée",
            "when": {"status": "EN_COURS", "event": "panne"},
            "then": "KO",
        },
        {"key": "P6", "title": "Le passage est ouvert", "when": {"status": "EN_COURS"}, "then": "OK"},
    ],
    "outcome": [
        {
            "when": {"elements": {"any": {"status": ["KO", "BLOQUE"]}}},
            "label": "Passage coupé",
            "status": "KO",
        },
        {"label": "Passage libre", "status": "OK"},
    ],
}
# Scénarios du catalogue que les règles déclarées rejouent à l'identique : mêmes états finaux, même issue.
REPLAYED = [
    *["01", "02", "03", "04", "05", "06", "11", "13", "14", "16-B", "16-C", "17", "18", "19", "21", "22"],
    *["23", "24-B", "27", "28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "39", "53", "56"],
    *["81", "82", "85"],
]


def declared(raw: dict = WORKSHOP, statuses: set = STATUSES) -> dict:
    report = Report()
    decl = workshop.normalize(raw, statuses, report)
    assert report.ok, [(i.path, i.code) for i in report.issues]
    return decl


def built(decl: dict, raw: dict) -> dict:
    report = Report()
    sit = workshop.situation(decl, raw, report)
    assert report.ok, [(i.path, i.code) for i in report.issues]
    return sit


def finals(page: str) -> dict:
    """État final de chaque brique, lu sur sa fiche."""
    return dict(re.findall(r'data-brick="(\w+)".*?data-final="(\w+)"', page, flags=re.DOTALL))


@pytest.fixture
def atelier(api):
    status, data = api.post("/studies", {**STUDY, "workshop": WORKSHOP})
    assert status == 201, data
    return data["id"]


# ---------------------------------------------------------------------------
# Déclaration : un vocabulaire fermé
# ---------------------------------------------------------------------------


def test_rules_are_a_closed_vocabulary():
    def codes(**changes) -> set:
        report = Report()
        workshop.normalize({**WORKSHOP, **changes}, STATUSES, report)
        return {(i.path, i.code) for i in report.errors}

    rule = WORKSHOP["rules"][0]
    assert ("workshop.rules[0].when.eval", "unknown_test") in codes(
        rules=[{**rule, "when": {"eval": "1 + 1"}}]
    )
    assert ("workshop.rules[0].then", "unknown_status") in codes(rules=[{**rule, "then": "PARTI"}])
    assert ("workshop.rules[0].when.status", "unknown_status") in codes(
        rules=[{**rule, "when": {"status": "X"}}]
    )
    assert ("workshop.rules[0].when.option.couleur", "unknown_option") in codes(
        rules=[{**rule, "when": {"option": {"couleur": "rouge"}}}]
    )
    assert ("workshop.rules[0].when.incoming", "type") in codes(
        rules=[{**rule, "when": {"incoming": {"all": {"status": "OK"}, "any": {"status": "OK"}}}}]
    )
    assert ("workshop.rules[0].on", "unknown_brick") in codes(rules=[{**rule, "on": "fenetre"}])
    assert ("workshop.outcome[0].when.status", "no_element") in codes(
        outcome=[{"when": {"status": "OK"}, "label": "x"}]
    )
    assert ("workshop", "unknown_field") in codes(script="print(1)")
    deep = {"status": "OK"}
    for _ in range(7):
        deep = {"not": deep}
    assert any(code == "too_deep" for _, code in codes(rules=[{**rule, "when": deep}]))
    assert not codes()


def test_a_declaration_without_rules_opens_no_workshop():
    assert not workshop.declared({}) and not workshop.declared(None)
    assert workshop.normalize(None, STATUSES, Report()) == {}
    assert workshop.declared(declared())


# ---------------------------------------------------------------------------
# Moteur
# ---------------------------------------------------------------------------


def test_rules_apply_step_by_step_until_nothing_moves():
    decl = declared()
    sit = built(
        decl,
        {
            "elements": [
                {"id": "A", "type": "porte", "events": ["panne"]},
                {"id": "B", "type": "porte"},
                {"id": "C", "type": "sas"},
                {"id": "D", "type": "porte"},
            ],
            "links": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}],
        },
    )
    result = workshop.run(decl, sit, "ATTENTE")
    assert result["end"] == "stable"
    assert [step["states"] for step in result["steps"]] == [
        {"A": "ATTENTE", "B": "ATTENTE", "C": "ATTENTE", "D": "ATTENTE"},
        {"A": "EN_COURS", "B": "ATTENTE", "C": "ATTENTE", "D": "EN_COURS"},
        {"A": "KO", "B": "ATTENTE", "C": "ATTENTE", "D": "OK"},
        # « En amont » remonte toute la chaîne : C, qui ne touche pas A, est bloqué au même pas que B.
        {"A": "KO", "B": "BLOQUE", "C": "BLOQUE", "D": "OK"},
    ]
    assert [c["rule"] for c in result["steps"][3]["changes"]] == ["P3", "P3"]
    assert workshop.outcome_of(decl, result["world"]) == {"label": "Passage coupé", "status": "KO"}


def test_the_first_matching_rule_wins_and_settings_count():
    decl = declared()
    raw = {
        "elements": [{"id": "A", "type": "porte", "options": {"niveau": "haut"}}],
        "settings": {"alerte": True},
    }
    result = workshop.run(decl, built(decl, raw), "ATTENTE")
    assert (
        result["steps"][-1]["states"] == {"A": "BLOQUE"} and result["steps"][1]["changes"][0]["rule"] == "P2"
    )
    calm = workshop.run(decl, built(decl, {**raw, "settings": {}}), "ATTENTE")
    assert calm["steps"][-1]["states"] == {"A": "OK"}


def test_a_situation_that_never_settles_stops():
    flip = {
        "bricks": [{"type": "lampe", "label": "Lampe"}],
        "rules": [
            {"key": "L1", "title": "S'allume", "when": {"status": "ATTENTE"}, "then": "OK"},
            {"key": "L2", "title": "S'éteint", "when": {"status": "OK"}, "then": "ATTENTE"},
        ],
    }
    decl = declared(flip)
    result = workshop.run(decl, built(decl, {"elements": [{"id": "A", "type": "lampe"}]}), "ATTENTE")
    assert result["end"] == "loop" and len(result["steps"]) == 3
    climb = {
        "bricks": [{"type": "lampe", "label": "Lampe"}],
        "max_steps": 2,
        "rules": [
            {"key": "L1", "title": "Un", "when": {"status": "ATTENTE"}, "then": "EN_COURS"},
            {"key": "L2", "title": "Deux", "when": {"status": "EN_COURS"}, "then": "OK"},
            {"key": "L3", "title": "Trois", "when": {"status": "OK"}, "then": "KO"},
            {"key": "L4", "title": "Quatre", "when": {"status": "KO"}, "then": "BLOQUE"},
        ],
    }
    decl = declared(climb)
    result = workshop.run(decl, built(decl, {"elements": [{"id": "A", "type": "lampe"}]}), "ATTENTE")
    assert result["end"] == "limit" and len(result["steps"]) == 3


def test_a_closed_circuit_of_links_does_not_loop_forever():
    decl = declared()
    raw = {
        "elements": [{"id": "A", "type": "porte"}, {"id": "B", "type": "porte"}],
        "links": [{"from": "A", "to": "B"}, {"from": "B", "to": "A"}],
    }
    result = workshop.run(decl, built(decl, raw), "ATTENTE")
    assert result["end"] == "stable" and result["steps"][-1]["states"] == {"A": "ATTENTE", "B": "ATTENTE"}


def test_a_situation_is_checked_against_the_declaration():
    decl = declared()
    report = Report()
    sit = workshop.situation(
        decl,
        {
            "elements": [
                {"id": "A", "type": "porte", "options": {"niveau": "moyen"}},
                {"id": "B", "type": "fenetre"},
                {"id": "C", "type": "sas", "events": ["panne"]},
            ],
            "links": [{"from": "C", "to": "A"}, {"from": "A", "to": "Z"}, {"from": "A", "to": "C"}],
            "settings": {"alerte": "oui"},
        },
        report,
    )
    assert {(i.path, i.code) for i in report.errors} == {
        ("situation.elements[0].options.niveau", "unknown_value"),
        ("situation.elements[1].type", "unknown_brick"),
        ("situation.elements[2].events", "unknown_event"),
        ("situation.links[0]", "forbidden_link"),
        ("situation.links[1]", "unknown_element"),
        ("situation.settings.alerte", "unknown_value"),
    }
    # Ce qui est valide est gardé : l'interface travaille avec le reste.
    assert [e["id"] for e in sit["elements"]] == ["A", "C"] and sit["links"] == [
        {"from": "A", "to": "C", "type": "mene"}
    ]
    assert sit["elements"][0]["options"] == {"active": True, "niveau": "bas"} and sit["settings"] == {
        "alerte": False
    }


def test_an_address_round_trips_and_only_keeps_what_differs():
    decl = declared()
    raw = {
        "elements": [
            {
                "id": "A",
                "type": "porte",
                "label": "Entrée",
                "options": {"active": False},
                "events": ["panne"],
            },
            {"id": "B", "type": "sas"},
        ],
        "links": [{"from": "A", "to": "B"}],
        "settings": {"alerte": True},
    }
    sit = built(decl, raw)
    query = workshop.to_query(decl, sit)
    assert query == [
        ("e", "A:porte"),
        ("e", "B:sas"),
        ("n.A", "Entrée"),
        ("o.A.active", "false"),
        ("ev", "A:panne"),
        ("l", "A:mene:B"),
        ("r.alerte", "true"),
    ]
    as_lists: dict = {}
    for name, value in query:
        as_lists.setdefault(name, []).append(value)
    assert built(decl, workshop.from_query(decl, as_lists)) == sit


# ---------------------------------------------------------------------------
# Les deux études de démonstration : mêmes outils, règles différentes
# ---------------------------------------------------------------------------


def test_the_catalogue_rules_replay_its_task_scenarios():
    """Les règles que l'étude du catalogue déclare redonnent, scénario par scénario, les états finaux et
    l'issue que le catalogue annonce."""
    data = catalogue.load()
    decl = declared(catalogue.WORKSHOP, {s["key"] for s in catalogue.STATUSES})
    same = []
    for case in data["cases"]:
        if case["scope"] != "task" or case["actions"]:
            continue
        final = {key: state["status"] for key, state in case["frames"][-1]["states"].items()}
        events = {k: ["echec"] for k, v in final.items() if v in ("FINISHED_KO", "KO_IGNORED")}
        events.update({k: ["avertissement"] for k, v in final.items() if v == "WARNING"})
        report = Report()
        sit = workshop.situation(
            decl,
            {
                "elements": [
                    {
                        "id": n["id"],
                        "type": "task",
                        "events": events.get(n["id"], []),
                        "options": {k: n[k] for k in ("active", "always_run", "ignore_on_error")},
                    }
                    for n in case["nodes"]
                ],
                "links": [{"from": a, "to": b} for a, b in case["edges"]],
                "settings": {"stop_on_error": case["stop_on_error"]},
            },
            report,
        )
        if not report.ok:
            continue
        result = workshop.run(decl, sit, "WAITING")
        outcome = workshop.outcome_of(decl, result["world"])["status"]
        if result["steps"][-1]["states"] == final and outcome == case["frames"][-1]["workflow"]:
            same.append(case["displayNumber"])
    assert same == REPLAYED


def test_a_second_unrelated_study_gets_its_workshop_from_its_declarations_alone():
    """Un circuit de validation de document : d'autres briques, d'autres liens, d'autres règles, le même
    moteur. Ses règles redonnent, pas pour pas, les cas que l'étude dépose."""
    definition = circuit.DEFINITION
    decl = declared(circuit.WORKSHOP, {s["key"] for s in definition["statuses"]})
    assert [b["type"] for b in decl["bricks"]] == ["relecture", "signature", "publication"]
    for case in circuit.cases():
        final = {e["id"]: "A_FAIRE" for e in case["entities"]}
        for step in case["steps"]:
            final.update(step["changes"])
        sit = built(
            decl,
            {
                "elements": [
                    {
                        "id": e["id"],
                        "type": e["type"],
                        "label": e["label"],
                        "options": e.get("attrs", {}),
                        "events": ["refus"] if final[e["id"]] in ("REFUSE", "RESERVE") else [],
                    }
                    for e in case["entities"]
                ],
                "links": case["links"],
                "settings": case["config"],
            },
        )
        result = workshop.run(decl, sit, "A_FAIRE")
        assert result["steps"][-1]["states"] == final, case["key"]
        assert [
            step["changes"] and {c["id"]: c["to"] for c in step["changes"]} for step in result["steps"][1:]
        ] == [step["changes"] for step in case["steps"]], case["key"]
        assert workshop.outcome_of(decl, result["world"]) == case["outcome"], case["key"]


def test_the_site_code_names_no_demo_study():
    """Le moteur et l'écran ne connaissent aucune étude : le mot « Lancelot » ne vit que dans core/demo/."""
    core = Path(svc.__file__).parent
    found = [
        str(path.relative_to(core))
        for path in core.rglob("*")
        if path.is_file()
        and path.suffix in {".py", ".html", ".js", ".css", ".md", ".json", ".txt"}
        and "demo" not in path.relative_to(core).parts
        and "lancelot" in path.read_text(encoding="utf-8").lower()
    ]
    assert found == []


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def test_a_study_declares_its_workshop_through_the_api(api, atelier):
    status, data = api.get(f"/studies/{atelier}")
    assert status == 200 and data["workshop"]["rules"][0]["key"] == "P1"
    status, data = api.get(f"/studies/{atelier}/workshop")
    assert status == 200 and data["declared"] and data["default_status"] == "ATTENTE"
    assert [b["type"] for b in data["workshop"]["bricks"]] == ["porte", "sas"]
    assert (
        data["web_url"] == f"/etudes/{atelier}/atelier/"
        and data["limits"]["elements"] == workshop.MAX_ELEMENTS
    )
    bad = {**WORKSHOP, "rules": [{**WORKSHOP["rules"][0], "when": {"import": "os"}}]}
    status, data = api.patch(f"/studies/{atelier}", {"workshop": bad})
    assert status == 422 and data["error"]["details"][0]["path"] == "workshop.rules[0].when.import"
    # Un statut ne se retire pas sous une règle qui le nomme.
    status, data = api.patch(f"/studies/{atelier}", {"statuses": STUDY["statuses"][:4]})
    assert status == 422 and any(d["path"].startswith("workshop.rules") for d in data["error"]["details"])
    # Retirer la déclaration ferme l'atelier.
    status, _ = api.patch(f"/studies/{atelier}", {"workshop": {}})
    assert status == 200 and api.get(f"/studies/{atelier}/workshop")[1]["declared"] is False


def test_the_api_runs_a_situation_and_writes_nothing(api, atelier):
    study = svc.Study.objects.get(public_id=atelier)
    revision = study.revision
    situation = {
        "elements": [{"id": "A", "type": "porte", "events": ["panne"]}, {"id": "B", "type": "sas"}],
        "links": [{"from": "A", "to": "B", "type": "mene"}],
    }
    status, data = api.post(f"/studies/{atelier}/workshop/run", {"situation": situation})
    assert status == 200, data
    assert data["final"] == {"A": "KO", "B": "BLOQUE"} and data["end"] == "stable"
    assert data["outcome"] == {"label": "Passage coupé", "status": "KO"}
    assert [r["key"] for r in data["rules_applied"]] == ["P4", "P5", "P3"]
    assert data["steps"][2]["changes"] == [{"id": "A", "from": "EN_COURS", "to": "KO", "rule": "P5"}]
    assert data["case"]["entities"][0]["id"] == "A" and len(data["case"]["steps"]) == 4
    assert data["web_url"] == f"/etudes/{atelier}/atelier/?" + urlencode(
        [("e", "A:porte"), ("e", "B:sas"), ("ev", "A:panne"), ("l", "A:mene:B")]
    )
    study.refresh_from_db()
    assert study.revision == revision and not study.cases.exists()


def test_the_api_refuses_an_invalid_situation_field_by_field(api, atelier):
    status, data = api.post(
        f"/studies/{atelier}/workshop/run",
        {"situation": {"elements": [{"id": "A", "type": "fenetre"}], "links": [{"from": "A", "to": "A"}]}},
    )
    assert status == 422 and data["error"]["guide"].endswith("atelier")
    assert {d["path"] for d in data["error"]["details"]} == {
        "situation.elements[0].type",
        "situation.links[0]",
    }
    status, data = api.post(f"/studies/{atelier}/workshop/run", {"situation": {"elements": []}})
    assert status == 422 and data["error"]["details"][0]["code"] == "required"


def test_a_read_only_token_runs_the_workshop(atelier, token_for):
    reader = Api(token_for("ana", scopes=["studies:read"]))
    status, data = reader.post(
        f"/studies/{atelier}/workshop/run", {"situation": {"elements": [{"id": "A", "type": "sas"}]}}
    )
    assert status == 200 and data["final"] == {"A": "OK"}


def test_a_read_only_token_validates_a_declaration_and_writes_nothing(atelier, token_for):
    """Valider ne demande que de lire l'étude : la déclaration proposée est vérifiée, ses règles rendues, et
    celle de l'étude reste en place."""
    reader = Api(token_for("ana", scopes=["studies:read"]))
    before = svc.Study.objects.get(public_id=atelier)
    proposed = json.loads(json.dumps(WORKSHOP))
    proposed["title"] = "Une autre déclaration"
    del proposed["rules"][-1]
    status, data = reader.post(f"/studies/{atelier}/workshop/validate", {"workshop": proposed})
    assert status == 200 and data["valid"] and data["declared"] and data["written"] is False
    assert data["family"] == "linked" and data["workshop"]["title"] == "Une autre déclaration"
    # Pour cette famille, les règles rendues sont la table déclarée, normalisée.
    assert [r["key"] for r in data["rules"]] == [r["key"] for r in WORKSHOP["rules"][:-1]]
    after = svc.Study.objects.get(public_id=atelier)
    assert after.workshop == before.workshop and after.workshop["title"] != "Une autre déclaration"
    assert (after.revision, after.updated_at) == (before.revision, before.updated_at)
    assert data["study_revision"] == before.revision
    # Une règle qui nomme un statut que l'étude n'a pas : l'erreur est rendue, pas levée.
    proposed["rules"][0]["then"] = "INCONNU"
    status, data = reader.post(f"/studies/{atelier}/workshop/validate", {"workshop": proposed})
    assert status == 200 and data["valid"] is False and data["workshop"] is None
    assert data["errors"][0]["path"].startswith("workshop.rules[0]")
    # Sans accès à l'étude, elle est introuvable, comme partout.
    status, data = Api(token_for("ben")).post(f"/studies/{atelier}/workshop/validate", {"workshop": {}})
    assert status == 404


def test_a_study_without_rules_has_no_workshop(api, study, web):
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a")]})
    status, data = api.get(f"/studies/{study}/workshop")
    assert (
        status == 200
        and data["declared"] is False
        and data["workshop"] is None
        and "workshop" in data["hint"]
    )
    status, data = api.post(f"/studies/{study}/workshop/run", {"situation": {"elements": []}})
    assert status == 409 and data["error"]["code"] == "no_workshop"
    page = unescape(web("ana").get(f"/etudes/{study}/atelier/").content.decode())
    assert "Cette étude ne déclare pas de règles" in page
    assert f'href="/etudes/{study}/"' in page and "Voir les cas de l'étude" in page
    assert "data-atelier" not in page


# ---------------------------------------------------------------------------
# Écran
# ---------------------------------------------------------------------------


def test_the_workshop_starts_empty_and_shows_no_deposited_case(api, atelier, web):
    api.post(
        f"/studies/{atelier}/cases/batch",
        {"cases": [make_case("a", title="Un cas déposé bien reconnaissable")]},
    )
    page = unescape(web("ana").get(f"/etudes/{atelier}/atelier/").content.decode())
    assert (
        "Briques de l'étude" in page
        and 'name="add" value="porte"' in page
        and 'name="add" value="sas"' in page
    )
    assert "data-brick" not in page and "data-final" not in page
    assert "Un cas déposé bien reconnaissable" not in page
    assert "Les 6 règles que l'étude déclare" in page and "Une porte hors service ne s'ouvre pas" in page


def test_bricks_are_placed_linked_and_removed_through_the_address(atelier, web):
    client = web("ana")
    base = f"/etudes/{atelier}/atelier/"
    response = client.get(base + "?add=porte")
    assert response.status_code == 302 and response["Location"] == base + "?e=A%3Aporte"
    response = client.get(base + "?e=A:porte&add=sas")
    assert response["Location"] == base + "?e=A%3Aporte&e=B%3Asas"
    # Relier depuis la fiche de B (« accessible depuis A ») pose le lien de A vers B.
    response = client.get(base + "?e=A:porte&e=B:sas&lk.B=in:mene:A")
    assert response["Location"] == base + "?e=A%3Aporte&e=B%3Asas&l=A%3Amene%3AB"
    page = client.get(response["Location"]).content.decode()
    assert finals(page) == {"A": "OK", "B": "OK"} and "Passage libre" in page
    assert "mène à <b>Sas B</b>" in page and "accessible depuis <b>Porte A</b>" in page
    # Un lien que l'étude ne permet pas (un sas ne mène à rien) est ignoré.
    assert (
        client.get(base + "?e=A:porte&e=B:sas&lk.B=out:mene:A")["Location"] == base + "?e=A%3Aporte&e=B%3Asas"
    )
    response = client.get(base + "?e=A:porte&e=B:sas&l=A:mene:B&unlink=A:mene:B")
    assert response["Location"] == base + "?e=A%3Aporte&e=B%3Asas"
    # Retirer une brique retire ses liens ; la lettre libérée resservira.
    response = client.get(base + "?e=A:porte&e=B:sas&l=A:mene:B&del=A&add=porte")
    assert response["Location"] == base + "?e=B%3Asas&e=A%3Aporte"


def test_a_brick_dropped_on_another_is_chained_to_it(atelier, web):
    """Glisser une brique sur une autre : elle est posée, et reliée par le premier lien que l'étude permet."""
    client = web("ana")
    base = f"/etudes/{atelier}/atelier/"
    response = client.get(base + "?e=A:porte&add=sas&on=A")
    assert response["Location"] == base + "?e=A%3Aporte&e=B%3Asas&l=A%3Amene%3AB"
    # Un sas ne mène à rien : la porte déposée sur lui est posée, sans lien.
    assert client.get(base + "?e=A:sas&add=porte&on=A")["Location"] == base + "?e=A%3Asas&e=B%3Aporte"
    # Une cible qui n'existe pas ne change rien à la pose.
    assert client.get(base + "?e=A:porte&add=sas&on=Z")["Location"] == base + "?e=A%3Aporte&e=B%3Asas"


def test_the_schema_can_be_grabbed_in_the_workshop_and_nowhere_else(atelier, web):
    """Dans l'atelier, chaque brique et chaque lien du schéma dit qui il est, pour qu'on puisse le saisir. Le
    même déroulé, enregistré comme cas, est dessiné sans cela : l'espace de revue ne change pas."""
    client = web("ana")
    state = "e=A%3Aporte&e=B%3Asas&l=A%3Amene%3AB"
    page = client.get(f"/etudes/{atelier}/atelier/?{state}").content.decode()
    assert 'data-e="A"' in page and 'data-e="B"' in page
    assert 'data-l="A:mene:B"' in page and 'class="lk-hit"' in page
    assert 'data-kind="porte"' in page and "data-at-plan" in page
    links = json.loads(unescape(re.search(r'data-at-links="([^"]*)"', page).group(1)))
    assert links == [{"type": "mene", "label": "mène à", "from": ["porte"], "to": ["porte", "sas"]}]
    client.post(f"/etudes/{atelier}/atelier/", {"etat": state, "title": "Porte et sas"})
    panel = client.get(f"/etudes/{atelier}/?cas=atelier-1").content.decode()
    assert "Porte et sas" in panel and "rep-svg" in panel
    assert "data-e=" not in panel and "data-l=" not in panel and "lk-hit" not in panel


def test_options_events_and_settings_redraw_the_result(atelier, web):
    client = web("ana")
    base = f"/etudes/{atelier}/atelier/?e=A%3Aporte&e=B%3Asas"
    page = client.get(base + "&ev=A%3Apanne&l=A%3Amene%3AB").content.decode()
    assert finals(page) == {"A": "KO", "B": "BLOQUE"} and "Passage coupé" in page
    assert "Obtenu en 3 pas" in page and page.count("chip chip-on") == 3
    page = client.get(base + "&o.A.niveau=haut&l=A%3Amene%3AB&r.alerte=true").content.decode()
    assert finals(page) == {"A": "BLOQUE", "B": "BLOQUE"}
    # Un formulaire envoyé porte toutes les cases : une case décochée y vaut « non ».
    response = client.get(f"/etudes/{atelier}/atelier/?f=1&e=A:porte&n.A=Entrée")
    assert response["Location"].endswith("?e=A%3Aporte&n.A=Entr%C3%A9e&o.A.active=false")
    assert finals(client.get(response["Location"]).content.decode()) == {"A": "BLOQUE"}
    # Dans une adresse ordinaire, une option absente garde sa valeur par défaut.
    assert finals(client.get(f"/etudes/{atelier}/atelier/?e=A%3Aporte").content.decode()) == {"A": "OK"}


def test_the_walk_can_be_followed_without_script(atelier, web):
    client = web("ana")
    base = f"/etudes/{atelier}/atelier/?e=A%3Aporte&ev=A%3Apanne"
    page = client.get(base).content.decode()
    assert 'data-panel data-step="2"' in page and f'href="{escape(base)}&amp;etape=1"' in page
    first = client.get(base + "&etape=1").content.decode()
    assert 'data-panel data-step="0"' in first and "Situation de départ" in first
    assert client.get(base + "&etape=99")["Location"].endswith("&etape=3")


def test_a_damaged_address_gives_a_smaller_situation(atelier, web):
    client = web("ana")
    response = client.get(
        f"/etudes/{atelier}/atelier/?e=A:porte&e=A:sas&e=B:fenetre&e=%3Cscript%3E:porte&l=A:mene:Z&l=x"
        "&o.A.niveau=zzz&ev=A:rien&r.alerte=peut-etre&etape=abc"
    )
    assert response.status_code == 302 and response["Location"].endswith("?e=A%3Aporte")
    assert (
        client.get(f"/etudes/{atelier}/atelier/?" + "&".join("add=porte" for _ in range(40)))[
            "Location"
        ].count("porte")
        == workshop.MAX_ELEMENTS
    )


def test_the_workshop_needs_access(atelier, web):
    assert web("ben").get(f"/etudes/{atelier}/atelier/").status_code == 404


# ---------------------------------------------------------------------------
# De la situation construite à la revue : un geste humain
# ---------------------------------------------------------------------------


def test_a_human_saves_a_built_situation_as_a_case_to_review(atelier, web, users):
    study = svc.Study.objects.get(public_id=atelier)
    state = "e=A%3Aporte&e=B%3Asas&ev=A%3Apanne&l=A%3Amene%3AB"
    page = web("ana").get(f"/etudes/{atelier}/atelier/?{state}").content.decode()
    assert "Enregistrer comme cas" in page
    response = web("ana").post(f"/etudes/{atelier}/atelier/", {"etat": state, "title": "Panne à l'entrée"})
    assert response.status_code == 302 and "cas=atelier-1" in response["Location"]
    case = study.cases.get(key="atelier-1")
    assert case.title == "Panne à l'entrée" and case.family == "Atelier"
    assert case.content["references"][0]["kind"] == "atelier" and len(case.content["steps"]) == 4
    assert case.content["outcome"] == {"label": "Passage coupé", "status": "KO"}
    # Il attend un avis, comme tout cas : personne ne l'a jugé.
    assert svc.review_summary(svc.get_study(svc.Actor(users["ana"]), atelier))["without_decision"] == 1
    assert svc.AuditEvent.objects.filter(study=study, action="workshop.save").count() == 1


def test_an_ai_cannot_save_a_built_situation(api, atelier, users):
    study = svc.Study.objects.get(public_id=atelier)
    decl = study.workshop
    sit = built(decl, {"elements": [{"id": "A", "type": "sas"}]})
    token, _ = svc.create_token(users["ana"], "jeton", list(svc.SCOPES))
    study.my_role = "owner"
    with pytest.raises(svc.ServiceError) as caught:
        svc.save_built_case(svc.Actor(users["ana"], token), study, sit, "x")
    assert caught.value.code == "human_only" and not study.cases.exists()
    # L'API n'a aucune route pour enregistrer une situation : elle déroule, elle n'écrit pas.
    for path in ("workshop", "workshop/save", "workshop/run/save"):
        status, _ = api.post(
            f"/studies/{atelier}/{path}", {"situation": {"elements": [{"id": "A", "type": "sas"}]}}
        )
        assert status in (404, 405), path
    assert not study.cases.exists()


def test_a_viewer_builds_but_cannot_save(atelier, web, users):
    study = svc.Study.objects.get(public_id=atelier)
    svc.Membership.objects.create(study=study, user=users["ben"], role="viewer")
    client = web("ben")
    state = "e=A%3Asas"
    page = client.get(f"/etudes/{atelier}/atelier/?{state}").content.decode()
    assert finals(page) == {"A": "OK"} and "Enregistrer comme cas" not in page
    client.post(f"/etudes/{atelier}/atelier/", {"etat": state, "title": "x"})
    assert not study.cases.exists()


# ---------------------------------------------------------------------------
# Le mode d'emploi suit le code
# ---------------------------------------------------------------------------


def test_the_guide_examples_are_valid_and_give_what_the_guide_says(api):
    """La déclaration et la situation données en exemple aux IA passent telles quelles, et donnent le résultat
    que le chapitre annonce."""
    text = (Path(svc.__file__).parent / "guide" / "atelier.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)```", text, flags=re.DOTALL)
    declaration = json.loads("{" + next(b for b in blocks if b.startswith('"workshop"')) + "}")["workshop"]
    situation = json.loads(next(b for b in blocks if b.startswith('{"situation"')))
    statuses = [
        {"key": "A_FAIRE", "label": "À faire", "role": "waiting", "default": True},
        {"key": "EN_COURS", "label": "En cours", "role": "active"},
        {"key": "FAIT", "label": "Fait", "role": "success"},
        {"key": "ECHEC", "label": "Échec", "role": "error"},
        {"key": "BLOQUEE", "label": "Bloquée", "role": "blocked"},
    ]
    status, data = api.post(
        "/studies", {"title": "Exemple du guide", "statuses": statuses, "workshop": declaration}
    )
    assert status == 201, data
    status, data = api.post(f"/studies/{data['id']}/workshop/run", situation)
    assert status == 200, data
    assert data["final"] == {"A": "ECHEC", "B": "BLOQUEE", "C": "A_FAIRE"} and data["end"] == "stable"
    assert data["outcome"] == {"label": "Enchaînement en échec", "status": "ECHEC"}
    assert [r["key"] for r in data["rules_applied"]] == ["R2", "R3", "R1"]
    assert data["steps"][1]["changes"] == [{"id": "A", "from": "A_FAIRE", "to": "EN_COURS", "rule": "R2"}]
    # Chaque code d'erreur et chaque test de condition que le moteur connaît est nommé dans le chapitre.
    for word in (
        *workshop.ELEMENT_TESTS,
        *workshop.SHARED_TESTS,
        *workshop.QUANTIFIERS,
        "no_workshop",
        "max_steps",
    ):
        assert f"`{word}`" in text or f'"{word}"' in text, word
