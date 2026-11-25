"""Cas paramétré : paramètres, étapes conditionnelles, rejeu de toutes les combinaisons, couverture, avis."""

from __future__ import annotations

import copy

from core import parametric
from core import services as svc

from .conftest import make_case


def param_case(key: str = "p", **extra) -> dict:
    """Un seul cas pour « badge valide » et « badge expiré », de jour."""
    case = make_case(key, title="Badge présenté de jour")
    case["dimensions"] = {"horaire": "jour"}
    case["params"] = [{"key": "badge", "label": "Badge", "values": ["valide", "expiré"]}]
    case["steps"] = [
        {"title": "Le badge est lu", "changes": {"lecture": "EN_COURS"}},
        {"when": {"badge": "valide"}, "title": "Le badge est accepté", "changes": {"lecture": "OK"}},
        {"when": {"badge": "valide"}, "title": "La porte s'ouvre", "changes": {"porte": "OK"}},
        {"when": {"badge": "expiré"}, "title": "Le badge est refusé", "changes": {"lecture": "KO"}},
        {"when": {"badge": "expiré"}, "title": "La porte reste fermée", "changes": {"porte": "BLOQUE"}},
    ]
    case["outcome"] = [
        {"when": {"badge": "valide"}, "label": "Entrée", "status": "OK"},
        {"label": "Refus", "status": "KO"},
    ]
    case.update(extra)
    return case


def deposit(api, study, *cases):
    status, data = api.post(f"/studies/{study}/cases/batch", {"cases": list(cases)})
    assert status == 200, data
    return data


def test_conditions_are_a_closed_vocabulary():
    values = {"essais": 2, "mode": "auto", "strict": True}
    assert parametric.holds({"mode": "auto"}, values)
    assert parametric.holds({"essais": {"gte": 2, "lt": 3}}, values)
    assert parametric.holds({"mode": ["manuel", "auto"]}, values)
    assert parametric.holds({"all": [{"mode": "auto"}, {"not": {"essais": {"gt": 2}}}]}, values)
    assert parametric.holds({"any": [{"mode": "manuel"}, {"strict": True}]}, values)
    assert not parametric.holds({"mode": "auto", "essais": 3}, values)
    # Égalité stricte : vrai ne vaut pas 1.
    assert not parametric.holds({"strict": 1}, values)


def test_a_parametrised_case_is_replayed_for_every_combination(api, study):
    data = deposit(api, study, param_case())
    assert data["results"][0]["status"] == "created", data
    obj = svc.Study.objects.get(public_id=study)
    content = obj.cases.get(key="p").content
    variants = parametric.expand(content)
    assert [combo for combo, _ in variants] == [{"badge": "valide"}, {"badge": "expiré"}]
    assert [s["title"] for s in variants[1][1]["steps"]][-1] == "La porte reste fermée"
    assert variants[1][1]["outcome"]["label"] == "Refus"
    assert variants[1][1]["dimensions"] == {"horaire": "jour", "badge": "expiré"}


def test_one_invalid_combination_refuses_the_whole_case(api, study):
    case = param_case()
    case["steps"][3]["changes"] = {"lecture": "INCONNU"}
    data = deposit(api, study, case)
    entry = data["results"][0]
    assert entry["status"] == "error"
    error = next(e for e in entry["errors"] if e["code"] == "unknown_status")
    assert "steps[3]" in error["path"] and "badge = expiré" in error["message"]
    assert not svc.Study.objects.get(public_id=study).cases.exists()


def test_parametrised_case_errors(api, study):
    unknown = param_case(steps=[{"title": "x", "changes": {"lecture": "OK"}, "when": {"porte": "ouverte"}}])
    never = param_case()
    never["steps"].append(
        {"when": {"all": [{"badge": "valide"}, {"badge": "expiré"}]}, "title": "Jamais", "changes": {}}
    )
    too_many = param_case(
        params=[{"key": f"p{i}", "label": f"P{i}", "values": [1, 2, 3, 4, 5]} for i in range(3)], steps=[]
    )
    operator = param_case()
    operator["steps"][1]["when"] = {"badge": {"exec": "valide"}}
    repeated = param_case(dimensions={"horaire": "jour", "badge": "valide"})
    for case, code in (
        (unknown, "unknown_param"),
        (never, "never_true"),
        (too_many, "too_many_combinations"),
        (operator, "enum"),
        (repeated, "duplicate"),
    ):
        entry = deposit(api, study, case)["results"][0]
        assert entry["status"] == "error", code
        assert code in {e["code"] for e in entry["errors"]}, (code, entry["errors"])


