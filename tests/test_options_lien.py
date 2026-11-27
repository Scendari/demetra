"""Options portées par un lien, et trace des demandes : chaque lien posé a ses valeurs, lisibles par les
règles (`link_option`) ; un changement causé par un voisin dit qui l'a demandé (`by`) ; une demande restée
sans effet s'explique (`no_effect`)."""

from __future__ import annotations

import copy
from urllib.parse import parse_qs

from core import workshop
from core.casemodel import Report
from core.demo import mairie


def _decl(raw=mairie.WORKSHOP) -> dict:
    report = Report()
    decl = workshop.normalize(raw, {s["key"] for s in mairie.DEFINITION["statuses"]}, report)
    assert report.ok, [(i.path, i.code, i.message) for i in report.errors]
    return decl


def _run(decl, links, order="BA"):
    raw = {
        "elements": [{"id": k, "type": "demande"} for k in order],
        "links": links,
        "settings": {"guichets": 1},
    }
    report = Report()
    sit = workshop.situation(decl, raw, report)
    assert report.ok, [(i.path, i.code) for i in report.errors]
    return sit, workshop.run(decl, sit, "EN_FILE")


def _replaces(immediat: bool) -> dict:
    return {"from": "B", "to": "A", "type": "remplace", "options": {"immediat": immediat}}


def test_deux_liens_du_meme_type_aux_options_differentes():
    decl = _decl()
    assert decl["links"][0]["options"][0]["key"] == "immediat" and decl["links"][0]["request"] is True
    _, now = _run(decl, [_replaces(True)])
    _, later = _run(decl, [_replaces(False)])
    assert now["steps"][2]["states"]["A"] == "ANNULEE", "retrait immédiat : A part quand B passe au guichet"
    assert later["steps"][2]["states"]["A"] == "EN_FILE" and later["steps"][-1]["states"]["A"] == "ANNULEE"


def test_un_changement_dit_qui_l_a_demande():
    _, result = _run(_decl(), [_replaces(True)])
    change = next(c for step in result["steps"] for c in step["changes"] if c["id"] == "A")
    assert change["rule"] == "M5" and change["by"] == ["B"]
    assert all(
        "by" not in c for step in result["steps"] for c in step["changes"] if c["rule"] in ("M3", "M4")
    )


def test_une_demande_sans_effet_s_explique():
    decl = _decl()
    _, result = _run(decl, [_replaces(False)], order="AB")  # A passe au guichet avant que B soit traitée
    found = workshop.extra(decl, result)["no_effect"]["A"]
    assert found["rule"] == "M6" and found["by"] == ["B"] and found["state"] == "TRAITEE"


def test_l_adresse_porte_les_options_du_lien():
    decl = _decl()
    sit, _ = _run(decl, [_replaces(False)])
    query = workshop.to_query(decl, sit)
    assert ("lo.B:remplace:A.immediat", "false") in query
    again = workshop.from_query(decl, parse_qs("&".join(f"{k}={v}" for k, v in query)))
    assert again["links"] == [_replaces(False)]
    assert ("lo.B:remplace:A.immediat", "true") not in workshop.to_query(
        decl, _run(decl, [_replaces(True)])[0]
    )


def test_une_declaration_fausse_est_refusee():
    raw = copy.deepcopy(mairie.WORKSHOP)
    raw["rules"][0]["when"] = {"status": "EN_FILE", "link_option": {"immediat": True}}
    raw["rules"][1]["when"]["incoming"]["any"] = {"link_option": {"inconnue": True}}
    report = Report()
    workshop.normalize(raw, {s["key"] for s in mairie.DEFINITION["statuses"]}, report)
    codes = {(i.path, i.code) for i in report.errors}
    assert ("workshop.rules[0].when.link_option", "no_link") in codes
    assert ("workshop.rules[1].when.incoming.any.link_option.inconnue", "unknown_link_option") in codes


def test_sans_option_de_lien_rien_ne_change():
    raw = copy.deepcopy(mairie.WORKSHOP)
    raw["links"][0].pop("options")
    raw["links"][0].pop("request")
    raw["rules"] = raw["rules"][1:]  # la règle qui lit l'option s'en va avec elle
    decl = _decl(raw)
    assert set(decl["links"][0]) == {"type", "label", "reverse", "from", "to"}
    sit, _ = _run(decl, [{"from": "B", "to": "A", "type": "remplace"}])
    assert sit["links"] == [{"from": "B", "to": "A", "type": "remplace"}]


def test_l_api_et_l_ecran(api, web):
    status, data = api.post("/studies", mairie.DEFINITION)
    assert status == 201, data
    sid = data["id"]
    situation = {"elements": [{"id": k, "type": "demande"} for k in "AB"], "links": [_replaces(False)]}
    data = api.post(f"/studies/{sid}/workshop/run", {"situation": situation})[1]
    assert data["no_effect"]["A"]["by"] == ["B"] and "lo.B%3Aremplace%3AA.immediat=false" in data["web_url"]
    page = web("ana").get(data["web_url"]).content.decode()
    assert 'name="lo.B:remplace:A.immediat"' in page and "data-no-effect" in page
    assert "La demande de Demande B (règle M6) est restée sans effet" in page


def test_une_case_de_lien_decochee_vaut_non(api, web):
    sid = api.post("/studies", mairie.DEFINITION)[1]["id"]
    client = web("ana")
    sent = client.get(f"/etudes/{sid}/atelier/?f=1&e=B:demande&e=A:demande&l=B:remplace:A")
    assert sent.status_code == 302 and "lo.B%3Aremplace%3AA.immediat=false" in sent["Location"]
    ticked = client.get(
        f"/etudes/{sid}/atelier/?f=1&e=B:demande&e=A:demande&l=B:remplace:A&lo.B:remplace:A.immediat=true"
    )
    assert "immediat" not in ticked["Location"], "cochée : la valeur par défaut, rien à écrire"
