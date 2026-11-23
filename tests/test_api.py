"""API pour IA externe : jetons, cas, couverture, revue, partage, journal."""

from __future__ import annotations

import pytest

from core import services as svc
from core.models import (
    ApiToken,
    Case,
    IdempotencyRecord,
    Membership,
    ShareRequest,
    Study,
    Verdict,
    VerdictEvent,
)

from .conftest import STUDY, Api, make_case

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------- Mode d'emploi


def test_guide_is_public_and_complete(client):
    status, guide = Api().get("/guide")
    assert status == 200 and guide["version"]
    slugs = {t["topic"] if "topic" in t else t.get("slug") for t in guide["topics"]}
    assert {"auth", "studies", "cases", "coverage", "review", "representations", "sharing"} <= slugs
    for slug in slugs:
        status, chapter = Api().get(f"/guide/{slug}")
        assert status == 200 and len(chapter["markdown"]) > 200
    assert Api().get("/guide/inconnu")[0] == 404


def test_llms_txt_page_and_openapi(client):
    llms = client.get("/llms.txt")
    assert llms.status_code == 200 and "/api/v1/guide" in llms.content.decode()
    page = client.get("/guide/")
    assert page.status_code == 200 and "Mode d'emploi" in page.content.decode()
    status, schema = Api().get("/openapi.json")
    assert status == 200 and "/api/v1/studies/{sid}/cases/batch" in schema["paths"]


# ---------------------------------------------------------------- Jetons


def test_token_required_and_stored_hashed(users, token_for):
    assert Api().get("/me")[0] == 401
    assert Api("dmt_inconnu_secret").get("/me")[0] == 401
    secret = token_for("ana")
    status, me = Api(secret).get("/me")
    assert status == 200 and me["user"] == "ana"
    token = ApiToken.objects.get()
    stored = " ".join(str(getattr(token, f.name)) for f in ApiToken._meta.fields)
    assert secret not in stored and secret.split("_")[-1] not in stored
    assert len(token.token_hash) == 64


def test_revoked_and_expired_tokens_are_refused(users, token_for):
    secret = token_for("ana")
    token = ApiToken.objects.get()
    svc.revoke_token(users["ana"], token.pk)
    status, error = Api(secret).get("/me")
    assert status == 401 and error["error"]["code"]
    from datetime import timedelta

    from django.utils import timezone

    other = token_for("ben")
    ApiToken.objects.filter(user=users["ben"]).update(expires_at=timezone.now() - timedelta(days=1))
    assert Api(other).get("/me")[0] == 401


def test_scopes_limit_what_a_token_can_do(token_for, study):
    reader = Api(token_for("ana", scopes=["studies:read"]))
    assert reader.get(f"/studies/{study}")[0] == 200
    status, error = reader.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a")]})
    assert status == 403 and error["error"]["code"] == "missing_scope"
    assert reader.post("/representations", {"name": "x", "parent": "table-trace", "overrides": {}})[0] == 403
    assert reader.post(f"/studies/{study}/share-requests", {"user": "ben", "role": "viewer"})[0] == 403


def test_token_restricted_to_a_study_sees_only_that_study(api, token_for, study):
    other = api.post("/studies", {**STUDY, "title": "Autre étude"})[1]["id"]
    limited = Api(token_for("ana", studies=[study]))
    assert limited.get(f"/studies/{study}")[0] == 200
    assert limited.get(f"/studies/{other}")[0] == 404
    assert [s["id"] for s in limited.get("/studies")[1]["items"]] == [study]


def test_private_study_is_invisible_to_others(study, token_for):
    stranger = Api(token_for("ben"))
    status, error = stranger.get(f"/studies/{study}")
    assert status == 404 and error["error"]["code"] == "not_found"
    assert stranger.get("/studies")[1]["items"] == []


# ---------------------------------------------------------------- Cas


def test_dry_run_writes_nothing_and_reports_coverage(api, study):
    status, report = api.post(
        f"/studies/{study}/cases/validate",
        {"cases": [make_case("a"), make_case("b", "expiré", "nuit", ok=False)]},
    )
    assert status == 200 and report["dry_run"] is True and report["written"] is False
    assert report["counts"] == {"created": 2}
    assert report["coverage"]["covered"] == 2
    assert Case.objects.count() == 0


def test_batch_is_replayable(api, study):
    cases = [make_case("a"), make_case("b", "valide", "nuit")]
    status, first = api.post(f"/studies/{study}/cases/batch", {"cases": cases})
    assert status == 200 and first["counts"] == {"created": 2}
    status, second = api.post(f"/studies/{study}/cases/batch", {"cases": cases})
    assert second["counts"] == {"unchanged": 2}
    assert (
        Case.objects.count() == 2 and Study.objects.get(public_id=study).revision == first["study_revision"]
    )


