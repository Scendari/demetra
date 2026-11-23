"""Connexion par le SSO de l'entreprise (OpenID Connect, flux « authorization code » avec PKCE).

Écrit avec la bibliothèque standard et PyJWT : le module social de django-allauth tire `requests`, donc
`certifi`, sous licence MPL, exclue du projet. Fournisseurs visés : Entra ID (Azure AD), Okta, Keycloak,
Google Workspace, ADFS, Authentik… tout ce qui publie un document `/.well-known/openid-configuration`.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

import jwt
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.db import transaction
from django.http import HttpResponseNotFound
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET

from .models import AuditEvent, ExternalIdentity

_SESSION_KEY = "demetra_oidc"
_DISCOVERY: dict[str, tuple[float, dict]] = {}
_DISCOVERY_TTL = 3600


class SSOError(Exception):
    """Refus lisible par la personne qui se connecte."""


# ----- Échanges HTTP (remplacés dans les tests) -----

def _ssl_context(conf) -> ssl.SSLContext:
    return ssl.create_default_context(cafile=conf.get("ca_bundle"))


def _get_json(url: str, conf) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=conf["timeout"], context=_ssl_context(conf)) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_form(url: str, data: dict, conf) -> dict:
    body = urllib.parse.urlencode(data).encode("ascii")
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(request, timeout=conf["timeout"], context=_ssl_context(conf)) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise SSOError("Le fournisseur d'identité a refusé l'échange du code.") from exc


def discovery(conf) -> dict:
    cached = _DISCOVERY.get(conf["issuer"])
    if cached and time.monotonic() - cached[0] < _DISCOVERY_TTL:
        return cached[1]
    document = _get_json(conf["issuer"] + "/.well-known/openid-configuration", conf)
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not document.get(key):
            raise SSOError("Le document de découverte du fournisseur est incomplet.")
    _DISCOVERY[conf["issuer"]] = (time.monotonic(), document)
    return document


# ----- Jeton d'identité -----

def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def verify_id_token(token: str, conf, meta: dict, nonce: str) -> dict:
    try:
        header = jwt.get_unverified_header(token)
        keys = jwt.PyJWKSet.from_dict(_get_json(meta["jwks_uri"], conf))
        candidates = [k for k in keys.keys if not header.get("kid") or k.key_id == header.get("kid")]
        if not candidates:
            raise SSOError("La clé de signature du jeton est inconnue.")
        algorithms = meta.get("id_token_signing_alg_values_supported") or ["RS256"]
        algorithms = [a for a in algorithms if a != "none"]
        claims = jwt.decode(token, candidates[0], algorithms=algorithms, audience=conf["client_id"],
                            issuer=meta.get("issuer", conf["issuer"]), leeway=60,
                            options={"require": ["exp", "iat", "sub", "iss", "aud"]})
    except jwt.PyJWTError as exc:
        raise SSOError("Le jeton d'identité n'est pas valide.") from exc
    if claims.get("nonce") != nonce:
        raise SSOError("Le jeton d'identité ne correspond pas à cette connexion.")
    return claims


# ----- Compte local -----

def _username_from(claims, conf) -> str:
    raw = str(claims.get(conf["username_claim"]) or claims.get("email") or claims["sub"])
    base = re.sub(r"[^\w.@+-]", "", raw)[:140] or "sso"
    User = get_user_model()
    candidate, n = base, 1
    while User.objects.filter(username__iexact=candidate).exists():
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def user_for(claims: dict, conf) -> object:
    """Retrouve ou crée le compte lié à l'identité ; applique les groupes d'administration s'ils sont réglés."""
    User = get_user_model()
    issuer, subject = claims["iss"], str(claims["sub"])
    email = str(claims.get("email") or "").strip()
    if conf["allowed_domains"]:
        domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
        if domain not in conf["allowed_domains"]:
            raise SSOError("Ce compte n'appartient pas à un domaine autorisé.")
    with transaction.atomic():
        identity = ExternalIdentity.objects.select_related("user").filter(issuer=issuer, subject=subject).first()
        if identity:
            user = identity.user
        else:
            user = None
            if conf["link_by_email"] and email:
                user = User.objects.filter(email__iexact=email).order_by("id").first()
            if user is None:
                if not conf["create_users"]:
                    raise SSOError("Aucun compte Demetra n'est ouvert pour cette identité. Demandez-le à "
                                   "l'administrateur du site.")
                user = User(username=_username_from(claims, conf), email=email,
                            first_name=str(claims.get("given_name") or "")[:150],
                            last_name=str(claims.get("family_name") or "")[:150])
                user.set_unusable_password()
                user.save()
            identity = ExternalIdentity.objects.create(user=user, issuer=issuer, subject=subject)
        if not user.is_active:
            raise SSOError("Ce compte Demetra est désactivé.")
        if conf["admin_groups"]:
            groups = claims.get(conf["groups_claim"]) or []
            groups = [groups] if isinstance(groups, str) else list(groups)
            is_admin = any(g in groups for g in conf["admin_groups"])
            if user.is_staff != is_admin or user.is_superuser != is_admin:
                user.is_staff = user.is_superuser = is_admin
                user.save(update_fields=["is_staff", "is_superuser"])
        identity.last_login_at = timezone.now()
        identity.save(update_fields=["last_login_at"])
    return user


