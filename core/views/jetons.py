"""Jetons d'accès de l'API, pour connecter une IA."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .. import services as svc
from ..models import ApiToken
from .commun import actor, web


@login_required
@web
def tokens(request):
    if request.method == "POST":
        data = request.POST
        if data.get("action") == "revoke":
            token = svc.revoke_token(request.user, int(data.get("token", 0)))
            messages.success(
                request, f"Jeton « {token.name} » révoqué. Toute requête qui l'utilise est désormais refusée."
            )
            return redirect("tokens")
        days = {"30": 30, "90": 90, "365": 365, "0": None}.get(data.get("days", "90"), 90)
        token, secret = svc.create_token(
            request.user, data.get("name", ""), data.getlist("scopes"), data.getlist("studies"), days
        )
        request.session["new_token"] = {"secret": secret, "name": token.name}
        return redirect("tokens")
    fresh = request.session.pop("new_token", None)
    origin = request.build_absolute_uri("/").rstrip("/")
    rows = []
    for token in ApiToken.objects.filter(user=request.user).prefetch_related("studies"):
        state = "révoqué" if token.revoked_at else ("expiré" if not token.is_active else "actif")
        rows.append(
            {
                "token": token,
                "state": state,
                "scopes": [(s, svc.SCOPES.get(s, s)) for s in token.scopes],
                "studies": list(token.studies.all()),
            }
        )
    return render(
        request,
        "core/tokens.html",
        {
            "rows": rows,
            "fresh": fresh,
            "scopes": [(k, v, k in svc.DEFAULT_SCOPES) for k, v in svc.SCOPES.items()],
            "my_studies": svc.studies_for(actor(request)),
            "origin": origin,
            "nav": "tokens",
        },
    )