def test_idempotency_key(api, study):
    body = {"cases": [make_case("a")]}
    first = api.post(f"/studies/{study}/cases/batch", body, **{"Idempotency-Key": "lot-1"})[1]
    status, again = api.post(f"/studies/{study}/cases/batch", body, **{"Idempotency-Key": "lot-1"})
    assert status == 200 and again["replayed"] is True and again["results"] == first["results"]
    status, conflict = api.post(
        f"/studies/{study}/cases/batch", {"cases": [make_case("z")]}, **{"Idempotency-Key": "lot-1"}
    )
    assert status == 409 and conflict["error"]["code"]
    assert IdempotencyRecord.objects.count() == 1 and Case.objects.count() == 1


def test_errors_are_precise_and_fixable(api, study):
    bad = make_case("a")
    bad["steps"][1]["changes"]["lecture"] = "OKK"
    bad["dimensions"]["horaire"] = "minuit"
    bad["links"].append({"from": "porte", "to": "fantome", "type": "prerequisite"})
    status, report = api.post(
        f"/studies/{study}/cases/batch", {"cases": [bad, make_case("b", "valide", "nuit")]}
    )
    assert status == 200 and report["counts"] == {"error": 1, "created": 1}
    errors = {e["code"]: e for e in report["results"][0]["errors"]}
    assert errors["unknown_status"]["path"] == "cases[0].steps[1].changes.lecture"
    assert errors["unknown_status"]["received"] == "OKK" and "OK" in errors["unknown_status"]["expected"]
    assert (
        errors["unknown_value"]["path"] == "cases[0].dimensions.horaire"
        and "nuit" in errors["unknown_value"]["expected"]
    )
    assert errors["unknown_entity"]["path"].startswith("cases[0].links[1]")
    assert all(e["message"] for e in errors.values())
    assert list(Case.objects.values_list("key", flat=True)) == ["b"]


def test_atomic_batch_writes_nothing_on_error(api, study):
    bad = make_case("a")
    bad["steps"] = []
    status, report = api.post(
        f"/studies/{study}/cases/batch", {"cases": [bad, make_case("b")], "atomic": True}
    )
    assert status == 422 or report["written"] is False
    assert Case.objects.count() == 0


def test_dependency_cycle_is_refused(api, study):
    bad = make_case("a")
    bad["links"].append({"from": "porte", "to": "lecture", "type": "prerequisite"})
    report = api.post(f"/studies/{study}/cases/validate", {"cases": [bad]})[1]
    assert "cycle" in {e["code"] for e in report["results"][0]["errors"]}


def test_case_is_replayed_into_full_states(api, study):
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a", ok=False)]})
    status, case = api.get(f"/studies/{study}/cases/a")
    assert status == 200
    frames = case["frames"]
    last = frames[-1]["states"] if "states" in frames[-1] else frames[-1]["statuses"]
    assert last == {"lecture": "KO", "porte": "BLOQUE"}
    first = frames[0]["states"] if "states" in frames[0] else frames[0]["statuses"]
    assert first["porte"] == "ATTENTE", (
        "le statut par défaut de l'étude s'applique aux entités sans changement"
    )


def test_a_case_read_from_the_api_can_be_posted_back_unchanged(api, study):
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a", ok=False)]})
    stored = api.get(f"/studies/{study}/cases/a")[1]["case"]
    report = api.post(f"/studies/{study}/cases/batch", {"cases": [stored]})[1]
    assert report["counts"] == {"unchanged": 1}, report


def test_retire_and_restore(api, study):
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a")]})
    assert api.delete(f"/studies/{study}/cases/a")[0] == 200
    assert api.get(f"/studies/{study}/cases")[1]["total"] == 0
    assert api.get(f"/studies/{study}/cases?include_retired=true")[1]["total"] == 1
    assert api.post(f"/studies/{study}/cases/a/restore")[0] == 200
    assert api.get(f"/studies/{study}/cases")[1]["total"] == 1


def test_definitions_in_use_cannot_be_removed(api, study):
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a")]})
    status, error = api.patch(f"/studies/{study}", {"statuses": STUDY["statuses"][:2]})
    assert status in (409, 422) and error["error"]["details"]
    assert any(d["code"] == "in_use" for d in error["error"]["details"])


# ---------------------------------------------------------------- Couverture


