"""Un cas déposé, rejoué dans l'atelier de son étude : concorde, s'écarte (avertissement) ou ne s'y traduit
pas."""

from __future__ import annotations

import copy

import pytest

from core import families, workshop, workshopcheck
from core.casemodel import Report, StudyContext, normalize_case, normalize_dimensions
from core.demo import catalogue, magasin

from .conftest import STUDY
from .test_atelier import WORKSHOP, built, declared
from .test_periodes import STUDY as PERIOD_STUDY
from .test_periodes import WORKSHOP as PERIOD_WORKSHOP

DIMENSIONS = normalize_dimensions(STUDY["dimensions"], Report())
BOUND = copy.deepcopy(WORKSHOP)
BOUND["settings"][0]["dimension"] = {"key": "horaire", "values": {"nuit": True, "jour": False}}


def case_of(elements, links=(), steps=(), **extra) -> dict:
    """Un cas « porte / sas » écrit à la main : chaque pas ne donne que les changements."""
    return {
        "key": extra.pop("key", "accord"),
        "title": "Un passage",
        "rules": ["R1"],
        "dimensions": extra.pop("dimensions", {"badge": "valide", "horaire": "jour"}),
        "entities": [
            {"id": key, "label": f"{kind} {key}", "type": kind, **more} for key, kind, more in elements
        ],
        "links": [{"from": a, "to": b, "type": "mene"} for a, b in links],
        "steps": [{"title": f"Pas {n}", "changes": changes} for n, changes in enumerate(steps, 1)],
        **extra,
    }


def replayed(case: dict, decl: dict | None = None) -> dict | None:
    """Le cas normalisé comme au dépôt, puis rejoué dans l'atelier."""
    decl = decl or declared()
    content, report = normalize_case(case, StudyContext(STUDY["statuses"], DIMENSIONS, STUDY["rules"]))
    assert content is not None, [(i.path, i.code) for i in report.errors]
    return workshopcheck.agreement(decl, content, STUDY["statuses"])


def deposit(api, sid: str, case: dict) -> dict:
    status, data = api.post(f"/studies/{sid}/cases/batch", {"cases": [case]})
    assert status in (200, 201), data
    return data["results"][0]


def codes(entry: dict) -> set[str]:
    return {w["code"] for w in entry.get("warnings", [])}


@pytest.fixture
def bound(api):
    status, data = api.post("/studies", {**STUDY, "workshop": BOUND})
    assert status == 201, data
    return data["id"]


CHAIN = [("A", "porte", {}), ("B", "sas", {})]


def test_a_case_that_follows_the_rules_raises_nothing(api, bound):
    case = case_of(CHAIN, [("A", "B")], [{"A": "EN_COURS"}, {"A": "OK", "B": "EN_COURS"}, {"B": "OK"}])
    entry = deposit(api, bound, case)
    assert entry["status"] == "created" and "workshop_mismatch" not in codes(entry)
    findings = api.get(f"/studies/{bound}/checks")[1]["findings"]
    assert not {"workshop_mismatch", "workshop_untranslatable"} & {f["code"] for f in findings}


def test_a_case_that_contradicts_the_rules_is_written_with_a_warning(api, bound):
    case = case_of(CHAIN, [("A", "B")], [{"A": "EN_COURS"}, {"A": "OK", "B": "BLOQUE"}], key="contraire")
    entry = deposit(api, bound, case)
    assert entry["status"] == "created"
    warning = next(w for w in entry["warnings"] if w["code"] == "workshop_mismatch")
    assert "sas B : le cas finit en BLOQUE, les règles donnent OK" in warning["message"]
    assert "Soit le cas se trompe, soit les règles de l'atelier sont incomplètes" in warning["message"]
    finding = next(
        f for f in api.get(f"/studies/{bound}/checks")[1]["findings"] if f["code"] == "workshop_mismatch"
    )
    assert finding["severity"] == "warning" and finding["cases"] == ["contraire"]


def test_an_event_the_case_does_not_name_is_supposed():
    """Le cas ne dit pas que A tombe en panne : le site retrouve l'évènement qui l'explique."""
    case = case_of(CHAIN, [("A", "B")], [{"A": "EN_COURS"}, {"A": "KO", "B": "BLOQUE"}])
    found = replayed(case)
    assert found["status"] == "agree" and found["events"] == {"A": ["panne"]}


