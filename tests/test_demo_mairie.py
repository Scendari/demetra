"""L'étude de démonstration « Guichets d'une mairie » : un atelier à places limitées. Ses cas sont écrits par
le moteur, s'accordent avec l'atelier, et ne mettent jamais plus de demandes au guichet que de guichets."""

from __future__ import annotations

from pathlib import Path

from django.core.management import call_command

from core import casemodel
from core import services as svc
from core.demo import mairie
from core.models import Study


def test_jamais_plus_de_demandes_au_guichet_que_de_guichets():
    for case in mairie.cases():
        open_ = int(case["dimensions"]["guichets"])
        states = dict(case.get("initial", {}))
        for step in case["steps"]:
            states.update(step.get("changes", {}))
            assert sum(1 for s in states.values() if s == "AU_GUICHET") <= open_, case["key"]


def test_le_semis_et_l_accord_avec_l_atelier(db):
    call_command("seed_demo", "--no-verdicts", verbosity=0)
    study = Study.objects.get(title=mairie.TITLE)
    assert study.cases.count() == len(mairie.cases()) and study.workshop.get("resources")
    codes = {f["code"] for f in svc.checks_report(study)}
    assert not codes & {"workshop_mismatch", "workshop_untranslatable"}
    waiting = study.cases.get(key="la-troisieme-attend").content["steps"][1]["note"]
    assert "Demande C attend une place : Guichets au complet." in waiting


def test_rien_de_la_mairie_dans_core():
    core = Path(casemodel.__file__).parent
    for path in core.rglob("*.py"):
        if "demo" in path.parts or path.name == "seed_demo.py":  # le semis liste les démonstrations
            continue
        text = path.read_text(encoding="utf-8").lower()
        assert "mairie" not in text and "guichet" not in text, path
