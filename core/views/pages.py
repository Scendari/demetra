"""Pages publiques et documentation : accueil, mode d'emploi, llms.txt, catalogue des briques, sprite."""

from __future__ import annotations

import json

import markdown as md
from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils.safestring import mark_safe

from .. import bricks, casemodel, guide, samples
from ..models import BrickRequest
from ..render import icon_sprite, status_map
from ..render import render as render_rep
from .commun import _steps_context, legend_of

SAMPLE_STATUSES = [
    {"key": "WAITING", "label": "En attente", "role": "waiting", "default": True},
    {"key": "RUNNING", "label": "En cours", "role": "active"},
    {"key": "FINISHED_OK", "label": "Réussi", "role": "success"},
    {"key": "FINISHED_KO", "label": "En échec", "role": "error"},
    {"key": "BLOCKED", "label": "Bloqué", "role": "blocked"},
]

SAMPLE_CASE = {
    "key": "exemple",
    "number": 1,
    "family": "Exemple",
    "title": "Un échec bloque la suite",
    "summary": "",
    "kind": "workflow",
    "rules": [],
    "dimensions": {},
    "tags": [],
    "config": {},
    "entities": [
        {"id": "A", "label": "extraction", "type": "tâche", "group": "", "attrs": {}},
        {"id": "B", "label": "contrôle", "type": "tâche", "group": "", "attrs": {}},
        {"id": "C", "label": "chargement", "type": "tâche", "group": "", "attrs": {}},
        {"id": "D", "label": "notification", "type": "tâche", "group": "", "attrs": {}},
    ],
    "links": [
        {"from": "A", "to": "B", "type": "prerequisite", "label": ""},
        {"from": "A", "to": "C", "type": "prerequisite", "label": ""},
        {"from": "B", "to": "D", "type": "prerequisite", "label": ""},
        {"from": "C", "to": "D", "type": "prerequisite", "label": ""},
    ],
    "initial": {},
    "steps": [
        {
            "title": "L'extraction démarre",
            "note": "Les trois autres tâches attendent.",
            "changes": {"A": {"status": "RUNNING"}},
            "annotations": {},
        },
        {
            "title": "Contrôle et chargement démarrent ensemble",
            "note": "L'extraction a réussi : ses deux suites partent en parallèle.",
            "changes": {
                "A": {"status": "FINISHED_OK"},
                "B": {"status": "RUNNING"},
                "C": {"status": "RUNNING"},
            },
            "annotations": {},
        },
        {
            "title": "Le contrôle échoue",
            "note": "Le chargement continue ; la notification ne pourra plus partir.",
            "changes": {"B": {"status": "FINISHED_KO"}, "D": {"status": "BLOCKED"}},
            "annotations": {"D": "prérequis en échec"},
        },
        {
            "title": "Fin : la notification reste bloquée",
            "note": "Le chargement se termine bien, mais le cas se conclut sur un blocage.",
            "changes": {"C": {"status": "FINISHED_OK"}},
            "annotations": {},
        },
    ],
    "outcome": {"label": "Notification bloquée", "status": "BLOCKED"},
    "references": [],
    "caution": "",
    "proof": "asserted",
}


def sample_render(slug: str = "graphe-couches", step: int = 2, own: dict | None = None) -> dict:
    spec = next(r["spec"] for r in bricks.SYSTEM_REPRESENTATIONS if r["slug"] == slug)
    own = own or samples.extended_sample(slug)
    if (
        own is not None
    ):  # les représentations du catalogue élargi se montrent sur un cas qui porte leurs données
        case, statuses = own["case"], own["statuses"]
        frames = casemodel.replay(case, statuses)
        step = min(own["step"], len(frames) - 1)
        html, summary = render_rep(
            spec,
            case,
            frames,
            statuses,
            step=step,
            siblings=own["siblings"],
            dimensions=own["dimensions"],
            ruleset=own["ruleset"],
            lifecycles=own["lifecycles"],
        )
        return {
            "html": mark_safe(html),
            "summary": summary,
            "legend": legend_of(frames, statuses),
            "study": own["title"],
            "case_title": case["title"],
            **_steps_context(case, frames, statuses, status_map(statuses), step),
        }
    frames = casemodel.replay(SAMPLE_CASE, SAMPLE_STATUSES)
    html, summary = render_rep(spec, SAMPLE_CASE, frames, SAMPLE_STATUSES, step=step)
    return {
        "html": mark_safe(html),
        "summary": summary,
        "legend": legend_of(frames, SAMPLE_STATUSES),
        **_steps_context(SAMPLE_CASE, frames, SAMPLE_STATUSES, status_map(SAMPLE_STATUSES), step),
    }


