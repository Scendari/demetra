"""Règles d'atelier qui comparent (gt, gte, lt, lte, ne, in) et qui comptent (count), dans le socle commun :
pour les éléments reliés comme pour les périodes. Une valeur simple garde son sens d'égalité stricte."""

from __future__ import annotations

import copy

import pytest

from core import periods, workshop
from core.casemodel import Report

from .test_atelier import STATUSES, built
from .test_periodes import STATUSES as PERIOD_STATUSES
from .test_periodes import WORKSHOP as PERIOD_WORKSHOP

LEVELS = {
    "title": "Des portes à niveaux",
    "bricks": [
        {
            "type": "porte",
            "label": "Porte",
            "options": [
                {"key": "niveau", "label": "Niveau", "values": [1, 2, 3]},
                {"key": "zone", "label": "Zone", "values": ["hall", "quai", "toit"]},
            ],
        },
        {"type": "sas", "label": "Sas"},
    ],
    "links": [{"type": "mene", "label": "mène à", "from": ["porte"], "to": ["sas"]}],
    "settings": [{"key": "seuil", "label": "Seuil d'alerte", "values": [0, 2, 3]}],
    "rules": [
        {
            "key": "N1",
            "title": "Au-dessus du seuil, une porte reste fermée",
            "on": "porte",
            "when": {"status": "ATTENTE", "option": {"niveau": {"gt": 1}}, "setting": {"seuil": {"gte": 2}}},
            "then": "BLOQUE",
        },
        {
            "key": "N2",
            "title": "Une porte hors du toit s'ouvre",
            "on": "porte",
            "when": {"status": "ATTENTE", "option": {"zone": {"ne": "toit"}}},
            "then": "OK",
        },
        {
            "key": "N3",
            "title": "Un sas s'ouvre quand au moins deux portes ouvertes y mènent",
            "on": "sas",
            "when": {"status": "ATTENTE", "incoming": {"count": {"gte": 2}, "where": {"status": "OK"}}},
            "then": "OK",
        },
    ],
    "outcome": [
        {"when": {"elements": {"type": "porte", "count": 0}}, "label": "Aucune porte"},
        {"when": {"elements": {"count": {"gte": 1}, "where": {"status": "BLOQUE"}}}, "label": "Passage gêné"},
        {"label": "Passage libre"},
    ],
}


def declared(raw=LEVELS) -> dict:
    report = Report()
    decl = workshop.normalize(raw, STATUSES, report)
    assert report.ok, [(i.path, i.code, i.message) for i in report.errors]
    return decl


def finals(decl, elements, links=(), settings=None) -> tuple[dict, str | None]:
    sit = built(decl, {"elements": elements, "links": list(links), "settings": settings or {}})
    result = workshop.run(decl, sit, "ATTENTE")
    found = workshop.outcome(decl, result)
    return result["steps"][-1]["states"], found and found["label"]


def door(key, niveau=1, zone="hall"):
    return {"id": key, "type": "porte", "options": {"niveau": niveau, "zone": zone}}


def test_an_option_and_a_setting_are_compared_to_a_number():
    decl = declared()
    states, outcome = finals(decl, [door("A", 3), door("B", 1)], settings={"seuil": 2})
    assert states == {"A": "BLOQUE", "B": "OK"} and outcome == "Passage gêné"
    states, _ = finals(decl, [door("A", 3)], settings={"seuil": 0})  # sous le seuil : la règle N1 ne joue pas
    assert states == {"A": "OK"}


def test_ne_excludes_a_value():
    states, _ = finals(declared(), [door("A", zone="toit"), door("B", zone="quai")])
    assert states == {"A": "ATTENTE", "B": "OK"}


