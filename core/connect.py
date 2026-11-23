"""Connexion d'une IA par lien d'autorisation : l'utilisateur ne copie aucun jeton, ne tape aucune commande.

1. L'IA appelle POST /api/v1/connect : elle reçoit un code secret (device_code) et un lien à donner à la personne.
2. La personne ouvre le lien, connectée à Demetra, voit qui demande quoi, règle les droits et autorise.
3. L'IA appelle POST /api/v1/connect/token avec son code secret : elle reçoit le jeton, une seule fois, et le range
   elle-même dans la session sans l'afficher.

Le site ne garde que le condensé du code secret ; le jeton est créé à l'instant où l'IA vient le chercher.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from . import services as svc
from .models import ConnectRequest

LIFETIME = timedelta(minutes=10)
INTERVAL = 3  # secondes minimales entre deux interrogations
_CODE_ALPHABET = "BCDFGHJKLMNPQRSTVWXZ23456789"  # ni voyelles (pas de mots), ni 0/O, 1/I


def _hash(device_code: str) -> str:
    return hashlib.sha256(device_code.encode()).hexdigest()


def _user_code() -> str:
    raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def normalize_code(value: str) -> str:
    raw = re.sub(r"[^A-Za-z0-9]", "", value or "").upper()
    return f"{raw[:4]}-{raw[4:8]}" if len(raw) == 8 else ""


def start(client_name: str, scopes: list[str] | None, origin: str) -> dict:
    now = timezone.now()
    ConnectRequest.objects.filter(expires_at__lt=now - timedelta(days=1)).delete()
    if ConnectRequest.objects.filter(status=ConnectRequest.Status.PENDING, expires_at__gt=now).count() > 500:
        raise svc.ServiceError(429, "too_many_requests", "Trop de demandes de connexion en cours. Réessayez dans quelques minutes.")
    name = re.sub(r"\s+", " ", str(client_name or "")).strip()[:60] or "IA sans nom"
    wanted = [s for s in (scopes or svc.DEFAULT_SCOPES) if s in svc.SCOPES] or list(svc.DEFAULT_SCOPES)
    device_code = secrets.token_urlsafe(32)
    code = _user_code()
    while ConnectRequest.objects.filter(user_code=code, status=ConnectRequest.Status.PENDING, expires_at__gt=now).exists():
        code = _user_code()
    ConnectRequest.objects.create(device_hash=_hash(device_code), user_code=code, client_name=name,
                                  requested_scopes=wanted, expires_at=now + LIFETIME)
    url = f"{origin}/connecter/?code={code}"
    return {
        "device_code": device_code, "user_code": code, "verification_url": url,
        "expires_in": int(LIFETIME.total_seconds()), "interval": INTERVAL,
        "next": ("Donnez le lien verification_url à la personne (pas le device_code, qui reste secret). Quand elle "
                 "a cliqué « Autoriser », appelez POST /api/v1/connect/token avec {\"device_code\": …} pour recevoir "
                 "le jeton, puis rangez-le dans la variable DEMETRA_TOKEN sans l'afficher."),
    }


def fetch_token(device_code: str) -> tuple[int, dict]:
    """Rend (statut HTTP, corps). 200 avec le jeton une seule fois ; 202 tant que la personne n'a pas répondu."""
    now = timezone.now()
    with transaction.atomic():
        request = ConnectRequest.objects.select_for_update().filter(device_hash=_hash(device_code or "")).first()
        if request is None:
            return 404, {"error": {"code": "unknown_device_code", "message": "Code inconnu. Recommencez avec POST /api/v1/connect."}}
        if request.status == ConnectRequest.Status.CONSUMED:
            return 410, {"error": {"code": "already_used", "message": "Le jeton de cette demande a déjà été remis. Recommencez avec POST /api/v1/connect si vous l'avez perdu."}}
        if request.status == ConnectRequest.Status.DENIED:
            return 403, {"error": {"code": "access_denied", "message": "La personne a refusé l'accès."}}
        if request.expires_at <= now:
            return 410, {"error": {"code": "expired", "message": "Le lien a expiré (10 minutes). Recommencez avec POST /api/v1/connect."}}
        if request.status == ConnectRequest.Status.PENDING:
            too_soon = request.last_poll_at and (now - request.last_poll_at).total_seconds() < INTERVAL - 0.5
            request.last_poll_at = now
            request.save(update_fields=["last_poll_at"])
            if too_soon:
                return 429, {"error": {"code": "slow_down", "message": f"Attendez {INTERVAL} secondes entre deux appels."}}
            return 202, {"status": "pending", "interval": INTERVAL,
                         "message": "La personne n'a pas encore autorisé. Demandez-lui d'ouvrir le lien et de cliquer « Autoriser », puis rappelez."}
        token, secret = svc.create_token(request.user, request.client_name, request.scopes, request.study_ids or None, request.days)
        request.status, request.token = ConnectRequest.Status.CONSUMED, token
        request.save(update_fields=["status", "token"])
    return 200, {"status": "approved", "token": secret, "token_name": token.name, "scopes": token.scopes,
                 "expires_at": token.expires_at.isoformat() if token.expires_at else None,
                 "next": "Rangez ce jeton dans DEMETRA_TOKEN sans l'afficher, puis appelez GET /api/v1/me."}


@login_required
def approve_page(request):
    code = normalize_code(request.POST.get("code") or request.GET.get("code", ""))
    now = timezone.now()
    pending = None
    if code:
        pending = ConnectRequest.objects.filter(user_code=code, status=ConnectRequest.Status.PENDING, expires_at__gt=now).first()
    if request.method == "POST" and pending:
        if request.POST.get("action") == "deny":
            pending.status, pending.user = ConnectRequest.Status.DENIED, request.user
            pending.save(update_fields=["status", "user"])
            messages.success(request, f"Accès refusé à « {pending.client_name} ».")
            return redirect("tokens")
        scopes = [s for s in request.POST.getlist("scopes") if s in svc.SCOPES]
        if not scopes:
            messages.error(request, "Choisissez au moins une permission.")
        else:
            days = {"30": 30, "90": 90, "365": 365, "0": None}.get(request.POST.get("days", "90"), 90)
            pending.status, pending.user, pending.scopes, pending.days = ConnectRequest.Status.APPROVED, request.user, scopes, days
            pending.study_ids = request.POST.getlist("studies")
            pending.save(update_fields=["status", "user", "scopes", "days", "study_ids"])
            return render(request, "core/connect_done.html", {"client": pending.client_name, "nav": "tokens"})
    return render(request, "core/connect.html", {
        "code": code, "pending": pending, "asked": bool(code) and pending is None, "nav": "tokens",
        "scopes": [(k, v, k in (pending.requested_scopes if pending else svc.DEFAULT_SCOPES)) for k, v in svc.SCOPES.items()],
        "my_studies": svc.studies_for(svc.Actor(request.user)),
        "minutes_left": max(1, int((pending.expires_at - now).total_seconds() // 60)) if pending else 0,
    })
