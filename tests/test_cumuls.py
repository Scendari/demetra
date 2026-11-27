"""Plusieurs cumuls dans un atelier de calcul : chaque ligne dit lequel elle touche (`into`), une valeur peut
lire n'importe quel cumul, et le résultat peut les combiner. Un atelier à un seul cumul ne change pas."""

from __future__ import annotations

import copy

import pytest

from core import calc
from core.casemodel import Report

from .test_calcul import KEYS, REPAS, declared, meal, ran

PARTAGE = copy.deepcopy(REPAS)
PARTAGE["accumulators"] = [
    {"key": "rembourse", "label": "Remboursé", "unit": "€"},
    {"key": "salarie", "label": "À la charge du salarié", "unit": "€"},
]
PARTAGE["lines"] = [
    {
        "key": "plafonne",
        "label": "Chaque repas, au plus le plafond",
        "op": "=",
        "into": "rembourse",
        "value": {"sum": {"type": "repas", "of": {"min": [{"option": "montant"}, {"setting": "plafond"}]}}},
        "unit": "€",
    },
    {
        "key": "depasse",
        "label": "Ce qui dépasse le plafond",
        "op": "=",
        "into": "salarie",
        "value": {
            "sub": [{"sum": {"type": "repas", "of": {"option": "montant"}}}, {"accumulator": "rembourse"}]
        },
        "unit": "€",
    },
    {
        "key": "geste",
        "label": "Au-delà de 10 € à sa charge, l'entreprise en reprend 5",
        "when": {"accumulator": {"salarie": {"gt": 10}}},
        "op": "-",
        "into": "salarie",
        "value": 5,
        "unit": "€",
    },
]
PARTAGE["result"] = {
    "label": "Total des repas",
    "unit": "€",
    "of": {"add": [{"accumulator": "rembourse"}, {"accumulator": "salarie"}]},
}
PARTAGE["outcome"] = [{"label": "Note établie", "status": "A_PAYER"}]


def test_deux_cumuls_menes_en_parallele():
    _, result = ran(declared(PARTAGE), [meal("A", 30), meal("B", 25)], {"plafond": 20})
    assert result["accumulators"] == {"rembourse": 40, "salarie": 10}
    assert [e["into"] for e in result["entries"]] == ["rembourse", "salarie", "salarie"]
    assert result["entries"][2]["status"] == "applied", "15 € à sa charge avant le geste, puis 10"
    assert result["total"] == 50, "le résultat combine les deux cumuls"


def test_total_lit_le_cumul_de_la_ligne_et_une_condition_lit_un_cumul():
    _, result = ran(declared(PARTAGE), [meal("A", 40), meal("B", 25)], {"plafond": 20})
    geste = result["entries"][2]
    assert geste["status"] == "applied" and geste["before"] == 25 and geste["after"] == 20
    assert result["accumulators"] == {"rembourse": 40, "salarie": 20}


def test_l_extra_dit_chaque_cumul():
    decl = declared(PARTAGE)
    _, result = ran(decl, [meal("A", 30)], {"plafond": 20})
    extra = calc.extra(decl, result)
    assert [a["label"] for a in extra["accumulators"]] == ["Remboursé", "À la charge du salarié"]
    assert "of" not in extra["result"]


@pytest.mark.parametrize(
    ("mutate", "path", "code"),
    [
        (lambda r: r["lines"][0].update(into="autre"), "workshop.lines[0].into", "unknown_accumulator"),
        (
            lambda r: r["lines"][1].update(value={"accumulator": "autre"}),
            "workshop.lines[1].value.accumulator",
            "unknown_accumulator",
        ),
        (lambda r: r.update(accumulators=[{"key": "seul"}]), "workshop.accumulators", "type"),
    ],
)
def test_une_declaration_fausse_est_refusee(mutate, path, code):
    raw = copy.deepcopy(PARTAGE)
    mutate(raw)
    report = Report()
    calc.normalize(raw, KEYS, report)
    assert (path, code) in {(i.path, i.code) for i in report.errors}


def test_of_sans_cumuls_est_refuse():
    raw = copy.deepcopy(REPAS)
    raw["result"] = {"label": "Total", "of": {"total": True}}
    report = Report()
    calc.normalize(raw, KEYS, report)
    assert ("workshop.result.of", "type") in {(i.path, i.code) for i in report.errors}


def test_un_seul_cumul_ne_change_rien():
    decl = declared(REPAS)
    assert "accumulators" not in decl
    _, result = ran(decl, [meal("A", 30)], {"plafond": 20})
    assert "accumulators" not in result and all("into" not in e for e in result["entries"])
