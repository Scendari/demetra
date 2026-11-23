"""Catalogue élargi : format de cas étendu, neuf représentations, choix à trois niveaux, conseil."""

from __future__ import annotations

import copy
import json
import re

import pytest
from django.core.management import call_command

from core import bricks, casemodel, samples
from core import services as svc
from core.demo import elargi
from core.models import Case, CasePreference, Representation, Study, Verdict
from core.recommend import recommend

from .conftest import make_case

pytestmark = pytest.mark.django_db

NEW = [slug for slug, _, _ in elargi.STUDIES]
EXPECTED = [
    "matrice-croisee",
    "calcul-pas-a-pas",
    "axe-a-bandes",
    "avant-apres",
    "table-regles",
    "arbre-decision",
    "table-etats",
    "diagramme-etats",
    "diagramme-sequence",
]

STATUSES = [
    {"key": "NOUVEAU", "label": "Nouveau", "role": "waiting", "default": True},
    {"key": "PAYE", "label": "Payé", "role": "info"},
    {"key": "LIVRE", "label": "Livré", "role": "success"},
    {"key": "ANNULE", "label": "Annulé", "role": "error"},
]
RICH = {
    "title": "Commande : prix, règles et cycle de vie",
    "kind": "decision",
    "statuses": STATUSES,
    "dimensions": [
        {
            "key": "montant",
            "label": "Montant",
            "unit": "€",
            "inclusive": "from",
            "values": [
                {"value": "petit", "label": "Moins de 100 €"},
                {"value": "grand", "label": "100 € et plus"},
            ],
            "bands": [
                {"value": "petit", "to": 100, "result": "Port payant"},
                {"value": "grand", "from": 100, "result": "Port offert"},
            ],
        },
    ],
    "rules": [{"key": "R1", "title": "Port", "text": "Le port est offert à partir de 100 €."}],
    "ruleset": {
        "title": "Frais de port",
        "policy": "first",
        "conditions": [{"key": "client", "label": "Client"}, {"key": "montant", "label": "Montant"}],
        "rows": [
            {"key": "L1", "when": {"client": "Fidèle"}, "then": "Port offert", "status": "LIVRE"},
            {"key": "L2", "when": {"montant": "100 € et plus"}, "then": "Port offert"},
            {"key": "L3", "when": {}, "then": "Port payant"},
        ],
    },
    "lifecycles": [
        {
            "type": "commande",
            "initial": "NOUVEAU",
            "transitions": [
                {"from": "NOUVEAU", "to": "PAYE", "label": "payer"},
                {"from": "PAYE", "to": "LIVRE", "label": "livrer"},
                {"from": "NOUVEAU", "to": "ANNULE", "label": "annuler"},
                {"from": "NOUVEAU", "to": "NOUVEAU", "label": "paiement refusé"},
            ],
        }
    ],
}


def rich_case(key: str = "riche", **extra) -> dict:
    case = {
        "key": key,
        "title": "Commande de 120 €, client standard",
        "rules": ["R1"],
        "dimensions": {"montant": "grand"},
        "measures": {"montant": 120},
        "entities": [
            {
                "id": "cmd",
                "label": "Commande",
                "type": "commande",
                "fields": {"Port": "à calculer", "Total": "120 €"},
            },
            {"id": "client", "label": "Client", "type": "acteur"},
            {"id": "boutique", "label": "Boutique", "type": "acteur"},
        ],
        "steps": [
            {
                "title": "Le total est calculé",
                "values": [
                    {"label": "Articles", "op": "=", "value": 130, "unit": "€", "result": 130},
                    {"label": "Remise", "op": "-", "value": 10, "unit": "€", "result": 120},
                ],
                "rows": {"L1": {"result": "failed", "on": "client"}, "L2": "selected"},
            },
            {
                "title": "Le client paie",
                "changes": {"cmd": "PAYE"},
                "fields": {"cmd": {"Port": "offert"}},
                "messages": [
                    {"from": "client", "to": "boutique", "label": "Payer 120 €"},
                    {"from": "boutique", "to": "client", "label": "Reçu", "status": "lost"},
                ],
            },
            {"title": "Le colis est livré", "changes": {"cmd": "LIVRE"}, "global": "LIVRE"},
        ],
        "outcome": {"label": "Port offert", "status": "LIVRE"},
    }
    case.update(extra)
    return case


@pytest.fixture
def rich(api):
    status, data = api.post("/studies", RICH)
    assert status == 201, data
    return data["id"]


@pytest.fixture
def demo(db):
    call_command("seed_demo", "--no-verdicts", verbosity=0)
    return {slug: Study.objects.get(title=definition["title"]) for slug, definition, _ in elargi.STUDIES}


