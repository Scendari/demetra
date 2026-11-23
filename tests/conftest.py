"""Outils communs aux tests : comptes, jetons, client d'API, étude d'exemple."""
from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from core import services as svc

PASSWORD = "mot-de-passe-de-test"

STUDY = {
    "title": "Accès à un bâtiment",
    "kind": "workflow",
    "statuses": [
        {"key": "ATTENTE", "label": "En attente", "role": "waiting", "default": True},
        {"key": "EN_COURS", "label": "En cours", "role": "active"},
        {"key": "OK", "label": "Réussi", "role": "success"},
        {"key": "KO", "label": "En échec", "role": "error"},
        {"key": "BLOQUE", "label": "Bloqué", "role": "blocked"},
    ],
    "dimensions": [
        {"key": "badge", "label": "Badge", "values": ["valide", "expiré"]},
        {"key": "horaire", "label": "Horaire", "values": ["jour", "nuit", "week-end"]},
    ],
    "rules": [{"key": "R1", "title": "Badge valide", "text": "Un badge expiré n'ouvre aucune porte."}],
    "exclusions": [{"when": {"badge": "expiré", "horaire": "week-end"}, "reason": "Les badges expirés sont désactivés le vendredi soir."}],
}


def make_case(key: str, badge: str = "valide", horaire: str = "jour", *, ok: bool = True, title: str | None = None, **extra) -> dict:
    case = {
        "key": key, "title": title or f"Badge {badge}, {horaire}", "family": "Entrées", "rules": ["R1"],
        "dimensions": {"badge": badge, "horaire": horaire},
        "entities": [{"id": "lecture", "label": "Lecture du badge", "type": "task"}, {"id": "porte", "label": "Ouverture", "type": "task"}],
        "links": [{"from": "lecture", "to": "porte", "type": "prerequisite"}],
        "steps": [
            {"title": "Le badge est lu", "changes": {"lecture": "EN_COURS"}},
            {"title": "Le badge est accepté" if ok else "Le badge est refusé", "changes": {"lecture": "OK" if ok else "KO"}},
            {"title": "La porte s'ouvre" if ok else "La porte reste fermée", "changes": {"porte": "OK" if ok else "BLOQUE"}, "global": "OK" if ok else "KO"},
        ],
        "outcome": {"label": "Entrée" if ok else "Refus", "status": "OK" if ok else "KO"},
    }
    case.update(extra)
    return case


class Api:
    """Client d'API : un jeton, des appels JSON."""

    def __init__(self, secret: str | None = None):
        self.client, self.secret = Client(), secret

    def call(self, method: str, path: str, body=None, **headers):
        extra = {f"HTTP_{k.upper().replace('-', '_')}": v for k, v in headers.items()}
        if self.secret:
            extra["HTTP_AUTHORIZATION"] = f"Bearer {self.secret}"
        kwargs = {"data": json.dumps(body), "content_type": "application/json"} if body is not None else {}
        response = getattr(self.client, method.lower())("/api/v1" + path, **kwargs, **extra)
        try:
            return response.status_code, response.json()
        except ValueError:
            return response.status_code, response.content.decode()

    def get(self, path, **headers):
        return self.call("GET", path, **headers)

    def post(self, path, body=None, **headers):
        return self.call("POST", path, body if body is not None else {}, **headers)

    def patch(self, path, body):
        return self.call("PATCH", path, body)

    def delete(self, path):
        return self.call("DELETE", path)


@pytest.fixture
def users(db):
    User = get_user_model()
    return {name: User.objects.create_user(name, f"{name}@example.org", PASSWORD) for name in ("ana", "ben", "cleo")}


@pytest.fixture
def token_for(users):
    def build(name: str, scopes=None, studies=None, days=30) -> str:
        _, secret = svc.create_token(users[name], f"jeton-{name}", list(scopes or svc.SCOPES), studies, days)
        return secret
    return build


@pytest.fixture
def api(token_for):
    return Api(token_for("ana"))


@pytest.fixture
def study(api):
    status, data = api.post("/studies", STUDY)
    assert status == 201, data
    return data["id"]


@pytest.fixture
def web(users):
    def login(name: str) -> Client:
        client = Client()
        assert client.login(username=name, password=PASSWORD)
        return client
    return login
