"""Combiner des périodes simultanées, famille périodes : au lieu d'en garder une, le site combine les champs
des périodes en vigueur (somme, minimum, maximum, liste). Les autres départages ne changent pas."""

from __future__ import annotations

import copy

import pytest
from django.core.management import call_command

from core import periods
from core import services as svc
from core.casemodel import Report
from core.demo import garanties
from core.models import Study

KEYS = {s["key"] for s in garanties.DEFINITION["statuses"]}


def _decl(raw=garanties.WORKSHOP) -> dict:
    report = Report()
    decl = periods.normalize(raw, KEYS, report)
    assert report.ok, [(i.path, i.code, i.message) for i in report.errors]
    return decl


def _images(decl, elements):
    situation = periods.situation(decl, {"elements": elements}, Report())
    return periods.run(decl, situation, "A_VENIR")["images"]


def _rows(images):
    return [(i["start"], i["end"], i["fields"]["garanties"], i["fields"]["surprime"]) for i in images]


ELEMENTS = garanties._SITUATIONS[3][3]  # trois garanties qui se croisent


def test_les_surprimes_s_additionnent_et_les_noms_se_lisent_ensemble():
    assert _rows(_images(_decl(), ELEMENTS)) == [
        (1, 3, "Vol", 5),
        (3, 5, "Vol + Bris de glace", 8),
        (5, 6, "Vol + Bris de glace + Assistance", 16),
        (6, 7, "Vol + Bris de glace", 8),
        (7, 9, "Bris de glace", 3),
        (9, 13, None, None),
    ]


@pytest.mark.parametrize(("how", "value"), [("min", 3), ("max", 8)])
def test_minimum_et_maximum(how, value):
    raw = copy.deepcopy(garanties.WORKSHOP)
    raw["image"]["sources"][1]["combine"]["surprime"] = how
    assert _rows(_images(_decl(raw), ELEMENTS))[2][3] == value


def test_les_periodes_combinees_sont_toutes_en_vigueur():
    decl = _decl()
    situation = periods.situation(decl, {"elements": ELEMENTS}, Report())
    case = periods.to_case(decl, situation, periods.run(decl, situation, "A_VENIR"), "A_VENIR")
    notes = " ".join(step.get("note", "") for step in case["steps"])
    assert "combinées" in notes
    lost = [k for image in periods.run(decl, situation, "A_VENIR")["images"] for k in image["beaten"]]
    assert lost == [], "aucune garantie n'est devancée : toutes comptent"


@pytest.mark.parametrize(
    ("combine", "code"),
    [
        (None, "required"),
        ({"inconnu": "sum"}, "unknown_option"),
        ({"surprime": "moyenne"}, "enum"),
        ({"nom": "sum"}, "not_numeric"),
    ],
)
def test_une_combinaison_fausse_est_refusee(combine, code):
    raw = copy.deepcopy(garanties.WORKSHOP)
    if combine is None:
        del raw["image"]["sources"][1]["combine"]
    else:
        raw["image"]["sources"][1]["combine"] = combine
    report = Report()
    periods.normalize(raw, KEYS, report)
    assert code in {i.code for i in report.errors}


def test_le_semis_et_l_accord_avec_l_atelier(db):
    call_command("seed_demo", "--no-verdicts", verbosity=0)
    study = Study.objects.get(title=garanties.TITLE)
    assert study.cases.count() == len(garanties._SITUATIONS)
    codes = {f["code"] for f in svc.checks_report(study)}
    assert not codes & {"workshop_mismatch", "workshop_untranslatable"}
