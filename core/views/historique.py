"""Journal d'une étude : qui a fait quoi, quand."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .. import services as svc
from ..models import AuditEvent, Decision, Role
from .commun import actor, study_nav, web

ACTION_LABELS = {
    "study.create": "Étude créée",
    "study.update": "Définitions modifiées",
    "study.archive": "Étude archivée",
    "cases.upsert": "Cas déposés",
    "case.retire": "Cas retiré",
    "case.restore": "Cas rétabli",
    "verdict.set": "Avis rendu",
    "share.grant": "Accès accordé",
    "share.change": "Rôle modifié",
    "share.revoke": "Accès retiré",
    "share.request": "Partage demandé",
    "share.confirm": "Demande de partage confirmée",
    "share.reject": "Demande de partage refusée",
    "representation.create": "Représentation créée",
    "representation.update": "Représentation ajustée",
    "representation.propose": "Représentation proposée",
    "representation.choose_default": "Représentation de l'étude choisie",
    "representation.dismiss": "Proposition écartée",
    "representation.archive": "Représentation supprimée",
    "brick.request": "Brique manquante signalée",
    "workshop.save": "Situation de l'atelier enregistrée comme cas",
    "case.request": "Cas demandé à l'IA",
    "case.request.close": "Demande de cas retirée",
    "token.create": "Jeton créé",
    "token.revoke": "Jeton révoqué",
    "admin.transfer": "Propriété transférée",
    "admin.unarchive": "Étude désarchivée",
    "login.sso": "Connexion par le SSO",
}

DECISION_LABELS = {d.value: d.label.lower() for d in Decision}


def _event_rows(events) -> list[dict]:
    rows = []
    for event in events:
        detail = event.detail or {}
        bits = []
        if event.action == "cases.upsert":
            for key, label in (("created", "créés"), ("updated", "modifiés"), ("restored", "rétablis")):
                if detail.get(key):
                    bits.append(f"{detail[key]} {label}")
            if detail.get("verdicts_reset"):
                bits.append(f"{detail['verdicts_reset']} avis repassés à analyser")
        elif event.action == "verdict.set":
            bits.append(DECISION_LABELS.get(detail.get("decision"), ""))
        elif detail.get("role"):
            bits.append(Role(detail["role"]).label.lower())
        elif detail.get("fields"):
            bits.append(", ".join(detail["fields"]))
        if event.action == "admin.transfer":
            bits.append(f"de {detail.get('previous', '?')} à {detail.get('owner', '?')}")
        if event.channel == "admin":
            bits.append("par l'administration du site")
        rows.append(
            {
                "event": event,
                "label": ACTION_LABELS.get(event.action, event.action),
                "bits": " · ".join(b for b in bits if b),
                "kind": event.actor_kind,
                "who": event.actor_user.username if event.actor_user else "—",
                "token": event.actor_token.name if event.actor_token else "",
            }
        )
    return rows


@login_required
@web
def study_history(request, sid: str):
    study = svc.get_study(actor(request), sid)
    who = request.GET.get("acteur")
    events = AuditEvent.objects.filter(study=study).select_related("actor_user", "actor_token")
    if who == "jeton":
        events = events.filter(actor_token__isnull=False)
    elif who == "humain":
        events = events.filter(actor_token__isnull=True)
    total = AuditEvent.objects.filter(study=study)
    return render(
        request,
        "core/history.html",
        {
            **study_nav(study, "history"),
            "rows": _event_rows(events[:200]),
            "who": who or "tous",
            "count_all": total.count(),
            "count_token": total.filter(actor_token__isnull=False).count(),
            "count_human": total.filter(actor_token__isnull=True).count(),
            "nav": "studies",
        },
    )
