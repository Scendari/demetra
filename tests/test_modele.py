"""Jeu de règles déclaré par l'étude : politiques de résolution, accord d'un cas avec le calcul du site."""

from __future__ import annotations

from core import extensions
from core.demo import elargi


def deposit(api, study, *cases):
    status, data = api.post(f"/studies/{study}/cases/batch", {"cases": list(cases)})
    assert status == 200, data
    return data


def tickets_study(api) -> str:
    status, data = api.post("/studies", elargi.REGLES)
    assert status == 201, data
    report = deposit(api, data["id"], *elargi.regles_cases())
    assert not [r for r in report["results"] if r["status"] == "error"], report
    return data["id"]


def test_ruleset_policies():
    ruleset = {
        "policy": "first",
        "conditions": [{"key": "a"}, {"key": "b"}],
        "rows": [
            {"key": "R1", "when": {"a": "x", "b": "y"}, "then": "Un"},
            {"key": "R2", "when": {"a": "x"}, "then": "Deux"},
            {"key": "R3", "when": {}, "then": "Trois"},
        ],
    }
    verdict = extensions.evaluate_ruleset(ruleset, {"a": "x", "b": "z"})
    assert verdict["selected"] == ["R2"] and verdict["conclusion"] == "Deux"
    assert verdict["rows"]["R1"] == {"result": "failed", "on": "b"}
    assert verdict["rows"]["R3"]["result"] == "discarded"
    assert not extensions.evaluate_ruleset(ruleset, {"a": "x"})["complete"]
    unique = extensions.evaluate_ruleset({**ruleset, "policy": "unique"}, {"a": "x", "b": "y"})
    assert unique["issue"] == "several_unique"


def test_the_demo_rule_table_agrees_with_its_own_cases(api):
    """Le calcul du site retrouve le sort des lignes que chaque cas de démonstration annonce."""
    status, data = api.get(f"/studies/{tickets_study(api)}/checks")
    assert status == 200
    assert "model_mismatch" not in {f["code"] for f in data["findings"]}


def test_a_case_that_contradicts_the_ruleset_is_accepted_with_a_warning(api):
    tickets = tickets_study(api)
    case = elargi.regles_cases()[0]
    step = next(s for s in case["steps"] if "T1" in (s.get("rows") or {}))
    assert step["rows"]["T1"] == {"result": "selected"}
    step["rows"]["T1"], step["rows"]["T2"] = {"result": "discarded"}, {"result": "selected"}
    case["key"] = "ticket-contradictoire"
    entry = deposit(api, tickets, case)["results"][0]
    assert entry["status"] == "created", entry
    assert "model_mismatch" in {w["code"] for w in entry["warnings"]}
    status, data = api.get(f"/studies/{tickets}/checks")
    finding = next(f for f in data["findings"] if f["code"] == "model_mismatch")
    assert finding["severity"] == "warning" and "ticket-contradictoire" in finding["cases"]
