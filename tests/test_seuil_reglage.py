"""Un seuil lu dans un réglage : {"lt": {"setting": "capacite"}} au lieu d'un nombre écrit dans la règle, dans
les trois familles d'atelier. Le réglage doit exister et, pour un ordre (gt, gte, lt, lte), être numérique."""

from __future__ import annotations

import copy

import pytest

from core import calc, periods, workshop
from core.casemodel import Report

from .test_atelier import STATUSES
from .test_calcul import KEYS, REPAS, declared, lines, meal, ran
from .test_comparer_compter import LEVELS, door, finals
from .test_periodes import STATUSES as PERIOD_STATUSES
from .test_periodes import WORKSHOP as PERIOD_WORKSHOP


def _linked(outcome_when: dict) -> dict:
    raw = copy.deepcopy(LEVELS)
    raw["settings"] += [
        {"key": "capacite", "label": "Portes ouvertes au plus", "values": [1, 2, 3]},
        {"key": "mode", "label": "Mode", "values": ["jour", "nuit"]},
    ]
    raw["outcome"] = [{"when": outcome_when, "label": "Trop de portes"}, {"label": "Dans la limite"}]
    return raw


def _codes(raw, normalize, statuses) -> set[str]:
    report = Report()
    normalize(raw, statuses, report)
    return {issue.code for issue in report.errors}


def test_un_compte_compare_a_un_reglage():
    raw = _linked(
        {"elements": {"type": "porte", "count": {"gt": {"setting": "capacite"}}, "where": {"status": "OK"}}}
    )
    report = Report()
    decl = workshop.normalize(raw, STATUSES, report)
    assert report.ok, [(i.path, i.code) for i in report.errors]
    doors = [door("A"), door("B"), door("C")]  # trois portes hors du toit : elles s'ouvrent (règle N2)
    assert finals(decl, doors, settings={"seuil": 0, "capacite": 2})[1] == "Trop de portes"
    assert finals(decl, doors, settings={"seuil": 0, "capacite": 3})[1] == "Dans la limite"


def test_une_option_comparee_a_un_reglage():
    raw = _linked(
        {"elements": {"count": {"gte": 1}, "where": {"option": {"niveau": {"gt": {"setting": "capacite"}}}}}}
    )
    report = Report()
    decl = workshop.normalize(raw, STATUSES, report)
    assert report.ok
    assert finals(decl, [door("A", 3)], settings={"seuil": 0, "capacite": 2})[1] == "Trop de portes"
    assert finals(decl, [door("A", 2)], settings={"seuil": 0, "capacite": 2})[1] == "Dans la limite"


@pytest.mark.parametrize(
    ("count", "code"),
    [
        ({"gt": {"setting": "inconnu"}}, "unknown_setting"),
        ({"gt": {"setting": "mode"}}, "not_numeric"),
        ({"in": {"setting": "capacite"}}, "type"),
    ],
)
def test_un_reglage_inconnu_ou_non_numerique_est_refuse(count, code):
    raw = _linked({"elements": {"count": count}})
    assert code in _codes(raw, workshop.normalize, STATUSES)


def test_les_periodes_comparent_a_un_reglage():
    raw = copy.deepcopy(PERIOD_WORKSHOP)
    raw["settings"] += [
        {"key": "palier", "label": "Palier", "values": [0, 5, 10]},
        {"key": "seuil_remise", "label": "Seuil de remise", "values": [5, 8]},
    ]
    raw["image"]["status"] = [
        {"when": {"setting": {"palier": {"gte": {"setting": "seuil_remise"}}}}, "then": "REMISE"},
        {"then": "PLEIN"},
    ]
    report = Report()
    decl = periods.normalize(raw, PERIOD_STATUSES, report)
    assert report.ok, [(i.path, i.code) for i in report.errors]
    for palier, seuil, status in ((5, 5, "REMISE"), (5, 8, "PLEIN"), (10, 8, "REMISE")):
        situation = periods.situation(
            decl,
            {
                "elements": [{"id": "A", "type": "contrat", "start": 1, "end": 4}],
                "settings": {"palier": palier, "seuil_remise": seuil},
            },
            Report(),
        )
        assert {image["status"] for image in periods.run(decl, situation, "ACTIVE")["images"]} == {status}


def test_le_calcul_compare_le_cumul_a_un_reglage():
    raw = copy.deepcopy(REPAS)
    raw["settings"].append({"key": "alerte", "label": "Alerte", "values": [20, 30, 40], "default": 30})
    raw["lines"][2]["when"] = {"total": {"gt": {"setting": "alerte"}}}
    decl = declared(raw)
    _, low = ran(decl, [meal("A", 25)], {"alerte": 30})
    _, high = ran(decl, [meal("A", 25)], {"alerte": 20, "plafond": 25})
    assert lines(low)["cher"][0] == "skipped" and lines(high)["cher"][0] == "applied"
    raw["lines"][2]["when"] = {"total": {"gt": {"setting": "absent"}}}
    report = Report()
    calc.normalize(raw, KEYS, report)
    assert not report.ok