def errors_of(api, study: str, case: dict) -> dict:
    status, report = api.post(f"/studies/{study}/cases/batch", {"cases": [case]})
    assert status == 200, report
    result = report["results"][0]
    assert result["status"] == "error", result
    return {e["code"]: e for e in result["errors"]}


# ---------------------------------------------------------------- 1. Format étendu


def test_extended_case_is_accepted_replayed_and_identical_on_redeposit(api, rich):
    status, report = api.post(f"/studies/{rich}/cases/batch", {"cases": [rich_case()]})
    assert status == 200 and report["counts"] == {"created": 1}, report
    status, again = api.post(f"/studies/{rich}/cases/batch", {"cases": [rich_case()]})
    assert again["counts"] == {"unchanged": 1}
    study = Study.objects.get(public_id=rich)
    case = study.cases.get(key="riche")
    frames = casemodel.replay(case.content, study.statuses)
    assert [v["label"] for v in frames[0]["values"]] == ["Articles", "Remise"]
    assert frames[0]["rules"] == {"L1": {"result": "failed", "on": "client"}, "L2": {"result": "selected"}}
    assert frames[2]["rules"]["L2"]["result"] == "selected", (
        "le sort des lignes reste connu aux étapes suivantes"
    )
    assert (
        frames[0]["fields"]["cmd"]["Port"] == "à calculer" and frames[1]["fields"]["cmd"]["Port"] == "offert"
    )
    assert frames[1]["fields_changed"] == [["cmd", "Port"]]
    assert [m["status"] for m in frames[1]["messages"]] == ["received", "lost"]
    out = api.get(f"/studies/{rich}")[1]
    assert out["ruleset"]["policy"] == "first" and out["lifecycles"][0]["states"] == [
        "NOUVEAU",
        "PAYE",
        "LIVRE",
        "ANNULE",
    ]


def test_old_cases_stay_unchanged_and_keep_their_verdicts(api, study, users):
    """Un cas déposé avant l'extension se redépose à l'identique : même empreinte, avis conservé."""
    old = [make_case("a"), make_case("b", "valide", "nuit", ok=False)]
    api.post(f"/studies/{study}/cases/batch", {"cases": old})
    obj = svc.get_study(svc.Actor(users["ana"]), study)
    svc.set_verdict(svc.Actor(users["ana"]), obj, "a", "accepted", "")
    hashes = dict(Case.objects.filter(study=obj).values_list("key", "content_hash"))
    # L'étude gagne un jeu de règles : les anciens cas n'en dépendent pas.
    ruleset = {
        **RICH["ruleset"],
        "rows": [{k: v for k, v in row.items() if k != "status"} for row in RICH["ruleset"]["rows"]],
    }
    status, out = api.patch(f"/studies/{study}", {"ruleset": ruleset})
    assert status == 200, out
    status, report = api.post(f"/studies/{study}/cases/batch", {"cases": old})
    assert report["counts"] == {"unchanged": 2}
    assert dict(Case.objects.filter(study=obj).values_list("key", "content_hash")) == hashes
    verdict = Verdict.objects.get(case__key="a")
    assert verdict.decision == "accepted" and verdict.stale_from == "", "l'avis rendu reste valable"
    for case in Case.objects.filter(study=obj):
        assert not (set(case.content) & {"measures"}) and all(
            not (set(s) & {"values", "fields", "messages", "rows"}) for s in case.content["steps"]
        )


def test_changing_an_extended_case_reopens_its_review(api, rich, users):
    api.post(f"/studies/{rich}/cases/batch", {"cases": [rich_case()]})
    obj = svc.get_study(svc.Actor(users["ana"]), rich)
    svc.set_verdict(svc.Actor(users["ana"]), obj, "riche", "accepted", "")
    changed = rich_case()
    changed["steps"][1]["messages"][1]["status"] = "received"
    report = api.post(f"/studies/{rich}/cases/batch", {"cases": [changed]})[1]
    assert report["counts"] == {"updated": 1}
    verdict = Verdict.objects.get(case__key="riche")
    assert verdict.decision == "to_analyze" and verdict.stale_from == "accepted", (
        "un message qui change de sort change le cas : l'avis est à revoir"
    )


