"""Connexion d'une IA par lien d'autorisation : aucun jeton à copier pour la personne."""
from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from core import connect
from core.models import ApiToken, ConnectRequest

from .conftest import Api


def start(client=None, **body):
    client = client or Client()
    response = client.post("/api/v1/connect", data=json.dumps(body or {"client_name": "Copilot VS Code"}),
                           content_type="application/json")
    assert response.status_code == 201, response.content
    return response.json()


def poll(device_code, plain=False):
    headers = {"HTTP_ACCEPT": "text/plain"} if plain else {}
    ConnectRequest.objects.update(last_poll_at=None)  # pas de « slow_down » entre deux appels du test
    return Client().post("/api/v1/connect/token", data=json.dumps({"device_code": device_code}),
                         content_type="application/json", **headers)


@pytest.mark.django_db
def test_full_flow_gives_a_working_token_once(web, users):
    data = start()
    assert data["verification_url"] == f"http://testserver/connecter/?code={data['user_code']}"
    assert len(data["device_code"]) > 30 and data["expires_in"] == 600
    stored = ConnectRequest.objects.get()
    assert data["device_code"] not in stored.device_hash  # seul le condensé est gardé
    assert poll(data["device_code"]).status_code == 202

    browser = web("ana")
    page = browser.get(data["verification_url"]).content.decode()
    assert "Copilot VS Code" in page and data["user_code"] in page and "Autoriser" in page
    done = browser.post("/connecter/", {"code": data["user_code"], "action": "approve",
                                        "scopes": ["studies:read", "studies:write"], "days": "30"})
    assert "Retournez à votre IA" in done.content.decode()
    assert not ApiToken.objects.exists(), "le jeton n'existe qu'au moment où l'IA vient le chercher"

    response = poll(data["device_code"], plain=True)
    assert response.status_code == 200
    secret = response.content.decode()
    assert secret.startswith("dmt_")
    status, me = Api(secret).get("/me")
    assert status == 200 and me["user"] == "ana" and me["token"]["scopes"] == ["studies:read", "studies:write"]
    assert ApiToken.objects.get().name == "Copilot VS Code"
    # Une seule remise.
    assert poll(data["device_code"]).status_code == 410


@pytest.mark.django_db
def test_denied_expired_unknown_and_slow_down(web):
    data = start()
    web("ana").post("/connecter/", {"code": data["user_code"], "action": "deny"})
    assert poll(data["device_code"]).status_code == 403

    late = start()
    ConnectRequest.objects.filter(user_code=late["user_code"]).update(expires_at=timezone.now() - timedelta(seconds=1))
    assert poll(late["device_code"]).status_code == 410
    page = web("ana").get(f"/connecter/?code={late['user_code']}").content.decode()
    assert "inconnu, déjà utilisé ou expiré" in page

    assert poll("pas-un-code").status_code == 404

    fast = start()
    client = Client()
    body = json.dumps({"device_code": fast["device_code"]})
    assert client.post("/api/v1/connect/token", data=body, content_type="application/json").status_code == 202
    assert client.post("/api/v1/connect/token", data=body, content_type="application/json").status_code == 429


@pytest.mark.django_db
def test_approval_needs_a_logged_in_human(client):
    data = start()
    response = client.get(data["verification_url"])
    assert response.status_code == 302 and "/comptes/login/" in response["Location"]
    response = client.post("/connecter/", {"code": data["user_code"], "action": "approve", "scopes": ["studies:read"]})
    assert ConnectRequest.objects.get().status == ConnectRequest.Status.PENDING


@pytest.mark.django_db
def test_code_is_forgiving_and_scopes_are_filtered(web):
    data = start(client_name="  Claude\nCode  ", scopes=["studies:read", "admin:all"])
    request = ConnectRequest.objects.get()
    assert request.client_name == "Claude Code" and request.requested_scopes == ["studies:read"]
    loose = data["user_code"].replace("-", "").lower()
    assert connect.normalize_code(loose) == data["user_code"]
    page = web("ana").get(f"/connecter/?code={loose}").content.decode()
    assert "Claude Code" in page


def test_guide_and_llms_explain_the_link(client):
    llms = client.get("/llms.txt").content.decode()
    assert "/api/v1/connect" in llms and "DEMETRA_TOKEN" in llms
    md = client.get("/api/v1/guide/agents?format=md").content.decode()
    assert "http://testserver/api/v1/connect/token" in md and "verification_url" in md
    assert "connect" in client.get("/api/v1/me").json()["error"]["hint"]
