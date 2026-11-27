"""Liste des études, création, et définitions d'une étude (statuts, dimensions, règles…)."""

from __future__ import annotations

import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .. import casemodel
from .. import services as svc
from ..models import Decision, Membership, Role, ShareRequest, Study, Verdict
from .commun import actor, study_nav, web

STARTER_STATUSES = {
    "workflow": [
        {"key": "EN_ATTENTE", "label": "En attente", "role": "waiting", "default": True},
        {"key": "EN_COURS", "label": "En cours", "role": "active"},
        {"key": "REUSSI", "label": "Réussi", "role": "success"},
        {"key": "ECHEC", "label": "En échec", "role": "error"},
        {"key": "BLOQUE", "label": "Bloqué", "role": "blocked"},
        {"key": "DESACTIVE", "label": "Désactivé", "role": "disabled"},
    ],
    "decision": [
        {"key": "A_EVALUER", "label": "À évaluer", "role": "waiting", "default": True},
        {"key": "SATISFAITE", "label": "Satisfaite", "role": "success"},
        {"key": "NON_SATISFAITE", "label": "Non satisfaite", "role": "error"},
        {"key": "SANS_OBJET", "label": "Sans objet", "role": "disabled"},
        {"key": "ACCORDE", "label": "Accordé", "role": "success"},
        {"key": "PARTIEL", "label": "Accordé en partie", "role": "warning"},
        {"key": "REFUSE", "label": "Refusé", "role": "error"},
    ],
    "temporal": [
        {"key": "A_VENIR", "label": "À venir", "role": "waiting", "default": True},
        {"key": "EN_COURS", "label": "En cours", "role": "active"},
        {"key": "ECHU", "label": "Échu", "role": "success"},
        {"key": "DEPASSE", "label": "Dépassé", "role": "error"},
        {"key": "SUSPENDU", "label": "Suspendu", "role": "blocked"},
        {"key": "ANNULE", "label": "Annulé", "role": "disabled"},
    ],
}
STARTER_STATUSES["mixed"] = STARTER_STATUSES["workflow"]


@login_required
@web
def studies(request):
    me = actor(request)
    if request.method == "POST":
        data = request.POST
        kind = data.get("kind") or "mixed"
        study = svc.create_study(
            me,
            {
                "title": data.get("title"),
                "description": data.get("description", ""),
                "kind": kind,
                "statuses": STARTER_STATUSES.get(kind, STARTER_STATUSES["mixed"]),
            },
        )
        messages.success(request, "Étude créée. Elle est privée : vous seul y avez accès.")
        return redirect("study_setup", sid=study.public_id)
    roles = dict(Membership.objects.filter(user=request.user).values_list("study_id", "role"))
    rows = []
    for study in svc.studies_for(me).select_related("owner"):
        total = study.cases.filter(retired_at__isnull=True).count()
        mine = Verdict.objects.filter(case__study=study, case__retired_at__isnull=True, reviewer=request.user)
        accepted, rejected = (
            mine.filter(decision=Decision.ACCEPTED).count(),
            mine.filter(decision=Decision.REJECTED).count(),
        )
        role = roles.get(study.pk)
        rows.append(
            {
                "study": study,
                "role": role,
                "role_label": Role(role).label,
                "shared": role != Role.OWNER,
                "total": total,
                "accepted": accepted,
                "rejected": rejected,
                "todo": total - accepted - rejected,
                "pct_accepted": round(100 * accepted / total, 1) if total else 0,
                "pct_rejected": round(100 * rejected / total, 1) if total else 0,
                "members": study.memberships.count(),
                "pending": study.share_requests.filter(status=ShareRequest.Status.PENDING).count()
                if role == Role.OWNER
                else 0,
            }
        )
    trashed = svc.trash_of(me).count()
    return render(
        request,
        "core/studies.html",
        {"rows": rows, "kinds": Study.Kind.choices, "nav": "studies", "trashed": trashed},
    )


@login_required
@web
def studies_trash(request):
    """La corbeille : les études supprimées par leur propriétaire, restaurables jusqu'à leur effacement."""
    me = actor(request)
    if request.method == "POST":
        sid, action = request.POST.get("study", ""), request.POST.get("action")
        request.session.pop("undo_trash", None)
        if action == "restore":
            study = svc.restore_study(me, sid)
            messages.success(request, f"Étude « {study.title} » restaurée.")
            return redirect("workspace", sid=study.public_id)
        if action == "purge":
            title = svc.purge_study(me, sid)
            messages.success(request, f"Étude « {title} » effacée définitivement.")
        return redirect("studies_trash")
    rows = [{"study": s, "until": svc.purge_date(s), "cases": s.cases.count()} for s in svc.trash_of(me)]
    return render(
        request,
        "core/trash.html",
        {"rows": rows, "days": settings.DEMETRA_TRASH_DAYS, "nav": "studies"},
    )


