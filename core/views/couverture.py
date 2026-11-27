"""Couverture des dimensions et contrôles d'une étude."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .. import coverage as cov
from .. import services as svc
from .commun import actor, study_nav, web


@login_required
@web
def study_coverage(request, sid: str):
    study = svc.get_study(actor(request), sid)
    try:
        strength = max(1, min(3, int(request.GET.get("force", "2"))))
    except ValueError:
        strength = 2
    report = svc.coverage_report(study, strength)
    labels = {
        d["key"]: {
            "label": d.get("label") or d["key"],
            "values": {v["value"]: v["label"] for v in d["values"]},
        }
        for d in study.dimensions
    }
    hints = report.get("workshop") or []
    missing = [
        {
            "parts": [
                {"dim": labels[k]["label"], "value": labels[k]["values"].get(v, v)} for k, v in combo.items()
            ],
            "workshop": hints[n] if n < len(hints) else None,
        }
        for n, combo in enumerate(report["missing"][:60])
    ]
    keys = [d["key"] for d in study.dimensions]
    row_key = request.GET.get("lignes") if request.GET.get("lignes") in keys else (keys[0] if keys else None)
    col_key = (
        request.GET.get("colonnes")
        if request.GET.get("colonnes") in keys
        else next((k for k in keys if k != row_key), None)
    )
    table = (
        cov.matrix(study.dimensions, study.exclusions, svc._case_rows(study, variants=True), row_key, col_key)
        if row_key and col_key
        else None
    )
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
    exclusions = [
        {
            "when": [
                {"dim": labels[k]["label"], "value": labels[k]["values"].get(v, v)}
                for k, v in e["when"].items()
                if k in labels
            ],
            "reason": e.get("reason", ""),
        }
        for e in study.exclusions
    ]
    return render(
        request,
        "core/coverage.html",
        {
            **study_nav(study, "coverage"),
            "report": report,
            "missing": missing,
            "pct": pct,
            "strength": strength,
            "table": table,
            "row_key": row_key,
            "col_key": col_key,
            "dimension_choices": [(k, labels[k]["label"]) for k in keys],
            "checks": svc.checks_report(study),
            "exclusions": exclusions,
            "nav": "studies",
            "strength_labels": [(1, "Chaque valeur"), (2, "Chaque paire"), (3, "Chaque triplet")],
        },
    )
