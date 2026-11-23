"""Réglages d'entreprise lus dans l'environnement : HTTPS, SSO OpenID Connect, annuaire LDAP.

Chaque fonction reçoit l'environnement (un dictionnaire) et rend des réglages Django ; rien n'est lu ailleurs,
ce qui permet de les essayer sans relancer le site. Toutes les variables sont décrites dans le README.
"""

from __future__ import annotations


def _flag(env, name: str, default: bool) -> bool:
    value = env.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "oui", "on")


def _list(env, name: str) -> list[str]:
    return [item.strip() for item in env.get(name, "").split(",") if item.strip()]


def https_settings(env, debug: bool) -> dict:
    """HTTPS : actif par défaut dès que le mode débogage est coupé.

    Le site ne termine pas TLS lui-même : un frontal (Caddy, nginx, Apache, répartiteur de charge) reçoit le
    HTTPS et transmet la requête. `DEMETRA_BEHIND_PROXY=1` fait confiance à son en-tête X-Forwarded-Proto.
    """
    https = _flag(env, "DEMETRA_HTTPS", not debug)
    out: dict = {
        "SECURE_CONTENT_TYPE_NOSNIFF": True,
        "SECURE_REFERRER_POLICY": "same-origin",
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SECURE": https,
        "CSRF_COOKIE_SECURE": https,
        "SECURE_SSL_REDIRECT": https and _flag(env, "DEMETRA_SSL_REDIRECT", True),
        "SECURE_HSTS_SECONDS": int(env.get("DEMETRA_HSTS_SECONDS", "31536000")) if https else 0,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": https and _flag(env, "DEMETRA_HSTS_SUBDOMAINS", False),
        "SECURE_HSTS_PRELOAD": https and _flag(env, "DEMETRA_HSTS_PRELOAD", False),
    }
    if _flag(env, "DEMETRA_BEHIND_PROXY", False):
        out["SECURE_PROXY_SSL_HEADER"] = ("HTTP_X_FORWARDED_PROTO", "https")
        out["USE_X_FORWARDED_HOST"] = _flag(env, "DEMETRA_FORWARDED_HOST", False)
    return out


def mail_settings(env) -> dict:
    """Envoi des e-mails (mot de passe oublié) : serveur SMTP si `DEMETRA_SMTP_HOST` est renseigné, console sinon."""
    host = env.get("DEMETRA_SMTP_HOST", "").strip()
    if not host:
        return {"MAILERS": {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}}
    options = {"host": host, "port": int(env.get("DEMETRA_SMTP_PORT", "587")),
               "use_tls": _flag(env, "DEMETRA_SMTP_STARTTLS", True), "timeout": 20}
    if env.get("DEMETRA_SMTP_USER"):
        options |= {"username": env["DEMETRA_SMTP_USER"], "password": env.get("DEMETRA_SMTP_PASSWORD", "")}
    out = {"MAILERS": {"default": {"BACKEND": "django.core.mail.backends.smtp.EmailBackend", "OPTIONS": options}}}
    if env.get("DEMETRA_MAIL_FROM"):
        out["DEFAULT_FROM_EMAIL"] = env["DEMETRA_MAIL_FROM"]
    return out


def oidc_settings(env) -> dict | None:
    """SSO OpenID Connect (Entra ID / Azure AD, Okta, Keycloak, Google Workspace, ADFS…). None s'il n'est pas réglé."""
    issuer = env.get("DEMETRA_OIDC_ISSUER", "").strip().rstrip("/")
    client_id = env.get("DEMETRA_OIDC_CLIENT_ID", "").strip()
    if not issuer or not client_id:
        return None
    return {
        "issuer": issuer,
        "client_id": client_id,
        "client_secret": env.get("DEMETRA_OIDC_CLIENT_SECRET", ""),
        "name": env.get("DEMETRA_OIDC_NAME", "").strip() or "le compte de l'entreprise",
        "scopes": env.get("DEMETRA_OIDC_SCOPES", "openid email profile").split(),
        "username_claim": env.get("DEMETRA_OIDC_USERNAME_CLAIM", "preferred_username"),
        "create_users": _flag(env, "DEMETRA_OIDC_CREATE_USERS", True),
        "link_by_email": _flag(env, "DEMETRA_OIDC_LINK_BY_EMAIL", False),
        "allowed_domains": [d.lower() for d in _list(env, "DEMETRA_OIDC_ALLOWED_DOMAINS")],
        "groups_claim": env.get("DEMETRA_OIDC_GROUPS_CLAIM", "groups"),
        "admin_groups": _list(env, "DEMETRA_OIDC_ADMIN_GROUPS"),
        "ca_bundle": env.get("DEMETRA_OIDC_CA_BUNDLE", "") or None,
        "timeout": float(env.get("DEMETRA_OIDC_TIMEOUT", "10")),
    }


