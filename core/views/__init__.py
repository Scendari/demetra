"""Pages web de Demetra (session + CSRF). Toute décision d'accès passe par core/services.py.

Un module par domaine ; ce fichier réexporte les vues (core/urls.py) et ce que l'administration et les tests
importent de `core.views`.
"""

from __future__ import annotations

from .commun import DECISION_KEYS, actor, body_of, legend_of, steps_payload, study_nav, wants_json, web
from .couverture import study_coverage
from .etudes import STARTER_STATUSES, studies, study_setup
from .historique import ACTION_LABELS, DECISION_LABELS, study_history
from .jetons import tokens
from .pages import (
    SAMPLE_CASE,
    SAMPLE_STATUSES,
    bricks_page,
    guide_page,
    home,
    llms_txt,
    sample_render,
    sprite,
)
from .partage import study_sharing
from .representations import TOKEN_LABELS, study_representations
from .revue import case_panel, case_verdict, study_events, study_state, workspace

__all__ = [
    "ACTION_LABELS",
    "DECISION_KEYS",
    "DECISION_LABELS",
    "SAMPLE_CASE",
    "SAMPLE_STATUSES",
    "STARTER_STATUSES",
    "TOKEN_LABELS",
    "actor",
    "body_of",
    "bricks_page",
    "case_panel",
    "case_verdict",
    "guide_page",
    "home",
    "legend_of",
    "llms_txt",
    "sample_render",
    "sprite",
    "steps_payload",
    "studies",
    "study_coverage",
    "study_events",
    "study_history",
    "study_nav",
    "study_representations",
    "study_setup",
    "study_sharing",
    "study_state",
    "tokens",
    "wants_json",
    "web",
    "workspace",
]