@login_required
@web
def study_setup(request, sid: str):
    me = actor(request)
    if request.method == "POST":
        data = request.POST
        action = data.get("action")
        if action == "trash":
            study = svc.trash_study(me, svc.get_study(me, sid, Role.OWNER, "studies:write"))
            # Le message porte un bouton « Annuler » : l'étude à restaurer est gardée dans la session.
            request.session["undo_trash"] = study.public_id
            messages.success(
                request,
                f"Étude « {study.title} » mise à la corbeille. Vous pouvez la restaurer pendant "
                f"{settings.DEMETRA_TRASH_DAYS} jours depuis la corbeille.",
                extra_tags="undo-trash",
            )
            return redirect("studies")
        if action == "archive":
            study = svc.get_study(me, sid, Role.OWNER)
            svc.archive_study(me, study)
            messages.success(
                request, f"Étude « {study.title} » archivée. Elle n'apparaît plus dans vos études."
            )
            return redirect("studies")
        study = svc.get_study(me, sid, Role.EDITOR)
        if action == "identity":
            svc.update_study(
                me, study, {"title": data.get("title", ""), "description": data.get("description", "")}
            )
            messages.success(request, "Titre et description enregistrés.")
        elif action == "add_rule":
            key = (data.get("key") or "").strip() or f"R{len(study.rules) + 1}"
            svc.update_study(
                me,
                study,
                {
                    "rules": [
                        *study.rules,
                        {"key": key, "title": data.get("title", ""), "text": data.get("text", "")},
                    ]
                },
            )
            messages.success(request, f"Règle « {key} » ajoutée.")
        elif action == "remove_rule":
            svc.update_study(me, study, {"rules": [r for r in study.rules if r["key"] != data.get("key")]})
            messages.success(request, "Règle retirée.")
        elif action in ("definitions", "import", "check"):
            return _setup_json(request, me, study, action)
        return redirect("study_setup", sid=sid)
    study = svc.get_study(me, sid)
    return render(request, "core/setup.html", _setup_context(study))


def _setup_context(study: Study, **extra) -> dict:
    usage = svc._usage(study)
    rules = [{**rule, "cases": usage["rules"].get(rule["key"], [])} for rule in study.rules]
    statuses = [
        {
            **s,
            "role_label": casemodel.ROLE_LABELS.get(s.get("role", "neutral"), ""),
            "cases": len(usage["statuses"].get(s["key"], [])),
        }
        for s in study.statuses
    ]
    # Les dimensions sont reprises telles quelles (tranches, mise en avant comprises) : les réenregistrer ne
    # les ampute pas.
    definitions = json.dumps(
        {
            "statuses": study.statuses,
            "dimensions": study.dimensions,
            "exclusions": study.exclusions,
            "attributes": study.attributes or [],
        },
        ensure_ascii=False,
        indent=2,
    )
    return {
        **study_nav(study, "setup"),
        "rules": rules,
        "statuses": statuses,
        "definitions_json": definitions,
        "example_case": json.dumps({"cases": [casemodel.EXAMPLE_CASE]}, ensure_ascii=False, indent=2),
        "cases_count": study.cases.filter(retired_at__isnull=True).count(),
        "trash_days": settings.DEMETRA_TRASH_DAYS,
        "nav": "studies",
        **extra,
    }


def _setup_json(request, me: svc.Actor, study: Study, action: str):
    raw = request.POST.get("json", "")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        messages.error(
            request,
            f"Ce texte n'est pas du JSON valide (ligne {exc.lineno}, colonne {exc.colno}) : {exc.msg}.",
        )
        return render(
            request,
            "core/setup.html",
            _setup_context(
                study, **{"posted_" + ("definitions" if action == "definitions" else "cases"): raw}
            ),
            status=422,
        )
    if action == "definitions":
        try:
            svc.update_study(
                me,
                study,
                {
                    k: data[k]
                    for k in ("statuses", "dimensions", "exclusions", "attributes")
                    if isinstance(data, dict) and k in data
                },
            )
        except svc.ServiceError as exc:
            return render(
                request,
                "core/setup.html",
                _setup_context(
                    study,
                    posted_definitions=raw,
                    definition_errors=exc.details,
                    definition_message=exc.message,
                ),
                status=422,
            )
        messages.success(request, "Statuts et dimensions enregistrés.")
        return redirect("study_setup", sid=study.public_id)
    cases = data.get("cases") if isinstance(data, dict) else data
    try:
        result = svc.upsert_cases(me, study, cases, dry_run=action == "check")
    except svc.ServiceError as exc:
        return render(
            request,
            "core/setup.html",
            _setup_context(study, posted_cases=raw, import_message=exc.message, import_errors=exc.details),
            status=422,
        )
    if action == "import" and not result["counts"].get("error"):
        written = sum(v for k, v in result["counts"].items() if k not in ("unchanged", "error"))
        messages.success(
            request, f"{written} cas enregistrés, {result['counts'].get('unchanged', 0)} inchangés."
        )
        return redirect("workspace", sid=study.public_id)
    return render(
        request,
        "core/setup.html",
        _setup_context(study, posted_cases=raw, import_result=result, import_checked=action == "check"),
        status=422 if result["counts"].get("error") else 200,
    )
