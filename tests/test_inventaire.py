"""Inventaire des points de décision : relevé dans les sources, couvert par des cas, exclu ou à confirmer.
Une étude à moitié faite se voit ; « couvert » veut dire « un cas le cite », jamais « vérifié »."""

from __future__ import annotations

from core import casemodel
from core import services as svc
from core.models import Verdict
from tests.conftest import make_case

INVENTORY = [
    {"key": "P1", "label": "Badge expiré refusé", "source": {"ref": "acces.py:42", "excerpt": "if expire:"}},
    {"key": "P2", "label": "Accès de nuit", "source": {"ref": "Règlement §2"}, "kind": "branche"},
    {
        "key": "P3",
        "label": "Badge visiteur",
        "source": {"ref": "acces.py:60"},
        "state": "excluded",
        "reason": "Hors périmètre : les visiteurs passent par l'accueil.",
    },
    {
        "key": "P4",
        "label": "Badge prêté",
        "source": {"ref": "Règlement §5"},
        "state": "to_confirm",
        "reason": "Le règlement est muet ; question posée.",
    },
    {"key": "P5", "label": "Porte forcée", "source": {"ref": "alarme.py:12"}},
]


def _codes(report: casemodel.Report) -> set[str]:
    return {issue.code for issue in report.errors}


def test_un_point_a_une_source_et_un_sort_motive():
    report = casemodel.Report()
    points = casemodel.normalize_inventory(INVENTORY, report)
    assert report.ok and [p["key"] for p in points] == ["P1", "P2", "P3", "P4", "P5"]
    assert points[0] == {
        "key": "P1",
        "label": "Badge expiré refusé",
        "source": {"ref": "acces.py:42", "excerpt": "if expire:"},
        "state": "open",
    }
    bad = [
        {"key": "P1", "label": "Sans source"},
        {"key": "P2", "label": "Exclu muet", "source": {"ref": "x"}, "state": "excluded"},
        {"key": "P3", "label": "Sort inconnu", "source": {"ref": "x"}, "state": "covered"},
        {"key": "P4", "label": "Double", "source": {"ref": "x"}},
        {"key": "P4", "label": "Double", "source": {"ref": "x"}},
    ]
    report = casemodel.Report()
    assert [p["key"] for p in casemodel.normalize_inventory(bad, report)] == ["P4"]
    assert _codes(report) == {"required", "enum", "duplicate"}, (
        "« couvert » ne se déclare pas : il se calcule"
    )


def _filled(api, study):
    assert api.patch(f"/studies/{study}", {"inventory": INVENTORY})[0] == 200
    cases = [make_case("a", covers=["P1"]), make_case("b", "expiré", "nuit", ok=False, covers=["P1", "P2"])]
    status, report = api.post(f"/studies/{study}/cases/batch", {"cases": cases})
    assert status in (200, 201), report


def test_couverture_et_controles(api, study):
    _filled(api, study)
    inv = api.get(f"/studies/{study}/coverage")[1]["inventory"]
    assert {k: inv[k] for k in ("total", "covered", "excluded", "to_confirm", "open")} == {
        "total": 5,
        "covered": 2,
        "excluded": 1,
        "to_confirm": 1,
        "open": 1,
    }
    assert inv["open_points"] == [{"key": "P5", "label": "Porte forcée", "ref": "alarme.py:12"}]
    assert inv["to_confirm_points"][0]["reason"].startswith("Le règlement est muet")
    findings = {f["code"]: f for f in api.get(f"/studies/{study}/checks")[1]["findings"]}
    assert findings["inventory_open"]["severity"] == "warning" and findings["inventory_open"]["points"] == [
        "P5"
    ]
    assert findings["inventory_to_confirm"]["severity"] == "info"
    assert api.get(f"/studies/{study}")[1]["inventory"][1]["kind"] == "branche"


def test_sans_inventaire_rien_ne_change(api, study):
    api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a")]})
    assert "inventory" not in api.get(f"/studies/{study}/coverage")[1]
    codes = {f["code"] for f in api.get(f"/studies/{study}/checks")[1]["findings"]}
    assert not codes & {"inventory_open", "inventory_to_confirm"}
    assert "covers" not in api.get(f"/studies/{study}/cases/a")[1]["case"]


def test_point_inconnu_refuse_et_point_cite_garde(api, study):
    _filled(api, study)
    status, report = api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("c", covers=["P9"])]})
    assert "unknown_inventory_point" in str(report)
    status, error = api.patch(f"/studies/{study}", {"inventory": INVENTORY[1:]})
    assert status == 422 and error["error"]["details"][0]["code"] == "inventory_point_in_use"
    assert api.patch(f"/studies/{study}", {"inventory": INVENTORY[:2]})[0] == 200, "P3 à P5 ne sont pas cités"


def test_changer_covers_garde_les_avis(api, study, users):
    _filled(api, study)
    me = svc.Actor(users["ana"])
    svc.set_verdict(me, svc.get_study(me, study), "a", "accepted", "Conforme.")
    report = api.post(f"/studies/{study}/cases/batch", {"cases": [make_case("a", covers=["P1", "P5"])]})[1]
    assert report["results"][0]["status"] == "updated_cosmetic"
    assert Verdict.objects.get().decision == "accepted"


def test_pages(api, study, web):
    _filled(api, study)
    client = web("ana")
    page = client.get(f"/etudes/{study}/couverture/").content.decode()
    assert "Inventaire des points de décision" in page and "Porte forcée" in page and "alarme.py:12" in page
    panel = client.get(f"/etudes/{study}/cas/b/panneau/").content.decode()
    assert "Points de l&#x27;inventaire couverts" in panel or "Points de l'inventaire couverts" in panel
    assert "Accès de nuit" in panel