# ----- Vues -----

def _conf():
    return getattr(settings, "DEMETRA_OIDC", None)


@require_GET
def start(request):
    conf = _conf()
    if not conf:
        return HttpResponseNotFound()
    next_url = request.GET.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        next_url = ""
    try:
        meta = discovery(conf)
    except (SSOError, OSError, ValueError):
        messages.error(request, "Le fournisseur d'identité ne répond pas. Réessayez dans un instant.")
        return redirect(settings.LOGIN_URL)
    state, nonce, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    request.session[_SESSION_KEY] = {"state": state, "nonce": nonce, "verifier": verifier, "next": next_url}
    params = {
        "response_type": "code",
        "client_id": conf["client_id"],
        "redirect_uri": request.build_absolute_uri(reverse("sso_callback")),
        "scope": " ".join(conf["scopes"]),
        "state": state,
        "nonce": nonce,
        "code_challenge": _b64(hashlib.sha256(verifier.encode("ascii")).digest()),
        "code_challenge_method": "S256",
    }
    separator = "&" if "?" in meta["authorization_endpoint"] else "?"
    return redirect(meta["authorization_endpoint"] + separator + urllib.parse.urlencode(params))


@require_GET
def callback(request):
    conf = _conf()
    if not conf:
        return HttpResponseNotFound()
    pending = request.session.pop(_SESSION_KEY, None)
    try:
        if request.GET.get("error"):
            raise SSOError("La connexion a été annulée ou refusée par le fournisseur d'identité.")
        if not pending or not secrets.compare_digest(str(request.GET.get("state", "")), pending["state"]):
            raise SSOError("La connexion a expiré. Recommencez.")
        code = request.GET.get("code")
        if not code:
            raise SSOError("Le fournisseur d'identité n'a pas rendu de code.")
        meta = discovery(conf)
        data = {"grant_type": "authorization_code", "code": code, "code_verifier": pending["verifier"],
                "redirect_uri": request.build_absolute_uri(reverse("sso_callback")),
                "client_id": conf["client_id"]}
        if conf["client_secret"]:
            data["client_secret"] = conf["client_secret"]
        tokens = _post_form(meta["token_endpoint"], data, conf)
        if not tokens.get("id_token"):
            raise SSOError("Le fournisseur d'identité n'a pas rendu de jeton d'identité.")
        claims = verify_id_token(tokens["id_token"], conf, meta, pending["nonce"])
        user = user_for(claims, conf)
    except SSOError as exc:
        messages.error(request, str(exc))
        return redirect(settings.LOGIN_URL)
    except (OSError, ValueError, KeyError):
        messages.error(request, "Le fournisseur d'identité ne répond pas correctement. Réessayez dans un instant.")
        return redirect(settings.LOGIN_URL)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    AuditEvent.objects.create(actor_user=user, channel="web", action="login.sso", target=user.username,
                              detail={"issuer": claims["iss"]})
    return redirect(pending.get("next") or settings.LOGIN_REDIRECT_URL)
