"""Règles de connexion et d'inscription appliquées par django-allauth."""

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        # Inscription fermée : la page d'inscription refuse aussi, pas seulement le lien masqué.
        return settings.ACCOUNT_SIGNUP_OPEN and settings.DEMETRA_PASSWORD_LOGIN

    def authenticate(self, request, **credentials):
        # Mot de passe coupé (tout passe par le SSO) : le formulaire de connexion ne laisse plus entrer
        # personne.
        if not settings.DEMETRA_PASSWORD_LOGIN:
            return None
        return super().authenticate(request, **credentials)
