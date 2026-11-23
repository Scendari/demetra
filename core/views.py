"""Pages web de Demetra (session + CSRF). Toute décision d'accès passe par core/services.py."""

from __future__ import annotations

import json
import time
from functools import wraps

import markdown as md
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET, require_POST

from . import bricks, casemodel, guide, samples
from . import coverage as cov
from . import services as svc
from .models import (
    ApiToken,
    AuditEvent,
    BrickRequest,
    Case,
    Decision,
    Membership,
    Representation,
    Role,
    ShareRequest,
    Study,
    Verdict,
)
from .recommend import recommend
from .render import attribute_info, attribute_value, flag_classes, icon_sprite, status_map
from .render import render as render_rep

DECISION_KEYS = {"accepted": "v", "rejected": "r", "to_analyze": "a"}


def actor(request) -> svc.Actor:
    return svc.Actor(request.user)


def wants_json(request) -> bool:
    return request.headers.get("X-Requested-With") == "fetch" or "application/json" in request.headers.get("Accept", "")


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
                text += " " + " ".join(f"{d.get('path', '')} : {d.get('message', '')}".strip(" :") for d in exc.details[:3])
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
    pending = study.share_requests.filter(status=ShareRequest.Status.PENDING).count() if study.my_role == Role.OWNER else 0
    proposals = study.proposals.filter(dismissed_at__isnull=True).count()
    return {
        "study": study, "active": active, "role_label": Role(study.my_role).label,
        "can_review": svc.ROLE_RANK[study.my_role] >= svc.ROLE_RANK[Role.COMMENTER],
        "can_edit": svc.ROLE_RANK[study.my_role] >= svc.ROLE_RANK[Role.EDITOR],
        "is_owner": study.my_role == Role.OWNER,
        "pending_shares": pending, "open_proposals": proposals,
    }


# ---------------------------------------------------------------------------
# Pages publiques
# ---------------------------------------------------------------------------

SAMPLE_STATUSES = [
    {"key": "WAITING", "label": "En attente", "role": "waiting", "default": True},
    {"key": "RUNNING", "label": "En cours", "role": "active"},
    {"key": "FINISHED_OK", "label": "Réussi", "role": "success"},
    {"key": "FINISHED_KO", "label": "En échec", "role": "error"},
    {"key": "BLOCKED", "label": "Bloqué", "role": "blocked"},
]
SAMPLE_CASE = {
    "key": "exemple", "number": 1, "family": "Exemple", "title": "Un échec bloque la suite", "summary": "", "kind": "workflow",
    "rules": [], "dimensions": {}, "tags": [], "config": {},
    "entities": [
        {"id": "A", "label": "extraction", "type": "tâche", "group": "", "attrs": {}},
        {"id": "B", "label": "contrôle", "type": "tâche", "group": "", "attrs": {}},
        {"id": "C", "label": "chargement", "type": "tâche", "group": "", "attrs": {}},
        {"id": "D", "label": "notification", "type": "tâche", "group": "", "attrs": {}},
    ],
    "links": [{"from": "A", "to": "B", "type": "prerequisite", "label": ""}, {"from": "A", "to": "C", "type": "prerequisite", "label": ""},
              {"from": "B", "to": "D", "type": "prerequisite", "label": ""}, {"from": "C", "to": "D", "type": "prerequisite", "label": ""}],
    "initial": {},
    "steps": [
        {"title": "L'extraction démarre", "note": "Les trois autres tâches attendent.", "changes": {"A": {"status": "RUNNING"}}, "annotations": {}},
        {"title": "Contrôle et chargement démarrent ensemble", "note": "L'extraction a réussi : ses deux suites partent en parallèle.",
         "changes": {"A": {"status": "FINISHED_OK"}, "B": {"status": "RUNNING"}, "C": {"status": "RUNNING"}}, "annotations": {}},
        {"title": "Le contrôle échoue", "note": "Le chargement continue ; la notification ne pourra plus partir.",
         "changes": {"B": {"status": "FINISHED_KO"}, "D": {"status": "BLOCKED"}}, "annotations": {"D": "prérequis en échec"}},
        {"title": "Fin : la notification reste bloquée", "note": "Le chargement se termine bien, mais le cas se conclut sur un blocage.",
         "changes": {"C": {"status": "FINISHED_OK"}}, "annotations": {}},
    ],
    "outcome": {"label": "Notification bloquée", "status": "BLOCKED"}, "references": [], "caution": "", "proof": "asserted",
}


