"""Axe en dates, famille périodes : des rangs en jours ou en mois comptés depuis une date d'origine. Les
bornes s'écrivent en dates ISO, l'historique et la frise écrivent des dates, sur plusieurs années."""

from __future__ import annotations

import copy
import datetime as dt

import pytest

from core import casemodel, periods, temps
from core.casemodel import Report
from core.demo import garanties

KEYS = {s["key"] for s in garanties.DEFINITION["statuses"]}


def _decl(raw=garanties.WORKSHOP) -> dict:
    report = Report()
    decl = periods.normalize(raw, KEYS, report)
    assert report.ok, [(i.path, i.code, i.message) for i in report.errors]
    return decl


def test_les_conversions():
    origin = dt.date(2024, 1, 1)
    assert temps.index("day", origin, dt.date(2024, 3, 1)) == 60, "2024 est bissextile"
    assert temps.iso("day", origin, 60) == "2024-03-01" and temps.label("day", origin, 60) == "1 mars 2024"
    assert temps.index("month", origin, temps.parse("month", "2026-03")) == 26
    assert temps.label("month", origin, 26) == "mars 2026"
    assert [t[1] for t in temps.ticks("day", origin, 0, 1096)][:3] == [
        "janv. 2024",
        "juil. 2024",
        "janv. 2025",
    ]


def test_un_axe_de_trois_ans_en_jours():
    decl = _decl()
    assert decl["axis"]["calendar"] == "day" and decl["axis"]["max"] == 1095
    situation = periods.situation(decl, {"elements": garanties._SITUATIONS[1][3]}, Report())
    assert situation["elements"][1]["start"] == 273, "1er octobre 2025"
    images = periods.run(decl, situation, "A_VENIR")["images"]
    extra = periods.extra(decl, periods.run(decl, situation, "A_VENIR"))
    assert [(i["start_date"], i["end_date"]) for i in extra["images"]] == [
        ("2025-01-01", "2025-10-01"),
        ("2025-10-01", "2026-10-01"),
        ("2026-10-01", "2028-01-01"),
    ]
    assert len(images) == 3


def test_un_axe_en_mois():
    raw = copy.deepcopy(garanties.WORKSHOP)
    raw["axis"] = {"label": "Mois", "calendar": "month", "from": "2025-01", "to": "2028-01"}
    decl = _decl(raw)
    elements = [
        {
            "id": "A",
            "type": "contrat",
            "start": "2025-01",
            "end": "2028-01",
            "options": {"formule": "Essentielle"},
        },
        {
            "id": "B",
            "type": "garantie",
            "start": "2025-04",
            "end": "2025-07",
            "options": {"nom": "Vol", "surprime": 5},
        },
    ]
    situation = periods.situation(decl, {"elements": elements}, Report())
    assert [e["start"] for e in situation["elements"]] == [0, 3]
    assert ("de.B", "2025-04") in periods.to_query(decl, situation)


def test_l_adresse_et_les_bornes():
    decl = _decl()
    situation = periods.situation(decl, {"elements": garanties._SITUATIONS[1][3]}, Report())
    query = dict(periods.to_query(decl, situation))
    assert query["de.B"] == "2025-10-01" and query["a.B"] == "2026-10-01"
    again = periods.from_query(decl, {k: [v] for k, v in query.items()} | {"e": ["A:contrat", "B:garantie"]})
    assert [e["start"] for e in again["elements"]] == [0, 273]
    report = Report()
    periods.situation(
        decl,
        {"elements": [{"id": "A", "type": "contrat", "start": "2030-01-01", "end": "2031-01-01"}]},
        report,
    )
    issue = next(i for i in report.errors if i.code == "out_of_range")
    assert "2025-01-01" in issue.message and "2028-01-01" in issue.message


@pytest.mark.parametrize(
    "axis",
    [
        {"calendar": "semaine", "from": "2025-01-01", "to": "2026-01-01"},
        {"calendar": "day", "from": "2026-01-01", "to": "2025-01-01"},
        {"calendar": "day", "from": "hier", "to": "2026-01-01"},
        {"calendar": "day", "from": "2000-01-01", "to": "2030-01-01"},  # plus de 4 000 jours
    ],
)
def test_un_axe_en_dates_mal_ecrit_est_refuse(axis):
    raw = copy.deepcopy(garanties.WORKSHOP)
    raw["axis"] = axis
    report = Report()
    periods.normalize(raw, KEYS, report)
    assert ("workshop.axis", "type") in {(i.path, i.code) for i in report.errors}


def test_le_cas_porte_son_axe_et_la_frise_ecrit_des_dates(api, web):
    case = garanties.cases()[3]
    assert case["time_axis"] == {"unit": "day", "origin": "2025-01-01"}
    assert case["steps"][1]["title"].startswith("1 janv. 2025 :")
    sid = api.post("/studies", garanties.DEFINITION)[1]["id"]
    assert api.post(f"/studies/{sid}/cases/batch", {"cases": [case]})[0] in (200, 201)
    html = web("ana").get(f"/etudes/{sid}/cas/{case['key']}/panneau/").content.decode()
    assert ">janv. 2026<" in html, "graduations datées sur la frise"


def test_time_axis_mal_ecrit_est_refuse():
    raw = copy.deepcopy(garanties.cases()[0])
    raw["time_axis"] = {"unit": "day", "origin": "demain"}
    raw.pop("dimensions")
    raw["rules"] = []
    ctx = casemodel.StudyContext(statuses=garanties.DEFINITION["statuses"], dimensions=[], rules=[])
    _, report = casemodel.normalize_case(raw, ctx)
    assert "type" in {i.code for i in report.errors if i.path.endswith("time_axis")}


def test_l_atelier_montre_des_champs_de_date(api, web):
    sid = api.post("/studies", garanties.DEFINITION)[1]["id"]
    page = (
        web("ana")
        .get(f"/etudes/{sid}/atelier/?e=A:contrat&de.A=2025-01-01&a.A=2028-01-01", follow=True)
        .content.decode()
    )
    assert 'type="date" name="de.A" value="2025-01-01"' in page and 'data-origin="2025-01-01"' in page
    assert "1 janv. 2025" in page