def ldap_settings(env) -> dict:
    """Annuaire LDAP ou Active Directory (django-auth-ldap). Dictionnaire vide s'il n'est pas réglé.

    Le paquet est facultatif : `uv sync --extra ldap`. Il n'est importé que si `DEMETRA_LDAP_URI` est renseigné.
    """
    uri = env.get("DEMETRA_LDAP_URI", "").strip()
    if not uri:
        return {}
    try:
        import ldap
        from django_auth_ldap.config import (
            GroupOfNamesType,
            LDAPSearch,
            NestedActiveDirectoryGroupType,
            PosixGroupType,
        )
    except ImportError as exc:  # pragma: no cover - dépend de l'installation
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "DEMETRA_LDAP_URI est renseigné mais le module LDAP n'est pas installé : lancez « uv sync --extra ldap »."
        ) from exc

    out: dict = {
        "AUTH_LDAP_SERVER_URI": uri,
        "AUTH_LDAP_BIND_DN": env.get("DEMETRA_LDAP_BIND_DN", ""),
        "AUTH_LDAP_BIND_PASSWORD": env.get("DEMETRA_LDAP_BIND_PASSWORD", ""),
        "AUTH_LDAP_START_TLS": _flag(env, "DEMETRA_LDAP_START_TLS", False),
        "AUTH_LDAP_USER_ATTR_MAP": {
            "first_name": env.get("DEMETRA_LDAP_ATTR_FIRST_NAME", "givenName"),
            "last_name": env.get("DEMETRA_LDAP_ATTR_LAST_NAME", "sn"),
            "email": env.get("DEMETRA_LDAP_ATTR_EMAIL", "mail"),
        },
        "AUTH_LDAP_ALWAYS_UPDATE_USER": True,
        "AUTH_LDAP_CONNECTION_OPTIONS": {ldap.OPT_REFERRALS: 0},
        "AUTH_LDAP_CACHE_TIMEOUT": int(env.get("DEMETRA_LDAP_CACHE_SECONDS", "300")),
    }
    ca_file = env.get("DEMETRA_LDAP_CA_FILE", "")
    if ca_file:
        out["AUTH_LDAP_GLOBAL_OPTIONS"] = {ldap.OPT_X_TLS_CACERTFILE: ca_file,
                                           ldap.OPT_X_TLS_REQUIRE_CERT: ldap.OPT_X_TLS_DEMAND}

    template = env.get("DEMETRA_LDAP_USER_DN_TEMPLATE", "")
    if template:
        out["AUTH_LDAP_USER_DN_TEMPLATE"] = template
    else:
        base = env.get("DEMETRA_LDAP_USER_BASE", "")
        if not base:
            from django.core.exceptions import ImproperlyConfigured
            raise ImproperlyConfigured("LDAP : renseignez DEMETRA_LDAP_USER_BASE ou DEMETRA_LDAP_USER_DN_TEMPLATE.")
        user_filter = env.get("DEMETRA_LDAP_USER_FILTER", "(uid=%(user)s)")
        out["AUTH_LDAP_USER_SEARCH"] = LDAPSearch(base, ldap.SCOPE_SUBTREE, user_filter)

    group_base = env.get("DEMETRA_LDAP_GROUP_BASE", "")
    if group_base:
        kind = env.get("DEMETRA_LDAP_GROUP_TYPE", "groupOfNames").strip().lower()
        if kind in ("activedirectory", "ad"):
            group_type, group_filter = NestedActiveDirectoryGroupType(), "(objectClass=group)"
        elif kind == "posix":
            group_type, group_filter = PosixGroupType(), "(objectClass=posixGroup)"
        else:
            group_type, group_filter = GroupOfNamesType(), "(objectClass=groupOfNames)"
        out["AUTH_LDAP_GROUP_SEARCH"] = LDAPSearch(group_base, ldap.SCOPE_SUBTREE, group_filter)
        out["AUTH_LDAP_GROUP_TYPE"] = group_type
        if env.get("DEMETRA_LDAP_REQUIRE_GROUP"):
            out["AUTH_LDAP_REQUIRE_GROUP"] = env["DEMETRA_LDAP_REQUIRE_GROUP"]
        if env.get("DEMETRA_LDAP_ADMIN_GROUP"):
            admin = env["DEMETRA_LDAP_ADMIN_GROUP"]
            out["AUTH_LDAP_USER_FLAGS_BY_GROUP"] = {"is_staff": admin, "is_superuser": admin}
    return out