def test_coverage_lists_missing_combinations(api, study):
    api.post(
        f"/studies/{study}/cases/batch",
        {
            "cases": [
                make_case("a"),
                make_case("b", "valide", "nuit"),
                make_case("c", "expiré", "jour", ok=False),
            ]
        },
    )
    status, report = api.get(f"/studies/{study}/coverage")
    assert status == 200
    assert (report["total"], report["covered"], report["excluded"], report["missing_count"]) == (5, 3, 1, 2)
    assert {"badge": "valide", "horaire": "week-end"} in report["missing"]
    assert {"badge": "expiré", "horaire": "nuit"} in report["missing"]
    assert {"badge": "expiré", "horaire": "week-end"} not in report["missing"], (
        "combinaison déclarée impossible"
    )
    single = api.get(f"/studies/{study}/coverage?strength=1")[1]
    assert single["missing"] == [{"horaire": "week-end"}]


def test_structure_checks(api, study):
    twin = make_case("b", title="Le même déroulé sous un autre nom")
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a"), twin]})
    status, checks = api.get(f"/studies/{study}/checks")
    assert status == 200
    duplicate = next(f for f in checks["findings"] if f["code"] == "duplicate_content")
    assert sorted(duplicate["cases"]) == ["a", "b"]
    assert "unused_status" in {f["code"] for f in checks["findings"]}


# ---------------------------------------------------------------- Revue


def test_token_cannot_set_a_verdict_but_reads_them(api, study, users):
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a"), make_case("b", "valide", "nuit")]})
    status, error = api.post(f"/studies/{study}/cases/a/verdict", {"decision": "accepted"})
    assert status == 403 and error["error"]["code"] == "human_only"
    assert Verdict.objects.count() == 0
    obj = svc.get_study(svc.Actor(users["ana"]), study)
    svc.set_verdict(svc.Actor(users["ana"]), obj, "a", "rejected", "La porte devrait rester fermée la nuit.")
    status, verdicts = api.get(f"/studies/{study}/verdicts")
    assert status == 200 and len(verdicts["items"]) == 1
    item = verdicts["items"][0]
    assert (
        item["decision"] == "rejected"
        and item["comment"].startswith("La porte")
        and item["reviewer"] == "ana"
    )
    worklist = api.get(f"/studies/{study}/worklist")[1]
    assert [r["case"] for r in worklist["rejected"]] == ["a"] and worklist["rejected"][0][
        "on_current_content"
    ] is True


def test_cosmetic_change_keeps_verdicts_and_real_change_resets_them(api, study, users):
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a")]})
    me = svc.Actor(users["ana"])
    obj = svc.get_study(me, study)
    svc.set_verdict(me, obj, "a", "accepted", "Conforme.")

    cosmetic = make_case("a", title="Badge valide en journée")
    cosmetic["steps"][0]["note"] = "Précision ajoutée."
    report = api.post(f"/studies/{study}/cases/batch", {"cases": [cosmetic]})[1]
    assert report["results"][0]["status"] == "updated_cosmetic"
    assert Verdict.objects.get().decision == "accepted"

    changed = make_case("a", title="Badge valide en journée", ok=False)
    report = api.post(f"/studies/{study}/cases/batch", {"cases": [changed]})[1]
    assert report["results"][0]["status"] == "updated" and report["results"][0]["verdicts_reset"] == 1
    verdict = Verdict.objects.get()
    assert verdict.decision == "to_analyze" and verdict.stale_from == "accepted"
    assert verdict.comment == "Conforme.", "le commentaire reste visible"

    revisions = api.get(f"/studies/{study}/cases/a/revisions")[1]["items"]
    assert len(revisions) == 3
    events = list(VerdictEvent.objects.order_by("id").values_list("decision", "reason"))
    assert events == [("accepted", "review"), ("to_analyze", "reset")], (
        "l'ancien avis reste dans l'historique"
    )


def test_highlights_put_chosen_characteristics_forward(api, study, users):
    """L'IA désigne les caractéristiques à garder sous les yeux : clés de « dimensions » ou de « config » du
    cas."""
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a", config={"essais": 3})]})
    me = svc.Actor(users["ana"])
    svc.set_verdict(me, svc.get_study(me, study), "a", "accepted", "")

    marked = make_case("a", config={"essais": 3}, highlights=["horaire", "essais", "horaire"])
    report = api.post(f"/studies/{study}/cases/batch", {"cases": [marked]})[1]
    assert report["results"][0]["status"] == "updated_cosmetic", (
        "mettre une option en avant ne remet pas les avis en cause"
    )
    assert Verdict.objects.get().decision == "accepted"
    assert api.get(f"/studies/{study}/cases/a")[1]["case"]["highlights"] == ["horaire", "essais"]
    assert (
        api.post(f"/studies/{study}/cases/batch", {"cases": [marked]})[1]["results"][0]["status"]
        == "unchanged"
    )

    report = api.post(
        f"/studies/{study}/cases/validate", {"cases": [make_case("b", highlights=["inconnue"])]}
    )[1]
    error = report["results"][0]["errors"][0]
    assert (
        error["code"] == "unknown_highlight"
        and error["path"].endswith("highlights[0]")
        and "horaire" in error["expected"]
    )
    report = api.post(
        f"/studies/{study}/cases/validate",
        {
            "cases": [
                make_case(
                    "b", config={"a": 1, "b": 2, "c": 3}, highlights=["badge", "horaire", "a", "b", "c"]
                )
            ]
        },
    )[1]
    assert any(e["code"] == "max_items" for e in report["results"][0]["errors"])