@pytest.mark.parametrize(
    "mutate, code, path",
    [
        (lambda c: c["steps"][0]["rows"].update(L9="selected"), "unknown_rule", "cases[0].steps[0].rows.L9"),
        (
            lambda c: c["steps"][0]["rows"].update(L1={"result": "failed", "on": "pays"}),
            "unknown_condition",
            "cases[0].steps[0].rows.L1.on",
        ),
        (lambda c: c["steps"][0]["rows"].update(L1="peut-être"), "enum", "cases[0].steps[0].rows.L1"),
        (
            lambda c: c["steps"][1]["messages"][0].update(to="banque"),
            "unknown_entity",
            "cases[0].steps[1].messages[0].to",
        ),
        (
            lambda c: c["steps"][1]["messages"][1].update(status="égaré"),
            "enum",
            "cases[0].steps[1].messages[1].status",
        ),
        (
            lambda c: c["steps"][1]["fields"].update(facture={"Total": "1 €"}),
            "unknown_entity",
            "cases[0].steps[1].fields.facture",
        ),
        (
            lambda c: c["steps"][0]["values"][1].update(op="puissance"),
            "enum",
            "cases[0].steps[0].values[1].op",
        ),
        (
            lambda c: c["steps"][0]["values"][0].update(value="cent trente"),
            "type",
            "cases[0].steps[0].values[0].value",
        ),
        (
            lambda c: c["steps"][1]["changes"].update(cmd="LIVRE"),
            "forbidden_transition",
            "cases[0].steps[1].changes.cmd",
        ),
        (lambda c: c.update(measures={"montant": 80}), "out_of_band", "cases[0].measures.montant"),
        (lambda c: c.update(measures={"poids": 3}), "unknown_measure", "cases[0].measures.poids"),
        (lambda c: c.update(measures={"montant": "cent"}), "type", "cases[0].measures.montant"),
        (
            lambda c: c["entities"][0].update(fields={"Port": ["a", "b"]}),
            "type",
            "cases[0].entities[0].fields.Port",
        ),
    ],
)
def test_each_addition_is_checked_with_the_exact_path(api, rich, mutate, code, path):
    case = rich_case()
    mutate(case)
    errors = errors_of(api, rich, case)
    assert code in errors, errors
    assert errors[code]["path"] == path
    assert errors[code]["message"]
    assert Case.objects.count() == 0


def test_a_measure_on_a_threshold_follows_the_inclusive_side(api, rich):
    on_threshold = rich_case("seuil", measures={"montant": 100})
    report = api.post(f"/studies/{rich}/cases/batch", {"cases": [on_threshold]})[1]
    assert report["counts"] == {"created": 1}, (
        "100 € appartient à la tranche qui commence à 100 (borne basse incluse)"
    )
    below = rich_case("dessous", measures={"montant": 99.99})
    errors = errors_of(api, rich, below)
    assert errors["out_of_band"]["received"] == 99.99 and "petit" in errors["out_of_band"]["message"]


def test_rows_without_a_ruleset_and_initial_outside_the_lifecycle(api, study, rich):
    plain = make_case("a")
    plain["steps"][0]["rows"] = {"L1": "selected"}
    errors = errors_of(api, study, plain)
    assert errors["no_ruleset"]["path"] == "cases[0].steps[0].rows"
    errors = errors_of(
        api,
        rich,
        rich_case(
            steps=[
                {"title": "Paiement", "changes": {"cmd": "PAYE"}},
                {"title": "Annulation tardive", "changes": {"cmd": "ANNULE"}},
            ]
        ),
    )
    assert errors["forbidden_transition"]["path"] == "cases[0].steps[1].changes.cmd"
    assert errors["forbidden_transition"]["expected"] == ["LIVRE"], (
        "l'erreur dit ce qui est permis depuis cet état"
    )
    statuses = [*RICH["statuses"], {"key": "PERDU", "label": "Perdu", "role": "error"}]
    assert api.patch(f"/studies/{rich}", {"statuses": statuses})[0] == 200
    errors = errors_of(api, rich, rich_case(initial={"cmd": "PERDU"}, steps=[{"title": "Rien ne bouge"}]))
    assert errors["outside_lifecycle"]["path"] == "cases[0].initial.cmd"


def test_a_self_loop_declared_in_the_lifecycle_is_allowed(api, rich):
    looping = rich_case(
        steps=[
            {"title": "Paiement refusé", "changes": {"cmd": "NOUVEAU"}},
            {"title": "Paiement accepté", "changes": {"cmd": "PAYE"}},
        ]
    )
    report = api.post(f"/studies/{rich}/cases/batch", {"cases": [looping]})[1]
    assert report["counts"] == {"created": 1}, report
    study = Study.objects.get(public_id=rich)
    spec = Representation.objects.get(slug="diagramme-etats", scope="system").spec
    html, summary, _ = svc.render_case(study, study.cases.get(key="riche"), spec, step=0)
    assert "paiement refusé" in summary["text"] and "boucle" in summary["text"]
    assert "arrivé par « paiement refusé »" in html, (
        "rester dans le même état par une transition déclarée est une boucle, pas une absence de changement"
    )


