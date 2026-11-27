"""Accord entre un cas déposé et les règles d'atelier de son étude.

Le site rejoue le cas comme une situation de l'atelier — mêmes briques, mêmes options, mêmes liens, même
point de départ — et compare ce que les règles donnent à ce que le cas annonce. Un écart est un avertissement,
jamais un refus : soit le cas se trompe, soit les règles sont incomplètes ; c'est à un humain de trancher.

Un cas ne dit pas quels évènements (« échoue »…) ont été provoqués : le site cherche, parmi ceux que les
règles savent traiter, une combinaison qui explique le cas. Un cas peut aussi s'arrêter en cours de route : il
concorde s'il décrit un moment que les règles traversent. Pur : aucun accès à la base, aucun code fourni par
l'étude n'est exécuté.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

from . import periods, workshop
from .casemodel import Report, default_status, replay

MAX_EVENTS_TRIED = 3  # évènements supposés à la fois, au plus
MAX_RUNS = 96  # déroulés tentés pour un cas, au plus


def agreement(decl: dict | None, case: dict, statuses: list[dict]) -> dict | None:
    """L'accord d'un cas avec l'atelier de l'étude.

    None quand l'atelier ne concerne pas ce cas (pas d'atelier, ou aucune entité d'un type qu'il déclare).
    Sinon {status: agree | differ | untranslatable, differences: [texte], reason: texte, events: {id: [clé]}}.
    """
    if not decl or not case.get("entities"):
        return None
    if (decl.get("family") or "linked") == "periods":
        return _periods(decl, case, statuses)
    return _linked(decl, case, statuses)


def settings_of(decl: dict, case: dict) -> dict:
    """Les réglages de l'atelier que porte un cas : dans sa configuration, sinon dans la dimension où l'étude
    dit qu'ils se lisent."""
    config, dims = case.get("config") or {}, case.get("dimensions") or {}
    out = {}
    for item in decl["settings"]:
        binding = item.get("dimension") or {}
        if item["key"] in config:
            out[item["key"]] = config[item["key"]]
        elif dims.get(binding.get("key")) in binding.get("values", {}):
            out[item["key"]] = binding["values"][dims[binding["key"]]]
    return out


def _untranslatable(reason: str) -> dict:
    return {"status": "untranslatable", "differences": [], "reason": reason, "events": {}}


# ---------------------------------------------------------------------------
# Éléments reliés
# ---------------------------------------------------------------------------


def _situation_of(decl: dict, case: dict, bricks: dict) -> tuple[dict | None, str]:
    """La situation d'atelier que décrit le cas, ou la raison pour laquelle il ne s'y traduit pas."""
    foreign = [e for e in case["entities"] if e["type"] not in bricks]
    if foreign:
        e = foreign[0]
        return None, f"l'entité « {e['id']} » est de type « {e['type']} », que l'atelier ne déclare pas"
    raw = {
        "elements": [
            {
                "id": e["id"],
                "label": e.get("label") or e["id"],
                "type": e["type"],
                "options": {
                    k: v
                    for k, v in (e.get("attrs") or {}).items()
                    if k in {o["key"] for o in bricks[e["type"]]["options"]}
                },
            }
            for e in case["entities"]
        ],
        "links": [{"from": lk["from"], "to": lk["to"], "type": lk["type"]} for lk in case.get("links", [])],
        "settings": settings_of(decl, case),
    }
    report = Report()
    sit = workshop.situation(decl, raw, report)
    if not report.ok:
        issue = report.errors[0]
        where = issue.path.removeprefix("situation.")
        return None, f"{where} : {issue.message[:1].lower()}{issue.message[1:].rstrip('.')}"
    return sit, ""


def _mentions(cond: Any, found: set[str]) -> set[str]:
    """Les évènements qu'une condition teste sur l'élément lui-même (pas sur ses voisins)."""
    if isinstance(cond, dict):
        if "event" in cond:
            found.update(workshop.as_list(cond["event"]))
        for key in ("all", "any"):
            for item in cond.get(key, []) if isinstance(cond.get(key), list) else []:
                _mentions(item, found)
        if isinstance(cond.get("not"), dict):
            _mentions(cond["not"], found)
    return found


def _candidates(decl: dict, sit: dict, off: set[str]) -> list[tuple[str, str]]:
    """Les évènements qui pourraient expliquer le cas : ceux qu'une règle sait traiter pour la brique, sur
    les éléments que le déroulé sans évènement ne mène pas là où le cas les mène (tous, si l'écart est
    ailleurs)."""
    bricks = {b["type"]: b for b in decl["bricks"]}
    out = []
    for element in sit["elements"]:
        if off and element["id"] not in off:
            continue
        allowed = {e["key"] for e in bricks[element["type"]]["events"]}
        for rule in decl["rules"]:
            if element["type"] in rule["on"]:
                out += [(element["id"], e) for e in sorted(_mentions(rule["when"], set()) & allowed)]
    return list(dict.fromkeys(out))


