"""Dire pourquoi rien n'a changé : dans un atelier d'éléments reliés, une brique qui attend encore à la fin
dit quelle règle la ferait bouger et ce qui lui manque. Les périodes (« retenue devant ») et le calcul (ligne
sans objet) l'expliquent déjà."""

from __future__ import annotations

from core import workshop

from .test_atelier import built
from .test_comparer_compter import LEVELS, declared, door


def _run(elements, links=(), settings=None):
    decl = declared(LEVELS)
    sit = built(decl, {"elements": elements, "links": list(links), "settings": settings or {"seuil": 0}})
    result = workshop.run(decl, sit, "ATTENTE")
    return decl, result


def test_une_brique_qui_attend_dit_la_regle_et_ce_qui_manque():
    decl, result = _run(
        [door("A", zone="toit"), door("B"), {"id": "S", "type": "sas"}],
        [{"from": "A", "to": "S", "type": "mene"}, {"from": "B", "to": "S", "type": "mene"}],
    )
    waiting = workshop.extra(decl, result)["waiting"]
    assert waiting["A"] == {
        "rule": "N2",
        "title": "Une porte hors du toit s'ouvre",
        "test": "option",
        "why": "l'option « Zone » n'a pas la valeur voulue",
    }
    assert (
        waiting["S"]["rule"] == "N3"
        and waiting["S"]["why"] == "la condition sur ses liens entrants n'est pas remplie"
    )
    assert "B" not in waiting, "B est ouverte : aucune règle ne l'attend plus"


def test_rien_quand_tout_est_joue():
    decl, result = _run(
        [door("A"), door("B"), {"id": "S", "type": "sas"}],
        [{"from": "A", "to": "S", "type": "mene"}, {"from": "B", "to": "S", "type": "mene"}],
    )
    assert workshop.extra(decl, result) == {}


def test_l_api_et_l_ecran_le_disent(api, web):
    from .conftest import STUDY

    status, data = api.post("/studies", {**STUDY, "statuses": STUDY["statuses"], "workshop": LEVELS})
    assert status == 201, data
    sid = data["id"]
    situation = {
        "elements": [{"id": "A", "type": "porte", "options": {"niveau": 1, "zone": "toit"}}],
        "settings": {"seuil": 0},
    }
    data = api.post(f"/studies/{sid}/workshop/run", {"situation": situation})[1]
    assert data["waiting"]["A"]["rule"] == "N2"
    page = web("ana").get(f"/etudes/{sid}/atelier/?e=A:porte&o.A.zone=toit&s.seuil=0", follow=True)
    page = page.content.decode()
    assert 'data-wait="N2"' in page and "Reste ainsi" in page