def test_an_inconsistent_running_total_is_a_warning_not_a_refusal(api, rich):
    wrong = rich_case()
    wrong["steps"][0]["values"][1]["result"] = 125
    report = api.post(f"/studies/{rich}/cases/batch", {"cases": [wrong]})[1]
    assert report["counts"] == {"created": 1}
    warning = next(w for w in report["results"][0]["warnings"] if w["code"] == "inconsistent_total")
    assert warning["path"] == "cases[0].steps[0].values[1].result"


@pytest.mark.parametrize(
    "patch, code, path",
    [
        (
            {
                "dimensions": [
                    {
                        **RICH["dimensions"][0],
                        "bands": [{"value": "petit", "to": 100}, {"value": "grand", "from": 150}],
                    }
                ]
            },
            "gap",
            "dimensions[0].bands[1].from",
        ),
        (
            {"dimensions": [{**RICH["dimensions"][0], "bands": [{"value": "petit", "to": 100}]}]},
            "missing_band",
            "dimensions[0].bands",
        ),
        (
            {
                "dimensions": [
                    {
                        **RICH["dimensions"][0],
                        "bands": [{"value": "petit", "to": 100}, {"value": "énorme", "from": 100}],
                    }
                ]
            },
            "unknown_value",
            "dimensions[0].bands[1].value",
        ),
        ({"ruleset": {**RICH["ruleset"], "policy": "au hasard"}}, "enum", "ruleset.policy"),
        (
            {
                "ruleset": {
                    **RICH["ruleset"],
                    "rows": [{"key": "L1", "when": {"pays": "France"}, "then": "Port offert"}],
                }
            },
            "unknown_condition",
            "ruleset.rows[0].when.pays",
        ),
        (
            {"ruleset": {**RICH["ruleset"], "rows": [{"key": "L1", "when": {}, "then": ""}]}},
            "required",
            "ruleset.rows[0].then",
        ),
        (
            {
                "lifecycles": [
                    {
                        "type": "commande",
                        "initial": "NOUVEAU",
                        "transitions": [{"from": "NOUVEAU", "to": "PERDU", "label": "perdre"}],
                    }
                ]
            },
            "unknown_status",
            "lifecycles[0].transitions[0].to",
        ),
        (
            {
                "lifecycles": [
                    {
                        "type": "commande",
                        "initial": "NOUVEAU",
                        "transitions": [
                            {"from": "NOUVEAU", "to": "PAYE", "label": "payer"},
                            {"from": "NOUVEAU", "to": "ANNULE", "label": "payer"},
                        ],
                    }
                ]
            },
            "ambiguous",
            "lifecycles[0].transitions[1]",
        ),
        (
            {
                "lifecycles": [
                    {
                        "type": "commande",
                        "initial": "NOUVEAU",
                        "transitions": [{"from": "NOUVEAU", "to": "PAYE"}],
                    }
                ]
            },
            "required",
            "lifecycles[0].transitions[0].label",
        ),
    ],
)
def test_study_declarations_are_checked_with_the_exact_path(api, patch, code, path):
    status, error = api.post("/studies", {**copy.deepcopy(RICH), **patch})
    assert status == 422, error
    found = {d["code"]: d for d in error["error"]["details"]}
    assert code in found, found
    assert found[code]["path"] == path


def test_study_cannot_drop_what_its_cases_use(api, rich):
    api.post(f"/studies/{rich}/cases/batch", {"cases": [rich_case()]})
    smaller = copy.deepcopy(RICH["ruleset"])
    smaller["rows"] = [r for r in smaller["rows"] if r["key"] != "L2"]
    status, error = api.patch(f"/studies/{rich}", {"ruleset": smaller})
    assert status in (409, 422), error
    detail = next(d for d in error["error"]["details"] if d["code"] == "in_use")
    assert "riche" in str(detail), "l'erreur nomme le cas qui cite encore la ligne retirée"
    stricter = [
        {
            "type": "commande",
            "initial": "NOUVEAU",
            "transitions": [{"from": "NOUVEAU", "to": "PAYE", "label": "payer"}],
        }
    ]
    status, error = api.patch(f"/studies/{rich}", {"lifecycles": stricter})
    assert status in (409, 422) and any(d["code"] == "in_use" for d in error["error"]["details"])
    assert Study.objects.get(public_id=rich).ruleset["rows"][1]["key"] == "L2", "un refus ne modifie rien"


# ---------------------------------------------------------------- 2. Neuf représentations assemblées à partir
# de briques