def test_a_case_may_stop_half_way():
    case = case_of(CHAIN, [("A", "B")], [{"A": "EN_COURS"}])
    assert replayed(case)["status"] == "agree"


def test_a_case_starts_where_it_says():
    case = case_of(CHAIN, [("A", "B")], [{"B": "EN_COURS"}, {"B": "OK"}], initial={"A": "OK"})
    assert replayed(case)["status"] == "agree"


def test_a_setting_is_read_in_the_dimension_the_study_names(api, bound):
    """En alerte (la nuit, d'après la déclaration), une porte du niveau haut reste fermée."""
    high = [("A", "porte", {"attrs": {"niveau": "haut"}})]
    night = case_of(high, steps=[{"A": "BLOQUE"}], dimensions={"badge": "valide", "horaire": "nuit"})
    day = case_of(high, steps=[{"A": "BLOQUE"}], key="jour")
    assert "workshop_mismatch" not in codes(deposit(api, bound, night))
    assert "workshop_mismatch" in codes(deposit(api, bound, day))
    night["config"] = {"alerte": False}  # la configuration du cas l'emporte sur la dimension
    assert "workshop_mismatch" in codes(deposit(api, bound, night))


def test_a_setting_reads_only_a_declared_dimension(api, bound):
    wrong = copy.deepcopy(BOUND)
    wrong["settings"][0]["dimension"] = {"key": "meteo", "values": {"pluie": True}}
    status, data = api.patch(f"/studies/{bound}", {"workshop": wrong})
    assert status == 422 and data["error"]["details"][0]["code"] == "unknown_dimension"
    wrong["settings"][0]["dimension"] = {"key": "horaire", "values": {"aube": True}}
    status, data = api.patch(f"/studies/{bound}", {"workshop": wrong})
    path = data["error"]["details"][0]["path"]
    assert status == 422 and path == "workshop.settings[0].dimension.values.aube"
    wrong["settings"][0]["dimension"] = {"key": "horaire", "values": {"nuit": "peut-être"}}
    status, data = api.patch(f"/studies/{bound}", {"workshop": wrong})
    assert status == 422 and data["error"]["details"][0]["code"] == "unknown_value"
    status, data = api.patch(f"/studies/{bound}", {"dimensions": STUDY["dimensions"][:1]})
    assert status == 422 and "unknown_dimension" in {d["code"] for d in data["error"]["details"]}


def test_a_case_the_workshop_cannot_replay_is_only_listed(api, bound):
    foreign = case_of([("A", "porte", {}), ("T", "task", {})], steps=[{"A": "EN_COURS"}], key="mixte")
    entry = deposit(api, bound, foreign)
    assert entry["status"] == "created" and "workshop_mismatch" not in codes(entry)
    unrelated = case_of([("T", "task", {})], steps=[{"T": "OK"}], key="ailleurs")
    assert replayed(unrelated) is None
    deposit(api, bound, unrelated)
    finding = next(
        f
        for f in api.get(f"/studies/{bound}/checks")[1]["findings"]
        if f["code"] == "workshop_untranslatable"
    )
    assert finding["severity"] == "info" and finding["cases"] == ["mixte"]
    assert "« task », que l'atelier ne déclare pas" in finding["message"]


def test_without_a_workshop_nothing_is_replayed(api, study):
    case = case_of(CHAIN, [("A", "B")], [{"B": "KO"}])
    assert "workshop_mismatch" not in codes(deposit(api, study, case))


@pytest.mark.parametrize("events", [{}, {"A": ["panne"]}, {"B": ["panne"]}])
@pytest.mark.parametrize("alert", [False, True])
def test_a_situation_saved_from_the_workshop_agrees_with_it(events, alert):
    decl = declared()
    sit = built(
        decl,
        {
            "elements": [
                {"id": "A", "type": "porte", "options": {"niveau": "haut"}},
                {"id": "B", "type": "porte"},
                {"id": "C", "type": "sas"},
            ],
            "links": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}],
            "settings": {"alerte": alert},
        },
    )
    sit["events"] = events
    result = workshop.run(decl, sit, "ATTENTE")
    case = workshop.to_case(decl, sit, result, "ATTENTE")
    content, report = normalize_case(case, StudyContext(STUDY["statuses"], [], [], workshop=decl))
    assert content is not None and "workshop_mismatch" not in {i.code for i in report.warnings}
    assert workshopcheck.agreement(decl, content, STUDY["statuses"])["status"] == "agree"