def _differences(decl: dict, sit: dict, result: dict, expected: dict, case: dict) -> list[str]:
    labels = {e["id"]: e["label"] for e in sit["elements"]}
    final = result["steps"][-1]["states"]
    if final != expected and any(step["states"] == expected for step in result["steps"]):
        return []  # le cas s'arrête en cours de route, à un moment que les règles traversent
    out = [
        f"{labels[key]} : le cas finit en {status}, les règles donnent {final[key]}"
        for key, status in expected.items()
        if final.get(key) != status
    ]
    if result["end"] != "stable":
        out.append(workshop.END_NOTES[result["end"]])
    wanted = (case.get("outcome") or {}).get("status")
    found = (workshop.outcome(decl, result) or {}).get("status")
    if wanted and found and wanted != found:
        out.append(f"Résultat d'ensemble : le cas annonce {wanted}, les règles donnent {found}")
    return out


def _tries(candidates: list[tuple[str, str]]):
    for size in range(1, min(MAX_EVENTS_TRIED, len(candidates)) + 1):
        yield from combinations(candidates, size)


def _linked(decl: dict, case: dict, statuses: list[dict]) -> dict | None:
    bricks = {b["type"]: b for b in decl["bricks"]}
    if not any(e["type"] in bricks for e in case["entities"]):
        return None
    sit, reason = _situation_of(decl, case, bricks)
    if sit is None:
        return _untranslatable(reason)
    fallback = default_status(statuses)
    start = {e["id"]: (case.get("initial") or {}).get(e["id"], fallback) for e in case["entities"]}
    frames = replay(case, statuses)
    expected = {key: entry["status"] for key, entry in frames[-1]["states"].items()} if frames else start
    plain = workshop.run(decl, sit, fallback, start=start)
    found = _differences(decl, sit, plain, expected, case)
    if not found:
        return {"status": "agree", "differences": [], "reason": "", "events": {}}
    final = plain["steps"][-1]["states"]
    off = {key for key, status in expected.items() if final.get(key) != status}
    best: tuple[list[str], dict] = (found, {})
    for n, chosen in enumerate(_tries(_candidates(decl, sit, off))):
        if n >= MAX_RUNS:
            break
        events: dict[str, list[str]] = {}
        for key, event in chosen:
            events.setdefault(key, []).append(event)
        found = _differences(
            decl, sit, workshop.run(decl, {**sit, "events": events}, fallback, start=start), expected, case
        )
        if not found:
            return {"status": "agree", "differences": [], "reason": "", "events": events}
        if len(found) < len(best[0]):
            best = (found, events)
    return {"status": "differ", "differences": best[0], "reason": "", "events": best[1]}


# ---------------------------------------------------------------------------
# Périodes
# ---------------------------------------------------------------------------


def _periods(decl: dict, case: dict, statuses: list[dict]) -> dict | None:
    bricks = {b["type"]: b for b in decl["bricks"]}
    sources = [e for e in case["entities"] if e["type"] in bricks]
    if not sources:
        return None
    images = [e for e in case["entities"] if e["type"] not in bricks]
    raw = {
        "elements": [
            {
                "id": e["id"],
                "label": e.get("label") or e["id"],
                "type": e["type"],
                "options": {
                    k: v
                    for k, v in (e.get("attrs") or {}).items()
                    if k in {o["key"] for o in bricks[e["type"]]["options"]}
                },
                "start": (e.get("attrs") or {}).get("start"),
                "end": (e.get("attrs") or {}).get("end"),
            }
            for e in sources
        ],
        "settings": settings_of(decl, case),
    }
    report = Report()
    sit = periods.situation(decl, raw, report)
    if not report.ok:
        issue = report.errors[0]
        return _untranslatable(f"{issue.path.removeprefix('situation.')} : {issue.message.rstrip('.')}")
    result = periods.run(decl, sit, default_status(statuses))
    found = [(i["start"], i["end"]) for i in result["images"]]
    announced = sorted(
        (((e.get("attrs") or {}).get("start"), (e.get("attrs") or {}).get("end")) for e in images), key=_order
    )
    out = []
    if announced != sorted(found, key=_order):
        out.append(
            "Historique : le cas annonce "
            + (_spans(announced) or "aucune ligne")
            + ", les règles donnent "
            + (_spans(found) or "aucune ligne")
        )
    wanted = (case.get("outcome") or {}).get("status")
    got = (periods.outcome(decl, result) or {}).get("status")
    if wanted and got and wanted != got:
        out.append(f"Résultat d'ensemble : le cas annonce {wanted}, les règles donnent {got}")
    return {"status": "differ" if out else "agree", "differences": out, "reason": "", "events": {}}


def _order(pair: tuple) -> tuple:
    return tuple((value is None, value if isinstance(value, (int, float)) else 0) for value in pair)


def _spans(pairs: list[tuple]) -> str:
    def bound(value) -> str:
        return "∅" if value is None else workshop.text_of(value)

    return ", ".join(f"[{bound(a)} ; {bound(b)}[" for a, b in pairs)