def test_nine_new_system_representations_are_valid_assemblies():
    assert NEW == EXPECTED
    documented = {b["brick"] for f in bricks.catalog_payload()["families"] for b in f["bricks"]}
    for slug in NEW:
        rep = Representation.objects.get(slug=slug, scope="system")
        report = bricks.validate_spec(rep.spec)
        assert report.ok, (slug, [i.as_dict() for i in report.issues])
        used = bricks.bricks_used(rep.spec)
        assert used and set(used) <= documented, (
            f"{slug} : toute brique utilisée est documentée dans le catalogue"
        )
    for needed in (
        "layout.matrix",
        "layout.scale",
        "layout.tree",
        "layout.states",
        "layout.lifelines",
        "mark.value",
        "mark.field",
        "mark.rule_result",
        "mark.band",
        "mark.point",
        "mark.decision",
        "mark.conclusion",
        "mark.state",
        "mark.transition",
        "mark.lifeline",
        "mark.message",
        "mark.tally",
    ):
        assert needed in documented


def test_bricks_page_documents_and_shows_the_new_representations(client):
    page = client.get("/briques/").content.decode()
    for slug in NEW:
        assert f'id="exemple-{slug}"' in page
        assert samples.extended_sample(slug)["case"]["steps"]
    for brick in (
        "layout.matrix",
        "layout.scale",
        "layout.tree",
        "layout.states",
        "layout.lifelines",
        "mark.message",
        "mark.band",
    ):
        assert f'id="{brick}"' in page
    assert "<script>alert" not in page


@pytest.mark.parametrize(
    "mutate, where",
    [
        (lambda s: s["views"][0]["marks"].append({"brick": "mark.script", "code": "alert(1)"}), "marks"),
        (lambda s: s["views"][0]["layout"].update(onclick="alert(1)"), "layout"),
        (lambda s: s["views"][0]["marks"].clear(), "marks"),
        (lambda s: s.update(script="alert(1)"), "spec"),
    ],
)
@pytest.mark.parametrize("slug", ["diagramme-etats", "diagramme-sequence", "axe-a-bandes", "arbre-decision"])
def test_new_layouts_refuse_anything_that_is_not_a_brick(api, slug, mutate, where):
    spec = copy.deepcopy(Representation.objects.get(slug=slug, scope="system").spec)
    mutate(spec)
    status, error = api.post("/representations", {"name": "Essai", "spec": spec})
    assert status == 422
    assert any(where in d["path"] for d in error["error"]["details"]), error["error"]["details"]
    assert Representation.objects.filter(scope="theme").count() == 0


def test_hostile_text_in_the_new_fields_is_drawn_as_text(api, rich):
    hostile = "<script>alert(1)</script>"
    case = rich_case()
    case["steps"][0]["values"][0]["label"] = hostile
    case["steps"][1]["messages"][0]["label"] = hostile
    case["steps"][1]["fields"]["cmd"]["Port"] = hostile
    case["entities"][0]["fields"]["Total"] = "<img src=x onerror=alert(1)>"
    assert api.post(f"/studies/{rich}/cases/batch", {"cases": [case]})[1]["counts"] == {"created": 1}
    study = Study.objects.get(public_id=rich)
    obj = study.cases.get(key="riche")
    for slug in NEW:
        spec = Representation.objects.get(slug=slug, scope="system").spec
        for step in range(3):
            html, _, _ = svc.render_case(study, obj, spec, step=step)
            assert (
                "<script" not in html
                and "<img" not in html
                and "onerror=" not in html.replace("onerror=alert(1)&gt;", "")
            ), slug


def test_every_demo_case_renders_in_its_representation_at_every_step(demo):
    for slug, study in demo.items():
        spec = Representation.objects.get(slug=slug, scope="system").spec
        siblings = svc.siblings_of(study)
        for case in study.cases.all():
            for step in range(len(case.content["steps"])):
                html, summary, frames = svc.render_case(study, case, spec, step=step, siblings=siblings)
                assert html.startswith("<") and summary["views"], (slug, case.key)
                assert not [w for v in summary["views"] for w in v["warnings"] if "indisponible" in w], (
                    slug,
                    case.key,
                    summary,
                )
                assert "rep-empty" not in html, f"{slug} / {case.key} : la représentation a de quoi dessiner"


def test_any_case_renders_in_any_new_representation_without_error(api, study):
    """Une représentation choisie sur une étude qui n'a pas ses données reste lisible : un message, jamais une
    erreur."""
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a", ok=False)]})
    obj = Study.objects.get(public_id=study)
    case = obj.cases.get(key="a")
    for slug in NEW:
        html, summary, _ = svc.render_case(
            obj, case, Representation.objects.get(slug=slug, scope="system").spec, step=1
        )
        assert html.startswith("<") and summary["text"], slug


# ---------------------------------------------------------------- 6. Un statut porte toujours couleur, icône
# et libellé