def test_count_counts_the_neighbours_that_match():
    decl = declared()
    two = [door("A"), door("B"), {"id": "S", "type": "sas"}]
    states, outcome = finals(decl, two, [{"from": "A", "to": "S"}, {"from": "B", "to": "S"}])
    assert states["S"] == "OK" and outcome == "Passage libre"
    one = [door("A"), door("B", zone="toit"), {"id": "S", "type": "sas"}]
    states, _ = finals(decl, one, [{"from": "A", "to": "S"}, {"from": "B", "to": "S"}])
    assert states["S"] == "ATTENTE"
    assert finals(decl, [{"id": "S", "type": "sas"}])[1] == "Aucune porte"


def test_in_accepts_a_list_of_declared_values():
    raw = copy.deepcopy(LEVELS)
    raw["rules"][1]["when"]["option"] = {"zone": {"in": ["hall", "quai"]}}
    assert finals(declared(raw), [door("A", zone="toit"), door("B")])[0] == {"A": "ATTENTE", "B": "OK"}


@pytest.mark.parametrize(
    ("when", "path", "code"),
    [
        ({"option": {"zone": {"gt": 1}}}, "workshop.rules[0].when.option.zone.gt", "not_numeric"),
        ({"option": {"niveau": {"gte": "deux"}}}, "workshop.rules[0].when.option.niveau.gte", "type"),
        ({"option": {"niveau": {"ne": 9}}}, "workshop.rules[0].when.option.niveau.ne", "unknown_value"),
        ({"option": {"zone": {"in": []}}}, "workshop.rules[0].when.option.zone.in", "unknown_value"),
        ({"option": {"niveau": {"environ": 2}}}, "workshop.rules[0].when.option.niveau", "type"),
        ({"option": {"niveau": {"gt": 1, "lt": 3}}}, "workshop.rules[0].when.option.niveau", "type"),
        ({"incoming": {"count": "deux"}}, "workshop.rules[0].when.incoming.count", "type"),
        ({"incoming": {"count": 2, "all": {"status": "OK"}}}, "workshop.rules[0].when.incoming", "type"),
        ({"incoming": {"all": {"status": "OK"}, "where": {}}}, "workshop.rules[0].when.incoming", "type"),
        (
            {"incoming": {"count": 1, "where": {"couleur": 2}}},
            "workshop.rules[0].when.incoming.where.couleur",
            "unknown_test",
        ),
    ],
)
def test_a_wrong_comparison_or_count_is_refused_with_its_path(when, path, code):
    raw = copy.deepcopy(LEVELS)
    raw["rules"][0]["when"] = when
    report = Report()
    workshop.normalize(raw, STATUSES, report)
    assert (path, code) in [(i.path, i.code) for i in report.errors], [
        (i.path, i.code) for i in report.errors
    ]


def test_a_plain_value_keeps_meaning_strict_equality():
    raw = copy.deepcopy(LEVELS)
    raw["rules"][0]["when"] = {"status": "ATTENTE", "option": {"niveau": 3}}
    decl = declared(raw)
    assert finals(decl, [door("A", 3), door("B", 2)])[0] == {"A": "BLOQUE", "B": "OK"}


def test_periods_compare_a_setting_too():
    raw = copy.deepcopy(PERIOD_WORKSHOP)
    raw["settings"].append({"key": "palier", "label": "Palier", "values": [0, 5, 10]})
    raw["image"]["status"] = [
        {"when": {"setting": {"palier": {"gte": 5}}}, "then": "REMISE"},
        {"then": "PLEIN"},
    ]
    report = Report()
    decl = periods.normalize(raw, PERIOD_STATUSES, report)
    assert report.ok, [(i.path, i.code) for i in report.errors]
    for palier, status in ((10, "REMISE"), (0, "PLEIN")):
        situation = periods.situation(
            decl,
            {
                "elements": [{"id": "A", "type": "contrat", "start": 1, "end": 4}],
                "settings": {"palier": palier},
            },
            Report(),
        )
        images = periods.run(decl, situation, "ACTIVE")["images"]
        assert {image["status"] for image in images} == {status}
    raw["image"]["status"][0]["when"] = {"setting": {"sans_remise": {"gt": 1}}}
    report = Report()
    periods.normalize(raw, PERIOD_STATUSES, report)
    assert "unknown_value" in {i.code for i in report.errors}