# ---------------------------------------------------------------- Partage et journal


def test_share_request_by_token_waits_for_human_confirmation(api, study, users, web):
    status, pending = api.post(
        f"/studies/{study}/share-requests", {"user": "ben", "role": "commenter", "message": "Relecture."}
    )
    assert status == 202 and pending["status"] == "pending"
    assert not Membership.objects.filter(user=users["ben"]).exists()
    assert Api(svc.create_token(users["ben"], "b", list(svc.SCOPES))[1]).get(f"/studies/{study}")[0] == 404

    owner = web("ana")
    page = owner.get(f"/etudes/{study}/partage/")
    assert page.status_code == 200 and "Relecture." in page.content.decode()
    response = owner.post(f"/etudes/{study}/partage/", {"action": "confirm", "request": pending["id"]})
    assert response.status_code == 302
    assert Membership.objects.get(user=users["ben"]).role == "commenter"
    assert ShareRequest.objects.get().status == "confirmed"
    assert api.get(f"/studies/{study}/share-requests")[1]["items"][0]["status"] == "confirmed"


def test_share_request_can_be_rejected(api, study, users, web):
    pending = api.post(f"/studies/{study}/share-requests", {"user": "ben", "role": "editor"})[1]
    web("ana").post(f"/etudes/{study}/partage/", {"action": "reject", "request": pending["id"]})
    assert not Membership.objects.filter(user=users["ben"]).exists()


def test_roles(api, study, users, token_for):
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a")]})
    owner = svc.Actor(users["ana"])
    obj = svc.get_study(owner, study)
    svc.share(owner, obj, "ben", "viewer")
    svc.share(owner, obj, "cleo", "commenter")

    viewer = Api(token_for("ben"))
    assert viewer.get(f"/studies/{study}/cases/a")[0] == 200
    status, error = viewer.post(f"/studies/{study}/cases/batch", {"cases": [make_case("z")]})
    assert status == 403 and error["error"]["code"] == "forbidden", (
        "un jeton ne dépasse jamais le rôle de son titulaire"
    )

    with pytest.raises(svc.ServiceError) as refused:
        svc.set_verdict(
            svc.Actor(users["ben"]), svc.get_study(svc.Actor(users["ben"]), study), "a", "accepted"
        )
    assert refused.value.status == 403
    cleo = svc.Actor(users["cleo"])
    assert svc.set_verdict(cleo, svc.get_study(cleo, study), "a", "accepted").decision == "accepted"
    with pytest.raises(svc.ServiceError):
        svc.share(cleo, svc.get_study(cleo, study), "ben", "editor")


def test_audit_tells_humans_from_tokens(api, study, users):
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a")]})
    me = svc.Actor(users["ana"])
    svc.set_verdict(me, svc.get_study(me, study), "a", "accepted")
    items = api.get(f"/studies/{study}/audit")[1]["items"]
    by_action = {i["action"]: i for i in items}
    assert (
        by_action["cases.upsert"]["actor_kind"] == "jeton"
        and by_action["cases.upsert"]["token"] == "jeton-ana"
    )
    assert by_action["verdict.set"]["actor_kind"] == "humain" and not by_action["verdict.set"]["token"]


def test_every_api_route_is_documented_in_the_guide():
    """Le mode d'emploi des IA doit citer chaque route de l'API : une route ajoutée sans documentation fait
    échouer ce test."""
    import re
    from pathlib import Path

    from core import guide

    text = guide.full_markdown()
    routes = re.findall(
        r'@api\.(?:get|post|put|patch|delete)\("([^"]+)"', Path("core/api.py").read_text(encoding="utf-8")
    )
    missing = []
    for route in routes:
        pattern = re.sub(r"\\\{[^}]+\\\}", r"[^ /`)]+", re.escape(route))
        if not re.search(pattern + r"(?![a-z/])", text):
            missing.append(route)
    assert not missing, f"Routes absentes du mode d'emploi : {missing}"
