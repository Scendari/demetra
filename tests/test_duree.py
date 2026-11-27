"""Durée d'un état, famille liens : le test `since` compte les pas qu'une brique a passés dans son état ;
quand seule une durée peut encore faire bouger la situation, le temps avance (`waited`). Sans `since`, rien
ne change."""

from __future__ import annotations

import copy

import pytest

from core import workshop
from core.casemodel import Report

from .test_atelier import built

STATUSES = {"ATTENTE", "EN_COURS", "FINI"}
TRAVAUX = {
    "title": "Des travaux qui durent",
    "bricks": [
        {
            "type": "tache",
            "label": "Tâche",
            "options": [{"key": "duree", "label": "Durée", "values": [1, 2, 4]}],
        }
    ],
    "settings": [{"key": "delai", "label": "Délai", "values": [1, 3]}],
    "rules": [
        {"key": "T1", "title": "Une tâche démarre", "when": {"status": "ATTENTE"}, "then": "EN_COURS"},
        {
            "key": "T2",
            "title": "Une tâche finit au bout de sa durée",
            "when": {"status": "EN_COURS", "since": {"gte": {"option": "duree"}}},
            "then": "FINI",
        },
    ],
}


def _decl(raw=TRAVAUX) -> dict:
    report = Report()
    decl = workshop.normalize(raw, STATUSES, report)
    assert report.ok, [(i.path, i.code, i.message) for i in report.errors]
    return decl


def _run(decl, durations, settings=None):
    elements = [{"id": k, "type": "tache", "options": {"duree": d}} for k, d in zip("ABC", durations)]
    return workshop.run(decl, built(decl, {"elements": elements, "settings": settings or {}}), "ATTENTE")


def test_une_tache_finit_au_bout_de_sa_duree():
    result = _run(_decl(), [4])
    assert [s["states"]["A"] for s in result["steps"]] == ["ATTENTE", "EN_COURS", "FINI"]
    assert result["steps"][2]["waited"] == 3, "trois pas sans changement, puis la fin au quatrième"


def test_des_durees_differentes_finissent_dans_l_ordre():
    result = _run(_decl(), [4, 1, 2])
    order = [c["id"] for step in result["steps"] for c in step["changes"] if c["to"] == "FINI"]
    assert order == ["B", "C", "A"]


def test_un_seuil_lu_dans_un_reglage():
    raw = copy.deepcopy(TRAVAUX)
    raw["rules"][1]["when"]["since"] = {"gte": {"setting": "delai"}}
    decl = _decl(raw)
    assert _run(decl, [1], {"delai": 3})["steps"][2]["waited"] == 2
    assert "waited" not in _run(decl, [1], {"delai": 1})["steps"][2]


def test_l_etape_du_cas_le_dit():
    decl = _decl()
    elements = [{"id": "A", "type": "tache", "options": {"duree": 2}}]
    sit = built(decl, {"elements": elements})
    case = workshop.to_case(decl, sit, workshop.run(decl, sit, "ATTENTE"), "ATTENTE")
    assert case["steps"][2]["note"].startswith("Après 1 pas sans changement.")


@pytest.mark.parametrize(
    ("since", "code"),
    [
        ({"gte": {"option": "inconnue"}}, "unknown_option"),
        ({"gte": {"setting": "absent"}}, "unknown_setting"),
        ({"in": [1, 2]}, "type"),
        ("longtemps", "type"),
    ],
)
def test_une_duree_mal_ecrite_est_refusee(since, code):
    raw = copy.deepcopy(TRAVAUX)
    raw["rules"][1]["when"]["since"] = since
    report = Report()
    workshop.normalize(raw, STATUSES, report)
    assert code in {i.code for i in report.errors}


def test_une_option_non_numerique_est_refusee():
    raw = copy.deepcopy(TRAVAUX)
    raw["bricks"][0]["options"][0]["values"] = ["court", "long"]
    report = Report()
    workshop.normalize(raw, STATUSES, report)
    assert "not_numeric" in {i.code for i in report.errors}


def test_sans_duree_le_temps_n_avance_pas():
    raw = copy.deepcopy(TRAVAUX)
    raw["rules"][1]["when"] = {"status": "EN_COURS"}
    result = _run(_decl(raw), [4])
    assert len(result["steps"]) == 3 and all("waited" not in s for s in result["steps"])


def test_une_duree_jamais_atteinte_laisse_la_situation_stable():
    raw = copy.deepcopy(TRAVAUX)
    raw["rules"][1]["when"]["since"] = {"gte": 99}
    decl = _decl(raw)
    result = _run(decl, [1])
    assert result["end"] == "stable" and result["steps"][-1]["states"]["A"] == "EN_COURS"
    assert workshop.extra(decl, result)["waiting"]["A"]["test"] == "since"