def _steps_context(case: dict, frames: list[dict], statuses: list[dict], smap: dict, step: int) -> dict:
    """Le déroulé d'un cas : la liste des étapes, et pour chacune ce qui change d'état (avant → après)."""
    steps = steps_payload(frames, smap)
    steps_json = json.dumps(steps, ensure_ascii=False)
    names = {e["id"]: (f'{e["id"]} · {e["label"]}' if e.get("label") and e["label"] != e["id"] else e["id"]) for e in case.get("entities", [])}
    fallback = casemodel.default_status(statuses)
    before = {ent: case.get("initial", {}).get(ent, fallback) for ent in names}
    overall = None
    for item, frame in zip(steps, frames, strict=True):
        item["changes"] = []
        for ent in frame["changed"]:
            now = frame["states"][ent]["status"]
            info, old = smap.get(now, {}), smap.get(before.get(ent), {})
            item["changes"].append({"entity": names.get(ent, ent), "before": old.get("label", before.get(ent) or ""),
                                    "status": info.get("label", now), "role": info.get("role", "neutral")})
        # Ce que l'auteur du cas désigne au relecteur à cette étape, avec son annotation s'il y en a une.
        item["focus"] = [{"entity": names.get(ent, ent), "note": frame.get("annotations", {}).get(ent, "")} for ent in frame.get("focus", [])]
        before = {ent: state["status"] for ent, state in frame["states"].items()}
        # L'état d'ensemble du cas est une ligne comme les autres, et seulement quand il change.
        if frame.get("global") and frame["global"] != overall:
            info, old = smap.get(frame["global"], {}), smap.get(overall, {})
            item["changes"].append({"entity": "Ensemble du cas", "overall": True, "before": old.get("label", overall or ""),
                                    "status": info.get("label", frame["global"]), "role": info.get("role", "neutral")})
            overall = frame["global"]
    step = min(step, len(steps) - 1) if steps else 0
    return {"steps": steps, "steps_json": steps_json, "current": steps[step] if steps else None, "step": step, "step_n": step + 1, "n_steps": len(steps)}


def sample_render(slug: str = "graphe-couches", step: int = 2, own: dict | None = None) -> dict:
    spec = next(r["spec"] for r in bricks.SYSTEM_REPRESENTATIONS if r["slug"] == slug)
    own = own or samples.extended_sample(slug)
    if own is not None:   # les représentations du catalogue élargi se montrent sur un cas qui porte leurs données
        case, statuses = own["case"], own["statuses"]
        frames = casemodel.replay(case, statuses)
        step = min(own["step"], len(frames) - 1)
        html, summary = render_rep(spec, case, frames, statuses, step=step, siblings=own["siblings"], dimensions=own["dimensions"],
                                   ruleset=own["ruleset"], lifecycles=own["lifecycles"])
        return {"html": mark_safe(html), "summary": summary, "legend": legend_of(frames, statuses), "study": own["title"], "case_title": case["title"],
                **_steps_context(case, frames, statuses, status_map(statuses), step)}
    frames = casemodel.replay(SAMPLE_CASE, SAMPLE_STATUSES)
    html, summary = render_rep(spec, SAMPLE_CASE, frames, SAMPLE_STATUSES, step=step)
    return {"html": mark_safe(html), "summary": summary, "legend": legend_of(frames, SAMPLE_STATUSES),
            **_steps_context(SAMPLE_CASE, frames, SAMPLE_STATUSES, status_map(SAMPLE_STATUSES), step)}


def home(request):
    if request.user.is_authenticated:
        return redirect("studies")
    return render(request, "core/home.html", {"sample": sample_render("diagramme-etats", own=samples.home_sample())})


def guide_page(request, topic: str = "index"):
    if topic not in guide.TOPICS:
        raise Http404
    html = md.markdown(guide.markdown(topic), extensions=["tables", "fenced_code", "toc"])
    return render(request, "core/guide.html", {
        "nav": "guide", "topic": topic, "topics": guide.topics("/guide/"), "content": mark_safe(html), "title": guide.TOPICS[topic],
        "version": settings.DEMETRA_GUIDE_VERSION, "origin": request.build_absolute_uri("/").rstrip("/"),
    })


def llms_txt(request):
    return HttpResponse(guide.llms_txt(request.build_absolute_uri("/").rstrip("/")), content_type="text/plain; charset=utf-8")


def bricks_page(request):
    catalog = bricks.catalog_payload()
    for family in catalog["families"]:
        for brick in family["bricks"]:
            brick["param_rows"] = [
                {"name": name, "type": _param_type(schema), "default": schema.get("default"), "has_default": "default" in schema,
                 "description": schema.get("description", "")}
                for name, schema in brick["params"].items() if name != "brick"
            ]
            brick["example_json"] = json.dumps(brick["example"], ensure_ascii=False)
    shown, extended = [], []
    for item in bricks.SYSTEM_REPRESENTATIONS:
        if item["slug"] in ("graphe-couches", "table-trace", "graphe-et-trace", "vignettes") or item["slug"] in samples.SHOWN:
            target = extended if item["slug"] in samples.SHOWN else shown
            target.append({"name": item["name"], "slug": item["slug"], "description": item["description"], "bricks": bricks.bricks_used(item["spec"]),
                           "render": sample_render(item["slug"], 2), "json": json.dumps(item["spec"], ensure_ascii=False, indent=2)})
    requests_open = BrickRequest.objects.select_related("user")[:20] if request.user.is_authenticated else []
    return render(request, "core/bricks.html", {"nav": "bricks", "catalog": catalog, "samples": shown, "extended": extended, "brick_requests": requests_open})


def _param_type(schema: dict) -> str:
    if "enum" in schema:
        return " | ".join(str(v) for v in schema["enum"])
    kind = schema.get("type")
    if isinstance(kind, list):
        kind = " ou ".join(kind)
    names = {"string": "texte", "integer": "entier", "number": "nombre", "boolean": "oui/non", "array": "liste", "object": "objet"}
    text = names.get(kind, kind or "valeur")
    if "minimum" in schema and "maximum" in schema:
        text += f" ({schema['minimum']}–{schema['maximum']})"
    return text