def test_status_is_never_shown_by_colour_alone_in_the_new_representations(demo):
    for slug, study in demo.items():
        spec = Representation.objects.get(slug=slug, scope="system").spec
        case = study.cases.first()
        html, _, frames = svc.render_case(study, case, spec, step=len(case.content["steps"]) - 1)
        assert "<script" not in html and "onclick" not in html
        coloured = re.findall(r"<[^>]*data-role=\"[^\"]+\"[^>]*>", html)
        if (
            not coloured
        ):  # ces trois-là ne montrent que des nombres et des textes : aucun statut, donc rien à vérifier
            assert slug in ("calcul-pas-a-pas", "axe-a-bandes", "avant-apres")
            continue
        # Pastilles : la couleur de rôle, une icône du même rôle et un libellé écrit.
        pills = re.findall(
            r'<span class="st" data-role="([^"]+)"[^>]*>(.*?)</span></span>', html, flags=re.DOTALL
        )
        for role, inner in pills:
            assert f'href="#ic-{role}"' in inner, (slug, inner[:160])
            assert re.search(r'<span class="st-tx"[^>]*>[^<]+', inner), (slug, inner[:160])
        # Formes dessinées (états, feuilles, acteurs) : même règle, icône et texte dans le même groupe.
        shapes = [
            chunk.split("</g>")[0] + chunk.split("</g>")[1] if chunk.count("</g>") > 1 else chunk
            for chunk in re.split(r'<g [^>]*data-role="[^"]+"', html)[1:]
        ]
        for inner in shapes:
            assert 'href="#ic-' in inner and "<text" in inner, (slug, inner[:200])
        assert pills or shapes, (
            f"{slug} : le statut passe par une pastille ou une forme, jamais par un simple aplat"
        )


def test_text_summary_describes_each_new_representation(demo, token_for):
    from .conftest import Api

    call = Api(svc.create_token(Study.objects.first().owner, "lecture", list(svc.SCOPES), None, 30)[1])
    expected = {
        "matrice-croisee": "combinaison",
        "calcul-pas-a-pas": "résultat du calcul",
        "axe-a-bandes": "tranches :",
        "avant-apres": "champs modifiés",
        "table-regles": "sort des lignes",
        "arbre-decision": "chemin du cas",
        "table-etats": "évènements",
        "diagramme-etats": "transitions :",
        "diagramme-sequence": "messages, dans l'ordre",
    }
    for slug, study in demo.items():
        case = study.cases.first()
        status, preview = call.post(
            f"/studies/{study.public_id}/cases/{case.key}/preview", {"representation": slug, "image": False}
        )
        assert status == 200, preview
        text = preview["summary"]["text"]
        assert expected[slug] in text.lower(), (slug, text)
        assert preview["representation"] == Representation.objects.get(slug=slug, scope="system").name


def test_image_preview_of_each_new_representation(demo):
    """L'aperçu image passe par l'API pour chacune des neuf, en clair et en sombre (si Chromium est
    installé)."""
    import base64

    from .conftest import Api

    call = Api(svc.create_token(Study.objects.first().owner, "apercu", list(svc.SCOPES), None, 30)[1])
    for slug, study in demo.items():
        case = study.cases.order_by("number")[1]
        theme = "dark" if slug in ("diagramme-etats", "table-regles") else "light"
        status, preview = call.post(
            f"/studies/{study.public_id}/cases/{case.key}/preview",
            {"representation": slug, "step": 2, "image": True, "theme": theme},
        )
        assert status == 200 and preview["summary"]["text"], preview
        if not preview.get("image"):
            pytest.skip(f"Chromium indisponible : {preview.get('image_unavailable')}")
        png = base64.b64decode(preview["image"]["data"])
        assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 4000, (slug, len(png))


# ---------------------------------------------------------------- 3. Une étude = une représentation, trois
# niveaux de choix


