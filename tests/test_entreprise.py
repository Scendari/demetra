"""Connexion d'entreprise (SSO OpenID Connect, LDAP) et réglages HTTPS."""
from __future__ import annotations

import time
import urllib.parse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth import get_user_model

from core import sso
from core.models import ExternalIdentity
from demetra.entreprise import https_settings, ldap_settings, oidc_settings

ISSUER = "https://idp.exemple.test"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWK = {**jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key(), as_dict=True), "kid": "k1", "use": "sig"}
META = {"issuer": ISSUER, "authorization_endpoint": ISSUER + "/authorize", "token_endpoint": ISSUER + "/token",
        "jwks_uri": ISSUER + "/jwks", "id_token_signing_alg_values_supported": ["RS256"]}


def conf(**extra):
    env = {"DEMETRA_OIDC_ISSUER": ISSUER, "DEMETRA_OIDC_CLIENT_ID": "demetra", "DEMETRA_OIDC_CLIENT_SECRET": "s",
           "DEMETRA_OIDC_NAME": "Annuaire test", **extra}
    return oidc_settings(env)


@pytest.fixture
def idp(monkeypatch, settings):
    """Faux fournisseur : découverte, clés, échange du code. `claims` règle le contenu du prochain jeton."""
    settings.DEMETRA_OIDC = conf()
    sso._DISCOVERY.clear()
    state = {"claims": {}, "posted": None, "nonce": None}

    def get_json(url, _conf):
        return {ISSUER + "/.well-known/openid-configuration": META, ISSUER + "/jwks": {"keys": [JWK]}}[url]

    def post_form(url, data, _conf):
        assert url == META["token_endpoint"]
        state["posted"] = data
        now = int(time.time())
        claims = {"iss": ISSUER, "aud": "demetra", "sub": "abc-123", "iat": now, "exp": now + 300,
                  "nonce": state["nonce"], "preferred_username": "camille.martin",
                  "email": "camille@exemple.test", **state["claims"]}
        return {"id_token": jwt.encode(claims, KEY, algorithm="RS256", headers={"kid": "k1"})}

    monkeypatch.setattr(sso, "_get_json", get_json)
    monkeypatch.setattr(sso, "_post_form", post_form)
    return state


def run_flow(client, idp, next_url="/etudes/"):
    response = client.get("/comptes/sso/", {"next": next_url})
    assert response.status_code == 302
    query = urllib.parse.parse_qs(urllib.parse.urlparse(response["Location"]).query)
    assert response["Location"].startswith(META["authorization_endpoint"])
    assert query["code_challenge_method"] == ["S256"] and query["client_id"] == ["demetra"]
    idp["nonce"] = query["nonce"][0]
    return client.get("/comptes/sso/retour/", {"code": "c0de", "state": query["state"][0]})


@pytest.mark.django_db
def test_sso_creates_account_and_logs_in(client, idp):
    response = run_flow(client, idp, next_url="/guide/")
    assert response.status_code == 302 and response["Location"] == "/guide/"
    user = get_user_model().objects.get(username="camille.martin")
    assert not user.has_usable_password() and user.email == "camille@exemple.test"
    assert ExternalIdentity.objects.get(user=user).subject == "abc-123"
    assert idp["posted"]["code_verifier"] and idp["posted"]["code"] == "c0de"
    assert client.get("/etudes/").status_code == 200
    # Deuxième connexion : même compte, pas de doublon.
    client.logout()
    run_flow(client, idp)
    assert get_user_model().objects.filter(username__startswith="camille").count() == 1


@pytest.mark.django_db
def test_sso_never_matches_an_existing_account_by_email_unless_asked(client, idp, settings):
    User = get_user_model()
    User.objects.create_user("camille", "camille@exemple.test", "x-long-password")
    run_flow(client, idp)
    assert ExternalIdentity.objects.get().user.username == "camille.martin"
    settings.DEMETRA_OIDC = conf(DEMETRA_OIDC_LINK_BY_EMAIL="1")
    idp["claims"] = {"sub": "autre"}
    client.logout()
    run_flow(client, idp)
    assert ExternalIdentity.objects.get(subject="autre").user.username == "camille"


@pytest.mark.django_db
def test_sso_refusals(client, idp, settings):
    # Jeton rejoué pour une autre connexion : le nonce ne correspond pas.
    idp["claims"] = {"nonce": "pas-le-bon"}
    response = run_flow(client, idp)
    assert response["Location"] == "/comptes/login/"
    assert not get_user_model().objects.exists()
    # State absent ou faux.
    assert client.get("/comptes/sso/retour/", {"code": "x", "state": "y"})["Location"] == "/comptes/login/"
    # Mauvaise audience.
    idp["claims"] = {"aud": "autre-appli"}
    run_flow(client, idp)
    assert not get_user_model().objects.exists()
    # Domaine non autorisé, création coupée.
    idp["claims"] = {}
    settings.DEMETRA_OIDC = conf(DEMETRA_OIDC_ALLOWED_DOMAINS="entreprise.test")
    run_flow(client, idp)
    settings.DEMETRA_OIDC = conf(DEMETRA_OIDC_CREATE_USERS="0")
    run_flow(client, idp)
    assert not get_user_model().objects.exists()
    # Redirection vers un autre site refusée.
    settings.DEMETRA_OIDC = conf()
    assert run_flow(client, idp, next_url="https://ailleurs.test/")["Location"] == "/etudes/"


