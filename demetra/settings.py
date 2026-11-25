"""Réglages Django de Demetra (POC, usage local ou petite équipe auto-hébergée)."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

from .entreprise import https_settings, ldap_settings, mail_settings, oidc_settings

_DEV_SECRET = "dev-insecure-change-me-demetra-poc"
SECRET_KEY = os.environ.get("DEMETRA_SECRET_KEY", _DEV_SECRET)
DEBUG = os.environ.get("DEMETRA_DEBUG", "1") == "1"
# Mode production tel que réglé par l'environnement (pytest force DEBUG=False, pas ce drapeau).
DEMETRA_PRODUCTION = not DEBUG
if not DEBUG and SECRET_KEY == _DEV_SECRET:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("DEMETRA_SECRET_KEY doit être renseignée quand DEMETRA_DEBUG=0.")
ALLOWED_HOSTS = os.environ.get("DEMETRA_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DEMETRA_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "core",
]

MIDDLEWARE = [
    "core.sante.HealthMiddleware",  # avant tout : la sonde du conteneur passe sans hôte autorisé ni HTTPS
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "demetra.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context.shell",
            ],
        },
    },
]

WSGI_APPLICATION = "demetra.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DEMETRA_DB", BASE_DIR / "db.sqlite3"),
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
        },
    }
}

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# HTTPS (derrière un frontal), SSO OpenID Connect et annuaire LDAP : tout se règle par variables
# d'environnement.
globals().update(https_settings(os.environ, DEBUG))
DEMETRA_OIDC = oidc_settings(os.environ)
_LDAP = ldap_settings(os.environ)
if _LDAP:
    globals().update(_LDAP)
    AUTHENTICATION_BACKENDS.insert(0, "django_auth_ldap.backend.LDAPBackend")
DEMETRA_LDAP = bool(_LDAP)
# Connexion par mot de passe local : à couper quand tout passe par le SSO (le compte d'administration créé par
# « createsuperuser » reste utilisable sur /admin/).
DEMETRA_PASSWORD_LOGIN = os.environ.get("DEMETRA_PASSWORD_LOGIN", "1") == "1"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

# Comptes (django-allauth) : inscription locale, sans vérification d'e-mail pour le POC.
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_LOGOUT_ON_GET = False
LOGIN_URL = "/comptes/login/"
LOGIN_REDIRECT_URL = "/etudes/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"
ACCOUNT_SIGNUP_OPEN = os.environ.get("DEMETRA_SIGNUP_OPEN", "1") == "1"
ACCOUNT_ADAPTER = "core.accounts.AccountAdapter"
globals().update(mail_settings(os.environ))

LANGUAGE_CODE = "fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = os.environ.get("DEMETRA_STATIC_ROOT", BASE_DIR / "staticfiles")
# Fichiers statiques servis par WhiteNoise. Dans l'image Docker, collectstatic produit des noms avec empreinte
# et des versions compressées (DEMETRA_STATIC_MANIFEST=1) ; en développement et en test, le stockage simple.
if not Path(STATIC_ROOT).is_dir():
    # Développement et tests : pas de collectstatic, WhiteNoise n'a rien à servir et le dit.
    import warnings

    warnings.filterwarnings("ignore", message="No directory at")
if os.environ.get("DEMETRA_STATIC_MANIFEST") == "1":
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Demetra
DEMETRA_GUIDE_VERSION = "2026-11-25.6"
DEMETRA_TOKEN_PREFIX = "dmt"
DEMETRA_SSE_MAX_SECONDS = int(os.environ.get("DEMETRA_SSE_MAX_SECONDS", "55"))
DEMETRA_MAX_BATCH = 200