# ---------------------------------------------------------------------------
# Études
# ---------------------------------------------------------------------------

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
        study = svc.create_study(me, {"title": data.get("title"), "description": data.get("description", ""), "kind": kind,
                                      "statuses": STARTER_STATUSES.get(kind, STARTER_STATUSES["mixed"])})
        messages.success(request, "Étude créée. Elle est privée : vous seul y avez accès.")
        return redirect("study_setup", sid=study.public_id)
    roles = dict(Membership.objects.filter(user=request.user).values_list("study_id", "role"))
    rows = []
    for study in svc.studies_for(me).select_related("owner"):
        total = study.cases.filter(retired_at__isnull=True).count()
        mine = Verdict.objects.filter(case__study=study, case__retired_at__isnull=True, reviewer=request.user)
        accepted, rejected = mine.filter(decision=Decision.ACCEPTED).count(), mine.filter(decision=Decision.REJECTED).count()
        role = roles.get(study.pk)
        rows.append({
            "study": study, "role": role, "role_label": Role(role).label, "shared": role != Role.OWNER, "total": total,
            "accepted": accepted, "rejected": rejected, "todo": total - accepted - rejected,
            "pct_accepted": round(100 * accepted / total, 1) if total else 0, "pct_rejected": round(100 * rejected / total, 1) if total else 0,
            "members": study.memberships.count(),
            "pending": study.share_requests.filter(status=ShareRequest.Status.PENDING).count() if role == Role.OWNER else 0,
        })
    return render(request, "core/studies.html", {"rows": rows, "kinds": Study.Kind.choices, "nav": "studies"})


def legend_of(frames: list[dict], statuses: list[dict]) -> list[dict]:
    used = {state["status"] for frame in frames for state in frame["states"].values()} | {f["global"] for f in frames if f.get("global")}
    return [{"key": s["key"], "label": s.get("label") or s["key"], "role": s.get("role", "neutral"),
             "role_label": casemodel.ROLE_LABELS.get(s.get("role", "neutral"), "")} for s in statuses if s["key"] in used]


def steps_payload(frames: list[dict], smap: dict) -> list[dict]:
    out = []
    for i, frame in enumerate(frames):
        info = smap.get(frame["global"]) if frame.get("global") else None
        out.append({"n": i + 1, "title": frame["title"], "note": frame["note"], "at": frame.get("at"),
                    "global": frame["global"] if info else None, "global_label": info["label"] if info else "",
                    "global_role": info["role"] if info else "", "changed": len(frame["changed"])})
    return out


def _list_rows(study: Study, user) -> tuple[list[dict], dict]:
    mine = {v.case_id: v for v in Verdict.objects.filter(case__study=study, reviewer=user)}
    others: dict[int, dict] = {}
    for case_id, decision in Verdict.objects.filter(case__study=study).exclude(reviewer=user).values_list("case_id", "decision"):
        others.setdefault(case_id, {"accepted": 0, "rejected": 0, "to_analyze": 0})[decision] += 1
    rows, counts = [], {"accepted": 0, "rejected": 0, "to_analyze": 0, "stale": 0, "retired": 0}
    for case in study.cases.all():
        verdict = mine.get(case.pk)
        decision = verdict.decision if verdict else Decision.TO_ANALYZE
        stale = bool(verdict and verdict.stale_from)
        retired = bool(case.retired_at)
        if retired:
            counts["retired"] += 1
        else:
            counts[decision] += 1
            counts["stale"] += stale
        content = case.content
        other = others.get(case.pk, {})
        rows.append({
            "key": case.key, "number": case.display_number, "n": case.number, "title": case.title, "family": case.family,
            "decision": decision, "decision_label": Decision(decision).label, "stale": stale, "retired": retired,
            "has_comment": bool(verdict and verdict.comment.strip()),
            "others_accepted": other.get("accepted", 0), "others_rejected": other.get("rejected", 0),
            "search": " ".join([case.display_number, case.key, case.title, case.summary, case.family, *content.get("tags", [])]).lower(),
            "steps": len(content.get("steps", [])), "changed_at": int(case.content_changed_at.timestamp()),
            "hash": case.content_hash[:10], "rev": case.revision_no,
        })
    # Les familles restent groupées, dans l'ordre de leur premier cas.
    first: dict[str, int] = {}
    for row in rows:
        first.setdefault(row["family"], row["n"])
    rows.sort(key=lambda row: (first[row["family"]], row["n"]))
    for position, row in enumerate(rows):
        row["pos"] = position
    counts["total"] = counts["accepted"] + counts["rejected"] + counts["to_analyze"]
    counts["done"] = counts["accepted"] + counts["rejected"]
    total = counts["total"] or 1
    counts["pct_accepted"] = round(100 * counts["accepted"] / total, 2)
    counts["pct_rejected"] = round(100 * counts["rejected"] / total, 2)
    return rows, counts


def _raw(value):
    """Une valeur de réglage, telle qu'elle est écrite dans les données (true / false, pas oui / non)."""
    return "true" if value is True else ("false" if value is False else value)


