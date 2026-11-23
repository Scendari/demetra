"""Revue des cas : espace de travail, panneau d'un cas, avis, état et flux d'événements de l'étude."""

from __future__ import annotations

import time

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET, require_POST

from .. import services as svc
from ..models import Case, Decision, Role, Study, Verdict
from ..render import attribute_info, attribute_value, flag_classes, status_map
from .commun import _raw, _step_arg, _steps_context, actor, body_of, legend_of, study_nav, wants_json, web


def _list_rows(study: Study, user) -> tuple[list[dict], dict]:
    mine = {v.case_id: v for v in Verdict.objects.filter(case__study=study, reviewer=user)}
    others: dict[int, dict] = {}
    for case_id, decision in (
        Verdict.objects.filter(case__study=study).exclude(reviewer=user).values_list("case_id", "decision")
    ):
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
        rows.append(
            {
                "key": case.key,
                "number": case.display_number,
                "n": case.number,
                "title": case.title,
                "family": case.family,
                "decision": decision,
                "decision_label": Decision(decision).label,
                "stale": stale,
                "retired": retired,
                "has_comment": bool(verdict and verdict.comment.strip()),
                "others_accepted": other.get("accepted", 0),
                "others_rejected": other.get("rejected", 0),
                "search": " ".join(
                    [
                        case.display_number,
                        case.key,
                        case.title,
                        case.summary,
                        case.family,
                        *content.get("tags", []),
                    ]
                ).lower(),
                "steps": len(content.get("steps", [])),
                "changed_at": int(case.content_changed_at.timestamp()),
                "hash": case.content_hash[:10],
                "rev": case.revision_no,
            }
        )
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


