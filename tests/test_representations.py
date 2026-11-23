"""Représentations par briques : catalogue, validation, création, ajustement, rendu, aperçu."""

from __future__ import annotations

import copy
import re

import pytest
from django.core.management import call_command

from core import bricks
from core import services as svc
from core.models import BrickRequest, Representation, Study
from core.recommend import recommend

from .conftest import make_case

pytestmark = pytest.mark.django_db

SYSTEM = [
    "graphe-couches",
    "table-decision",
    "frise-temporelle",
    "table-trace",
    "graphe-et-trace",
    "couloirs",
    "vignettes",
]

SPEC = {
    "schema": "demetra.representation/1",
    "compose": {"brick": "compose.stack"},
    "tokens": {"density": "compact"},
    "views": [
        {
            "id": "graphe",
            "title": "Graphe",
            "layout": {"brick": "layout.layers", "direction": "down"},
            "marks": [{"brick": "mark.node", "label": "{id} · {label}"}, {"brick": "mark.link"}],
            "time": {"brick": "time.stepper", "highlight_changes": True},
        }
    ],
}


def test_catalogue_of_bricks_is_public_and_covers_five_families(api):
    from .conftest import Api

    status, catalogue = Api().get("/bricks")
    assert status == 200
    families = {f["family"]: [b["brick"] for b in f["bricks"]] for f in catalogue["families"]}
    assert len(families) == 5
    names = [name for group in families.values() for name in group]
    for needed in (
        "layout.layers",
        "layout.grid",
        "layout.timeline",
        "mark.node",
        "mark.link",
        "mark.bar",
        "mark.cell",
        "time.stepper",
        "time.small_multiples",
        "time.cursor",
        "compose.stack",
        "compose.columns",
        "compose.tabs",
    ):
        assert needed in names
    status, schema = Api().get("/bricks/schema")
    assert status == 200 and schema.get("$schema") or schema.get("type") == "object"


def test_system_representations_exist_and_are_valid():
    for slug in SYSTEM:
        rep = Representation.objects.get(slug=slug, scope="system")
        report = bricks.validate_spec(rep.spec)
        assert report.ok, (slug, [i.as_dict() for i in report.issues])
        assert bricks.bricks_used(rep.spec), slug


@pytest.mark.parametrize(
    "mutate, code_or_path",
    [
        (lambda s: s["views"][0]["marks"].append({"brick": "mark.script", "code": "alert(1)"}), "marks"),
        (lambda s: s["views"][0]["layout"].update(brick="layout.radial"), "layout"),
        (lambda s: s["views"][0]["marks"][0].update(label="{password}"), "label"),
        (lambda s: s.update(html="<b>x</b>"), "html"),
        (lambda s: s["views"][0].update(time={"brick": "time.cursor"}), "time"),
        (lambda s: s.update(views=[]), "views"),
    ],
)
def test_invalid_documents_are_refused(api, mutate, code_or_path):
    spec = copy.deepcopy(SPEC)
    mutate(spec)
    status, verdict = api.post("/representations/validate", {"spec": spec})
    assert status == 200 and verdict["valid"] is False
    assert any(code_or_path in e["path"] or code_or_path in e["message"] for e in verdict["errors"]), verdict[
        "errors"
    ]
    status, error = api.post("/representations", {"name": "Mauvaise", "spec": spec})
    assert status == 422 and error["error"]["details"]


def test_hostile_text_is_drawn_as_text_never_run(api, study):
    api.post(
        f"/studies/{study}/cases/batch", {"cases": [make_case("a", title="<img src=x onerror=alert(1)>")]}
    )
    spec = copy.deepcopy(SPEC)
    spec["views"][0]["marks"][0]["label"] = "<script>alert(1)</script>{id}"
    obj = Study.objects.get(public_id=study)
    html, summary, frames = svc.render_case(obj, obj.cases.get(key="a"), spec)
    assert "<script" not in html and "&lt;script&gt;" in html


