"""Administration du site (/admin/) : exploitation, sans toucher au contenu des études."""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from core.models import ApiToken, AuditEvent, Membership, Role, Study

from .conftest import PASSWORD


@pytest.fixture
def boss(users):
    return get_user_model().objects.create_superuser("chef", "chef@example.org", PASSWORD)


@pytest.fixture
def admin_client(boss):
    client = Client()
    assert client.login(username="chef", password=PASSWORD)
    return client


def test_every_admin_page_opens(admin_client, study, users):
    pages = ["/admin/", "/admin/auth/user/", f"/admin/auth/user/{users['ana'].pk}/change/", "/admin/core/study/",
             f"/admin/core/study/{Study.objects.get(public_id=study).pk}/change/", "/admin/core/apitoken/",
             "/admin/core/case/", "/admin/core/verdict/", "/admin/core/representation/", "/admin/core/auditevent/",
             "/admin/core/brickrequest/", "/admin/core/sharerequest/", "/admin/core/externalidentity/",
             "/admin/core/representationproposal/"]
    for url in pages:
        response = admin_client.get(url)
        assert response.status_code == 200, url
    home = admin_client.get("/admin/").content.decode()
    assert "Comptes actifs" in home and "Jetons actifs" in home and "Administration Demetra" in home
    assert admin_client.get("/admin/auth/group/").status_code == 404


def test_content_is_read_only(admin_client, study):
    case_pages = admin_client.get("/admin/core/case/").content.decode()
    assert "/admin/core/case/add/" not in case_pages
    assert admin_client.get("/admin/core/case/add/").status_code == 403
    assert admin_client.get("/admin/core/auditevent/add/").status_code == 403
    event = AuditEvent.objects.first()
    admin_client.post(f"/admin/core/auditevent/{event.pk}/delete/", {"post": "yes"})
    assert AuditEvent.objects.filter(pk=event.pk).exists()


def test_rail_link_only_for_staff(admin_client, web):
    assert "Administration" in admin_client.get("/etudes/").content.decode()
    assert "Administration" not in web("ana").get("/etudes/").content.decode()
    assert web("ana").get("/admin/").status_code == 302


def test_transfer_ownership_is_traced(admin_client, study, users):
    s = Study.objects.get(public_id=study)
    response = admin_client.post(f"/admin/core/study/{s.pk}/change/", {
        "title": s.title, "owner": users["ben"].pk,
        "memberships-TOTAL_FORMS": "0", "memberships-INITIAL_FORMS": "0",
        "memberships-MIN_NUM_FORMS": "0", "memberships-MAX_NUM_FORMS": "1000"})
    assert response.status_code == 302, response.content.decode()[:2000]
    s.refresh_from_db()
    assert s.owner == users["ben"]
    assert Membership.objects.get(study=s, user=users["ben"]).role == Role.OWNER
    assert Membership.objects.get(study=s, user=users["ana"]).role == Role.EDITOR
    event = AuditEvent.objects.get(study=s, action="admin.transfer")
    assert event.channel == "admin" and event.detail["previous"] == "ana"
    # L'historique de l'étude le montre au nouveau propriétaire.
    client = Client()
    client.login(username="ben", password=PASSWORD)
    history = client.get(f"/etudes/{study}/historique/").content.decode()
    assert "Propriété transférée" in history and "par l&#x27;administration du site" in history


def test_grant_access_from_admin(admin_client, study, users):
    s = Study.objects.get(public_id=study)
    admin_client.post(f"/admin/core/study/{s.pk}/change/", {
        "title": s.title, "owner": users["ana"].pk,
        "memberships-TOTAL_FORMS": "1", "memberships-INITIAL_FORMS": "0",
        "memberships-MIN_NUM_FORMS": "0", "memberships-MAX_NUM_FORMS": "1000",
        "memberships-0-user": users["cleo"].pk, "memberships-0-role": "commenter", "memberships-0-study": s.pk})
    assert Membership.objects.get(study=s, user=users["cleo"]).role == Role.COMMENTER
    assert AuditEvent.objects.filter(study=s, action="share.grant", channel="admin", target="cleo").exists()


def test_deactivate_users_revokes_their_tokens(admin_client, users, token_for):
    token_for("ben")
    response = admin_client.post("/admin/auth/user/", {"action": "deactivate", "_selected_action": [users["ben"].pk]})
    assert response.status_code == 302
    users["ben"].refresh_from_db()
    assert not users["ben"].is_active
    assert not ApiToken.objects.filter(user=users["ben"], revoked_at__isnull=True).exists()
    # Pas de suppression en masse : elle emporterait les études.
    page = admin_client.get("/admin/auth/user/").content.decode()
    assert "delete_selected" not in page


def test_revoke_token_from_admin(admin_client, users, token_for):
    token_for("ana")
    token = ApiToken.objects.get(user=users["ana"])
    admin_client.post("/admin/core/apitoken/", {"action": "revoke", "_selected_action": [token.pk]})
    token.refresh_from_db()
    assert token.revoked_at is not None
    assert AuditEvent.objects.filter(action="token.revoke", channel="admin").exists()
    assert "token_hash" not in admin_client.get(f"/admin/core/apitoken/{token.pk}/change/").content.decode()