def test_the_demo_catalogue_reads_its_stop_on_error_setting_in_a_dimension():
    report = Report()
    decl = families.normalize(catalogue.WORKSHOP, {s["key"] for s in catalogue.STATUSES}, report)
    assert report.ok
    assert decl["settings"][0]["dimension"] == {
        "key": "arret_sur_erreur",
        "values": {"non": False, "oui": True},
    }


def test_periods_saved_from_the_workshop_agree_and_a_wrong_history_is_flagged(api):
    status, data = api.post("/studies", {**PERIOD_STUDY, "workshop": PERIOD_WORKSHOP})
    assert status == 201, data
    sid = data["id"]
    decl = api.get(f"/studies/{sid}/workshop")[1]["workshop"]
    situation = magasin_like_situation(decl)
    status, run = api.post(f"/studies/{sid}/workshop/run", {"situation": situation})
    assert status == 200, run
    case = {**run["case"], "key": "periodes"}
    assert "workshop_mismatch" not in codes(deposit(api, sid, case))
    images = [e for e in case["entities"] if e.get("group") == "Historique obtenu"]
    images[0]["attrs"]["end"] = images[0]["attrs"]["start"] + 1
    case["key"] = "periodes-fausses"
    entry = deposit(api, sid, case)
    warning = next(w for w in entry["warnings"] if w["code"] == "workshop_mismatch")
    assert "Historique : le cas annonce" in warning["message"]


def magasin_like_situation(decl: dict) -> dict:
    """Deux périodes de chaque source déclarée, qui se chevauchent : de quoi produire plusieurs images."""
    elements = []
    for n, brick in enumerate(decl["bricks"]):
        elements += [
            {"id": f"{brick['type'][:1].upper()}{n}a", "type": brick["type"], "start": 1, "end": 5},
            {"id": f"{brick['type'][:1].upper()}{n}b", "type": brick["type"], "start": 4, "end": 9},
        ]
    return {"elements": elements}


def test_the_demo_period_study_agrees_with_its_cases():
    decl, statuses = magasin.declaration(), magasin.DEFINITION["statuses"]
    for case in magasin.cases():
        found = workshopcheck.agreement(decl, case, statuses)
        assert found is None or found["status"] == "agree", (case["key"], found)


def test_coverage_offers_to_unroll_a_missing_combination_in_the_workshop(api, bound, web):
    """La nuit, l'atelier se règle en alerte : la combinaison manquante « valide × nuit » se déroule à partir
    du cas « valide × jour » ; « valide × week-end » n'a pas de réglage, donc pas de piste."""
    case = case_of(
        CHAIN, [("A", "B")], [{"A": "EN_COURS"}, {"A": "OK", "B": "EN_COURS"}, {"B": "OK"}], key="jour"
    )
    deposit(api, bound, case)
    report = api.get(f"/studies/{bound}/coverage")[1]
    hints = dict(zip((tuple(sorted(c.items())) for c in report["missing"]), report["workshop"]))
    night = hints[(("badge", "valide"), ("horaire", "nuit"))]
    assert night["settings"] == {"alerte": True} and night["from_case"] == "jour"
    assert night["web_url"].startswith(f"/etudes/{bound}/atelier/?e=A%3Aporte&e=B%3Asas")
    assert "r.alerte=true" in night["web_url"]
    assert hints[(("badge", "valide"), ("horaire", "week-end"))] is None
    expired = hints[(("badge", "expiré"), ("horaire", "nuit"))]
    assert expired["from_case"] is None and expired["web_url"] == f"/etudes/{bound}/atelier/?r.alerte=true"
    ana = web("ana")
    assert ana.get(night["web_url"]).status_code == 200  # l'adresse est déjà rangée : pas de redirection
    page = ana.get(f"/etudes/{bound}/couverture/").content.decode()
    assert "Dérouler dans l&#x27;atelier" in page or "Dérouler dans l'atelier" in page
    assert "d&#x27;après jour" in page or "d'après jour" in page


def test_coverage_without_a_workshop_offers_nothing(api, study):
    assert "workshop" not in api.get(f"/studies/{study}/coverage")[1]
