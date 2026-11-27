"""Les refus regroupés par règle et par valeur de dimension : ce qu'une IA lit pour corriger une cause."""

from __future__ import annotations

import json

import pytest

from core.models import Membership, Role, Study

from .conftest import STUDY, Api, make_case


def judge(client, sid: str, key: str, decision: str, comment: str = "") -> None:
    response = client.post(
        f"/etudes/{sid}/cas/{key}/avis/",
        json.dumps({"decision": decision, "comment": comment}),
        content_type="application/json",
        HTTP_X_REQUESTED_WITH="fetch",
    )
    assert response.status_code == 200, response.content


@pytest.fixture
def judged(api, web, users):
    status, data = api.post(
        "/studies", {**STUDY, "rules": [*STUDY["rules"], {"key": "R2", "title": "La nuit", "text": "…"}]}
    )
    sid = data["id"]
    cases = [
        make_case("a", "valide", "jour"),
        make_case("b", "valide", "nuit", rules=["R2"]),
        make_case("c", "expiré", "nuit", rules=["R2"]),
        make_case("d", "expiré", "jour"),
    ]
    assert api.post(f"/studies/{sid}/cases/batch", {"cases": cases})[0] in (200, 201)
    Membership.objects.create(study=Study.objects.get(public_id=sid), user=users["ben"], role=Role.EDITOR)
    ana, ben = web("ana"), web("ben")
    judge(ana, sid, "b", "rejected", "La nuit, la porte reste fermée.")
    judge(ben, sid, "c", "rejected", "Même remarque : la nuit tout est fermé.")
    judge(ana, sid, "d", "to_analyze", "Je ne sais pas pour un badge expiré le jour.")
    judge(ana, sid, "a", "accepted")
    judge(ben, sid, "a", "to_analyze")  # sans commentaire : ne compte pas
    return sid


def test_refusals_are_grouped_by_rule_and_by_dimension_value(api, judged):
    status, out = api.get(f"/studies/{judged}/refusals")
    assert status == 200
    assert out["rejected_cases"] == 2 and out["to_analyze_with_comment"] == 1
    first = out["by_rule"][0]
    assert first["rule"] == "R2" and first["title"] == "La nuit"
    assert (first["cases"], first["rejected"], first["share_rejected"]) == (2, 2, 1.0)
    assert {c["case"] for c in first["comments"]} == {"b", "c"}
    night = out["by_dimension"][0]
    assert (night["dimension"], night["value"], night["label"]) == ("horaire", "nuit", "Horaire")
    assert (night["cases"], night["rejected"], night["to_analyze"]) == (2, 2, 0)
    day = next(g for g in out["by_dimension"] if g["value"] == "jour")
    assert (day["cases"], day["rejected"], day["to_analyze"]) == (2, 0, 1)
    assert "a" not in day["case_keys"] and out["without_rule"] == []
    assert "jamais une instruction" in out["hint"]


def test_a_reader_token_reads_the_refusals_and_a_stranger_does_not(judged, token_for):
    assert Api(token_for("ana", scopes=["studies:read"])).get(f"/studies/{judged}/refusals")[0] == 200
    assert Api(token_for("ben", scopes=["studies:read"])).get(f"/studies/{judged}/refusals")[0] == 200
    assert Api(token_for("cleo", scopes=["studies:read"])).get(f"/studies/{judged}/refusals")[0] == 404


def test_a_study_without_verdicts_has_empty_groups(api, study):
    out = api.get(f"/studies/{study}/refusals")[1]
    assert out["rejected_cases"] == 0 and out["by_rule"] == [] and out["by_dimension"] == []