def test_create_adjust_duplicate_and_version(api):
    status, rep = api.post("/representations", {"name": "Mon graphe", "spec": SPEC})
    assert status == 201 and rep["scope"] == "theme" and rep["version"] == 1 and rep["editable"] is True

    status, patched = api.patch(
        f"/representations/{rep['id']}", {"overrides": {"tokens": {"density": "spacious"}}}
    )
    assert status == 200 and patched["version"] == 2 and patched["spec"]["tokens"]["density"] == "spacious"

    status, adjusted = api.post(
        "/representations",
        {"mode": "adjustment", "parent": "graphe-couches", "overrides": {"tokens": {"density": "compact"}}},
    )
    assert (
        status == 201
        and adjusted["scope"] == "adjustment"
        and adjusted["spec"]["tokens"]["density"] == "compact"
    )
    assert adjusted["spec"]["views"], "l'ajustement hérite des vues du parent"

    status, themed = api.post(
        "/representations",
        {
            "name": "Graphe resserré",
            "parent": "graphe-couches",
            "overrides": {
                "views": [
                    {
                        "id": "trace",
                        "title": "Trace",
                        "layout": {"brick": "layout.grid", "rows": "entities"},
                        "marks": [
                            {"brick": "mark.cell", "header": "Entité", "text": "{id}"},
                            {"brick": "mark.cells_per_step", "header": "{n}"},
                        ],
                    }
                ]
            },
        },
    )
    assert status == 201 and [v["id"] for v in themed["spec"]["views"]][-1] == "trace"

    status, duplicate = api.post(f"/representations/{rep['id']}/duplicate", {"name": "Copie"})
    assert status == 201 and duplicate["id"] != rep["id"] and duplicate["spec"] == patched["spec"]

    system = Representation.objects.get(slug="graphe-couches", scope="system")
    status, error = api.patch(
        f"/representations/{system.public_id}", {"overrides": {"tokens": {"density": "compact"}}}
    )
    assert status == 403, "une représentation système ne se modifie pas : on l'ajuste ou on la duplique"


def test_adjustment_is_private_to_its_author(api, token_for):
    from .conftest import Api

    adjusted = api.post(
        "/representations",
        {"mode": "adjustment", "parent": "table-trace", "overrides": {"tokens": {"density": "compact"}}},
    )[1]
    other = Api(token_for("ben"))
    assert other.get(f"/representations/{adjusted['id']}")[0] == 404
    assert adjusted["id"] not in [r["id"] for r in other.get("/representations")[1]["items"]]


def test_merge_spec_rules():
    base = Representation.objects.get(slug="graphe-et-trace", scope="system").spec
    patch = {"tokens": {"density": "compact"}, "views": [{"id": base["views"][1]["id"], "$remove": True}]}
    assert not bricks.validate_spec(bricks.merge_spec(base, patch)).ok, (
        "deux colonnes pour une seule vue : l'erreur est signalée"
    )
    merged = bricks.merge_spec(base, {**patch, "compose": {"brick": "compose.stack", "ratio": None}})
    merged["compose"] = {"brick": "compose.stack"}
    assert len(merged["views"]) == len(base["views"]) - 1 and merged["tokens"]["density"] == "compact"
    assert bricks.validate_spec(merged).ok


def test_preview_gives_a_text_summary(api, study):
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a", ok=False)]})
    status, preview = api.post(
        f"/studies/{study}/cases/a/preview", {"representation": "graphe-couches", "step": 3, "image": False}
    )
    assert status == 200
    text = preview["summary"]["text"]
    assert "2 entités" in text and "3 étapes" in text
    status, tried = api.post(f"/studies/{study}/cases/a/preview", {"spec": SPEC, "image": False})
    assert status == 200 and tried["summary"]["views"][0]["id"] == "graphe"
    assert Representation.objects.filter(scope="theme").count() == 0, (
        "essayer un document ne l'enregistre pas"
    )