def home(request):
    if request.user.is_authenticated:
        return redirect("studies")
    return render(
        request, "core/home.html", {"sample": sample_render("diagramme-etats", own=samples.home_sample())}
    )


def guide_page(request, topic: str = "index"):
    if topic not in guide.TOPICS:
        raise Http404
    html = md.markdown(
        guide.markdown(topic, request.build_absolute_uri("/").rstrip("/"), html=True),
        extensions=["tables", "fenced_code", "toc"],
    )
    return render(
        request,
        "core/guide.html",
        {
            "nav": "guide",
            "topic": topic,
            "topics": guide.topics("/guide/"),
            "content": mark_safe(html),
            "title": guide.TOPICS[topic],
            "version": settings.DEMETRA_GUIDE_VERSION,
            "origin": request.build_absolute_uri("/").rstrip("/"),
        },
    )


def llms_txt(request):
    return HttpResponse(
        guide.llms_txt(request.build_absolute_uri("/").rstrip("/")), content_type="text/plain; charset=utf-8"
    )


def bricks_page(request):
    catalog = bricks.catalog_payload()
    for family in catalog["families"]:
        for brick in family["bricks"]:
            brick["param_rows"] = [
                {
                    "name": name,
                    "type": _param_type(schema),
                    "default": schema.get("default"),
                    "has_default": "default" in schema,
                    "description": schema.get("description", ""),
                }
                for name, schema in brick["params"].items()
                if name != "brick"
            ]
            brick["example_json"] = json.dumps(brick["example"], ensure_ascii=False)
    shown, extended = [], []
    for item in bricks.SYSTEM_REPRESENTATIONS:
        if (
            item["slug"] in ("graphe-couches", "table-trace", "graphe-et-trace", "vignettes")
            or item["slug"] in samples.SHOWN
        ):
            target = extended if item["slug"] in samples.SHOWN else shown
            target.append(
                {
                    "name": item["name"],
                    "slug": item["slug"],
                    "description": item["description"],
                    "bricks": bricks.bricks_used(item["spec"]),
                    "render": sample_render(item["slug"], 2),
                    "json": json.dumps(item["spec"], ensure_ascii=False, indent=2),
                }
            )
    requests_open = BrickRequest.objects.select_related("user")[:20] if request.user.is_authenticated else []
    return render(
        request,
        "core/bricks.html",
        {
            "nav": "bricks",
            "catalog": catalog,
            "samples": shown,
            "extended": extended,
            "brick_requests": requests_open,
        },
    )


def _param_type(schema: dict) -> str:
    if "enum" in schema:
        return " | ".join(str(v) for v in schema["enum"])
    kind = schema.get("type")
    if isinstance(kind, list):
        kind = " ou ".join(kind)
    names = {
        "string": "texte",
        "integer": "entier",
        "number": "nombre",
        "boolean": "oui/non",
        "array": "liste",
        "object": "objet",
    }
    text = names.get(kind, kind or "valeur")
    if "minimum" in schema and "maximum" in schema:
        text += f" ({schema['minimum']}–{schema['maximum']})"
    return text


def sprite(request):
    return HttpResponse(icon_sprite(), content_type="image/svg+xml")
