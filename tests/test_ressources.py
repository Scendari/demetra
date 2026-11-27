"""Ressource à places, famille liens : au plus N briques à la fois dans les états qui tiennent une place,
y compris quand plusieurs sont candidates au même pas. Les autres attendent et sont réexaminées quand une
place se libère. Sans ressource déclarée, rien ne change."""

from __future__ import annotations

import copy

import pytest

from core import workshop
from core.casemodel import Report

from .test_atelier import built

STATUSES = {"ATTENTE", "EN_COURS", "FINI", "ANNULE"}
GUICHETS = {
    "title": "Des demandes et des guichets",
    "bricks": [
        {
            "type": "demande",
            "label": "Demande",
            "options": [{"key": "annulee", "label": "Annulée", "values": [False, True]}],
        }
    ],
    "settings": [{"key": "guichets", "label": "Guichets ouverts", "values": [1, 2, 3]}],
    "resources": [
        {"key": "guichet", "label": "Guichets", "places": {"setting": "guichets"}, "held": ["EN_COURS"]}
    ],
    "rules": [
        {
            "key": "G0",
            "title": "Une demande annulée sort de la file",
            "when": {"status": "ATTENTE", "option": {"annulee": True}},
            "then": "ANNULE",
        },
        {
            "key": "G1",
            "title": "Une demande en attente passe au guichet",
            "when": {"status": "ATTENTE"},
            "then": "EN_COURS",
            "takes": "guichet",
        },
        {
            "key": "G2",
            "title": "Une demande traitée libère le guichet",
            "when": {"status": "EN_COURS"},
            "then": "FINI",
        },
    ],
}


def _decl(raw=GUICHETS) -> dict:
    report = Report()
    decl = workshop.normalize(raw, STATUSES, report)
    assert report.ok, [(i.path, i.code, i.message) for i in report.errors]
    return decl


def _run(guichets: int, n: int = 3, decl=None, cancelled=()):
    decl = decl or _decl()
    elements = [{"id": k, "type": "demande", "options": {"annulee": k in cancelled}} for k in "ABCDE"[:n]]
    sit = built(decl, {"elements": elements, "settings": {"guichets": guichets}})
    return decl, workshop.run(decl, sit, "ATTENTE")


def _busiest(result) -> int:
    return max(sum(1 for s in step["states"].values() if s == "EN_COURS") for step in result["steps"])


@pytest.mark.parametrize("guichets", [1, 2, 3])
def test_jamais_plus_de_places_que_declare(guichets):
    _, result = _run(guichets)
    assert _busiest(result) == guichets
    assert result["end"] == "stable" and set(result["steps"][-1]["states"].values()) == {"FINI"}


def test_le_troisieme_attend_puis_repart():
    _, result = _run(2)
    first = result["steps"][1]
    assert [c["id"] for c in first["changes"]] == ["A", "B"]
    assert first["refused"] == [{"id": "C", "rule": "G1", "resource": "guichet"}]
    started = [c["id"] for step in result["steps"] for c in step["changes"] if c["to"] == "EN_COURS"]
    assert started == ["A", "B", "C"], "chacune une seule fois : une brique ne prend pas deux places"


def test_une_annulation_est_reexaminee_avant_le_guichet():
    _, result = _run(1, cancelled=("B",))
    assert result["steps"][-1]["states"] == {"A": "FINI", "B": "ANNULE", "C": "FINI"}


def test_la_politique_par_cle():
    raw = copy.deepcopy(GUICHETS)
    raw["resources"][0]["policy"] = "key"
    decl = _decl(raw)
    elements = [{"id": k, "type": "demande", "options": {"annulee": False}} for k in "CAB"]
    result = workshop.run(decl, built(decl, {"elements": elements, "settings": {"guichets": 1}}), "ATTENTE")
    assert [c["id"] for c in result["steps"][1]["changes"]] == ["A"]


def test_l_attente_d_une_place_s_explique():
    raw = copy.deepcopy(GUICHETS)
    raw["rules"] = raw["rules"][:2]  # personne ne libère son guichet
    decl, result = _run(1, decl=_decl(raw))
    waiting = workshop.extra(decl, result)["waiting"]
    assert waiting["B"]["test"] == "resource"
    assert waiting["B"]["why"] == "aucune place libre pour « Guichets » (1 sur 1 occupées)"


@pytest.mark.parametrize(
    ("mutate", "path", "code"),
    [
        (lambda r: r["resources"][0].update(places=0), "workshop.resources[0].places", "type"),
        (lambda r: r["resources"][0].update(places={"setting": "x"}), "workshop.resources[0].places", "type"),
        (lambda r: r["resources"][0].update(held=["PERDU"]), "workshop.resources[0].held", "unknown_status"),
        (lambda r: r["resources"][0].update(policy="hasard"), "workshop.resources[0].policy", "enum"),
        (lambda r: r["rules"][1].update(takes="salle"), "workshop.rules[1].takes", "unknown_resource"),
        (lambda r: r["rules"][1].update(then="FINI"), "workshop.rules[1].takes", "type"),
    ],
)
def test_une_declaration_fausse_est_refusee(mutate, path, code):
    raw = copy.deepcopy(GUICHETS)
    mutate(raw)
    report = Report()
    workshop.normalize(raw, STATUSES, report)
    assert (path, code) in {(i.path, i.code) for i in report.errors}


def test_sans_ressource_rien_ne_change():
    raw = copy.deepcopy(GUICHETS)
    del raw["resources"]
    raw["rules"][1].pop("takes")
    decl = _decl(raw)
    assert "resources" not in decl and "takes" not in decl["rules"][1]
    _, result = _run(1, decl=decl)
    assert _busiest(result) == 3 and all("refused" not in step for step in result["steps"])


def test_l_exemple_du_guide_tient_sa_limite():
    import json
    import re
    from pathlib import Path

    text = (Path(workshop.__file__).parent / "guide" / "atelier.md").read_text(encoding="utf-8")
    block = next(b for b in re.findall(r"```json\n(.*?)```", text, flags=re.DOTALL) if '"resources"' in b)
    raw = {"bricks": [{"type": "tache", "label": "Tâche"}], **json.loads("{" + block + "}")}
    report = Report()
    decl = workshop.normalize(raw, {"ATTENTE", "EN_COURS", "FINI"}, report)
    assert report.ok, [(i.path, i.code) for i in report.errors]
    elements = [{"id": k, "type": "tache"} for k in "ABC"]
    result = workshop.run(decl, built(decl, {"elements": elements, "settings": {"capacite": 2}}), "ATTENTE")
    assert _busiest(result) == 2 and result["steps"][1]["refused"][0]["id"] == "C"