def _case_facts(study: Study, content: dict) -> dict[str, tuple[str, str]]:
    """Ce qui distingue un cas d'un autre, pour la comparaison : dimensions, réglages, options des entités,
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
            # Une même différence peut se lire à deux endroits (la dimension, et l'entité-condition qui la
            # recopie) : une ligne suffit.
            if here != there and (here, there) not in seen:
                seen.add((here, there))
                diffs.append({"label": (mine.get(k) or theirs.get(k))[0], "here": here, "there": there})
        rows.append(
            {
                "key": key,
                "number": other.display_number,
                "title": other.title,
                "diffs": diffs[:8],
                "more": max(0, len(diffs) - 8),
            }
        )
    return rows


def _dimension_facts(study: Study, case: Case, content: dict) -> tuple[dict, dict]:
    """(dimensions du cas avec leurs libellés, options de configuration), prêtes pour le panneau."""
    dims = {d["key"]: d for d in study.dimensions}
    facts = {}
    for key, value in (case.dimensions or {}).items():
        dim = dims.get(key)
        label = next((v["label"] for v in dim["values"] if v["value"] == value), value) if dim else value
        facts[key] = {"label": (dim or {}).get("label") or key, "value": label}
    config = {k: {"label": k, "key": k, "value": _raw(v)} for k, v in (content.get("config") or {}).items()}
    return facts, config


def _highlight_rows(
    study: Study, content: dict, highlights: list[str], facts: dict, config: dict
) -> list[dict]:
    """Ce que l'auteur du cas garde sous les yeux du relecteur : dimensions ou options, puis options d'entité
    et liens (une option portée par une entité, par exemple always_run sur la tâche C, est nommée avec
    elle)."""
    rows = [facts.get(key) or config[key] for key in highlights if key in facts or key in config]
    entities = {e["id"]: e for e in content.get("entities", [])}
    for h in content.get("highlights") or []:
        if not isinstance(h, dict):
            continue
        if "link" in h:  # la règle tient à ce lien
            link = next((l for l in content.get("links", []) if [l["from"], l["to"]] == h["link"]), None)
            if link:
                rows.append(
                    {
                        "label": f"Lien {link['from']} → {link['to']}",
                        "value": link.get("label") or link["type"],
                        "cls": flag_classes(h.get("style")),
                    }
                )
            continue
        ent = entities.get(h.get("entity"))
        if ent and h["attr"] in (ent.get("attrs") or {}):
            value = ent["attrs"][h["attr"]]
            name = " · ".join(x for x in (ent["id"], ent.get("label")) if x)
            label, definition = attribute_info(study.attributes, h["attr"])
            rows.append(
                {
                    "label": f"{label} ({name})",
                    "value": attribute_value(study.attributes, h["attr"], value),
                    "cls": flag_classes(h.get("style")),
                    "title": definition,
                }
            )
    return rows


def _proof_of(case: Case, content: dict) -> tuple[str, str]:
    """Le niveau de preuve affiché et son explication."""
    has_human = Verdict.objects.filter(
        case=case, decision=Decision.ACCEPTED, content_hash=case.content_hash
    ).exists()
    proof = (
        "validé" if has_human else ("observé" if content.get("proof") == "observed" else "structure vérifiée")
    )
    proof_help = {
        "validé": "Un relecteur a validé ce déroulé.",
        "observé": "Son auteur déclare l'avoir constaté sur le système réel (voir les références).",
        "structure vérifiée": "Le site a vérifié la structure et rejoué les étapes ; "
        "rien ne prouve encore que le système se comporte ainsi.",
    }[proof]
    return proof, proof_help


def _panel_context(request, study: Study, case: Case, step: int = 0) -> dict:
    content = case.content
    rep = svc.current_representation(request.user, study, case)
    rep_for_case = case.preferences.filter(user=request.user, representation=rep).exists()
    html, summary, frames = svc.render_case(study, case, svc.resolved_spec(rep), step=step)
    step = max(0, min(step, len(frames) - 1))
    smap = status_map(study.statuses)
    verdict = Verdict.objects.filter(case=case, reviewer=request.user).first()
    others = (
        Verdict.objects.filter(case=case)
        .exclude(reviewer=request.user)
        .select_related("reviewer")
        .order_by("reviewer__username")
    )
    rules = {r["key"]: r for r in study.rules}
    # Les caractéristiques que l'auteur du cas a mises en avant restent visibles ; les autres se déplient à la
    # demande.
    # Deux sources : une dimension marquée pour toute l'étude, puis ce que le cas ajoute pour lui-même.
    case_high = content.get("highlights") or []
    highlights = list(
        dict.fromkeys(
            [d["key"] for d in study.dimensions if d.get("highlight")]
            + [h for h in case_high if isinstance(h, str)]
        )
    )
    facts, config = _dimension_facts(study, case, content)
    dimension_rows = [row for key, row in facts.items() if key not in highlights]
    proof, proof_help = _proof_of(case, content)
    outcome = content.get("outcome") or {}
    outcome_info = smap.get(outcome.get("status")) if outcome.get("status") else None
    return {
        "study": study,
        "case": case,
        "content": content,
        "rep": rep,
        "rep_for_case": rep_for_case,
        "rep_html": mark_safe(html),
        "summary": summary,
        "frames": frames,
        **_steps_context(content, frames, study.statuses, smap, step),
        "legend": legend_of(frames, study.statuses),
        "verdict": verdict,
        "decision": verdict.decision if verdict else Decision.TO_ANALYZE,
        "stale_label": Decision(verdict.stale_from).label.lower() if verdict and verdict.stale_from else "",
        "others": others,
        "rules": [rules[k] for k in content.get("rules", []) if k in rules],
        "proof": proof,
        "proof_help": proof_help,
        "outcome": outcome,
        "outcome_role": outcome_info["role"] if outcome_info else "",
        "revisions": case.revisions.select_related("actor_user")[:12],
        "can_review": svc.ROLE_RANK[study.my_role] >= svc.ROLE_RANK[Role.COMMENTER] and not case.retired_at,
        "comment": verdict.comment if verdict else "",
        "highlight_rows": _highlight_rows(study, content, highlights, facts, config),
        "compare": _compare_rows(study, case),
        "other_rows": dimension_rows
        + [row for key, row in config.items() if key not in highlights or key in facts],
    }


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
        first = next(
            (r for r in rows if not r["retired"] and r["decision"] == Decision.TO_ANALYZE), None
        ) or next((r for r in rows if not r["retired"]), None)
        selected = study.cases.get(key=first["key"]) if first else None
    context = {
        **study_nav(study, "cases"),
        "rows": rows,
        "counts": counts,
        "families": families,
        "selected": selected,
        "state": svc.study_state(study),
        "nav": "studies",
    }
    if selected:
        context["panel"] = _panel_context(request, study, selected, _step_arg(request))
    return render(request, "core/workspace.html", context)


@login_required
@web
def case_panel(request, sid: str, key: str):
    study = svc.get_study(actor(request), sid)
    case = svc.get_case(study, key)
    return render(
        request,
        "core/_panel.html",
        {"panel": _panel_context(request, study, case, _step_arg(request)), **study_nav(study, "cases")},
    )


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
    payload = {
        "decision": verdict.decision,
        "label": Decision(verdict.decision).label,
        "comment": verdict.comment,
        "counts": counts,
    }
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
    """Flux d'événements (SSE) : signale tout changement de l'étude, qu'il vienne de l'interface ou de
    l'API."""
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