def _case_facts(study: Study, content: dict) -> dict[str, tuple[str, str]]:
    """Ce qui distingue un cas d'un autre, pour la comparaison : dimensions, réglages, options des entités, résultat."""
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
            facts[f"attr:{ent['id']}:{key}"] = (f"{label} ({ent['id']})", attribute_value(study.attributes, key, value))
    outcome = content.get("outcome") or {}
    if outcome.get("label"):
        facts["outcome"] = ("Résultat attendu", outcome["label"])
    return facts


def _compare_rows(study: Study, case: Case) -> list[dict]:
    """Les cas que l'auteur propose de comparer à celui-ci (« compare_with »), avec ce qui diffère."""
    keys = case.content.get("compare_with") or []
    if not keys:
        return []
    others = {c.key: c for c in study.cases.filter(key__in=keys, retired_at__isnull=True)}
    mine = _case_facts(study, case.content)
    rows = []
    for key in keys:
        other = others.get(key)
        if other is None:
            rows.append({"key": key, "missing": True})
            continue
        theirs = _case_facts(study, other.content)
        diffs, seen = [], set()
        for k in dict.fromkeys([*mine, *theirs]):
            here, there = (mine.get(k) or ("", "—"))[1], (theirs.get(k) or ("", "—"))[1]
            # Une même différence peut se lire à deux endroits (la dimension, et l'entité-condition qui la recopie) : une ligne suffit.
            if here != there and (here, there) not in seen:
                seen.add((here, there))
                diffs.append({"label": (mine.get(k) or theirs.get(k))[0], "here": here, "there": there})
        rows.append({"key": key, "number": other.display_number, "title": other.title, "diffs": diffs[:8], "more": max(0, len(diffs) - 8)})
    return rows


def _panel_context(request, study: Study, case: Case, step: int = 0) -> dict:
    content = case.content
    rep = svc.current_representation(request.user, study, case)
    rep_for_case = case.preferences.filter(user=request.user, representation=rep).exists()
    html, summary, frames = svc.render_case(study, case, svc.resolved_spec(rep), step=step)
    step = max(0, min(step, len(frames) - 1))
    smap = status_map(study.statuses)
    verdict = Verdict.objects.filter(case=case, reviewer=request.user).first()
    others = Verdict.objects.filter(case=case).exclude(reviewer=request.user).select_related("reviewer").order_by("reviewer__username")
    rules = {r["key"]: r for r in study.rules}
    dims = {d["key"]: d for d in study.dimensions}
    # Les caractéristiques que l'auteur du cas a mises en avant restent visibles ; les autres se déplient à la demande.
    # Deux sources : une dimension marquée pour toute l'étude, puis ce que le cas ajoute pour lui-même.
    case_high = content.get("highlights") or []
    highlights = list(dict.fromkeys([d["key"] for d in study.dimensions if d.get("highlight")] + [h for h in case_high if isinstance(h, str)]))
    entities = {e["id"]: e for e in content.get("entities", [])}
    facts = {}
    for key, value in (case.dimensions or {}).items():
        dim = dims.get(key)
        label = next((v["label"] for v in dim["values"] if v["value"] == value), value) if dim else value
        facts[key] = {"label": (dim or {}).get("label") or key, "value": label}
    dimension_rows = [row for key, row in facts.items() if key not in highlights]
    config = {k: {"label": k, "key": k, "value": _raw(v)} for k, v in (content.get("config") or {}).items()}
    highlight_rows = [facts.get(key) or config[key] for key in highlights if key in facts or key in config]
    # Une option portée par une entité (par exemple always_run sur la tâche C) : nommée avec son entité.
    for h in case_high:
        if not isinstance(h, dict):
            continue
        if "link" in h:   # la règle tient à ce lien
            link = next((l for l in content.get("links", []) if [l["from"], l["to"]] == h["link"]), None)
            if link:
                highlight_rows.append({"label": f"Lien {link['from']} → {link['to']}", "value": link.get("label") or link["type"],
                                       "cls": flag_classes(h.get("style"))})
            continue
        ent = entities.get(h.get("entity"))
        if ent and h["attr"] in (ent.get("attrs") or {}):
            value = ent["attrs"][h["attr"]]
            name = " · ".join(x for x in (ent["id"], ent.get("label")) if x)
            label, definition = attribute_info(study.attributes, h["attr"])
            highlight_rows.append({"label": f"{label} ({name})", "value": attribute_value(study.attributes, h["attr"], value), "cls": flag_classes(h.get("style")), "title": definition})
    has_human = Verdict.objects.filter(case=case, decision=Decision.ACCEPTED, content_hash=case.content_hash).exists()
    proof = "validé" if has_human else ("observé" if content.get("proof") == "observed" else "structure vérifiée")
    proof_help = {
        "validé": "Un relecteur a validé ce déroulé.",
        "observé": "Son auteur déclare l'avoir constaté sur le système réel (voir les références).",
        "structure vérifiée": "Le site a vérifié la structure et rejoué les étapes ; rien ne prouve encore que le système se comporte ainsi.",
    }[proof]
    outcome = content.get("outcome") or {}
    outcome_info = smap.get(outcome.get("status")) if outcome.get("status") else None
    return {
        "study": study, "case": case, "content": content, "rep": rep, "rep_for_case": rep_for_case, "rep_html": mark_safe(html), "summary": summary,
        "frames": frames, **_steps_context(content, frames, study.statuses, smap, step), "legend": legend_of(frames, study.statuses),
        "verdict": verdict, "decision": verdict.decision if verdict else Decision.TO_ANALYZE,
        "stale_label": Decision(verdict.stale_from).label.lower() if verdict and verdict.stale_from else "",
        "others": others, "rules": [rules[k] for k in content.get("rules", []) if k in rules],
        "proof": proof, "proof_help": proof_help, "outcome": outcome, "outcome_role": outcome_info["role"] if outcome_info else "",
        "revisions": case.revisions.select_related("actor_user")[:12],
        "can_review": svc.ROLE_RANK[study.my_role] >= svc.ROLE_RANK[Role.COMMENTER] and not case.retired_at,
        "comment": verdict.comment if verdict else "",
        "highlight_rows": highlight_rows,
        "compare": _compare_rows(study, case),
        "other_rows": dimension_rows + [row for key, row in config.items() if key not in highlights or key in facts],
    }