def test_three_levels_of_choice_by_the_api(api, study, token_for, users):
    from .conftest import Api

    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a"), make_case("b", "valide", "nuit")]})
    status, initial = api.get(f"/studies/{study}/representation")
    assert status == 200 and initial["study"] is None and initial["me"] is None and initial["cases"] == []
    # L'IA en charge de l'étude fixe sa représentation.
    status, chosen = api.call("PUT", f"/studies/{study}/representation", {"representation": "table-trace"})
    assert (
        status == 200
        and chosen["study"]["slug"] == "table-trace"
        and chosen["study_chosen_by"] == "ai"
        and chosen["effective"]["slug"] == "table-trace"
    )
    # Pour moi, sur toute l'étude ; puis pour un seul cas.
    status, mine = api.call(
        "PUT", f"/studies/{study}/representation", {"representation": "vignettes", "level": "me"}
    )
    assert (
        mine["me"]["slug"] == "vignettes"
        and mine["study"]["slug"] == "table-trace"
        and mine["effective"]["slug"] == "vignettes"
    )
    status, one = api.call(
        "PUT",
        f"/studies/{study}/representation",
        {"representation": "graphe-couches", "level": "case", "case": "b"},
    )
    assert [(c["case"], c["representation"]["slug"]) for c in one["cases"]] == [("b", "graphe-couches")]
    obj = Study.objects.get(public_id=study)
    a, b = obj.cases.get(key="a"), obj.cases.get(key="b")
    assert svc.current_representation(users["ana"], obj, a).slug == "vignettes"
    assert svc.current_representation(users["ana"], obj, b).slug == "graphe-couches"
    assert svc.current_representation(users["ben"], obj, b).slug == "table-trace", (
        "les choix personnels ne changent rien pour les autres"
    )
    # L'aperçu sans représentation nommée suit le même ordre.
    names = {r.slug: r.name for r in Representation.objects.filter(scope="system")}
    assert (
        api.post(f"/studies/{study}/cases/b/preview", {"image": False})[1]["representation"]
        == names["graphe-couches"]
    )
    assert (
        api.post(f"/studies/{study}/cases/a/preview", {"image": False})[1]["representation"]
        == names["vignettes"]
    )
    # Revenir en arrière, niveau par niveau.
    back = api.call(
        "PUT", f"/studies/{study}/representation", {"representation": None, "level": "case", "case": "b"}
    )[1]
    assert back["cases"] == [] and CasePreference.objects.count() == 0
    back = api.call("PUT", f"/studies/{study}/representation", {"representation": None, "level": "me"})[1]
    assert back["me"] is None and back["effective"]["slug"] == "table-trace"
    # Erreurs : niveau inconnu, cas manquant, rôle insuffisant.
    assert (
        api.call("PUT", f"/studies/{study}/representation", {"representation": "vignettes", "level": "tous"})[
            0
        ]
        == 422
    )
    status, error = api.call(
        "PUT", f"/studies/{study}/representation", {"representation": "vignettes", "level": "case"}
    )
    assert status == 422 and error["error"]["details"][0]["path"] == "case"
    reader = Api(token_for("ben"))
    assert (
        reader.call("PUT", f"/studies/{study}/representation", {"representation": "vignettes"})[0] == 404
    ), "une étude privée reste introuvable pour les autres"


def test_a_token_does_not_replace_a_human_choice_for_the_study(api, study, users):
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a")]})
    obj = Study.objects.get(public_id=study)
    svc.choose_representation(
        svc.Actor(users["ana"]),
        obj,
        Representation.objects.get(slug="couloirs", scope="system"),
        for_study=True,
    )
    status, error = api.call("PUT", f"/studies/{study}/representation", {"representation": "table-trace"})
    assert status == 409 and error["error"]["code"] == "human_choice"
    assert "proposals" in error["error"]["message"]
    obj.refresh_from_db()
    assert obj.representation.slug == "couloirs" and obj.representation_by == "human"
    # Le jeton garde son propre choix d'affichage, et peut proposer.
    assert (
        api.call("PUT", f"/studies/{study}/representation", {"representation": "table-trace", "level": "me"})[
            0
        ]
        == 200
    )
    assert (
        api.post(
            f"/studies/{study}/representations/proposals",
            {"representation": "table-trace", "reason": "Plus lisible."},
        )[0]
        == 201
    )


def test_three_levels_of_choice_in_the_interface(web, api, study, users):
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a"), make_case("b", "valide", "nuit")]})
    ana = web("ana")
    obj = Study.objects.get(public_id=study)
    reps = {
        slug: Representation.objects.get(slug=slug, scope="system")
        for slug in ("table-trace", "vignettes", "couloirs")
    }
    page = ana.get(f"/etudes/{study}/representation/?cas=b").content.decode()
    assert "Utiliser pour moi" in page and "seulement" in page and "Utiliser pour toute l'étude" in page
    url = f"/etudes/{study}/representation/"
    ana.post(url, {"action": "choose", "scope": "study", "representation": reps["table-trace"].public_id})
    obj.refresh_from_db()
    assert obj.representation == reps["table-trace"] and obj.representation_by == "human"
    ana.post(url, {"action": "choose", "scope": "me", "representation": reps["vignettes"].public_id})
    response = ana.post(
        url, {"action": "choose", "scope": "case", "case": "b", "representation": reps["couloirs"].public_id}
    )
    assert response.status_code == 302 and "cas=b" in response["Location"]
    a, b = obj.cases.get(key="a"), obj.cases.get(key="b")
    assert svc.current_representation(users["ana"], obj, a) == reps["vignettes"]
    assert svc.current_representation(users["ana"], obj, b) == reps["couloirs"]
    panel = ana.get(f"/etudes/{study}/?cas=b").content.decode()
    assert reps["couloirs"].name in panel and "pour ce cas" in panel and "Suivre l'étude" in panel
    assert "pour ce cas" not in ana.get(f"/etudes/{study}/?cas=a").content.decode()
    page = ana.get(f"{url}?cas=b").content.decode()
    assert "Choisie pour le cas" in page and "rep-case-choices" in page
    ana.post(url, {"action": "reset_case", "case": "b"})
    assert svc.current_representation(users["ana"], obj, b) == reps["vignettes"]
    ana.post(url, {"action": "reset"})
    assert svc.current_representation(users["ana"], obj, b) == reps["table-trace"]