@pytest.mark.django_db
def test_sso_admin_groups(client, idp, settings):
    settings.DEMETRA_OIDC = conf(DEMETRA_OIDC_ADMIN_GROUPS="demetra-admins")
    idp["claims"] = {"groups": ["demetra-admins"]}
    run_flow(client, idp)
    user = get_user_model().objects.get()
    assert user.is_staff and user.is_superuser
    idp["claims"] = {"groups": []}
    client.logout()
    run_flow(client, idp)
    user.refresh_from_db()
    assert not user.is_staff and not user.is_superuser


@pytest.mark.django_db
def test_login_page_offers_sso_and_can_hide_passwords(client, settings):
    page = client.get("/comptes/login/").content.decode()
    assert "Continuer avec" not in page and 'id="id_password"' in page
    settings.DEMETRA_OIDC = conf()
    page = client.get("/comptes/login/").content.decode()
    assert "Continuer avec Annuaire test" in page and 'id="id_password"' in page
    settings.DEMETRA_PASSWORD_LOGIN = False
    page = client.get("/comptes/login/").content.decode()
    assert "Continuer avec Annuaire test" in page and 'id="id_password"' not in page
    get_user_model().objects.create_user("demo2", "d@exemple.test", "x-long-password")
    client.post("/comptes/login/", {"login": "demo2", "password": "x-long-password"})
    assert client.get("/etudes/").status_code == 302


@pytest.mark.django_db
def test_closed_signup_is_enforced_not_just_hidden(client, settings):
    settings.ACCOUNT_SIGNUP_OPEN = False
    client.post("/comptes/signup/", {"username": "intrus", "email": "i@exemple.test",
                                     "password1": "x-long-password-1", "password2": "x-long-password-1"})
    assert not get_user_model().objects.filter(username="intrus").exists()


def test_sso_disabled_returns_404(client, settings):
    settings.DEMETRA_OIDC = None
    assert client.get("/comptes/sso/").status_code == 404


def test_https_settings():
    assert https_settings({}, debug=True)["SESSION_COOKIE_SECURE"] is False
    prod = https_settings({}, debug=False)
    assert prod["SESSION_COOKIE_SECURE"] and prod["CSRF_COOKIE_SECURE"] and prod["SECURE_SSL_REDIRECT"]
    assert prod["SECURE_HSTS_SECONDS"] == 31536000 and "SECURE_PROXY_SSL_HEADER" not in prod
    proxied = https_settings({"DEMETRA_BEHIND_PROXY": "1", "DEMETRA_HSTS_SECONDS": "600"}, debug=False)
    assert proxied["SECURE_PROXY_SSL_HEADER"] == ("HTTP_X_FORWARDED_PROTO", "https")
    assert proxied["SECURE_HSTS_SECONDS"] == 600
    assert https_settings({"DEMETRA_HTTPS": "0"}, debug=False)["SECURE_SSL_REDIRECT"] is False


def test_ldap_settings():
    pytest.importorskip("django_auth_ldap")
    assert ldap_settings({}) == {}
    out = ldap_settings({"DEMETRA_LDAP_URI": "ldaps://annuaire.exemple.test", "DEMETRA_LDAP_USER_BASE": "ou=people,dc=ex",
                         "DEMETRA_LDAP_USER_FILTER": "(sAMAccountName=%(user)s)", "DEMETRA_LDAP_GROUP_BASE": "ou=groups,dc=ex",
                         "DEMETRA_LDAP_GROUP_TYPE": "activedirectory", "DEMETRA_LDAP_REQUIRE_GROUP": "cn=demetra,ou=groups,dc=ex",
                         "DEMETRA_LDAP_ADMIN_GROUP": "cn=demetra-admins,ou=groups,dc=ex"})
    assert out["AUTH_LDAP_SERVER_URI"] == "ldaps://annuaire.exemple.test"
    assert out["AUTH_LDAP_USER_SEARCH"].filterstr == "(sAMAccountName=%(user)s)"
    assert type(out["AUTH_LDAP_GROUP_TYPE"]).__name__ == "NestedActiveDirectoryGroupType"
    assert out["AUTH_LDAP_REQUIRE_GROUP"] == "cn=demetra,ou=groups,dc=ex"
    assert out["AUTH_LDAP_USER_FLAGS_BY_GROUP"]["is_superuser"] == "cn=demetra-admins,ou=groups,dc=ex"
    with pytest.raises(Exception, match="USER_BASE"):
        ldap_settings({"DEMETRA_LDAP_URI": "ldap://x"})


@pytest.mark.django_db
def test_ldap_backend_is_used_by_the_login_form(client, settings, monkeypatch):
    """Le formulaire de connexion passe bien par le module LDAP quand il est réglé (annuaire simulé)."""
    pytest.importorskip("django_auth_ldap")
    from django_auth_ldap.backend import LDAPBackend
    seen = {}

    def fake_authenticate(self, request, username=None, password=None, **kwargs):
        seen["username"] = username

    monkeypatch.setattr(LDAPBackend, "authenticate", fake_authenticate)
    settings.AUTHENTICATION_BACKENDS = ["django_auth_ldap.backend.LDAPBackend", *settings.AUTHENTICATION_BACKENDS]
    client.post("/comptes/login/", {"login": "jdupont", "password": "secret"})
    assert seen["username"] == "jdupont"
