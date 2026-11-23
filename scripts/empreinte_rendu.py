"""Empreinte du comportement de Demetra sur les études de démonstration, pour vérifier qu'un remaniement ne
change rien.

Les données produites par les modules de démonstration (core/demo), puis, pour chaque cas actif de chaque
étude, avec chaque représentation système, à la première et à la dernière étape :
le fragment HTML/SVG rendu et le résumé structurel. En plus : le cas tel que `normalize_case` le reconstruit
(dictionnaire et rapport), le rejeu (`replay`), les deux empreintes, la couverture et les contrôles de
l'étude,
la recommandation de représentation.

Usage :
    uv run python scripts/empreinte_rendu.py ecrire test-results/empreinte-avant.json
    uv run python scripts/empreinte_rendu.py comparer test-results/empreinte-avant.json

« comparer » recalcule tout et liste les clés qui diffèrent ; code de sortie 1 s'il y en a.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "demetra.settings")

import django

django.setup()

from core import casemodel
from core import services as svc
from core.demo import catalogue, decision, elargi, temporal
from core.models import Case, Representation, Study
from core.recommend import recommend
from core.render import render


def _h(value) -> str:
    raw = (
        value
        if isinstance(value, str)
        else json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _report(report: casemodel.Report) -> list:
    return [i.as_dict() for i in report.issues]


def demo_empreinte() -> dict:
    """Ce que les modules de démonstration produisent, indépendamment de la base."""
    out: dict[str, str] = {}
    data = catalogue.load()
    out["demo | catalogue | definition"] = _h(catalogue.study_definition(data))
    out["demo | catalogue | cases"] = _h(catalogue.cases(data))
    out["demo | decision | definition"] = _h(decision.DEFINITION)
    out["demo | decision | cases"] = _h(decision.cases())
    out["demo | temporal | definition"] = _h(temporal.DEFINITION)
    out["demo | temporal | cases"] = _h(temporal.cases())
    for slug, definition, build in elargi.STUDIES:
        out[f"demo | {slug} | definition"] = _h(definition)
        out[f"demo | {slug} | cases"] = _h(build())
    return out


def empreinte() -> dict:
    out: dict[str, str] = demo_empreinte()
    specs = [
        (r.slug, r.spec)
        for r in Representation.objects.filter(scope=Representation.Scope.SYSTEM).order_by("slug")
    ]
    for study in Study.objects.filter(archived_at__isnull=True).order_by("title"):
        sid = study.title
        ctx = svc.context_of(study)
        siblings = svc.siblings_of(study)
        cases = list(Case.objects.filter(study=study, retired_at__isnull=True).order_by("number", "id"))
        out[f"{sid} | couverture"] = _h(svc.coverage_report(study))
        out[f"{sid} | controles"] = _h(svc.checks_report(study))
        out[f"{sid} | recommandation"] = _h(recommend(study))
        for case in cases:
            cid = f"{sid} | {case.key}"
            normalized, report = casemodel.normalize_case(case.content, ctx)
            out[f"{cid} | normalise"] = _h(normalized)
            out[f"{cid} | rapport"] = _h(_report(report))
            frames = casemodel.replay(case.content, study.statuses)
            out[f"{cid} | rejeu"] = _h(frames)
            out[f"{cid} | empreintes"] = _h(
                [casemodel.semantic_hash(case.content), casemodel.presentation_hash(case.content)]
            )
            for slug, spec in specs:
                for step in (0, max(0, len(frames) - 1)):
                    html, summary = render(
                        spec,
                        case.content,
                        frames,
                        study.statuses,
                        step=step,
                        siblings=siblings,
                        dimensions=study.dimensions,
                        ruleset=study.ruleset or {},
                        lifecycles=study.lifecycles or [],
                        attributes=study.attributes or [],
                    )
                    out[f"{cid} | {slug} | etape {step}"] = _h(html)
                    out[f"{cid} | {slug} | etape {step} | resume"] = _h(summary)
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in ("ecrire", "comparer"):
        print(__doc__)
        return 2
    path = Path(argv[2])
    current = empreinte()
    if argv[1] == "ecrire":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        print(f"{len(current)} empreintes écrites dans {path}")
        return 0
    before = json.loads(path.read_text(encoding="utf-8"))
    diff = sorted(k for k in set(before) | set(current) if before.get(k) != current.get(k))
    if diff:
        print(f"{len(diff)} différence(s) sur {len(before)} empreintes :")
        for key in diff[:60]:
            print("  ", key, "(absente)" if key not in current else "(nouvelle)" if key not in before else "")
        return 1
    print(f"identique : {len(current)} empreintes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