# ---------------------------------------------------------------- 4. Conseil de représentation


def test_first_recommendation_of_each_demo_study_is_the_one_it_illustrates(demo):
    for slug, study in demo.items():
        result = recommend(study)
        first = result["recommended"][0]
        assert first["slug"] == slug, (
            f"« {study.title} » : attendu {slug}, conseillé {[r['slug'] for r in result['recommended']]}"
        )
        assert first["reasons"], slug


def test_older_demo_studies_keep_their_recommendation(demo):
    expected = {
        "Remboursement d'une commande": "table-decision",
        "Relances d'une facture impayée": "frise-temporelle",
    }
    for title, slug in expected.items():
        assert recommend(Study.objects.get(title=title))["recommended"][0]["slug"] == slug
    workflow = Study.objects.filter(is_example=False).get()
    assert recommend(workflow)["recommended"][0]["slug"] == "graphe-couches"


def test_a_study_without_the_data_is_not_offered_the_new_representations(api, study):
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a"), make_case("b", "valide", "nuit")]})
    result = recommend(Study.objects.get(public_id=study))
    offered = [r["slug"] for r in result["recommended"]]
    assert not (set(offered) & (set(NEW) - {"matrice-croisee"})), offered
    missing = next(r for r in result["others"] if r["slug"] == "diagramme-sequence")
    assert missing["score"] < 50 and any("messages" in text for text in missing["reservations"])


# ---------------------------------------------------------------- 5. Études de démonstration


def test_one_example_study_per_new_representation_replayable_without_duplicates(demo):
    assert sorted(demo) == sorted(EXPECTED)

    def state():
        return {
            s.pk: sorted(s.cases.values_list("key", "content_hash", "revision_no"))
            for s in Study.objects.all()
        }

    before = state()
    assert len(before) == 12
    for slug, study in demo.items():
        assert study.is_example, f"{study.title} : marquée « Exemple »"
        assert study.representation.slug == slug, "chaque étude porte la représentation qu'elle illustre"
        assert study.cases.count() >= 3
    call_command("seed_demo", "--no-verdicts", verbosity=0)
    assert state() == before, "rejouer la commande ne crée ni étude ni cas, et ne révise aucun cas"


def test_example_studies_say_they_are_examples(demo, web, users):
    from django.contrib.auth import get_user_model
    from django.test import Client

    client = Client()
    assert client.login(username="demo", password="demetra-demo")
    assert get_user_model().objects.filter(username="demo").exists()
    for study in demo.values():
        page = client.get(f"/etudes/{study.public_id}/").content.decode()
        assert "Exemple" in page and "données fictives" in page


def test_state_diagram_draws_the_trail_of_the_journey():
    """Diagramme d'états : à chaque étape, états déjà traversés, état courant, états pas encore atteints ;
    transitions déjà empruntées et transition de l'étape. Rien ne bouge : seules les classes changent."""
    from core.views import sample_render

    html = str(sample_render("diagramme-etats", own=samples.home_sample())["html"])
    per_step = re.findall(r"data-cls='(\[[^']*\])'", html)
    assert any("is-ahead" in item for item in per_step), "les états pas encore atteints sont marqués"
    assert any("is-trail" in item for item in per_step), "les transitions déjà empruntées restent tracées"
    nodes = re.findall(r'<g class="n sd-node[^"]*" data-cls=\'(\[[^\']*\])\'', html)
    assert nodes, "chaque état porte ses classes par étape"
    steps = [json.loads(item.replace("&quot;", '"')) for item in nodes]
    last = [classes[-1] for classes in steps]
    assert last.count("is-here") == 1, "un seul état courant à la dernière étape"
    first = [classes[0] for classes in steps]
    assert first.count("is-ahead") >= 5, "au départ, presque tout le cycle reste à parcourir"
