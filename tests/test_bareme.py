"""Barème par tranches, famille calcul : à taux (appliqué part par part, comme un impôt progressif) ou à
montant (celui de la tranche où tombe la base, comme un port par paliers). Le détail par tranche se lit sous
la ligne."""

from __future__ import annotations

import copy

import pytest

from core import calc
from core.casemodel import Report
from core.demo import librairie

from .test_calcul import KEYS, REPAS, declared, ran

IMPOT = copy.deepcopy(REPAS)
IMPOT["outcome"] = [{"label": "Taxe calculée", "status": "A_PAYER"}]
IMPOT["lines"] = [
    {
        "key": "base",
        "label": "Base",
        "op": "=",
        "value": {"sum": {"type": "repas", "of": {"option": "montant"}}},
    },
    {
        "key": "taxe",
        "label": "Taxe progressive",
        "op": "=",
        "value": {
            "scale": {
                "of": {"total": True},
                "brackets": [{"upto": 10, "rate": 0}, {"upto": 30, "rate": 10}, {"rate": 20}],
            }
        },
    },
]


def _meal(key, montant):
    return {"id": key, "type": "repas", "options": {"montant": montant, "invite": False}}


def _entry(result, key):
    return next(e for e in result["entries"] if e["key"] == key)


def test_un_bareme_a_taux_s_applique_part_par_part():
    _, result = ran(declared(IMPOT), [_meal("A", 50)])
    taxe = _entry(result, "taxe")
    assert taxe["amount"] == 6  # 0 % de 10, 10 % de 20, 20 % de 20
    assert taxe["detail"] == [
        "0 à 10 : 0 % de 10 = 0",
        "10 à 30 : 10 % de 20 = 2",
        "au-delà de 30 : 20 % de 20 = 4",
    ]


def test_sous_la_premiere_tranche():
    _, result = ran(declared(IMPOT), [_meal("A", 8)])
    assert _entry(result, "taxe")["amount"] == 0 and len(_entry(result, "taxe")["detail"]) == 1


def test_un_bareme_a_montant_prend_la_tranche_de_la_base():
    decl = librairie.declaration()
    for prix, port in ((9, 6.9), (20, 4.9)):
        sit = calc.situation(
            decl,
            {
                "elements": [{"id": "A", "type": "livre", "options": {"prix": prix}}],
                "settings": {"livraison": "domicile"},
            },
            Report(),
        )
        entry = _entry(calc.run(decl, sit, "A_CALCULER"), "port")
        assert entry["amount"] == port and entry["detail"][0].startswith(f"Base {prix} → tranche")


@pytest.mark.parametrize(
    "brackets",
    [
        [],
        [{"upto": 10, "rate": 5}],  # la dernière tranche n'a pas de borne
        [{"upto": 30, "rate": 5}, {"upto": 10, "rate": 6}, {"rate": 7}],  # bornes décroissantes
        [{"upto": 10, "rate": 5}, {"amount": 3}],  # taux et montants mêlés
        [{"upto": 10, "rate": "cinq"}, {"rate": 7}],
    ],
)
def test_un_bareme_mal_forme_est_refuse(brackets):
    raw = copy.deepcopy(IMPOT)
    raw["lines"][1]["value"]["scale"]["brackets"] = brackets
    report = Report()
    calc.normalize(raw, KEYS, report)
    assert ("workshop.lines[1].value.scale", "type") in {(i.path, i.code) for i in report.errors}


def test_l_ecran_montre_le_detail(api, web):
    sid = api.post("/studies", librairie.DEFINITION)[1]["id"]
    page = web("ana").get(f"/etudes/{sid}/atelier/?e=A:livre&o.A.prix=9&r.livraison=domicile", follow=True)
    html = page.content.decode()
    assert 'class="sub at-bracket"' in html and "Base 9 → tranche sous 15 → 6,9" in html
