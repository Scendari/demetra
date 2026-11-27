"""Atelier, famille « calcul » : déclaration, moteur, adresse, API, écran, accord des cas, exemple du guide.

Deux déclarations sans rapport : la facture de la librairie de démonstration, et une note de frais de repas
écrite ici (plafond par repas, moyenne, division par zéro)."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from core import calc, families, workshopcheck
from core.casemodel import Report
from core.demo import librairie

STATUSES = [
    {"key": "A_CALCULER", "label": "À calculer", "role": "waiting", "default": True},
    {"key": "APPLIQUEE", "label": "Appliquée", "role": "success"},
    {"key": "SANS_OBJET", "label": "Sans objet", "role": "disabled"},
    {"key": "BLOQUEE", "label": "Bloquée", "role": "error"},
    {"key": "A_PAYER", "label": "À payer", "role": "active"},
]
KEYS = {s["key"] for s in STATUSES}
REPAS = {
    "family": "calc",
    "title": "Note de frais",
    "bricks": [
        {
            "type": "repas",
            "label": "Repas",
            "options": [
                {
                    "key": "montant",
                    "label": "Montant",
                    "number": {"min": 0, "max": 200, "step": 0.01},
                    "unit": "€",
                },
                {"key": "invite", "label": "Avec invité", "values": [False, True]},
            ],
        }
    ],
    "settings": [{"key": "plafond", "label": "Plafond par repas", "values": [15, 20, 25], "default": 20}],
    "lines": [
        {
            "key": "rembourse",
            "label": "Chaque repas, au plus le plafond (sans plafond avec un invité)",
            "op": "=",
            "value": {
                "add": [
                    {
                        "sum": {
                            "type": "repas",
                            "where": {"option": {"invite": False}},
                            "of": {"min": [{"option": "montant"}, {"setting": "plafond"}]},
                        }
                    },
                    {
                        "sum": {
                            "type": "repas",
                            "where": {"option": {"invite": True}},
                            "of": {"option": "montant"},
                        }
                    },
                ]
            },
            "unit": "€",
        },
        {
            "key": "moyenne",
            "label": "Moyenne par repas",
            "op": "÷",
            "value": {"count": {"type": "repas"}},
            "unit": "€",
        },
        {
            "key": "cher",
            "label": "Alerte au-delà de 30 € en moyenne",
            "when": {"total": {"gt": 30}},
            "op": "min",
            "value": 30,
        },
    ],
    "states": {"applied": "APPLIQUEE", "skipped": "SANS_OBJET", "blocked": "BLOQUEE"},
    "outcome": [{"when": {"line": {"rembourse": {"gt": 0}}}, "label": "À rembourser", "status": "A_PAYER"}],
}


def declared(raw=REPAS, keys=KEYS) -> dict:
    report = Report()
    decl = families.normalize(raw, keys, report)
    assert report.ok, [(i.path, i.code, i.message) for i in report.errors]
    return decl


def ran(decl, elements, settings=None, statuses_default="A_CALCULER"):
    report = Report()
    sit = calc.situation(decl, {"elements": elements, "settings": settings or {}}, report)
    assert report.ok, [(i.path, i.code) for i in report.errors]
    return sit, calc.run(decl, sit, statuses_default)


def meal(key, montant, invite=False):
    return {"id": key, "type": "repas", "options": {"montant": montant, "invite": invite}}


def lines(result) -> dict:
    return {e["key"]: (e["status"], e["amount"], e["after"]) for e in result["entries"]}


def test_meals_are_capped_averaged_and_capped_again():
    decl = declared()
    _, result = ran(decl, [meal("A", 18), meal("B", 32), meal("C", 50, invite=True)], {"plafond": 15})
    assert lines(result) == {
        "rembourse": ("applied", 80, 80),  # 15 + 15 + 50
        "moyenne": ("applied", 3, 26.666666667),
        "cher": ("skipped", None, 26.666666667),
    }
    assert result["end"] == "stable" and calc.outcome(decl, result)["label"] == "À rembourser"
    _, result = ran(decl, [meal("A", 90, invite=True)])
    assert lines(result)["cher"] == ("applied", 30, 30)


def test_a_division_by_zero_blocks_the_line_and_withholds_the_result():
    decl = declared()
    _, result = ran(decl, [])
    assert lines(result)["moyenne"] == ("blocked", None, 0)
    assert result["end"] == "blocked" and calc.outcome(decl, result) is None
    assert "division par zéro" in result["entries"][1]["why"]
    assert calc.extra(decl, result)["result"]["value"] is None


@pytest.mark.parametrize(
    ("key", "elements", "settings", "total", "outcome"),
    [
        ("simple", [{"id": "A", "type": "livre", "options": {"prix": 18.5}}], {}, 18.5, "Facture à régler"),
        (
            "port",
            [
                {"id": "A", "type": "livre", "options": {"prix": 12}},
                {"id": "B", "type": "papeterie", "options": {"prix": 3.5, "quantite": 2}},
            ],
            {"livraison": "domicile"},
            23.9,
            "Facture à régler",
        ),
        (
            "adherent",
            [{"id": "A", "type": "livre", "options": {"prix": 19.99, "quantite": 3}}],
            {"client": "adhérent"},
            56.97,
            "Facture à régler",
        ),
        (
            "coupon",
            [
                {"id": "A", "type": "livre", "options": {"prix": 7.5}},
                {"id": "B", "type": "coupon", "options": {"valeur": 10}},
            ],
            {},
            0,
            "Rien à régler",
        ),
    ],
)
def test_the_demo_bookshop_invoice(key, elements, settings, total, outcome):
    decl = librairie.declaration()
    _, result = ran(decl, elements, settings)
    assert result["total"] == total, (key, lines(result))
    assert calc.outcome(decl, result)["label"] == outcome


@pytest.mark.parametrize(
    ("mutate", "path", "code"),
    [
        (lambda d: d["lines"][0].update(op="^"), "workshop.lines[0].op", "enum"),
        (
            lambda d: d["lines"][1].update(value={"line": "cher"}),
            "workshop.lines[1].value.line",
            "unknown_line",
        ),
        (
            lambda d: d["lines"][1].update(value={"option": "montant"}),
            "workshop.lines[1].value.option",
            "type",
        ),
        (
            lambda d: d["lines"][1].update(value={"setting": "plafond2"}),
            "workshop.lines[1].value.setting",
            "unknown_setting",
        ),
        (lambda d: d["lines"][2].update(value=0), "workshop.lines[2].value", None),
        (lambda d: d["lines"][1].update(op="arrondi", value=-1), "workshop.lines[1].value", "type"),
        (
            lambda d: d["lines"][1].update(value={"count": {"type": "dessert"}}),
            "workshop.lines[1].value.count.type",
            "unknown_brick",
        ),
        (
            lambda d: d["lines"][1].update(value={"sum": {"of": {"option": "invite"}}}),
            "workshop.lines[1].value.sum.of.option",
            "not_numeric",
        ),
        (lambda d: d["lines"][1].update(value={"pow": [2, 3]}), "workshop.lines[1].value", "unknown_value"),
        (lambda d: d["lines"][1].update(value={"sub": [1]}), "workshop.lines[1].value.sub", "type"),
        (lambda d: d["lines"][2].update(when={"total": "beaucoup"}), "workshop.lines[2].when.total", "type"),
        (
            lambda d: d["lines"][2].update(when={"option": {"montant": 3}}),
            "workshop.lines[2].when.option",
            "unknown_test",
        ),
        (
            lambda d: d["bricks"][0]["options"][0].update(number={"min": 5, "max": 1}),
            "workshop.bricks[0].options[0].number",
            "type",
        ),
        (lambda d: d["states"].pop("blocked"), "workshop.states", "unknown_status"),
    ],
)
def test_a_wrong_declaration_is_refused_with_its_path(mutate, path, code):
    raw = copy.deepcopy(REPAS)
    mutate(raw)
    report = Report()
    families.normalize(raw, KEYS, report)
    found = [(i.path, i.code) for i in report.errors]
    if code is None:  # une valeur nulle est permise : min(cumul, 0)
        assert report.ok, found
    else:
        assert (path, code) in found, found


def test_a_number_option_is_compared_in_a_condition():
    raw = copy.deepcopy(REPAS)
    raw["lines"][0]["value"]["add"][0]["sum"]["where"] = {"option": {"montant": {"lte": 20}}}
    decl = declared(raw)
    _, result = ran(decl, [meal("A", 18), meal("B", 32)])
    assert lines(result)["rembourse"][1] == 18


def test_a_number_option_out_of_bounds_is_refused():
    report = Report()
    calc.situation(declared(), {"elements": [meal("A", 900)]}, report)
    assert ("situation.elements[0].options.montant", "unknown_value") in [
        (i.path, i.code) for i in report.errors
    ]


def test_the_address_carries_numbers_and_accepts_a_comma():
    decl = declared()
    sit, _ = ran(decl, [meal("A", 12.5, invite=True)], {"plafond": 25})
    query = calc.to_query(decl, sit)
    assert query == [("e", "A:repas"), ("o.A.montant", "12.5"), ("o.A.invite", "true"), ("r.plafond", "25")]
    back = calc.from_query(
        decl, {"e": ["A:repas"], "o.A.montant": ["12,5"], "o.A.invite": ["true"], "r.plafond": ["25"]}
    )
    assert back["elements"][0]["options"] == {"montant": 12.5, "invite": True} and back["settings"] == {
        "plafond": 25
    }
    wild = calc.from_query(decl, {"e": ["A:repas"], "o.A.montant": ["beaucoup"]})
    assert wild["elements"][0]["options"] == {}


def test_the_case_reads_line_by_line_and_agrees_with_the_workshop():
    decl = librairie.declaration()
    sit, result = ran(
        decl, [{"id": "A", "type": "livre", "options": {"prix": 40}}], {"livraison": "domicile"}
    )
    case = calc.to_case(decl, sit, result, "A_CALCULER")
    values = [v for step in case["steps"] for v in step.get("values", [])]
    assert [v["label"] for v in values] == ["Livres", "Papeterie", "Arrondi au centime"]
    assert values[0] == {"label": "Livres", "op": "=", "value": 40, "result": 40, "unit": "€"}
    assert {e["id"] for e in case["entities"]} >= {"A", "ligne-port", "ligne-coupons"}
    from core.casemodel import StudyContext, normalize_case, normalize_statuses

    statuses = normalize_statuses(librairie.DEFINITION["statuses"], Report())
    content, report = normalize_case(case, StudyContext(statuses, [], [], workshop=decl))
    assert content is not None and not report.warnings
    assert workshopcheck.agreement(decl, content, statuses)["status"] == "agree"
    content["config"]["livraison"] = "retrait"
    content["steps"][-1]["values"][0]["result"] = 99
    found = workshopcheck.agreement(decl, content, statuses)
    assert found["status"] == "differ" and any("Montant final" in d for d in found["differences"])


@pytest.fixture
def bookshop(api):
    status, data = api.post("/studies", {**librairie.DEFINITION, "title": "Librairie d'essai"})
    assert status == 201, data
    return data["id"]


def test_the_api_validates_and_runs_a_calc_workshop(api, bookshop):
    status, out = api.post(
        f"/studies/{bookshop}/workshop/validate", {"workshop": REPAS, "statuses": STATUSES}
    )
    assert status == 200 and out["valid"] and out["family"] == "calc"
    situation = {
        "elements": [{"id": "A", "type": "livre", "options": {"prix": 12, "quantite": 2}}],
        "settings": {"livraison": "domicile"},
    }
    status, run = api.post(f"/studies/{bookshop}/workshop/run", {"situation": situation})
    assert status == 200, run
    assert run["family"] == "calc" and run["total"] == 28.9 and run["result"]["label"] == "Montant à payer"
    assert [line["status"] for line in run["lines"]] == [
        "applied",
        "applied",
        "skipped",
        "skipped",
        "applied",
        "applied",
    ]
    assert run["outcome"] == {"label": "Facture à régler", "status": "A_REGLER"}
    status, data = api.post(f"/studies/{bookshop}/cases/batch", {"cases": [{**run["case"], "key": "essai"}]})
    assert status in (200, 201) and "workshop_mismatch" not in {
        w["code"] for w in data["results"][0].get("warnings", [])
    }
    bad = {**run["case"], "key": "faux", "config": {"livraison": "retrait"}}
    status, data = api.post(f"/studies/{bookshop}/cases/batch", {"cases": [bad]})
    assert "workshop_mismatch" in {w["code"] for w in data["results"][0].get("warnings", [])}
    status, error = api.post(
        f"/studies/{bookshop}/workshop/run",
        {"situation": {"elements": [], "links": [{"from": "A", "to": "B"}]}},
    )
    assert status == 422


def test_the_screen_shows_number_fields_and_the_lines(api, bookshop, web):
    client = web("ana")
    page = client.get(
        f"/etudes/{bookshop}/atelier/?e=A%3Alivre&o.A.prix=40&o.A.quantite=2&r.livraison=domicile"
    ).content.decode()
    assert 'type="number"' in page and 'name="o.A.prix" value="40"' in page and 'step="0.01"' in page
    assert "Montant à payer : <b>80 €</b>" in page
    assert re.search(r'data-line="port" class="is-quiet"', page) and 'data-line="livres" class=""' in page
    assert (
        "lignes de calcul que l&#x27;étude déclare" in page or "lignes de calcul que l'étude déclare" in page
    )
    response = client.post(
        f"/etudes/{bookshop}/atelier/?e=A%3Alivre&o.A.prix=40", {"title": "Un livre à 40 €"}
    )
    assert response.status_code == 302


def test_coverage_offers_the_workshop_for_a_bookshop_combination(api, bookshop):
    for case in librairie.cases()[:2]:
        api.post(f"/studies/{bookshop}/cases/batch", {"cases": [case]})
    report = api.get(f"/studies/{bookshop}/coverage")[1]
    hints = [h for h in report["workshop"] if h]
    assert hints and all("/atelier/" in h["web_url"] for h in hints)


def test_the_guide_example_gives_what_the_guide_says(api):
    text = (Path(calc.__file__).parent / "guide" / "atelier.md").read_text(encoding="utf-8")
    block = next(
        b for b in re.findall(r"```json\n(.*?)```", text, flags=re.DOTALL) if '"family": "calc"' in b
    )
    declaration = json.loads("{" + block + "}")["workshop"]
    status, data = api.post(
        "/studies", {"title": "Exemple calcul", "statuses": STATUSES, "workshop": declaration}
    )
    assert status == 201, data
    situation = {
        "elements": [{"id": "A", "type": "article", "options": {"prix": 40, "quantite": 3}}],
        "settings": {},
    }
    status, run = api.post(f"/studies/{data['id']}/workshop/run", {"situation": situation})
    assert status == 200 and run["total"] == 114
    assert [line["amount"] for line in run["lines"]] == [120, 6, 0.01]
    for word in (
        *calc.OPS,
        "unknown_line",
        "not_numeric",
        "applied",
        "skipped",
        "blocked",
        "pct",
        "sum",
        "count",
    ):
        assert f"`{word}`" in text or f'"{word}"' in text, word


def test_nothing_in_core_names_the_demo_bookshop():
    """Le moteur, l'écran et le mode d'emploi ne connaissent pas la librairie : ses mots ne vivent que dans
    core/demo/, et dans le semis qui l'importe."""
    core = Path(calc.__file__).parent
    words = ("librairie", "papeterie", "adhérent")
    found = [
        str(path.relative_to(core))
        for path in core.rglob("*")
        if path.is_file()
        and path.suffix in {".py", ".html", ".js", ".css", ".md", ".json", ".txt"}
        and "demo" not in path.relative_to(core).parts
        and path.name != "seed_demo.py"
        and any(word in path.read_text(encoding="utf-8").lower() for word in words)
    ]
    assert found == []
