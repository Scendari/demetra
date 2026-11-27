"""Une dimension qui décrit les cas un par un : sa couverture de 100 % ne mesure rien, le site le signale."""

from __future__ import annotations

from core import coverage as cov
from tests.conftest import make_case


def _dimension(n: int) -> dict:
    return {"key": "scenario", "label": "Scénario", "values": [{"value": f"s{i}"} for i in range(n)]}


def _rows(values: list[str]) -> list[dict]:
    return [{"key": f"cas-{i}", "dimensions": {"scenario": v}} for i, v in enumerate(values)]


def test_une_valeur_par_cas_est_signalee():
    found = cov.dimension_echoes([_dimension(5)], _rows([f"s{i}" for i in range(5)]))
    assert [f["code"] for f in found] == ["dimension_echoes_cases"]
    assert found[0]["severity"] == "warning" and found[0]["dimension"] == "scenario"
    assert "« Scénario »" in found[0]["message"] and "5 valeurs" in found[0]["message"]


def test_peu_de_valeurs_ne_dit_rien():
    assert cov.dimension_echoes([_dimension(4)], _rows([f"s{i}" for i in range(4)])) == []


def test_une_valeur_partagee_ne_dit_rien():
    values = ["s0", "s0", "s1", "s2", "s3", "s4"]
    assert cov.dimension_echoes([_dimension(5)], _rows(values)) == []


def test_un_cas_parametre_compte_une_fois():
    rows = _rows([f"s{i}" for i in range(5)]) + [{"key": "cas-0", "dimensions": {"scenario": "s0"}}]
    assert [f["code"] for f in cov.dimension_echoes([_dimension(5)], rows)] == ["dimension_echoes_cases"]


def test_par_l_api(api, study):
    dims = [
        {"key": "badge", "label": "Badge", "values": ["valide", "expiré"]},
        {"key": "scenario", "label": "Scénario", "values": [f"s{i}" for i in range(5)]},
    ]
    assert api.patch(f"/studies/{study}", {"dimensions": dims})[0] == 200
    cases = [make_case(f"c{i}", dimensions={"badge": "valide", "scenario": f"s{i}"}) for i in range(5)]
    assert api.post(f"/studies/{study}/cases/batch", {"cases": cases})[0] in (200, 201)
    findings = api.get(f"/studies/{study}/checks")[1]["findings"]
    echoes = [f for f in findings if f["code"] == "dimension_echoes_cases"]
    assert [f["dimension"] for f in echoes] == ["scenario"], "le badge est partagé : il n'est pas signalé"
