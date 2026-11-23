"""Interface web : comptes, pages, revue, représentation choisie, jetons, mise à jour en direct."""

from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from core import services as svc
from core.models import ApiToken, AuditEvent, Membership, Representation, Study, Verdict

from .conftest import Api, make_case

pytestmark = pytest.mark.django_db


@pytest.fixture
def filled(api, study):
    cases = [make_case("a"), make_case("b", "valide", "nuit"), make_case("c", "expiré", "jour", ok=False)]
    assert api.post(f"/studies/{study}/cases/batch", {"cases": cases})[0] == 200
    return study


def test_public_pages(client):
    for path in (
        "/",
        "/guide/",
        "/guide/cases/",
        "/briques/",
        "/llms.txt",
        "/comptes/login/",
        "/comptes/signup/",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
    home = client.get("/").content.decode()
    assert 'lang="fr"' in home and "data-theme-toggle" in home


def test_signup_then_login(client):
    response = client.post(
        "/comptes/signup/",
        {
            "username": "dana",
            "email": "dana@example.org",
            "password1": "un-mot-de-passe-long-9",
            "password2": "un-mot-de-passe-long-9",
        },
    )
    assert response.status_code == 302, response.content.decode()[:500]
    assert get_user_model().objects.filter(username="dana").exists()
    fresh = Client()
    response = fresh.post("/comptes/login/", {"login": "dana", "password": "un-mot-de-passe-long-9"})
    assert response.status_code == 302 and response["Location"] == "/etudes/"
    assert fresh.get("/etudes/").status_code == 200


def test_pages_require_login(client, filled):
    for path in ("/etudes/", f"/etudes/{filled}/", "/compte/jetons/"):
        response = client.get(path)
        assert response.status_code == 302 and "/comptes/login/" in response["Location"], path


def test_create_study_in_the_interface(web):
    client = web("ana")
    response = client.post("/etudes/", {"title": "Congés", "description": "", "kind": "decision"})
    assert response.status_code == 302
    study = Study.objects.get(title="Congés")
    assert Membership.objects.get(study=study).role == "owner" and study.statuses, (
        "une liste de statuts de départ est fournie"
    )
    assert client.get(response["Location"]).status_code == 200


def test_every_study_page_renders(web, filled):
    client = web("ana")
    for suffix in (
        "",
        "?cas=b&etape=2",
        "couverture/",
        "couverture/?force=1",
        "couverture/?force=3",
        "representation/",
        "partage/",
        "historique/",
        "historique/?acteur=jeton",
        "definitions/",
        "etat/",
        "cas/a/panneau/",
    ):
        response = client.get(f"/etudes/{filled}/{suffix}")
        assert response.status_code == 200, (suffix, response.content.decode()[:300])
    page = client.get(f"/etudes/{filled}/?cas=c").content.decode()
    assert "data-panel" in page and 'class="verdict' in page and "data-legend" in page or "legend" in page
    assert client.get("/compte/jetons/").status_code == 200


def test_private_study_is_not_found_for_other_users(web, filled):
    assert web("ben").get(f"/etudes/{filled}/").status_code == 404
    assert web("ben").get(f"/etudes/{filled}/etat/").status_code == 404


def test_review_a_case(web, filled, users):
    client = web("ana")
    url = f"/etudes/{filled}/cas/a/avis/"
    response = client.post(
        url,
        json.dumps({"decision": "rejected", "comment": "La porte ne devrait pas s'ouvrir."}),
        content_type="application/json",
        HTTP_X_REQUESTED_WITH="fetch",
    )
    assert response.status_code == 200
    data = response.json()
    assert (
        data["decision"] == "rejected"
        and data["counts"]["rejected"] == 1
        and data["counts"]["to_analyze"] == 2
    )
    verdict = Verdict.objects.get()
    assert verdict.reviewer == users["ana"] and verdict.comment.startswith("La porte")
    response = client.post(
        url,
        json.dumps({"decision": "accepted"}),
        content_type="application/json",
        HTTP_X_REQUESTED_WITH="fetch",
    )
    assert response.json()["decision"] == "accepted" and response.json()["comment"].startswith("La porte"), (
        "changer d'avis garde le commentaire"
    )
    assert (
        client.post(
            url,
            json.dumps({"decision": "peut-être"}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="fetch",
        ).status_code
        == 422
    )
    page = client.get(f"/etudes/{filled}/?cas=a").content.decode()
    assert 'data-decision="accepted"' in page


def test_highlighted_characteristics_stay_visible_in_the_panel(web, api, filled):
    client = web("ana")
    panel = client.get(f"/etudes/{filled}/cas/a/panneau/").content.decode()
    assert 'class="cp-key"' not in panel, "sans demande de l'auteur du cas, rien n'est mis en avant"
    api.post(
        f"/studies/{filled}/cases/batch",
        {"cases": [make_case("a", config={"essais": 3}, highlights=["horaire", "essais"])]},
    )
    panel = client.get(f"/etudes/{filled}/cas/a/panneau/").content.decode()
    forward, folded = (
        panel.split('class="cp-key"')[1].split("</dl>")[0],
        panel.split('class="cp-meta"')[1].split("</dl>")[0],
    )
    assert "<dt>Horaire</dt><dd>jour</dd>" in forward and "<dt>essais</dt><dd>3</dd>" in forward
    assert "Horaire" not in folded and "essais" not in folded and "<dt>Badge</dt>" in folded, (
        "une caractéristique mise en avant n'est pas répétée"
    )

    # Une dimension marquée dans l'étude vaut pour tous les cas, y compris ceux qui ne demandent rien.
    dims = api.get(f"/studies/{filled}")[1]["dimensions"]
    dims[0]["highlight"] = True
    status, study = api.patch(f"/studies/{filled}", {"dimensions": dims})
    assert (
        status == 200
        and study["dimensions"][0]["highlight"] is True
        and "highlight" not in study["dimensions"][1]
    )
    for key in ("a", "b"):
        panel = client.get(f"/etudes/{filled}/cas/{key}/panneau/").content.decode()
        assert "<dt>Badge</dt>" in panel.split('class="cp-key"')[1].split("</dl>")[0], key
    assert (
        api.patch(f"/studies/{filled}", {"dimensions": [{**dims[0], "highlight": "oui"}, dims[1]]})[0] == 422
    )


def test_entity_option_is_shown_on_the_entity_itself(web, api, filled):
    """Une option portée par une entité (always_run sur une tâche) se lit sur le schéma et dans les
    paramètres."""
    entities = [
        {
            "id": "lecture",
            "label": "Lecture du badge",
            "type": "task",
            "attrs": {"always_run": True, "essai": 2},
        },
        {"id": "porte", "label": "Ouverture", "type": "task", "attrs": {"always_run": False}},
    ]
    marked = make_case("a", entities=entities, highlights=[{"entity": "lecture", "attr": "always_run"}])
    assert api.post(f"/studies/{filled}/cases/batch", {"cases": [marked]})[1]["results"][0]["status"] in (
        "updated_cosmetic",
        "updated",
    )
    panel = web("ana").get(f"/etudes/{filled}/cas/a/panneau/").content.decode()
    forward = panel.split('class="cp-key"')[1].split("</dl>")[0]
    assert (
        '<dt>always_run (lecture · Lecture du badge)</dt><dd class="flag-bold flag-tone-ink">true</dd>'
        in forward
    ), "valeur telle qu'elle est écrite"
    assert panel.count('class="n-flag ') == 1 and ">always_run : true<" in panel, (
        "seule l'option mise en avant est écrite, sur sa tâche"
    )

    errors = lambda h: api.post(
        f"/studies/{filled}/cases/validate", {"cases": [make_case("b", entities=entities, highlights=[h])]}
    )[1]["results"][0]["errors"]
    assert errors({"entity": "fantome", "attr": "always_run"})[0]["code"] == "unknown_entity"
    assert errors({"entity": "porte", "attr": "essai"})[0]["code"] == "unknown_attr"
    assert errors({"entity": "porte"})[0]["code"] == "type"
    assert errors("lecture.always_run")[0]["code"] == "unknown_highlight"

    # Le style est choisi par l'IA dans une liste fermée : graisse, italique, teinte du site.
    styled = make_case(
        "a",
        entities=entities,
        highlights=[
            {
                "entity": "lecture",
                "attr": "always_run",
                "style": {"weight": "normal", "italic": True, "tone": "warning"},
            }
        ],
    )
    api.post(f"/studies/{filled}/cases/batch", {"cases": [styled]})
    panel = web("ana").get(f"/etudes/{filled}/cas/a/panneau/").content.decode()
    assert 'class="n-flag flag-normal flag-italic flag-tone-warning"' in panel
    assert '<dd class="flag-normal flag-italic flag-tone-warning">true</dd>' in panel
    bad = errors(
        {
            "entity": "lecture",
            "attr": "always_run",
            "style": {"tone": "#ff0000", "weight": "heavy", "size": 3},
        }
    )
    assert {e["code"] for e in bad} == {"enum", "unknown_field"} and len(bad) == 3, (
        "pas de couleur libre ni de style inconnu"
    )


def test_focus_points_the_reviewer_at_an_entity_that_does_not_change(web, api, filled):
    """« focus » désigne au relecteur l'entité à regarder à une étape, même quand elle ne change pas."""
    steps = make_case("a")["steps"]
    steps[0] = {**steps[0], "focus": ["porte"], "annotations": {"porte": "attend la lecture"}}
    report = api.post(f"/studies/{filled}/cases/batch", {"cases": [make_case("a", steps=steps)]})[1]
    assert report["results"][0]["status"] == "updated_cosmetic", (
        "désigner une entité ne remet pas les avis en cause"
    )
    panel = web("ana").get(f"/etudes/{filled}/cas/a/panneau/").content.decode()
    assert "<b>À regarder :</b>" in panel and "attend la lecture" in panel
    assert 'data-fo="100"' in panel and "is-focus" in panel
    steps[0] = {**steps[0], "focus": ["fantome"]}
    error = api.post(f"/studies/{filled}/cases/validate", {"cases": [make_case("b", steps=steps)]})[1][
        "results"
    ][0]["errors"][0]
    assert error["code"] == "unknown_entity" and error["path"].endswith("steps[0].focus[0]")


def test_question_is_asked_above_the_verdict_buttons(web, api, filled):
    api.post(
        f"/studies/{filled}/cases/batch",
        {"cases": [make_case("a", question="La porte reste-t-elle fermée la nuit ?")]},
    )
    panel = web("ana").get(f"/etudes/{filled}/cas/a/panneau/").content.decode()
    verdict = panel.split('class="verdict"')[1]
    assert "<b>À vérifier :</b> La porte reste-t-elle fermée la nuit ?" in verdict
    error = api.post(f"/studies/{filled}/cases/validate", {"cases": [make_case("b", question=12)]})[1][
        "results"
    ][0]["errors"][0]
    assert error["code"] == "type" and error["path"].endswith("question")


def test_compare_with_lists_what_differs(web, api, filled):
    api.post(f"/studies/{filled}/cases/batch", {"cases": [make_case("a", compare_with=["c", "absent"])]})
    panel = web("ana").get(f"/etudes/{filled}/cas/a/panneau/").content.decode()
    block = panel.split('class="compare-block"')[1].split("</section>")[0]
    assert (
        'data-open-case="c"' in block and '<th scope="row">Badge</th><td>valide</td><td>expiré</td>' in block
    )
    assert "Résultat attendu" in block and "« absent » n'existe pas" in block
    findings = api.get(f"/studies/{filled}/checks")[1]["findings"]
    assert any(c["code"] == "compare_missing_case" and "a → absent" in c["message"] for c in findings)
    error = api.post(f"/studies/{filled}/cases/validate", {"cases": [make_case("b", compare_with=["b"])]})[1][
        "results"
    ][0]["errors"][0]
    assert error["code"] == "self_reference"


def test_study_attributes_name_and_define_entity_options(web, api, filled):
    status, study = api.patch(
        f"/studies/{filled}",
        {
            "attributes": [
                {
                    "key": "always_run",
                    "label": "Toujours exécutée",
                    "text": "S'exécute même si un prérequis échoue.",
                }
            ]
        },
    )
    assert status == 200 and study["attributes"][0]["label"] == "Toujours exécutée"
    entities = [
        {
            "id": "lecture",
            "label": "Lecture du badge",
            "type": "task",
            "attrs": {"always_run": True, "alway_run": True},
        },
        {"id": "porte", "label": "Ouverture", "type": "task"},
    ]
    report = api.post(
        f"/studies/{filled}/cases/batch",
        {
            "cases": [
                make_case("a", entities=entities, highlights=[{"entity": "lecture", "attr": "always_run"}])
            ]
        },
    )[1]
    assert report["results"][0]["status"] == "updated", (
        "le cas garde sa clé : il est mis à jour, pas recréé sous un autre nom"
    )
    warnings = report["results"][0]["warnings"]
    assert any(w["code"] == "undeclared_attr" and w["received"] == "alway_run" for w in warnings), (
        "une faute de frappe est signalée"
    )
    panel = web("ana").get(f"/etudes/{filled}/cas/a/panneau/").content.decode()
    # Par défaut, le nom technique et la valeur telle qu'elle est écrite ; le libellé et la définition, au
    # survol.
    assert ">always_run : true<" in panel and "<dt>always_run (lecture · Lecture du badge)</dt>" in panel
    assert "Toujours exécutée (always_run) : S&#x27;exécute même si un prérequis échoue." in panel, (
        "la définition s'affiche au survol"
    )
    # Sur demande (« show »: « label »), le libellé lisible, et la valeur en oui / non.
    api.patch(
        f"/studies/{filled}",
        {
            "attributes": [
                {
                    "key": "always_run",
                    "label": "Toujours exécutée",
                    "text": "S'exécute même si un prérequis échoue.",
                    "show": "label",
                }
            ]
        },
    )
    panel = web("ana").get(f"/etudes/{filled}/cas/a/panneau/").content.decode()
    assert (
        ">Toujours exécutée : oui<" in panel
        and "<dt>Toujours exécutée (lecture · Lecture du badge)</dt>" in panel
    )
    assert (
        api.patch(f"/studies/{filled}", {"attributes": [{"key": "always_run", "label": "X", "show": "nom"}]})[
            0
        ]
        == 422
    )
    setup = web("ana").get(f"/etudes/{filled}/definitions/").content.decode()
    assert "Options des entités" in setup and "S&#x27;exécute même si un prérequis échoue." in setup
    assert api.patch(f"/studies/{filled}", {"attributes": [{"key": "x y", "label": ""}]})[0] == 422


def test_a_link_can_be_put_forward(web, api, filled):
    marked = make_case("a", highlights=[{"link": ["lecture", "porte"], "style": {"tone": "accent"}}])
    assert (
        api.post(f"/studies/{filled}/cases/batch", {"cases": [marked]})[1]["results"][0]["status"]
        == "updated_cosmetic"
    )
    panel = web("ana").get(f"/etudes/{filled}/cas/a/panneau/").content.decode()
    assert "<dt>Lien lecture → porte</dt>" in panel and "is-flagged flag-bold flag-tone-accent" in panel
    error = api.post(
        f"/studies/{filled}/cases/validate",
        {"cases": [make_case("b", highlights=[{"link": ["porte", "lecture"]}])]},
    )[1]["results"][0]["errors"][0]
    assert error["code"] == "unknown_link"


def test_detail_line_disappears_when_its_fields_are_empty():
    from core.render import fill_detail

    assert fill_detail("always_run : {attr.always_run}", {"attrs": {}}) == ""
    assert (
        fill_detail("always_run : {attr.always_run}", {"attrs": {"always_run": True}}) == "always_run : true"
    )
    assert fill_detail("ligne fixe", {}) == "ligne fixe"


def test_modified_case_goes_back_to_review_in_the_interface(web, api, filled):
    client = web("ana")
    client.post(
        f"/etudes/{filled}/cas/a/avis/", json.dumps({"decision": "accepted"}), content_type="application/json"
    )
    api.post(f"/studies/{filled}/cases/batch", {"cases": [make_case("a", ok=False)]})
    page = client.get(f"/etudes/{filled}/?cas=a").content.decode()
    assert "data-stale" in page and "data-stale-notice" in page
    assert Verdict.objects.get().decision == "to_analyze"
    panel = client.get(f"/etudes/{filled}/cas/a/panneau/").content.decode()
    assert "Révisions" in panel


def test_viewer_reads_but_cannot_review(web, filled, users):
    owner = svc.Actor(users["ana"])
    svc.share(owner, svc.get_study(owner, filled), "ben", "viewer")
    client = web("ben")
    page = client.get(f"/etudes/{filled}/?cas=a")
    assert page.status_code == 200 and 'class="vbtn' not in page.content.decode()
    response = client.post(
        f"/etudes/{filled}/cas/a/avis/",
        json.dumps({"decision": "accepted"}),
        content_type="application/json",
        HTTP_X_REQUESTED_WITH="fetch",
    )
    assert response.status_code == 403 and Verdict.objects.count() == 0
    assert client.post(
        f"/etudes/{filled}/partage/", {"action": "invite", "user": "cleo", "role": "editor"}
    ).status_code in (302, 403, 404)
    assert not Membership.objects.filter(user=users["cleo"]).exists()


def test_share_in_the_interface(web, filled, users):
    client = web("ana")
    response = client.post(
        f"/etudes/{filled}/partage/", {"action": "invite", "user": "ben", "role": "commenter"}
    )
    assert response.status_code == 302 and Membership.objects.get(user=users["ben"]).role == "commenter"
    assert web("ben").get(f"/etudes/{filled}/").status_code == 200
    client.post(f"/etudes/{filled}/partage/", {"action": "role", "member": users["ben"].pk, "role": "editor"})
    assert Membership.objects.get(user=users["ben"]).role == "editor"
    client.post(f"/etudes/{filled}/partage/", {"action": "remove", "member": users["ben"].pk})
    assert not Membership.objects.filter(user=users["ben"]).exists()
    assert web("ben").get(f"/etudes/{filled}/").status_code == 404


def test_choose_a_representation(web, filled, users):
    client = web("ana")
    trace = Representation.objects.get(slug="table-trace", scope="system")
    before = client.get(f"/etudes/{filled}/?cas=a").content.decode()
    assert 'data-rep="graphe-couches"' in before or "Graphe en couches" in before
    response = client.post(
        f"/etudes/{filled}/representation/",
        {"action": "choose", "representation": trace.public_id, "scope": "me"},
    )
    assert response.status_code == 302
    after = client.get(f"/etudes/{filled}/?cas=a").content.decode()
    assert "Table de trace" in after and "rep-grid" in after
    obj = Study.objects.get(public_id=filled)
    assert svc.current_representation(users["ana"], obj) == trace and obj.representation is None, (
        "choix personnel : l'étude ne change pas"
    )

    response = client.post(
        f"/etudes/{filled}/representation/",
        {"action": "adjust", "representation": trace.public_id, "density": "compact"},
    )
    assert response.status_code == 302
    mine = svc.current_representation(users["ana"], obj)
    assert mine.scope == "adjustment" and mine.parent == trace and mine.owner == users["ana"]

    client.post(
        f"/etudes/{filled}/representation/",
        {"action": "duplicate", "representation": trace.public_id, "name": "Ma trace"},
    )
    assert Representation.objects.filter(name="Ma trace", scope="theme", owner=users["ana"]).exists()


def test_tokens_are_created_shown_once_and_revoked(web, users):
    client = web("ana")
    response = client.post(
        "/compte/jetons/", {"name": "Claude Code", "scopes": ["studies:read", "studies:write"], "days": "30"}
    )
    assert response.status_code == 302
    page = client.get("/compte/jetons/").content.decode()
    token = ApiToken.objects.get()
    assert 'data-testid="new-token"' in page
    secret = page.split('data-testid="new-token"')[1].split(">")[1].split("<")[0].strip()
    assert secret.startswith("dmt_") and Api(secret).get("/me")[0] == 200
    assert secret not in client.get("/compte/jetons/").content.decode(), "le secret n'est montré qu'une fois"
    assert token.scopes == ["studies:read", "studies:write"]
    client.post("/compte/jetons/", {"action": "revoke", "token": token.pk})
    assert Api(secret).get("/me")[0] == 401


def test_state_endpoint_reflects_api_changes(web, api, filled):
    client = web("ana")
    before = client.get(f"/etudes/{filled}/etat/").json()
    api.post(f"/studies/{filled}/cases/batch", {"cases": [make_case("d", "valide", "week-end")]})
    after = client.get(f"/etudes/{filled}/etat/").json()
    assert after["revision"] > before["revision"] and "d" in after["cases"] and "d" not in before["cases"]


def test_event_stream_announces_a_revision(web, api, filled, settings):
    settings.DEMETRA_SSE_MAX_SECONDS = 3
    response = web("ana").get(f"/etudes/{filled}/events")
    assert response.status_code == 200 and response["Content-Type"].startswith("text/event-stream")
    stream = iter(response.streaming_content)
    first = next(stream).decode() + next(stream).decode()
    assert "event: hello" in first
    api.post(f"/studies/{filled}/cases/batch", {"cases": [make_case("e", "valide", "week-end")]})
    seen = ""
    for chunk in stream:
        seen += chunk.decode()
        if "event: revision" in seen:
            break
    assert "event: revision" in seen


def test_import_cases_in_the_interface(web, study):
    client = web("ana")
    raw = json.dumps({"cases": [make_case("a")]})
    checked = client.post(f"/etudes/{study}/definitions/", {"action": "check", "json": raw})
    assert checked.status_code == 200 and Study.objects.get(public_id=study).cases.count() == 0
    client.post(f"/etudes/{study}/definitions/", {"action": "import", "json": raw})
    assert Study.objects.get(public_id=study).cases.count() == 1
    assert AuditEvent.objects.filter(action="cases.upsert", actor_token__isnull=True).exists()
