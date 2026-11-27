"""Supprimer une étude : la corbeille, la restauration, l'effacement définitif réservé aux humains."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from core.models import AuditEvent, Case, Membership, Role, Study

from .conftest import Api, make_case


@pytest.fixture
def filled(api, study):
    status, _ = api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a"), make_case("b")]})
    assert status in (200, 201)
    return study


def test_the_owner_ai_sends_a_study_to_the_trash_and_brings_it_back(api, filled):
    status, out = api.delete(f"/studies/{filled}")
    assert status == 200 and out["deleted"] and out["purge_at"] > out["deleted_at"]
    assert f"/trash/{filled}/restore" in out["note"]
    assert api.get(f"/studies/{filled}")[0] == 404
    assert filled not in [s["id"] for s in api.get("/studies")[1]["items"]]
    assert [s["id"] for s in api.get("/trash")[1]["items"]] == [filled]
    status, back = api.post(f"/trash/{filled}/restore")
    assert status == 200 and back["id"] == filled
    assert api.get(f"/studies/{filled}/cases")[1]["total"] == 2
    actions = list(AuditEvent.objects.filter(study__public_id=filled).values_list("action", flat=True))
    assert "study.trash" in actions and "study.restore" in actions


def test_only_the_owner_deletes(api, filled, users, token_for):
    obj = Study.objects.get(public_id=filled)
    Membership.objects.create(study=obj, user=users["ben"], role=Role.EDITOR)
    ben = Api(token_for("ben"))
    assert ben.delete(f"/studies/{filled}")[0] == 403
    reader = Api(token_for("ana", scopes=["studies:read"]))
    assert reader.delete(f"/studies/{filled}")[0] == 403
    assert Study.objects.get(public_id=filled).deleted_at is None
    api.delete(f"/studies/{filled}")
    assert ben.post(f"/trash/{filled}/restore")[0] == 404  # pas propriétaire : rien à restaurer
    assert ben.get(f"/studies/{filled}")[0] == 404  # disparue pour tous ses membres


def test_an_ai_cannot_erase_for_good(api, filled):
    api.delete(f"/studies/{filled}")
    for method, path in (("DELETE", f"/trash/{filled}"), ("POST", f"/trash/{filled}/purge")):
        assert api.call(method, path, {})[0] in (404, 405)
    assert Study.objects.filter(public_id=filled).exists()


def test_the_person_deletes_restores_and_erases_in_the_interface(api, filled, web):
    ana = web("ana")
    response = ana.post(f"/etudes/{filled}/definitions/", {"action": "trash"})
    assert response.status_code == 302 and response.url == "/etudes/"
    page = ana.get("/etudes/").content.decode()
    assert "Corbeille (1)" in page and f'href="/etudes/{filled}/"' not in page
    trash = ana.get("/etudes/corbeille/").content.decode()
    assert "Accès à un bâtiment" in trash and "Restaurer" in trash
    assert ana.post("/etudes/corbeille/", {"study": filled, "action": "restore"}).url == f"/etudes/{filled}/"
    ana.post(f"/etudes/{filled}/definitions/", {"action": "trash"})
    ana.post("/etudes/corbeille/", {"study": filled, "action": "purge"})
    assert not Study.objects.filter(public_id=filled).exists()
    assert not Case.objects.filter(study__public_id=filled).exists()
    trace = AuditEvent.objects.get(action="study.purge")
    assert trace.study is None and trace.detail["id"] == filled and trace.detail["cases"] == 2
    assert trace.actor_user.username == "ana"


def test_another_member_cannot_trash_from_the_interface(api, filled, users, web):
    Membership.objects.create(study=Study.objects.get(public_id=filled), user=users["ben"], role=Role.EDITOR)
    web("ben").post(f"/etudes/{filled}/definitions/", {"action": "trash"})
    assert Study.objects.get(public_id=filled).deleted_at is None
    assert "Supprimer cette étude" not in web("ben").get(f"/etudes/{filled}/definitions/").content.decode()
    assert "Supprimer cette étude" in web("ana").get(f"/etudes/{filled}/definitions/").content.decode()


def test_the_trash_empties_itself_after_the_delay(api, filled, settings):
    api.delete(f"/studies/{filled}")
    Study.objects.filter(public_id=filled).update(deleted_at=timezone.now() - timedelta(days=29))
    call_command("purger_corbeille")
    assert Study.objects.filter(public_id=filled).exists()
    Study.objects.filter(public_id=filled).update(deleted_at=timezone.now() - timedelta(days=31))
    assert api.get("/trash")[1]["items"] == []  # la lecture de la corbeille la purge aussi
    assert not Study.objects.filter(public_id=filled).exists()
    assert AuditEvent.objects.get(action="study.purge").detail["expired"] is True
    settings.DEMETRA_TRASH_DAYS = 7
    assert api.get("/trash")[1]["days"] == 7


def test_a_token_limited_to_other_studies_does_not_see_this_trash(api, filled, token_for):
    _, other = api.post("/studies", {"title": "Autre", "kind": "mixed"})
    api.delete(f"/studies/{filled}")
    limited = Api(token_for("ana", studies=[other["id"]]))
    assert limited.get("/trash")[1]["items"] == []
    assert limited.post(f"/trash/{filled}/restore")[0] == 404


def test_the_trash_message_offers_to_undo(api, filled, web):
    ana = web("ana")
    page = ana.post(f"/etudes/{filled}/definitions/", {"action": "trash"}, follow=True).content.decode()
    assert "mise à la corbeille" in page and 'class="flash-undo"' in page
    assert f'name="study" value="{filled}"' in page and ">Annuler</button>" in page
    response = ana.post("/etudes/corbeille/", {"study": filled, "action": "restore"})
    assert response.url == f"/etudes/{filled}/"
    assert Study.objects.get(public_id=filled).deleted_at is None
    assert "flash-undo" not in ana.get("/etudes/").content.decode()  # le bouton ne survit pas au message


def test_only_the_trash_message_carries_the_undo_button(api, filled, web):
    ana = web("ana")
    page = ana.post("/etudes/", {"title": "Une autre", "kind": "mixed"}, follow=True).content.decode()
    assert "flash-success" in page and "flash-undo" not in page
