"""Étude de démonstration « Responsable d'un magasin au fil du temps » : un atelier de périodes semé.

Les onze situations ci-dessous ont d'abord été vérifiées à la main, par l'API, sur une étude réelle de même
mécanique : trois sources, source rattachée gardée ou non, rattachement par un champ, priorité, fusion,
périodes invalides. Elles sont transposées ici sur l'étude fictive : les périodes attendues sont écrites à la
main, le moteur doit les redonner."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.core.management import call_command

from core import periods
from core import services as svc
from core.casemodel import Report
from core.demo import magasin
from core.models import Study

PORT, PHARE = "Halle du Port", "Halle du Phare"


def m(key, start, end, enseigne=PORT, caisse="v1"):
    return {
        "id": key,
        "type": "magasin",
        "start": start,
        "end": end,
        "options": {"enseigne": enseigne, "caisse": caisse},
    }


def n(key, start, end, agent="A1"):
    return {"id": key, "type": "nomination", "start": start, "end": end, "options": {"agent": agent}}


def f(key, start, end, matricule="A1", nom="Alice"):
    options = {"matricule": matricule, "nom": nom}
    return {"id": key, "type": "agent", "start": start, "end": end, "options": options}


_DEUX = [m("A", 1, 10), n("B", 2, 4), n("C", 6, 8), f("D", 1, 10)]
_RIVALES = [f("D", 1, 4, "A1", "Alice"), f("F", 1, 4, "A2", "Bruno")]
# (nom, périodes posées, réglage, lignes attendues (du, au, enseigne, responsable), publication bloquée)
SITUATIONS = [
    ("jours-retires", _DEUX, magasin.RETIRES, [(2, 4, PORT, "Alice"), (6, 8, PORT, "Alice")], False),
    (
        "jours-gardes",
        _DEUX,
        magasin.GARDES,
        [
            (1, 2, PORT, None),
            (2, 4, PORT, "Alice"),
            (4, 6, PORT, None),
            (6, 8, PORT, "Alice"),
            (8, 10, PORT, None),
        ],
        False,
    ),
    (
        "fusion",
        [m("A", 1, 3), m("B", 3, 4), m("C", 4, 6, PHARE), m("D", 6, 7)],
        magasin.GARDES,
        [(1, 4, PORT, None), (4, 6, PHARE, None), (6, 7, PORT, None)],
        False,
    ),
    (
        "fin-exclue",
        [m("A", 2, 3), m("B", 3, 4, PHARE)],
        magasin.GARDES,
        [(2, 3, PORT, None), (3, 4, PHARE, None)],
        False,
    ),
    (
        "image-de-fin-de-jour",
        [m("A", 1, 1.5), m("B", 1.5, 1.75, PHARE), m("C", 1.75, 2)],
        magasin.GARDES,
        [(1, 2, PORT, None)],
        False,
    ),
    (
        "champ-non-restitue",
        [m("A", 1, 3, caisse="v1"), m("B", 3, 5, caisse="v2")],
        magasin.GARDES,
        [(1, 5, PORT, None)],
        False,
    ),
    ("duree-nulle", [m("A", 1, 4), m("B", 2, 2, PHARE)], magasin.GARDES, [(1, 4, PORT, None)], False),
    ("bornes-inversees", [m("A", 1, 4), m("B", 3, 2, PHARE)], magasin.GARDES, [(1, 4, PORT, None)], True),
    ("borne-absente", [m("A", 1, 4), m("B", 2, None, PHARE)], magasin.GARDES, [(1, 4, PORT, None)], True),
    (
        "priorite-debut-le-plus-recent",
        [m("A", 1, 4), n("B", 1, 4, "A1"), n("C", 2, 4, "A2"), *_RIVALES],
        magasin.GARDES,
        [(1, 2, PORT, "Alice"), (2, 4, PORT, "Bruno")],
        False,
    ),
    (
        "priorite-meme-debut",
        [m("A", 1, 4), n("B", 2, 4, "A1"), n("C", 2, 4, "A2"), *_RIVALES],
        magasin.GARDES,
        [(1, 2, PORT, None), (2, 4, PORT, None)],
        True,
    ),
]


def run(elements: list, setting: str) -> dict:
    decl = magasin.declaration()
    report = Report()
    raw = {"elements": elements, "settings": {"sans_responsable": setting}}
    situation = periods.situation(decl, raw, report)
    assert report.ok, [(i.path, i.code) for i in report.errors]
    return periods.run(decl, situation, "A_VENIR")


def test_the_declaration_is_valid_and_reads_as_seven_rules():
    report = Report()
    statuses = {s["key"] for s in magasin.DEFINITION["statuses"]}
    decl = periods.normalize(magasin.WORKSHOP, statuses, report)
    assert report.ok, [(i.path, i.code) for i in report.errors]
    assert [r["key"] for r in decl["rules"]] == [f"P{i}" for i in range(1, 8)]
    assert "sauf quand « Jours sans responsable » vaut « retirés »" in decl["rules"][4]["title"]
    assert "« Matricule » vaut « Agent nommé » de « Nomination »" in decl["rules"][5]["title"]


@pytest.mark.parametrize(("name", "elements", "setting", "expected", "blocked"), SITUATIONS, ids=lambda v: v)
def test_the_eleven_situations_give_the_expected_history(name, elements, setting, expected, blocked):
    result = run(elements, setting)
    rows = [(i["start"], i["end"], *i["fields"].values()) for i in result["images"]]
    assert rows == expected, name
    assert bool(result["blocking"]) is blocked, result["blocking"]
    if blocked:
        assert {i["status"] for i in result["images"]} == {"BLOQUEE"}


def test_there_are_eleven_situations_and_they_cover_every_mechanism():
    assert len(SITUATIONS) == 11
    used = {e["type"] for _, elements, *_ in SITUATIONS for e in elements}
    assert used == {"magasin", "nomination", "agent"}
    assert {setting for _, _, setting, *_ in SITUATIONS} == {magasin.GARDES, magasin.RETIRES}


def test_the_tie_is_what_blocks_and_the_reason_is_said():
    result = run(SITUATIONS[-1][1], magasin.GARDES)
    assert result["blocking"] == ["Jour 2 : plusieurs « Nomination » en vigueur, à égalité"]
    result = run(SITUATIONS[8][1], magasin.GARDES)
    assert result["blocking"] == ["Magasin B : une période dont une borne manque"]


@pytest.fixture
def seeded(db):
    call_command("seed_demo", "--no-verdicts", verbosity=0)
    return Study.objects.get(title=magasin.TITLE)


def test_the_seeded_study_declares_a_periods_workshop(seeded):
    described = svc.workshop_out(seeded)
    assert described["declared"] and described["family"] == "periods"
    assert seeded.is_example and seeded.representation.slug == "frise-temporelle"
    assert [b["type"] for b in described["workshop"]["bricks"]] == ["magasin", "nomination", "agent"]


def test_the_seeded_cases_cover_every_combination_and_say_what_the_rules_say(seeded):
    cases = {c.key: c.content for c in seeded.cases.all()}
    assert len(cases) == 8
    combos = {(c["dimensions"]["sans_responsable"], c["dimensions"]["nominations"]) for c in cases.values()}
    assert len(combos) == 8
    lines = {}
    for key, content in cases.items():
        images = [e for e in content["entities"] if e["type"] == "image"]
        lines[key] = [(e["attrs"]["start"], e["attrs"]["end"], e["label"]) for e in images]
    assert lines["trou-gardes"] == [
        (1, 3, "Halle du Port · Alice"),
        (3, 5, "Halle du Port · ∅"),
        (5, 7, "Halle du Port · Bruno"),
    ]
    assert lines["trou-retires"] == [(1, 3, "Halle du Port · Alice"), (5, 7, "Halle du Port · Bruno")]
    assert lines["chevauchement-gardes"] == [(1, 4, "Halle du Port · Alice"), (4, 7, "Halle du Port · Bruno")]
    assert cases["egalite-gardes"]["outcome"]["label"] == "Publication bloquée"
    assert cases["trou-gardes"]["outcome"]["label"] == "Historique publié, avec des jours sans responsable"
    assert cases["continue-retires"]["outcome"]["label"] == "Historique publié"


def test_the_seeded_study_runs_a_situation_through_the_service(seeded):
    decl = svc.workshop_of(seeded)
    raw = {"elements": SITUATIONS[0][1], "settings": {"sans_responsable": magasin.RETIRES}}
    situation = periods.situation(decl, raw, Report())
    out = svc.workshop_run(seeded, situation)
    assert [(i["start"], i["end"]) for i in out["extra"]["images"]] == [(2, 4), (6, 8)]
    assert out["content"] is not None and out["outcome"]["label"] == "Historique publié"


def test_seeding_twice_changes_nothing(seeded):
    before = sorted((c.key, c.revision_no) for c in seeded.cases.all())
    call_command("seed_demo", "--no-verdicts", verbosity=0)
    assert Study.objects.filter(title=magasin.TITLE).count() == 1
    assert sorted((c.key, c.revision_no) for c in seeded.cases.all()) == before


def test_the_site_code_knows_nothing_of_this_study():
    """Le moteur et l'écran ne connaissent pas cette étude : ses mots ne vivent que dans core/demo/, et dans
    le semis qui l'importe."""
    core = Path(svc.__file__).parent
    words = ("magasin", "nomination", "halle du")
    found = [
        str(path.relative_to(core))
        for path in core.rglob("*")
        if path.is_file()
        and path.suffix in {".py", ".html", ".js", ".css", ".md", ".json", ".txt"}
        and "demo" not in path.relative_to(core).parts
        and path.name != "seed_demo.py"
        and any(word in path.read_text(encoding="utf-8").lower() for word in words)
    ]
    assert found == []