def test_the_api_returns_the_case_as_deposited_and_it_round_trips(api, study):
    deposit(api, study, param_case())
    status, data = api.get(f"/studies/{study}/cases/p")
    assert status == 200
    assert [p["key"] for p in data["case"]["params"]] == ["badge"]
    assert data["case"]["steps"][1]["when"] == {"badge": "valide"}
    assert isinstance(data["case"]["outcome"], list) and "source" not in data["case"]
    assert data["parametric"]["combinations"] == [{"badge": "valide"}, {"badge": "expiré"}]
    again = deposit(api, study, data["case"])
    assert again["results"][0]["status"] == "unchanged", again


def test_coverage_counts_every_combination_but_one_case(api, study):
    deposit(api, study, param_case())
    status, cover = api.get(f"/studies/{study}/coverage?strength=2")
    assert status == 200
    assert cover["cases_counted"] == 1
    assert {"badge": "expiré", "horaire": "jour"} not in cover["missing"]
    assert {"badge": "valide", "horaire": "jour"} not in cover["missing"]
    assert {"badge": "valide", "horaire": "nuit"} in cover["missing"]
    badge = next(d for d in cover["by_dimension"] if d["key"] == "badge")
    assert {v["value"]: v["cases"] for v in badge["values"]} == {"valide": 1, "expiré": 1}


def test_the_coverage_page_marks_a_parametrised_case(api, study, web):
    deposit(api, study, param_case())
    page = web("ana").get(f"/etudes/{study}/couverture/").content.decode()
    assert "mx-param" in page and "paramétré" in page


def test_changing_what_a_combination_shows_resets_the_verdict(api, study, users):
    deposit(api, study, param_case())
    me = svc.Actor(users["ana"])
    svc.set_verdict(me, svc.get_study(me, study), "p", "accepted", "")

    # Une condition réécrite sans effet sur les variantes : l'avis est gardé.
    same = param_case()
    same["steps"][3]["when"] = {"not": {"badge": "valide"}}
    assert deposit(api, study, same)["results"][0]["status"] in ("unchanged", "updated_cosmetic")

    # La variante « expiré » ne montre plus la même chose : l'avis repasse à analyser.
    changed = copy.deepcopy(same)
    changed["steps"][4]["changes"] = {"porte": "KO"}
    entry = deposit(api, study, changed)["results"][0]
    assert entry["status"] == "updated" and entry["verdicts_reset"] == 1


def test_the_case_panel_lists_the_variants(api, study, web):
    deposit(api, study, param_case())
    page = web("ana").get(f"/etudes/{study}/cas/p/panneau/").content.decode()
    assert "Cas paramétré : 2 variantes" in page and "variante=2" in page
    assert "Le badge est accepté" in page and "Le badge est refusé" not in page


def test_a_variant_is_read_in_the_review_workspace(api, study, web):
    """Chaque variante d'un cas paramétré se lit dans l'espace de revue, par son adresse."""
    deposit(api, study, param_case())
    page = web("ana").get(f"/etudes/{study}/?cas=p&variante=2").content.decode()
    assert "Le badge est refusé" in page and "Le badge est accepté" not in page
    assert "(affichée)" in page
    # Une variante qui n'existe pas montre la première, sans erreur.
    page = web("ana").get(f"/etudes/{study}/?cas=p&variante=9").content.decode()
    assert "Le badge est accepté" in page


def test_a_plain_case_is_untouched_by_the_parametric_path(api, study):
    deposit(api, study, make_case("a"))
    content = svc.Study.objects.get(public_id=study).cases.get(key="a").content
    assert not parametric.is_parametric(content)
    assert parametric.source_of(content) == content
    assert parametric.expand(content) == [(None, content)]
