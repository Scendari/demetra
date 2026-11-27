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

« comparer » recalcule tout et dit ce qui diffère : lignes changées, absentes, nouvelles (comptées par
étude) ; code de sortie 1 s'il y en a. Après un ajout, seules des lignes nouvelles sont attendues.

Le script travaille sur sa propre base, test-results/empreinte.sqlite3, créée puis remise à jour par
`migrate` et `seed_demo` à chaque lancement : il ne lit jamais la base locale ni DEMETRA_DB, qui peuvent
contenir des études personnelles. La même base sert d'une mesure à l'autre : les identifiants des études ne
changent pas entre « ecrire » et « comparer ».
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "demetra.settings")
BASE = ROOT / "test-results" / "empreinte.sqlite3"
BASE.parent.mkdir(parents=True, exist_ok=True)
os.environ["DEMETRA_DB"] = str(BASE)  # jamais la base locale : elle peut contenir des études personnelles

import io

import django
from django.core.management import call_command

django.setup()
call_command("migrate", verbosity=0)
call_command("seed_demo", no_verdicts=True, verbosity=0, stdout=io.StringIO())

from core import casemodel
from core import services as svc
from core.demo import catalogue, circuit, decision, elargi, librairie, magasin, mairie, parametre, temporal
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


def _definition(out: dict, slug: str, definition: dict) -> None:
    """La définition sur sa ligne, la déclaration d'atelier sur la sienne : déclarer un atelier ajoute une
    ligne et ne masque pas un changement du reste de la définition."""
    out[f"demo | {slug} | definition"] = _h({k: v for k, v in definition.items() if k != "workshop"})
    if definition.get("workshop"):
        out[f"demo | {slug} | atelier"] = _h(definition["workshop"])


def demo_empreinte() -> dict:
    """Ce que les modules de démonstration produisent, indépendamment de la base."""
    out: dict[str, str] = {}
    data = catalogue.load()
    _definition(out, "catalogue", catalogue.study_definition(data))
    out["demo | catalogue | cases"] = _h(catalogue.cases(data))
    for slug, module in (("decision", decision), ("temporal", temporal)):
        _definition(out, slug, module.DEFINITION)
        out[f"demo | {slug} | cases"] = _h(module.cases())
    for slug, definition, build in elargi.STUDIES:
        _definition(out, slug, definition)
        out[f"demo | {slug} | cases"] = _h(build())
    for slug, module in (
        ("parametre", parametre),
        ("circuit", circuit),
        ("magasin", magasin),
        ("librairie", librairie),
        ("mairie", mairie),
    ):
        _definition(out, slug, module.DEFINITION)
        out[f"demo | {slug} | cases"] = _h(module.cases())
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
    new = sorted(k for k in current if k not in before)
    gone = sorted(k for k in before if k not in current)
    changed = sorted(k for k in current if k in before and before[k] != current[k])
    if new or gone or changed:
        print(f"{len(new) + len(gone) + len(changed)} différence(s) sur {len(before)} empreintes :")
        print(f"   {len(changed)} changée(s), {len(gone)} absente(s), {len(new)} nouvelle(s)")
        for key in changed[:60]:
            print("   changée  :", key)
        for key in gone[:60]:
            print("   absente  :", key)
        for study, count in sorted(Counter(k.split(" | ")[0] for k in new).items()):
            print(f"   nouvelles : {count:5d}  {study}")
        return 1
    print(f"identique : {len(current)} empreintes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
