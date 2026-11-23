"""Partage d'une étude : membres, rôles, demandes des IA."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .. import services as svc
from ..models import Role, ShareRequest
from .commun import actor, study_nav, web


@login_required
@web
def study_sharing(request, sid: str):
    me = actor(request)
    if request.method == "POST":
        study = svc.get_study(me, sid, Role.OWNER)
        data = request.POST
        action = data.get("action")
        if action == "invite":
            membership = svc.share(me, study, data.get("user", ""), data.get("role", Role.COMMENTER))
            messages.success(
                request,
                f"« {membership.user.username} » a maintenant accès à l'étude en tant que "
                f"{Role(membership.role).label.lower()}.",
            )
        elif action == "role":
            target = (
                study.memberships.filter(user_id=data.get("member"))
                .exclude(role=Role.OWNER)
                .select_related("user")
                .first()
            )
            if target:
                svc.share(me, study, target.user.username, data.get("role", target.role))
                messages.success(request, f"Rôle de « {target.user.username} » modifié.")
        elif action == "remove":
            svc.unshare(me, study, int(data.get("member", 0)))
            messages.success(request, "Accès retiré.")
        elif action in ("confirm", "reject"):
            req = svc.decide_share_request(me, study, int(data.get("request", 0)), accept=action == "confirm")
            messages.success(
                request,
                f"Demande {'confirmée' if action == 'confirm' else 'refusée'} : « {req.invitee.username} »"
                + (
                    f" a maintenant accès en tant que {Role(req.role).label.lower()}."
                    if action == "confirm"
                    else " n'a pas accès à l'étude."
                ),
            )
        return redirect("study_sharing", sid=sid)
    study = svc.get_study(me, sid)
    members = list(study.memberships.select_related("user").order_by("created_at"))
    for member in members:
        member.role_label = Role(member.role).label
    return render(
        request,
        "core/sharing.html",
        {
            **study_nav(study, "sharing"),
            "members": members,
            "pending": study.share_requests.filter(status=ShareRequest.Status.PENDING).select_related(
                "invitee", "requested_by", "via_token"
            ),
            "decided": study.share_requests.exclude(status=ShareRequest.Status.PENDING).select_related(
                "invitee", "requested_by", "decided_by"
            )[:10],
            "roles": [
                (Role.EDITOR, "Éditeur", "Modifie l'étude et ses cas, rend un avis"),
                (Role.COMMENTER, "Commentateur", "Rend un avis et commente"),
                (Role.VIEWER, "Lecteur", "Lit l'étude et les avis"),
            ],
            "nav": "studies",
        },
    )
