"""Choix et ajustement des représentations d'une étude."""

from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe

from .. import bricks
from .. import services as svc
from ..models import Case, Representation, Study
from ..recommend import recommend
from .commun import actor, study_nav, web


def _rep_card(
    study: Study,
    rep: Representation,
    case: Case | None,
    siblings: list[dict],
    current: Representation,
    extra: dict | None = None,
) -> dict:
    spec = svc.resolved_spec(rep)
    card = {
        "rep": rep,
        "bricks": bricks.bricks_used(spec),
        "is_current": rep.pk == current.pk,
        "is_default": study.representation_id == rep.pk,
        "json": json.dumps(spec, ensure_ascii=False, indent=2),
        "tokens": spec.get("tokens") or {},
        "thumb": None,
        "warnings": [],
        "views": len(spec.get("views", [])),
    }
    if case is not None:
        html, summary, _ = svc.render_case(
            study, case, spec, step=min(1, max(0, len(case.content.get("steps", [])) - 1)), siblings=siblings
        )
        card["thumb"] = mark_safe(html)
        card["warnings"] = [w for view in summary["views"] for w in view["warnings"]]
    card.update(extra or {})
    return card


@login_required
@web
def study_representations(request, sid: str):
    me = actor(request)
    study = svc.get_study(me, sid)
    if request.method == "POST":
        return _representation_action(request, me, study)
    current = svc.current_representation(request.user, study)
    cases = study.cases.filter(retired_at__isnull=True)
    case = cases.filter(key=request.GET.get("cas")).first() if request.GET.get("cas") else None
    if case is None:
        case = max(
            cases[:40],
            key=lambda c: len(c.content.get("entities", [])) * 10 + len(c.content.get("steps", [])),
            default=None,
        )
    siblings = svc.siblings_of(study)
    visible = svc.representations_for(me).select_related("owner", "parent")
    by_id = {r.public_id: r for r in visible}
    result = recommend(study, visible.exclude(scope=Representation.Scope.ADJUSTMENT))
    shown = set()

    def card(rep, **extra):
        shown.add(rep.pk)
        return _rep_card(study, rep, case, siblings, current, extra)

    proposals = [
        card(
            p.representation,
            reason=p.reason,
            proposed_by=p.proposed_by.username,
            via_token=bool(p.via_token_id),
            proposal_id=p.pk,
        )
        for p in study.proposals.filter(
            dismissed_at__isnull=True, representation__archived_at__isnull=True
        ).select_related("representation", "proposed_by")
    ]
    recommended = [
        card(by_id[r["id"]], reasons=r["reasons"], reservations=r["reservations"], score=r["score"])
        for r in result["recommended"]
        if by_id[r["id"]].pk not in shown
    ]
    mine = [card(r) for r in visible if r.owner_id == request.user.id and r.pk not in shown]
    others = [
        card(by_id[r["id"]], reasons=r["reasons"], reservations=r["reservations"], score=r["score"])
        for r in result["others"]
        if by_id[r["id"]].pk not in shown
    ]
    rest = [card(r) for r in visible if r.pk not in shown]
    pref = study.preferences.filter(user=request.user, representation__isnull=False).exists()
    choices = svc.representation_choices(request.user, study)
    case_choice = next(
        (rep for chosen, rep in choices["cases"] if case is not None and chosen.pk == case.pk), None
    )
    for group in (proposals, recommended, mine, others, rest):
        for item in group:
            item["is_case_choice"] = case_choice is not None and item["rep"].pk == case_choice.pk
    return render(
        request,
        "core/representations.html",
        {
            **study_nav(study, "representations"),
            "current": current,
            "has_personal_choice": pref,
            "sample_case": case,
            "case_choices_made": choices["cases"],
            "study_by": choices["study_by"],
            "proposals": proposals,
            "recommended": recommended,
            "mine": mine,
            "others": others + rest,
            "shape": result["shape"],
            "token_choices": {
                k: v.get("enum") for k, v in bricks.TOKENS_SCHEMA["properties"].items() if "enum" in v
            },
            "case_choices": cases.only("key", "number", "title")[:200],
            "nav": "studies",
        },
    )