def _step_arg(request) -> int:
    try:
        return max(0, int(request.GET.get("etape", "1")) - 1)
    except ValueError:
        return 0


@login_required
@web
def workspace(request, sid: str):
    study = svc.get_study(actor(request), sid)
    rows, counts = _list_rows(study, request.user)
    families = []
    for row in rows:
        if row["family"] not in families:
            families.append(row["family"])
    wanted = request.GET.get("cas")
    selected = None
    if wanted:
        selected = study.cases.filter(key=wanted).first()
    if selected is None:
        first = next((r for r in rows if not r["retired"] and r["decision"] == Decision.TO_ANALYZE), None) or next((r for r in rows if not r["retired"]), None)
        selected = study.cases.get(key=first["key"]) if first else None
    context = {**study_nav(study, "cases"), "rows": rows, "counts": counts, "families": families, "selected": selected,
               "state": svc.study_state(study), "nav": "studies"}
    if selected:
        context["panel"] = _panel_context(request, study, selected, _step_arg(request))
    return render(request, "core/workspace.html", context)


@login_required
@web
def case_panel(request, sid: str, key: str):
    study = svc.get_study(actor(request), sid)
    case = svc.get_case(study, key)
    return render(request, "core/_panel.html", {"panel": _panel_context(request, study, case, _step_arg(request)), **study_nav(study, "cases")})


@login_required
@require_POST
@web
def case_verdict(request, sid: str, key: str):
    study = svc.get_study(actor(request), sid, Role.COMMENTER)
    data = body_of(request)
    current = Verdict.objects.filter(case__study=study, case__key=key, reviewer=request.user).first()
    decision = data.get("decision") or (current.decision if current else Decision.TO_ANALYZE)
    verdict = svc.set_verdict(actor(request), study, key, decision, data.get("comment"))
    _, counts = _list_rows(study, request.user)
    payload = {"decision": verdict.decision, "label": Decision(verdict.decision).label, "comment": verdict.comment, "counts": counts}
    if wants_json(request):
        return JsonResponse(payload)
    return redirect(f"/etudes/{sid}/?cas={key}")


@login_required
@require_GET
@web
def study_state(request, sid: str):
    study = svc.get_study(actor(request), sid)
    return JsonResponse(svc.study_state(study))