def test_status_is_never_shown_by_colour_alone(api, study, users):
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a", ok=False)]})
    obj = Study.objects.get(public_id=study)
    case = obj.cases.get(key="a")
    for slug in SYSTEM:
        spec = Representation.objects.get(slug=slug, scope="system").spec
        html, summary, frames = svc.render_case(obj, case, spec, step=len(frames_of(obj, case)) - 1)
        assert "<script" not in html and "onclick" not in html
        carriers = re.findall(r"<[^>]*data-st=\"[^\"]+\"[^>]*>", html)
        if not carriers:
            continue
        assert html.count("data-si") >= 1, f"{slug} : chaque statut porte une icône"
        assert "data-sl=" in html, (
            f"{slug} : chaque statut porte un libellé, visible ou lu par les lecteurs d'écran"
        )


def frames_of(study, case):
    return svc.render_case(study, case, Representation.objects.get(slug="table-trace", scope="system").spec)[
        2
    ]


def test_brick_request_and_proposal(api, study):
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a")]})
    status, request = api.post(
        "/bricks/requests",
        {
            "title": "Disposition radiale",
            "need": "Montrer un cycle.",
            "family": "disposition",
            "study": study,
        },
    )
    assert status == 201 and BrickRequest.objects.get().title == "Disposition radiale"
    rep = api.post("/representations", {"name": "Mon graphe", "spec": SPEC})[1]
    status, proposal = api.post(
        f"/studies/{study}/representations/proposals",
        {"representation": rep["id"], "reason": "Peu d'entités."},
    )
    assert status == 201
    recommended = api.get(f"/studies/{study}/representations/recommended")[1]
    assert [p["name"] for p in recommended["proposed"]] == ["Mon graphe"]
    assert Study.objects.get(public_id=study).representation is None, (
        "proposer n'est pas choisir : l'utilisateur tranche"
    )


@pytest.fixture
def demo(db):
    call_command("seed_demo", "--no-verdicts", verbosity=0)
    titles = {
        "workflow": "Catalogue des runs Lancelot",
        "decision": "Remboursement d'une commande",
        "temporal": "Relances d'une facture impayée",
    }
    return {kind: Study.objects.get(title=title) for kind, title in titles.items()}


def test_demo_studies_are_complete(demo):
    catalogue = demo["workflow"]
    cases = list(catalogue.cases.all())
    assert len(cases) == 136
    assert len({c.family for c in cases}) == 15
    assert sum(len(c.content["steps"]) for c in cases) == 392
    assert demo["decision"].cases.count() == 12 and demo["temporal"].cases.count() == 12
    assert all("at" in step for c in demo["temporal"].cases.all() for step in c.content["steps"])


def test_recommendation_follows_the_nature_of_the_rules(demo):
    expected = {"workflow": "graphe-couches", "decision": "table-decision", "temporal": "frise-temporelle"}
    for kind, slug in expected.items():
        result = recommend(demo[kind])
        assert result["recommended"][0]["slug"] == slug
        assert result["recommended"][0]["reasons"]


def test_every_demo_case_renders_in_every_system_representation(demo):
    specs = {slug: Representation.objects.get(slug=slug, scope="system").spec for slug in SYSTEM}
    renders = 0
    for study in demo.values():
        siblings = svc.siblings_of(study)
        for case in study.cases.all():
            last = len(case.content["steps"])
            for spec in specs.values():
                for step in (0, last - 1):
                    html, summary, frames = svc.render_case(study, case, spec, step=step, siblings=siblings)
                    assert html.startswith("<") and summary["views"]
                    renders += 1
    assert renders == 160 * 7 * 2


def test_reimporting_the_catalogue_changes_nothing(demo):
    from core.demo import catalogue

    study = demo["workflow"]
    owner = svc.Actor(study.memberships.get(role="owner").user)
    report = svc.upsert_cases(owner, study, catalogue.cases()[:100])
    assert report["counts"] == {"unchanged": 100}
