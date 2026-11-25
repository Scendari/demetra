"""Petites briques partagées par toutes les pages : acteur, réponses JSON, navigation d'étude, étapes."""

from __future__ import annotations

import json
from functools import wraps

from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect

from .. import casemodel
from .. import services as svc
from ..models import Role, ShareRequest, Study
from ..render import attribute_info, attribute_value

DECISION_KEYS = {"accepted": "v", "rejected": "r", "to_analyze": "a"}


def actor(request) -> svc.Actor:
    return svc.Actor(request.user)


def wants_json(request) -> bool:
    return request.headers.get("X-Requested-With") == "fetch" or "application/json" in request.headers.get(
        "Accept", ""
    )


def web(view):
    """Traduit une erreur de service en réponse lisible : JSON pour un appel du script, message sinon."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except svc.ServiceError as exc:
            if wants_json(request):
                return JsonResponse(exc.payload(), status=exc.status)
            if exc.status == 404:
                raise Http404(exc.message) from exc
            text = exc.message
            if exc.details:
                text += " " + " ".join(
                    f"{d.get('path', '')} : {d.get('message', '')}".strip(" :") for d in exc.details[:3]
                )
            messages.error(request, text)
            return redirect(request.META.get("HTTP_REFERER") or "studies")

    return wrapper


def body_of(request) -> dict:
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body or b"{}")
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}
    return request.POST.dict()


def study_nav(study: Study, active: str) -> dict:
    pending = (
        study.share_requests.filter(status=ShareRequest.Status.PENDING).count()
        if study.my_role == Role.OWNER
        else 0
    )
    proposals = study.proposals.filter(dismissed_at__isnull=True).count()
    return {
        "study": study,
        "active": active,
        "role_label": Role(study.my_role).label,
        "can_review": svc.ROLE_RANK[study.my_role] >= svc.ROLE_RANK[Role.COMMENTER],
        "can_edit": svc.ROLE_RANK[study.my_role] >= svc.ROLE_RANK[Role.EDITOR],
        "is_owner": study.my_role == Role.OWNER,
        "pending_shares": pending,
        "open_proposals": proposals,
    }


def _steps_context(case: dict, frames: list[dict], statuses: list[dict], smap: dict, step: int) -> dict:
    """Le déroulé d'un cas : la liste des étapes, et pour chacune ce qui change d'état (avant → après)."""
    steps = steps_payload(frames, smap)
    steps_json = json.dumps(steps, ensure_ascii=False)
    names = {
        e["id"]: (f"{e['id']} · {e['label']}" if e.get("label") and e["label"] != e["id"] else e["id"])
        for e in case.get("entities", [])
    }
    fallback = casemodel.default_status(statuses)
    before = {ent: case.get("initial", {}).get(ent, fallback) for ent in names}
    overall = None
    for item, frame in zip(steps, frames, strict=True):
        item["changes"] = []
        for ent in frame["changed"]:
            now = frame["states"][ent]["status"]
            info, old = smap.get(now, {}), smap.get(before.get(ent), {})
            item["changes"].append(
                {
                    "entity": names.get(ent, ent),
                    "before": old.get("label", before.get(ent) or ""),
                    "status": info.get("label", now),
                    "role": info.get("role", "neutral"),
                }
            )
        # Ce que l'auteur du cas désigne au relecteur à cette étape, avec son annotation s'il y en a une.
        item["focus"] = [
            {"entity": names.get(ent, ent), "note": frame.get("annotations", {}).get(ent, "")}
            for ent in frame.get("focus", [])
        ]
        before = {ent: state["status"] for ent, state in frame["states"].items()}
        # L'état d'ensemble du cas est une ligne comme les autres, et seulement quand il change.
        if frame.get("global") and frame["global"] != overall:
            info, old = smap.get(frame["global"], {}), smap.get(overall, {})
            item["changes"].append(
                {
                    "entity": "Ensemble du cas",
                    "overall": True,
                    "before": old.get("label", overall or ""),
                    "status": info.get("label", frame["global"]),
                    "role": info.get("role", "neutral"),
                }
            )
            overall = frame["global"]
    step = min(step, len(steps) - 1) if steps else 0
    return {
        "steps": steps,
        "steps_json": steps_json,
        "current": steps[step] if steps else None,
        "step": step,
        "step_n": step + 1,
        "n_steps": len(steps),
    }


def case_facts(study: Study, content: dict) -> dict[str, tuple[str, str]]:
    """Ce qui distingue un cas d'un autre, pour une comparaison : dimensions, réglages, options des entités,
    résultat."""
    dims = {d["key"]: d for d in study.dimensions}
    facts = {}
    for key, value in (content.get("dimensions") or {}).items():
        dim = dims.get(key)
        label = next((v["label"] for v in dim["values"] if v["value"] == value), value) if dim else value
        facts[f"dim:{key}"] = ((dim or {}).get("label") or key, str(label))
    for key, value in (content.get("config") or {}).items():
        facts[f"cfg:{key}"] = (key, str(_raw(value)))
    for ent in content.get("entities", []):
        for key, value in (ent.get("attrs") or {}).items():
            label, _ = attribute_info(study.attributes, key)
            facts[f"attr:{ent['id']}:{key}"] = (
                f"{label} ({ent['id']})",
                attribute_value(study.attributes, key, value),
            )
    outcome = content.get("outcome") or {}
    if outcome.get("label"):
        facts["outcome"] = ("Résultat attendu", outcome["label"])
    return facts


def legend_of(frames: list[dict], statuses: list[dict]) -> list[dict]:
    used = {state["status"] for frame in frames for state in frame["states"].values()} | {
        f["global"] for f in frames if f.get("global")
    }
    return [
        {
            "key": s["key"],
            "label": s.get("label") or s["key"],
            "role": s.get("role", "neutral"),
            "role_label": casemodel.ROLE_LABELS.get(s.get("role", "neutral"), ""),
        }
        for s in statuses
        if s["key"] in used
    ]


def steps_payload(frames: list[dict], smap: dict) -> list[dict]:
    out = []
    for i, frame in enumerate(frames):
        info = smap.get(frame["global"]) if frame.get("global") else None
        out.append(
            {
                "n": i + 1,
                "title": frame["title"],
                "note": frame["note"],
                "at": frame.get("at"),
                "global": frame["global"] if info else None,
                "global_label": info["label"] if info else "",
                "global_role": info["role"] if info else "",
                "changed": len(frame["changed"]),
            }
        )
    return out


def _raw(value):
    """Une valeur de réglage, telle qu'elle est écrite dans les données (true / false, pas oui / non)."""
    return "true" if value is True else ("false" if value is False else value)


def _step_arg(request) -> int:
    try:
        return max(0, int(request.GET.get("etape", "1")) - 1)
    except ValueError:
        return 0