@login_required
@web
def study_events(request, sid: str):
    """Flux d'événements (SSE) : signale tout changement de l'étude, qu'il vienne de l'interface ou de l'API."""
    study = svc.get_study(actor(request), sid)
    pk, last = study.pk, study.revision
    deadline = time.monotonic() + settings.DEMETRA_SSE_MAX_SECONDS

    def stream():
        nonlocal last
        yield "retry: 1500\n\n"
        yield f"event: hello\ndata: {last}\n\n"
        beat = 0
        while time.monotonic() < deadline:
            time.sleep(1)
            revision = Study.objects.filter(pk=pk).values_list("revision", flat=True).first()
            if revision is None:
                return
            if revision != last:
                last = revision
                yield f"event: revision\ndata: {revision}\n\n"
            beat += 1
            if beat % 15 == 0:
                yield ": ping\n\n"

    response = StreamingHttpResponse(stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


# ---------------------------------------------------------------------------
# Couverture
# ---------------------------------------------------------------------------

@login_required
@web
def study_coverage(request, sid: str):
    study = svc.get_study(actor(request), sid)
    try:
        strength = max(1, min(3, int(request.GET.get("force", "2"))))
    except ValueError:
        strength = 2
    report = svc.coverage_report(study, strength)
    labels = {d["key"]: {"label": d.get("label") or d["key"], "values": {v["value"]: v["label"] for v in d["values"]}} for d in study.dimensions}
    missing = [[{"dim": labels[k]["label"], "value": labels[k]["values"].get(v, v)} for k, v in combo.items()] for combo in report["missing"][:60]]
    keys = [d["key"] for d in study.dimensions]
    row_key = request.GET.get("lignes") if request.GET.get("lignes") in keys else (keys[0] if keys else None)
    col_key = request.GET.get("colonnes") if request.GET.get("colonnes") in keys else next((k for k in keys if k != row_key), None)
    table = cov.matrix(study.dimensions, study.exclusions, svc._case_rows(study), row_key, col_key) if row_key and col_key else None
    if table:
        for row in table["rows"]:
            row["label"] = labels[row_key]["values"].get(row["value"], row["value"])
        table["col"]["labels"] = [labels[col_key]["values"].get(v, v) for v in table["col"]["values"]]
    for dim in report["by_dimension"]:
        info = labels.get(dim["key"], {"label": dim["key"], "values": {}})
        dim["label"] = info["label"]
        for value in dim["values"]:
            value["label"] = info["values"].get(value["value"], value["value"])
    pct = round(report["ratio"] * 100) if report["ratio"] is not None else None
    exclusions = [{"when": [{"dim": labels[k]["label"], "value": labels[k]["values"].get(v, v)} for k, v in e["when"].items() if k in labels],
                   "reason": e.get("reason", "")} for e in study.exclusions]
    return render(request, "core/coverage.html", {
        **study_nav(study, "coverage"), "report": report, "missing": missing, "pct": pct, "strength": strength, "table": table,
        "row_key": row_key, "col_key": col_key, "dimension_choices": [(k, labels[k]["label"]) for k in keys],
        "checks": svc.checks_report(study), "exclusions": exclusions, "nav": "studies",
        "strength_labels": [(1, "Chaque valeur"), (2, "Chaque paire"), (3, "Chaque triplet")],
    })


# ---------------------------------------------------------------------------
# Représentations
# ---------------------------------------------------------------------------

def _rep_card(study: Study, rep: Representation, case: Case | None, siblings: list[dict], current: Representation, extra: dict | None = None) -> dict:
    spec = svc.resolved_spec(rep)
    card = {"rep": rep, "bricks": bricks.bricks_used(spec), "is_current": rep.pk == current.pk, "is_default": study.representation_id == rep.pk,
            "json": json.dumps(spec, ensure_ascii=False, indent=2), "tokens": spec.get("tokens") or {}, "thumb": None, "warnings": [],
            "views": len(spec.get("views", []))}
    if case is not None:
        html, summary, _ = svc.render_case(study, case, spec, step=min(1, max(0, len(case.content.get("steps", [])) - 1)), siblings=siblings)
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
        case = max(cases[:40], key=lambda c: len(c.content.get("entities", [])) * 10 + len(c.content.get("steps", [])), default=None)
    siblings = svc.siblings_of(study)
    visible = svc.representations_for(me).select_related("owner", "parent")
    by_id = {r.public_id: r for r in visible}
    result = recommend(study, visible.exclude(scope=Representation.Scope.ADJUSTMENT))
    shown = set()

    def card(rep, **extra):
        shown.add(rep.pk)
        return _rep_card(study, rep, case, siblings, current, extra)

    proposals = [card(p.representation, reason=p.reason, proposed_by=p.proposed_by.username, via_token=bool(p.via_token_id), proposal_id=p.pk)
                 for p in study.proposals.filter(dismissed_at__isnull=True, representation__archived_at__isnull=True).select_related("representation", "proposed_by")]
    recommended = [card(by_id[r["id"]], reasons=r["reasons"], reservations=r["reservations"], score=r["score"]) for r in result["recommended"] if by_id[r["id"]].pk not in shown]
    mine = [card(r) for r in visible if r.owner_id == request.user.id and r.pk not in shown]
    others = [card(by_id[r["id"]], reasons=r["reasons"], reservations=r["reservations"], score=r["score"]) for r in result["others"] if by_id[r["id"]].pk not in shown]
    rest = [card(r) for r in visible if r.pk not in shown]
    pref = study.preferences.filter(user=request.user, representation__isnull=False).exists()
    choices = svc.representation_choices(request.user, study)
    case_choice = next((rep for chosen, rep in choices["cases"] if case is not None and chosen.pk == case.pk), None)
    for group in (proposals, recommended, mine, others, rest):
        for item in group:
            item["is_case_choice"] = case_choice is not None and item["rep"].pk == case_choice.pk
    return render(request, "core/representations.html", {
        **study_nav(study, "representations"), "current": current, "has_personal_choice": pref, "sample_case": case,
        "case_choices_made": choices["cases"], "study_by": choices["study_by"],
        "proposals": proposals, "recommended": recommended, "mine": mine, "others": others + rest, "shape": result["shape"],
        "token_choices": {k: v.get("enum") for k, v in bricks.TOKENS_SCHEMA["properties"].items() if "enum" in v},
        "case_choices": cases.only("key", "number", "title")[:200], "nav": "studies",
    })


TOKEN_LABELS = {"density": "Densité", "corners": "Angles", "status_label": "Libellé des statuts", "status_fill": "Remplissage des statuts", "canvas": "Fond"}


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
        messages.success(request, f"Le cas {case.display_number} suit de nouveau la représentation de l'étude.")
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
        messages.success(request, f"« {rep.name} » est maintenant la représentation du cas {case.display_number}, pour vous seulement. Les autres cas ne changent pas.")
        return redirect(f"{reverse('workspace', kwargs={'sid': study.public_id})}?cas={case.key}")
    if action == "choose":
        for_study = data.get("scope") == "study"
        svc.choose_representation(me, study, rep, for_study=for_study)
        if for_study:
            svc.choose_representation(me, study, None)
        messages.success(request, f"« {rep.name} » est maintenant la représentation " + ("de l'étude, pour tous ses membres." if for_study else "que vous voyez sur cette étude."))
        return redirect("workspace", sid=study.public_id) if data.get("then") == "cases" else back
    if action == "duplicate":
        copy = svc.duplicate_representation(me, rep, data.get("name") or None)
        messages.success(request, f"Thème « {copy.name} » créé à partir de « {rep.name} ». Il vous appartient : vous ou votre IA pouvez l'ajuster.")
        return back
    if action == "adjust":
        tokens = {k: data[k] for k in TOKEN_LABELS if data.get(k)}
        if rep.owner_id == request.user.id and rep.scope != Representation.Scope.SYSTEM:
            svc.update_representation(me, rep, {"overrides": {"tokens": tokens}, "note": "Réglages modifiés dans l'interface"})
            messages.success(request, f"« {rep.name} » ajustée.")
        else:
            adjusted = svc.create_representation(me, {"mode": "adjustment", "parent": rep.public_id, "overrides": {"tokens": tokens}})
            svc.choose_representation(me, study, adjusted)
            messages.success(request, f"Ajustement personnel créé à partir de « {rep.name} » et appliqué pour vous. Les autres membres ne voient pas de changement.")
        return back
    if action == "archive":
        svc.archive_representation(me, rep)
        messages.success(request, f"« {rep.name} » supprimée.")
        return back
    raise svc.ServiceError(422, "invalid", "Action inconnue.")


# ---------------------------------------------------------------------------
# Partage, historique, définitions
# ---------------------------------------------------------------------------

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
            messages.success(request, f"« {membership.user.username} » a maintenant accès à l'étude en tant que {Role(membership.role).label.lower()}.")
        elif action == "role":
            target = study.memberships.filter(user_id=data.get("member")).exclude(role=Role.OWNER).select_related("user").first()
            if target:
                svc.share(me, study, target.user.username, data.get("role", target.role))
                messages.success(request, f"Rôle de « {target.user.username} » modifié.")
        elif action == "remove":
            svc.unshare(me, study, int(data.get("member", 0)))
            messages.success(request, "Accès retiré.")
        elif action in ("confirm", "reject"):
            req = svc.decide_share_request(me, study, int(data.get("request", 0)), accept=action == "confirm")
            messages.success(request, f"Demande {'confirmée' if action == 'confirm' else 'refusée'} : « {req.invitee.username} »"
                             + (f" a maintenant accès en tant que {Role(req.role).label.lower()}." if action == "confirm" else " n'a pas accès à l'étude."))
        return redirect("study_sharing", sid=sid)
    study = svc.get_study(me, sid)
    members = list(study.memberships.select_related("user").order_by("created_at"))
    for member in members:
        member.role_label = Role(member.role).label
    return render(request, "core/sharing.html", {
        **study_nav(study, "sharing"), "members": members,
        "pending": study.share_requests.filter(status=ShareRequest.Status.PENDING).select_related("invitee", "requested_by", "via_token"),
        "decided": study.share_requests.exclude(status=ShareRequest.Status.PENDING).select_related("invitee", "requested_by", "decided_by")[:10],
        "roles": [(Role.EDITOR, "Éditeur", "Modifie l'étude et ses cas, rend un avis"), (Role.COMMENTER, "Commentateur", "Rend un avis et commente"),
                  (Role.VIEWER, "Lecteur", "Lit l'étude et les avis")],
        "nav": "studies",
    })


ACTION_LABELS = {
    "study.create": "Étude créée", "study.update": "Définitions modifiées", "study.archive": "Étude archivée",
    "cases.upsert": "Cas déposés", "case.retire": "Cas retiré", "case.restore": "Cas rétabli", "verdict.set": "Avis rendu",
    "share.grant": "Accès accordé", "share.change": "Rôle modifié", "share.revoke": "Accès retiré", "share.request": "Partage demandé",
    "share.confirm": "Demande de partage confirmée", "share.reject": "Demande de partage refusée",
    "representation.create": "Représentation créée", "representation.update": "Représentation ajustée",
    "representation.propose": "Représentation proposée", "representation.choose_default": "Représentation de l'étude choisie",
    "representation.dismiss": "Proposition écartée", "representation.archive": "Représentation supprimée", "brick.request": "Brique manquante signalée",
    "token.create": "Jeton créé", "token.revoke": "Jeton révoqué",
    "admin.transfer": "Propriété transférée", "admin.unarchive": "Étude désarchivée", "login.sso": "Connexion par le SSO",
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
        rows.append({"event": event, "label": ACTION_LABELS.get(event.action, event.action), "bits": " · ".join(b for b in bits if b),
                     "kind": event.actor_kind, "who": event.actor_user.username if event.actor_user else "—",
                     "token": event.actor_token.name if event.actor_token else ""})
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
    return render(request, "core/history.html", {
        **study_nav(study, "history"), "rows": _event_rows(events[:200]), "who": who or "tous",
        "count_all": total.count(), "count_token": total.filter(actor_token__isnull=False).count(),
        "count_human": total.filter(actor_token__isnull=True).count(), "nav": "studies",
    })


@login_required
@web
def study_setup(request, sid: str):
    me = actor(request)
    if request.method == "POST":
        data = request.POST
        action = data.get("action")
        if action == "archive":
            study = svc.get_study(me, sid, Role.OWNER)
            svc.archive_study(me, study)
            messages.success(request, f"Étude « {study.title} » archivée. Elle n'apparaît plus dans vos études.")
            return redirect("studies")
        study = svc.get_study(me, sid, Role.EDITOR)
        if action == "identity":
            svc.update_study(me, study, {"title": data.get("title", ""), "description": data.get("description", "")})
            messages.success(request, "Titre et description enregistrés.")
        elif action == "add_rule":
            key = (data.get("key") or "").strip() or f"R{len(study.rules) + 1}"
            svc.update_study(me, study, {"rules": [*study.rules, {"key": key, "title": data.get("title", ""), "text": data.get("text", "")}]})
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
    statuses = [{**s, "role_label": casemodel.ROLE_LABELS.get(s.get("role", "neutral"), ""), "cases": len(usage["statuses"].get(s["key"], []))} for s in study.statuses]
    # Les dimensions sont reprises telles quelles (tranches, mise en avant comprises) : les réenregistrer ne les ampute pas.
    definitions = json.dumps({"statuses": study.statuses, "dimensions": study.dimensions, "exclusions": study.exclusions,
                              "attributes": study.attributes or []}, ensure_ascii=False, indent=2)
    return {**study_nav(study, "setup"), "rules": rules, "statuses": statuses, "definitions_json": definitions,
            "example_case": json.dumps({"cases": [casemodel.EXAMPLE_CASE]}, ensure_ascii=False, indent=2),
            "cases_count": study.cases.filter(retired_at__isnull=True).count(), "nav": "studies", **extra}


def _setup_json(request, me: svc.Actor, study: Study, action: str):
    raw = request.POST.get("json", "")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        messages.error(request, f"Ce texte n'est pas du JSON valide (ligne {exc.lineno}, colonne {exc.colno}) : {exc.msg}.")
        return render(request, "core/setup.html", _setup_context(study, **{"posted_" + ("definitions" if action == "definitions" else "cases"): raw}), status=422)
    if action == "definitions":
        try:
            svc.update_study(me, study, {k: data[k] for k in ("statuses", "dimensions", "exclusions", "attributes") if isinstance(data, dict) and k in data})
        except svc.ServiceError as exc:
            return render(request, "core/setup.html", _setup_context(study, posted_definitions=raw, definition_errors=exc.details, definition_message=exc.message), status=422)
        messages.success(request, "Statuts et dimensions enregistrés.")
        return redirect("study_setup", sid=study.public_id)
    cases = data.get("cases") if isinstance(data, dict) else data
    try:
        result = svc.upsert_cases(me, study, cases, dry_run=action == "check")
    except svc.ServiceError as exc:
        return render(request, "core/setup.html", _setup_context(study, posted_cases=raw, import_message=exc.message, import_errors=exc.details), status=422)
    if action == "import" and not result["counts"].get("error"):
        written = sum(v for k, v in result["counts"].items() if k not in ("unchanged", "error"))
        messages.success(request, f"{written} cas enregistrés, {result['counts'].get('unchanged', 0)} inchangés.")
        return redirect("workspace", sid=study.public_id)
    return render(request, "core/setup.html", _setup_context(study, posted_cases=raw, import_result=result, import_checked=action == "check"),
                  status=422 if result["counts"].get("error") else 200)


# ---------------------------------------------------------------------------
# Jetons
# ---------------------------------------------------------------------------

@login_required
@web
def tokens(request):
    if request.method == "POST":
        data = request.POST
        if data.get("action") == "revoke":
            token = svc.revoke_token(request.user, int(data.get("token", 0)))
            messages.success(request, f"Jeton « {token.name} » révoqué. Toute requête qui l'utilise est désormais refusée.")
            return redirect("tokens")
        days = {"30": 30, "90": 90, "365": 365, "0": None}.get(data.get("days", "90"), 90)
        token, secret = svc.create_token(request.user, data.get("name", ""), data.getlist("scopes"), data.getlist("studies"), days)
        request.session["new_token"] = {"secret": secret, "name": token.name}
        return redirect("tokens")
    fresh = request.session.pop("new_token", None)
    origin = request.build_absolute_uri("/").rstrip("/")
    rows = []
    for token in ApiToken.objects.filter(user=request.user).prefetch_related("studies"):
        state = "révoqué" if token.revoked_at else ("expiré" if not token.is_active else "actif")
        rows.append({"token": token, "state": state, "scopes": [(s, svc.SCOPES.get(s, s)) for s in token.scopes], "studies": list(token.studies.all())})
    return render(request, "core/tokens.html", {
        "rows": rows, "fresh": fresh, "scopes": [(k, v, k in svc.DEFAULT_SCOPES) for k, v in svc.SCOPES.items()],
        "my_studies": svc.studies_for(actor(request)), "origin": origin, "nav": "tokens",
    })


def sprite(request):
    return HttpResponse(icon_sprite(), content_type="image/svg+xml")