TOKEN_LABELS = {
    "density": "Densité",
    "corners": "Angles",
    "status_label": "Libellé des statuts",
    "status_fill": "Remplissage des statuts",
    "canvas": "Fond",
}


def _representation_action(request, me: svc.Actor, study: Study):
    data = request.POST
    action = data.get("action")
    back = redirect("study_representations", sid=study.public_id)
    if action == "reset":
        svc.choose_representation(me, study, None)
        messages.success(request, "Vous suivez de nouveau la représentation de l'étude.")
        return back
    if action == "reset_case":
        case = svc.get_case(study, data.get("case", ""), include_retired=False)
        svc.choose_representation(me, study, None, case=case)
        messages.success(
            request, f"Le cas {case.display_number} suit de nouveau la représentation de l'étude."
        )
        if data.get("then") == "cases":
            return redirect(f"{reverse('workspace', kwargs={'sid': study.public_id})}?cas={case.key}")
        return back
    if action == "dismiss":
        proposal = study.proposals.filter(pk=data.get("proposal")).first()
        if proposal:
            from django.utils import timezone

            proposal.dismissed_at = timezone.now()
            proposal.save(update_fields=["dismissed_at"])
            svc.audit(me, "representation.dismiss", study, target=proposal.representation.name)
        return back
    rep = svc.get_representation(me, data.get("representation", ""))
    if action == "choose" and data.get("scope") == "case":
        case = svc.get_case(study, data.get("case", ""), include_retired=False)
        svc.choose_representation(me, study, rep, case=case)
        messages.success(
            request,
            f"« {rep.name} » est maintenant la représentation du cas {case.display_number}, pour vous "
            "seulement. Les autres cas ne changent pas.",
        )
        return redirect(f"{reverse('workspace', kwargs={'sid': study.public_id})}?cas={case.key}")
    if action == "choose":
        for_study = data.get("scope") == "study"
        svc.choose_representation(me, study, rep, for_study=for_study)
        if for_study:
            svc.choose_representation(me, study, None)
        messages.success(
            request,
            f"« {rep.name} » est maintenant la représentation "
            + ("de l'étude, pour tous ses membres." if for_study else "que vous voyez sur cette étude."),
        )
        return redirect("workspace", sid=study.public_id) if data.get("then") == "cases" else back
    if action == "duplicate":
        copy = svc.duplicate_representation(me, rep, data.get("name") or None)
        messages.success(
            request,
            f"Thème « {copy.name} » créé à partir de « {rep.name} ». Il vous appartient : vous ou votre IA "
            "pouvez l'ajuster.",
        )
        return back
    if action == "adjust":
        tokens = {k: data[k] for k in TOKEN_LABELS if data.get(k)}
        if rep.owner_id == request.user.id and rep.scope != Representation.Scope.SYSTEM:
            svc.update_representation(
                me, rep, {"overrides": {"tokens": tokens}, "note": "Réglages modifiés dans l'interface"}
            )
            messages.success(request, f"« {rep.name} » ajustée.")
        else:
            adjusted = svc.create_representation(
                me, {"mode": "adjustment", "parent": rep.public_id, "overrides": {"tokens": tokens}}
            )
            svc.choose_representation(me, study, adjusted)
            messages.success(
                request,
                f"Ajustement personnel créé à partir de « {rep.name} » et appliqué pour vous. Les autres "
                "membres ne voient pas de changement.",
            )
        return back
    if action == "archive":
        svc.archive_representation(me, rep)
        messages.success(request, f"« {rep.name} » supprimée.")
        return back
    raise svc.ServiceError(422, "invalid", "Action inconnue.")
