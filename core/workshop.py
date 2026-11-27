"""Atelier : les règles qu'une étude déclare pour des éléments reliés, et le moteur qui les exécute.

L'étude déclare un vocabulaire (des types de briques, leurs options, les évènements qu'on peut y provoquer,
les liens permis, des réglages) et une table de règles : « quand telle condition sur l'élément, ses voisins,
ses options ou les réglages, alors tel état ». Le site applique cette table à chaque élément, pas après pas,
jusqu'à ce que plus rien ne bouge.

Pur : aucun accès à la base. Aucun code fourni par l'étude n'est exécuté : les conditions sont un
vocabulaire fermé que ce module compare à des valeurs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .casemodel import ID_RE, Report, _is_str
from .rules import (
    ORDERED,
    Numbers,
    among,
    as_list,
    check_count,
    is_number,
    matches,
    operand_of,
    pairs_hold,
    same,
    setting_ref,
    text_of,
    values_of,
)
from .rules import bricks as _bricks
from .rules import check_pairs as _check_pairs
from .rules import choices as _choices
from .rules import chosen as _chosen
from .rules import item_key as _key
from .rules import item_label as _label

MAX_LINK_TYPES = 8
MAX_SETTINGS = 8
MAX_RULES = 60
MAX_OUTCOMES = 12
MAX_DEPTH = 5
MAX_RUN_STEPS = 40
DEFAULT_RUN_STEPS = 24
MAX_ELEMENTS = 24
MAX_SITUATION_LINKS = 60
QUANTIFIERS = ("all", "any", "none")
NEIGHBOURS = ("incoming", "outgoing", "upstream", "downstream")
ELEMENT_TESTS = ("status", "type", "option", "event", "since", *NEIGHBOURS)
MAX_WAIT = 20  # pas d'attente d'un coup, quand seule une durée peut encore faire bouger la situation
SHARED_TESTS = ("setting", "elements", "all", "any", "not")

EXAMPLE = {
    "bricks": [
        {
            "type": "task",
            "label": "Tâche",
            "options": [{"key": "always_run", "label": "Toujours exécutée", "values": [False, True]}],
            "events": [{"key": "echec", "label": "Échoue"}],
        }
    ],
    "links": [{"type": "prerequisite", "label": "précède", "reverse": "dépend de"}],
    "rules": [
        {
            "key": "R1",
            "title": "Une tâche démarre quand tous ses prérequis ont réussi",
            "when": {"status": "WAITING", "incoming": {"all": {"status": "OK"}}},
            "then": "RUNNING",
        }
    ],
}
EXAMPLE_CONDITION = {"status": "WAITING", "incoming": {"link": "prerequisite", "all": {"status": "OK"}}}


# ---------------------------------------------------------------------------
# Déclaration : briques, options, évènements, liens, réglages
# ---------------------------------------------------------------------------


def _ends(item: dict, name: str, types: list[str], report: Report, p: str) -> list[str]:
    raw = item.get(name)
    if raw is None:
        return list(types)
    wanted = as_list(raw)
    if not wanted or any(t not in types for t in wanted):
        report.error(
            f"{p}.{name}",
            "unknown_brick",
            f"« {name} » liste les types de briques que ce lien relie.",
            received=raw,
            expected=types,
        )
        return list(types)
    return wanted


MAX_LINK_OPTIONS = 4


def _links(raw, types: list[str], report: Report, path: str) -> list[dict]:
    if raw in (None, []):
        return []
    if not isinstance(raw, list) or len(raw) > MAX_LINK_TYPES:
        report.error(path, "type", f"« links » : {MAX_LINK_TYPES} types de liens au plus {{type, label}}.")
        return []
    out, seen = [], set()
    for i, item in enumerate(raw):
        p = f"{path}[{i}]"
        kind = _key(item, "type", seen, report, p, "Un type de lien")
        if kind is None:
            continue
        label = _label(item, report, p, kind, 40)
        link = {
            "type": kind,
            "label": label,
            "reverse": _label(item, report, p, "", 40, "reverse"),
            "from": _ends(item, "from", types, report, p),
            "to": _ends(item, "to", types, report, p),
        }
        # Absents sinon : une déclaration sans options de lien ne change pas d'un octet.
        options = _choices(
            item.get("options"), report, f"{p}.options", "Une option de lien", MAX_LINK_OPTIONS
        )
        if options:
            link["options"] = options
        if item.get("request") is True:
            link["request"] = True
        out.append(link)
    return out


# ---------------------------------------------------------------------------
# Conditions : un vocabulaire fermé
# ---------------------------------------------------------------------------


@dataclass
class Vocabulary:
    """Ce qu'une condition a le droit de nommer."""

    statuses: set[str]
    types: list[str]
    options: dict[str, list] = field(default_factory=dict)  # option → valeurs, tous types confondus
    events: set[str] = field(default_factory=set)
    links: set[str] = field(default_factory=set)
    settings: dict[str, list] = field(default_factory=dict)
    link_options: dict[str, list] = field(
        default_factory=dict
    )  # option de lien → valeurs, tous liens confondus


def vocabulary(bricks: list[dict], links: list[dict], settings: list[dict], statuses: set[str]) -> Vocabulary:
    voc = Vocabulary(statuses=statuses, types=[b["type"] for b in bricks])
    for brick in bricks:
        for option in brick["options"]:
            voc.options.setdefault(option["key"], [])
            voc.options[option["key"]] += [
                v for v in option["values"] if not among(v, voc.options[option["key"]])
            ]
        voc.events |= {e["key"] for e in brick["events"]}
    voc.links = {link["type"] for link in links}
    for link in links:
        for option in link.get("options", []):
            voc.link_options.setdefault(option["key"], [])
            voc.link_options[option["key"]] += [
                v for v in option["values"] if not among(v, voc.link_options[option["key"]])
            ]
    voc.settings = {s["key"]: s["values"] for s in settings}
    return voc


def _known(values, allowed, report: Report, p: str, code: str, what: str) -> bool:
    wanted = as_list(values)
    if wanted and all(isinstance(v, str) and v in allowed for v in wanted):
        return True
    report.error(p, code, f"{what} inconnu.", received=values, expected=sorted(allowed))
    return False


def _check_quantified(expected, voc: Vocabulary, report: Report, p: str, depth: int, scope: str) -> bool:
    """Voisins directs (`incoming`, `outgoing`), toute la chaîne (`upstream`, `downstream`), ou toute la
    situation (`elements`)."""
    used = [q for q in (*QUANTIFIERS, "count") if isinstance(expected, dict) and q in expected]
    extra = "type" if scope == "elements" else "link"
    counted = used == ["count"]
    if len(used) != 1 or set(expected) - {used[0], extra, *(["where"] if counted else [])}:
        report.error(
            p,
            "type",
            f"S'écrit {{{extra}?, all | any | none: condition}}, ou {{{extra}?, count, where?}} : un seul "
            "quantificateur.",
            received=expected,
            example={"all": {"status": "OK"}},
        )
        return False
    ok = True
    if extra in expected:
        allowed = voc.types if scope == "elements" else voc.links
        ok = _known(expected[extra], allowed, report, f"{p}.{extra}", "unknown_" + extra, "Nom")
    via = scope in ("incoming", "outgoing")  # un voisin direct : le lien traversé se lit (`link_option`)
    if counted:
        ok = check_count(expected["count"], report, f"{p}.count", voc.settings) and ok
        if "where" in expected:
            ok = check_condition(expected["where"], voc, report, f"{p}.where", depth + 1, True, via) and ok
        return ok
    return check_condition(expected[used[0]], voc, report, f"{p}.{used[0]}", depth + 1, True, via) and ok


def _check_since(expected, voc: Vocabulary, report: Report, p: str) -> bool:
    """Depuis combien de pas la brique est dans son état : un entier, ou une comparaison d'ordre à un nombre,
    à un réglage numérique ou à une option numérique de la brique ({"gte": {"option": "duree"}})."""
    if isinstance(expected, int) and not isinstance(expected, bool) and expected >= 0:
        return True
    op, operand = (
        next(iter(expected.items())) if isinstance(expected, dict) and len(expected) == 1 else ("", None)
    )
    option = operand.get("option") if isinstance(operand, dict) and len(operand) == 1 else None
    if op in ORDERED and isinstance(option, str):
        values = voc.options.get(option)
        if values is None:
            report.error(
                f"{p}.{op}.option", "unknown_option", "Option inconnue.", expected=sorted(voc.options)
            )
            return False
        if not all(is_number(v) for v in values):
            report.error(f"{p}.{op}.option", "not_numeric", f"L'option « {option} » n'a pas que des nombres.")
            return False
        return True
    if op in ORDERED and (is_number(operand) or setting_ref(operand)):
        return _check_pairs(
            {"since": expected}, {"since": Numbers()}, report, p.rsplit(".", 1)[0], "since", voc.settings
        )
    report.error(
        p,
        "type",
        "« since » : un nombre de pas, ou une comparaison à un nombre, à un réglage ou à une option.",
        received=expected,
        example={"gte": {"option": "duree"}},
    )
    return False


def check_condition(
    cond, voc: Vocabulary, report: Report, path: str, depth: int = 0, element: bool = True, via: bool = False
) -> bool:
    """Vérifie une condition. `element` : la condition porte sur un élément (sinon, sur la situation) ;
    `via` : elle porte sur un voisin direct, atteint par un lien dont les options se lisent."""
    if not isinstance(cond, dict) or not cond:
        report.error(path, "type", "Une condition est un objet non vide.", example=EXAMPLE_CONDITION)
        return False
    if depth > MAX_DEPTH:
        report.error(path, "too_deep", f"Une condition s'emboîte sur {MAX_DEPTH} niveaux au plus.")
        return False
    ok = True
    for key, expected in cond.items():
        p = f"{path}.{key}"
        if key in ELEMENT_TESTS and not element:
            report.error(
                p, "no_element", "Ce test porte sur un élément : ici, la condition porte sur la situation."
            )
            ok = False
        elif key == "status":
            ok &= _known(expected, voc.statuses, report, p, "unknown_status", "Statut")
        elif key == "type":
            ok &= _known(expected, voc.types, report, p, "unknown_brick", "Type de brique")
        elif key == "event":
            ok &= _known(expected, voc.events, report, p, "unknown_event", "Évènement")
        elif key == "option":
            ok &= _check_pairs(expected, voc.options, report, p, "option", voc.settings)
        elif key == "setting":
            ok &= _check_pairs(expected, voc.settings, report, p, "setting", voc.settings)
        elif key == "since":
            ok &= _check_since(expected, voc, report, p)
        elif key == "link_option":
            if via:
                ok &= _check_pairs(expected, voc.link_options, report, p, "link_option", voc.settings)
            else:
                report.error(
                    p,
                    "no_link",
                    "« link_option » porte sur le lien traversé : dans incoming ou outgoing seulement.",
                )
                ok = False
        elif key in (*NEIGHBOURS, "elements"):
            ok &= _check_quantified(expected, voc, report, p, depth, key)
        elif key in ("all", "any"):
            fine = isinstance(expected, list) and 1 <= len(expected) <= 12
            if not fine:
                report.error(p, "type", f"« {key} » prend une liste de 1 à 12 conditions.")
            for i, item in enumerate(expected if fine else []):
                ok &= check_condition(item, voc, report, f"{p}[{i}]", depth + 1, element, via)
            ok &= fine
        elif key == "not":
            ok &= check_condition(expected, voc, report, p, depth + 1, element, via)
        else:
            tests = [*ELEMENT_TESTS, *SHARED_TESTS, *(["link_option"] if via else [])]
            report.error(p, "unknown_test", "Test inconnu.", expected=tests)
            ok = False
    return ok


# ---------------------------------------------------------------------------
# Déclaration : règles et résultat
# ---------------------------------------------------------------------------


def _rules(raw, voc: Vocabulary, report: Report, path: str) -> list[dict]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_RULES:
        report.error(
            path,
            "type",
            f"« rules » : de 1 à {MAX_RULES} règles {{key, title, when, then}}, la plus prioritaire d'abord.",
            example=EXAMPLE["rules"],
        )
        return []
    out, seen = [], set()
    for i, item in enumerate(raw):
        p = f"{path}[{i}]"
        key = _key(item, "key", seen, report, p, "Une règle")
        if key is None:
            continue
        title = item.get("title")
        if not (_is_str(title, 160) and title.strip()):
            report.error(
                f"{p}.title", "required", "Une règle dit en une phrase ce qu'elle fait (160 caractères)."
            )
            continue
        on = as_list(item["on"]) if item.get("on") is not None else list(voc.types)
        if not _known(on, voc.types, report, f"{p}.on", "unknown_brick", "Type de brique"):
            continue
        fine = check_condition(item.get("when"), voc, report, f"{p}.when")
        if item.get("then") not in voc.statuses:
            report.error(
                f"{p}.then",
                "unknown_status",
                "« then » est le statut que prend l'élément.",
                received=item.get("then"),
                expected=sorted(voc.statuses),
            )
            fine = False
        if fine:
            out.append(
                {"key": key, "title": title.strip(), "on": on, "when": item["when"], "then": item["then"]}
            )
    return out


def _outcomes(raw, voc: Vocabulary, report: Report, path: str) -> list[dict]:
    if raw in (None, []):
        return []
    if not isinstance(raw, list) or len(raw) > MAX_OUTCOMES or not all(isinstance(o, dict) for o in raw):
        report.error(path, "type", f"« outcome » : {MAX_OUTCOMES} résultats au plus {{when, label, status}}.")
        return []
    out = []
    for i, item in enumerate(raw):
        p = f"{path}[{i}]"
        label = item.get("label")
        if not (_is_str(label, 200) and label.strip()):
            report.error(f"{p}.label", "required", "Un résultat a un libellé (200 caractères au plus).")
            continue
        entry: dict[str, Any] = {"label": label.strip()}
        if item.get("when") is not None:
            if not check_condition(item["when"], voc, report, f"{p}.when", element=False):
                continue
            entry["when"] = item["when"]
        if item.get("status") is not None:
            if item["status"] not in voc.statuses:
                report.error(f"{p}.status", "unknown_status", "Statut inconnu.", received=item["status"])
                continue
            entry["status"] = item["status"]
        out.append(entry)
    return out


MAX_RESOURCES = 6
MAX_PLACES = 50
POLICIES = ("order", "key")
EXAMPLE_RESOURCE = {
    "key": "postes",
    "label": "Postes",
    "places": {"setting": "capacite"},
    "held": ["EN_COURS"],
}


def _places(raw, settings: list[dict], report: Report, p: str):
    """Le nombre de places : un entier, ou un réglage numérique de l'étude."""
    if isinstance(raw, int) and not isinstance(raw, bool) and 1 <= raw <= MAX_PLACES:
        return raw
    key = setting_ref(raw)
    numeric = {s["key"]: s for s in settings if all(is_number(v) for v in values_of(s))}
    if key is not None and key in numeric:
        return raw
    report.error(
        p,
        "type",
        f'« places » : un entier de 1 à {MAX_PLACES}, ou un réglage numérique {{"setting": clé}}.',
        received=raw,
        example=EXAMPLE_RESOURCE["places"],
    )
    return None


def _resources(raw, settings: list[dict], voc: Vocabulary, report: Report, path: str) -> list[dict]:
    """Les ressources à places que l'étude déclare : au plus `places` briques à la fois dans les états de
    `held`, attribuées selon `policy` quand plusieurs se présentent au même pas."""
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > MAX_RESOURCES:
        report.error(
            path, "type", f"« resources » : {MAX_RESOURCES} ressources au plus.", example=[EXAMPLE_RESOURCE]
        )
        return []
    out, seen = [], set()
    for i, item in enumerate(raw):
        p = f"{path}[{i}]"
        key = _key(item, "key", seen, report, p, "Une ressource") if isinstance(item, dict) else None
        if key is None:
            continue
        places = _places(item.get("places"), settings, report, f"{p}.places")
        held = as_list(item.get("held"))
        fine = _known(held, voc.statuses, report, f"{p}.held", "unknown_status", "Statut")
        policy = item.get("policy", "order")
        if policy not in POLICIES:
            report.error(f"{p}.policy", "enum", "Politique inconnue.", received=policy, expected=POLICIES)
            fine = False
        if places is not None and fine:
            label = _label(item, report, p, key, 60)
            out.append({"key": key, "label": label, "places": places, "held": held, "policy": policy})
    return out


def _check_takes(rules: list[dict], raw_rules, resources: list[dict], report: Report, path: str) -> None:
    """Une règle qui « prend une place » nomme une ressource, et l'état qu'elle donne tient cette place."""
    by_key = {r["key"]: r for r in resources}
    raw_by_key = {item.get("key"): item for item in raw_rules if isinstance(item, dict)}
    for n, rule in enumerate(rules):
        takes = raw_by_key.get(rule["key"], {}).get("takes")
        if takes is None:
            continue
        p = f"{path}[{n}].takes"
        if takes not in by_key:
            report.error(
                p, "unknown_resource", "Ressource inconnue.", received=takes, expected=sorted(by_key)
            )
        elif rule["then"] not in by_key[takes]["held"]:
            report.error(p, "type", "L'état que donne la règle doit tenir une place de cette ressource.")
        else:
            rule["takes"] = takes


def normalize(raw: Any, status_keys: set[str], report: Report, path: str = "workshop") -> dict:
    """La déclaration d'atelier d'une étude, validée. Rend {} quand l'étude n'en déclare pas."""
    if raw in (None, {}):
        return {}
    if not isinstance(raw, dict):
        report.error(
            path, "type", "« workshop » est un objet {bricks, links, rules, outcome}.", example=EXAMPLE
        )
        return {}
    known = {"family", "title", "bricks", "links", "settings", "rules", "outcome", "max_steps", "resources"}
    unknown = set(raw) - known
    if unknown:
        report.error(path, "unknown_field", "Champ inconnu dans « workshop ».", received=sorted(unknown))
    bricks = _bricks(raw.get("bricks"), status_keys, report, f"{path}.bricks")
    links = _links(raw.get("links"), [b["type"] for b in bricks], report, f"{path}.links")
    settings = _choices(raw.get("settings"), report, f"{path}.settings", "Un réglage", MAX_SETTINGS, True)
    voc = vocabulary(bricks, links, settings, status_keys)
    limit = raw.get("max_steps", DEFAULT_RUN_STEPS)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_RUN_STEPS:
        report.error(f"{path}.max_steps", "type", f"Un entier de 1 à {MAX_RUN_STEPS}.", received=limit)
        limit = DEFAULT_RUN_STEPS
    out = {
        "title": _label(raw, report, path, "", 80, "title"),
        "bricks": bricks,
        "links": links,
        "settings": settings,
        "rules": _rules(raw.get("rules"), voc, report, f"{path}.rules") if bricks else [],
        "outcome": _outcomes(raw.get("outcome"), voc, report, f"{path}.outcome"),
        "max_steps": limit,
    }
    resources = _resources(raw.get("resources"), settings, voc, report, f"{path}.resources")
    if resources:  # absent sinon : une déclaration sans ressource ne change pas d'un octet
        out["resources"] = resources
    if isinstance(raw.get("rules"), list):
        _check_takes(out["rules"], raw["rules"], resources, report, f"{path}.rules")
    return out


def declared(decl: dict | None) -> bool:
    return bool(decl and decl.get("bricks") and decl.get("rules"))


# ---------------------------------------------------------------------------
# Situation : ce qu'une personne (ou une IA) a construit avec les briques de l'étude
# ---------------------------------------------------------------------------

LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # sans I ni O, qui se lisent comme des chiffres
EXAMPLE_SITUATION = {
    "elements": [
        {"id": "A", "type": "task", "events": ["echec"]},
        {"id": "B", "type": "task", "options": {"always_run": True}},
    ],
    "links": [{"from": "A", "to": "B", "type": "prerequisite"}],
    "settings": {"stop_on_error": True},
}


def _element(item, bricks: dict, seen: set, events: dict, report: Report, p: str) -> dict | None:
    key = _key(item, "id", seen, report, p, "Un élément")
    if key is None:
        return None
    brick = bricks.get(item.get("type"))
    if brick is None:
        seen.discard(key)
        report.error(
            f"{p}.type",
            "unknown_brick",
            "Type de brique inconnu.",
            received=item.get("type"),
            expected=list(bricks),
        )
        return None
    wanted = item.get("events") or []
    allowed = [e["key"] for e in brick["events"]]
    if not isinstance(wanted, list) or any(e not in allowed for e in wanted):
        report.error(
            f"{p}.events",
            "unknown_event",
            "Évènement inconnu pour cette brique.",
            received=wanted,
            expected=allowed,
        )
        wanted = [e for e in wanted if e in allowed] if isinstance(wanted, list) else []
    if wanted:
        events[key] = [e for e in allowed if e in wanted]
    return {
        "id": key,
        "label": _label(item, report, p, f"{brick['label']} {key}", 40),
        "type": brick["type"],
        "options": _chosen(brick["options"], item.get("options"), report, f"{p}.options"),
    }


def _situation_link(item, decl: dict, elements: dict, seen: set, report: Report, p: str) -> dict | None:
    kinds = {link["type"]: link for link in decl["links"]}
    if not isinstance(item, dict):
        report.error(
            p, "type", "Un lien est un objet {from, to, type}.", example=EXAMPLE_SITUATION["links"][0]
        )
        return None
    kind = item.get("type") or (next(iter(kinds)) if len(kinds) == 1 else None)
    a, b = item.get("from"), item.get("to")
    if kind not in kinds:
        report.error(
            f"{p}.type", "unknown_link", "Type de lien inconnu.", received=kind, expected=list(kinds)
        )
    elif a not in elements or b not in elements or a == b:
        report.error(
            p, "unknown_element", "Un lien relie deux éléments distincts de la situation.", received=item
        )
    elif elements[a]["type"] not in kinds[kind]["from"] or elements[b]["type"] not in kinds[kind]["to"]:
        report.error(
            p,
            "forbidden_link",
            f"L'étude ne permet pas ce lien « {kinds[kind]['label']} » entre ces deux types de briques.",
            received=item,
        )
    elif (a, kind, b) in seen:
        report.error(p, "duplicate", "Ce lien est posé deux fois.", received=item)
    else:
        seen.add((a, kind, b))
        link = {"from": a, "to": b, "type": kind}
        if kinds[kind].get("options"):
            link["options"] = _chosen(kinds[kind]["options"], item.get("options"), report, f"{p}.options")
        return link
    return None


def situation(decl: dict, raw: Any, report: Report, path: str = "situation") -> dict:
    """Une situation construite, vérifiée contre ce que l'étude déclare. Ce qui est invalide est signalé dans
    le rapport et écarté : l'API refuse alors la demande, l'interface garde le reste."""
    out: dict[str, Any] = {"elements": [], "links": [], "events": {}, "settings": {}}
    if not isinstance(raw, dict):
        report.error(
            path, "type", "Une situation est un objet {elements, links, settings}.", example=EXAMPLE_SITUATION
        )
        raw = {}
    out["settings"] = _chosen(decl["settings"], raw.get("settings"), report, f"{path}.settings")
    items = raw.get("elements") or []
    if not isinstance(items, list) or len(items) > MAX_ELEMENTS:
        report.error(
            f"{path}.elements", "max_items", f"{MAX_ELEMENTS} éléments au plus.", example=EXAMPLE_SITUATION
        )
        items = items[:MAX_ELEMENTS] if isinstance(items, list) else []
    bricks = {b["type"]: b for b in decl["bricks"]}
    seen: set = set()
    for i, item in enumerate(items):
        element = _element(item, bricks, seen, out["events"], report, f"{path}.elements[{i}]")
        if element:
            out["elements"].append(element)
    links = raw.get("links") or []
    if not isinstance(links, list) or len(links) > MAX_SITUATION_LINKS:
        report.error(f"{path}.links", "max_items", f"{MAX_SITUATION_LINKS} liens au plus.")
        links = links[:MAX_SITUATION_LINKS] if isinstance(links, list) else []
    by_id = {e["id"]: e for e in out["elements"]}
    placed: set = set()
    for i, item in enumerate(links):
        link = _situation_link(item, decl, by_id, placed, report, f"{path}.links[{i}]")
        if link:
            out["links"].append(link)
    return out


def placed(decl: dict, query: dict[str, list[str]], letter: str, kind: str) -> list[str]:
    """Une brique qu'on vient de poser sur une autre (« on ») s'y enchaîne, par le premier lien que l'étude
    permet entre elles. Rend les liens à ajouter."""
    kinds = dict(raw.partition(":")[::2] for raw in query.get("e", []))
    source = (query.get("on") or [""])[-1]
    for link in decl["links"]:
        if kinds.get(source) in link["from"] and kind in link["to"]:
            return [f"{source}:{link['type']}:{letter}"]
    return []


def next_id(taken) -> str | None:
    """La lettre de la prochaine brique posée ; None quand la situation est pleine."""
    return next((letter for letter in LETTERS if letter not in taken), None)


def _typed(declared: list[dict], key: str, text: str):
    """La valeur déclarée qui s'écrit ainsi dans une adresse ; None si aucune."""
    item = next((d for d in declared if d["key"] == key), None)
    if item and "number" in item:  # option numérique (famille calcul) : un nombre dans les bornes
        try:
            number = float(text.replace(",", "."))
        except ValueError:
            return None
        number = int(number) if number == int(number) else number
        return number if item["number"]["min"] <= number <= item["number"]["max"] else None
    return next((v for v in item["values"] if text_of(v) == text), None) if item else None


def from_query(decl: dict, query: dict[str, list[str]]) -> dict:
    """La situation écrite dans une adresse, sous la forme qu'attend `situation`. Ce que l'adresse contient
    d'inconnu est ignoré : une adresse abîmée donne une situation plus petite, pas une erreur.

    `e=A:task` pose une brique ; `n.A=…` la nomme ; `o.A.option=valeur` règle une option ; `ev=A:echec`
    provoque un évènement ; `l=A:lien:B` relie ; `r.reglage=valeur` fixe un réglage."""
    bricks = {b["type"]: b for b in decl["bricks"]}
    elements = []
    for raw in query.get("e", []):
        key, _, kind = raw.partition(":")
        if kind in bricks and ID_RE.match(key) and all(e["id"] != key for e in elements):
            element: dict[str, Any] = {"id": key, "type": kind, "options": {}, "events": []}
            name = (query.get(f"n.{key}") or [""])[-1].strip()[:40]
            if name:
                element["label"] = name
            for option in bricks[kind]["options"]:
                value = _typed(
                    bricks[kind]["options"],
                    option["key"],
                    (query.get(f"o.{key}.{option['key']}") or [""])[-1],
                )
                if value is not None:
                    element["options"][option["key"]] = value
            elements.append(element)
    by_id = {e["id"]: e for e in elements}
    for raw in query.get("ev", []):
        key, _, event = raw.partition(":")
        if key in by_id and event in [e["key"] for e in bricks[by_id[key]["type"]]["events"]]:
            by_id[key]["events"].append(event)
    links = []
    kinds = {link["type"]: link for link in decl["links"]}
    for raw in query.get("l", []):
        parts = raw.split(":")
        if len(parts) == 3:
            link: dict[str, Any] = {"from": parts[0], "type": parts[1], "to": parts[2]}
            declared = kinds.get(parts[1], {}).get("options", [])
            values = {
                o["key"]: _typed(declared, o["key"], (query.get(f"lo.{raw}.{o['key']}") or [""])[-1])
                for o in declared
            }
            if declared:
                link["options"] = {k: v for k, v in values.items() if v is not None}
            links.append(link)
    settings = {}
    for item in decl["settings"]:
        value = _typed(decl["settings"], item["key"], (query.get(f"r.{item['key']}") or [""])[-1])
        if value is not None:
            settings[item["key"]] = value
    return {"elements": elements, "links": links, "settings": settings}


def to_query(decl: dict, sit: dict) -> list[tuple[str, str]]:
    """L'adresse d'une situation : seulement ce qui s'écarte des valeurs par défaut, dans un ordre stable."""
    bricks = {b["type"]: b for b in decl["bricks"]}
    out = [("e", f"{e['id']}:{e['type']}") for e in sit["elements"]]
    for element in sit["elements"]:
        brick = bricks[element["type"]]
        if element["label"] != f"{brick['label']} {element['id']}":
            out.append((f"n.{element['id']}", element["label"]))
        out += [
            (f"o.{element['id']}.{o['key']}", text_of(element["options"][o["key"]]))
            for o in brick["options"]
            if not same(element["options"][o["key"]], o["default"])
        ]
    out += [("ev", f"{key}:{event}") for key, events in sit["events"].items() for event in events]
    kinds = {link["type"]: link for link in decl["links"]}
    for link in sit["links"]:
        value = f"{link['from']}:{link['type']}:{link['to']}"
        out.append(("l", value))
        out += [
            (f"lo.{value}.{o['key']}", text_of(link["options"][o["key"]]))
            for o in kinds[link["type"]].get("options", [])
            if not same(link["options"][o["key"]], o["default"])
        ]
    out += [
        (f"r.{item['key']}", text_of(sit["settings"][item["key"]]))
        for item in decl["settings"]
        if not same(sit["settings"][item["key"]], item["default"])
    ]
    return out


# ---------------------------------------------------------------------------
# Moteur : appliquer la table de règles pas après pas
# ---------------------------------------------------------------------------


@dataclass
class World:
    """Une situation à un instant : les éléments, leurs liens, ce qu'on y a provoqué, leurs états."""

    elements: dict[str, dict]
    incoming: dict[str, list[tuple[str, str]]]  # élément → [(voisin à l'origine du lien, type de lien)]
    outgoing: dict[str, list[tuple[str, str]]]
    events: dict[str, set[str]]
    settings: dict[str, Any]
    states: dict[str, str]
    link_options: dict[tuple, dict] = field(default_factory=dict)  # (de, type, vers) → options du lien
    ages: dict[str, int] = field(default_factory=dict)  # pas passés par chaque brique dans son état


def _quantified(expected: dict, world: World, items: list[tuple[dict, dict | None]]) -> bool:
    """`items` : les briques visées, chacune avec les options du lien par lequel on l'atteint (ou None)."""
    if "count" in expected:
        where = expected.get("where")
        found = sum(1 for item, via in items if where is None or holds(where, world, item, via))
        return matches(found, expected["count"], world.settings)
    if "all" in expected:
        return all(holds(expected["all"], world, item, via) for item, via in items)
    if "any" in expected:
        return any(holds(expected["any"], world, item, via) for item, via in items)
    return not any(holds(expected["none"], world, item, via) for item, via in items)


def _neighbours(world: World, element: dict, side: str, expected: dict) -> list[tuple[dict, dict | None]]:
    """Les voisins d'un élément : directs (`incoming`, `outgoing`) ou de proche en proche (`upstream`,
    `downstream`), par les liens du type demandé. Un circuit fermé ne fait pas tourner en rond."""
    wanted = as_list(expected["link"]) if "link" in expected else None
    pairs = world.incoming if side in ("incoming", "upstream") else world.outgoing
    found: dict[str, dict | None] = {}
    queue = [element["id"]]
    while queue:
        here = queue.pop(0)
        for other, kind in pairs.get(here, []):
            if (wanted is None or kind in wanted) and other not in found and other != element["id"]:
                ends = (other, kind, here) if side == "incoming" else (here, kind, other)
                found[other] = world.link_options.get(ends, {}) if side in ("incoming", "outgoing") else None
                if side in ("upstream", "downstream"):
                    queue.append(other)
    return [(world.elements[key], via) for key, via in found.items()]


def holds(cond: dict, world: World, element: dict | None, via: dict | None = None) -> bool:
    """Vrai si la condition est satisfaite. `element` vaut None quand elle porte sur toute la situation ;
    `via` : les options du lien par lequel on a atteint cette brique (voisin direct)."""
    for key, expected in cond.items():
        if key == "status":
            fine = world.states[element["id"]] in as_list(expected)
        elif key == "type":
            fine = element["type"] in as_list(expected)
        elif key == "event":
            fine = bool(world.events.get(element["id"], set()) & set(as_list(expected)))
        elif key == "option":
            fine = pairs_hold(expected, element["options"], world.settings)
        elif key == "setting":
            fine = pairs_hold(expected, world.settings, world.settings)
        elif key in NEIGHBOURS:
            fine = _quantified(expected, world, _neighbours(world, element, key, expected))
        elif key == "elements":
            wanted = as_list(expected["type"]) if "type" in expected else None
            fine = _quantified(
                expected,
                world,
                [(e, None) for e in world.elements.values() if wanted is None or e["type"] in wanted],
            )
        elif key == "link_option":
            fine = via is not None and pairs_hold(expected, via, world.settings)
        elif key == "since":
            fine = _since_holds(expected, world.ages.get(element["id"], 0), element, world)
        elif key == "all":
            fine = all(holds(c, world, element, via) for c in expected)
        elif key == "any":
            fine = any(holds(c, world, element, via) for c in expected)
        else:  # not
            fine = not holds(expected, world, element, via)
        if not fine:
            return False
    return True


def _since_holds(expected, age: int, element: dict, world: World) -> bool:
    if not isinstance(expected, dict):
        return age == expected
    op, operand = next(iter(expected.items()))
    if isinstance(operand, dict) and "option" in operand:
        operand = element["options"].get(operand["option"])
    return operand is not None and matches(age, {op: operand}, world.settings)


def world_of(decl: dict, situation: dict, default_status: str, start: dict | None = None) -> World:
    """Au départ, chaque brique dans l'état de départ de son type, sinon le statut par défaut — ou dans l'état
    que donne `start` (un cas rejoué part de son propre état de départ)."""
    initial = {b["type"]: b.get("initial") or default_status for b in decl["bricks"]}
    elements = {e["id"]: e for e in situation["elements"]}
    incoming: dict[str, list] = {key: [] for key in elements}
    outgoing: dict[str, list] = {key: [] for key in elements}
    for link in situation["links"]:
        outgoing[link["from"]].append((link["to"], link["type"]))
        incoming[link["to"]].append((link["from"], link["type"]))
    return World(
        elements=elements,
        incoming=incoming,
        outgoing=outgoing,
        events={key: set(found) for key, found in situation["events"].items()},
        settings=situation["settings"],
        states={key: (start or {}).get(key) or initial[e["type"]] for key, e in elements.items()},
        link_options={
            (lk["from"], lk["type"], lk["to"]): lk["options"] for lk in situation["links"] if "options" in lk
        },
    )


def _proposed(decl: dict, world: World) -> list[dict]:
    """Ce que la table de règles propose de changer en un pas. Chaque élément suit la première règle qui lui
    correspond ; toutes les règles lisent l'état du pas précédent."""
    changes = []
    for key, element in world.elements.items():
        for rule in decl["rules"]:
            if element["type"] in rule["on"] and holds(rule["when"], world, element):
                if rule["then"] != world.states[key]:
                    change = {"id": key, "from": world.states[key], "to": rule["then"], "rule": rule["key"]}
                    by = _by(rule["when"], world, element)
                    if by:  # la demande : les voisins directs qui ont fait jouer la règle
                        change["by"] = by
                    changes.append(change)
                break
    return changes


def _by(when: dict, world: World, element: dict) -> list[str]:
    """Les voisins directs qui satisfont un `any` ou un `count … where` de la condition : ceux dont vient la
    demande. Vide quand la règle ne tient pas à un voisin en particulier."""
    out: list[str] = []
    for side in ("incoming", "outgoing"):
        expected = when.get(side)
        inner = (expected or {}).get("any") or (expected or {}).get("where")
        if inner is None:
            continue
        for other, via in _neighbours(world, element, side, expected):
            if holds(inner, world, other, via) and other["id"] not in out:
                out.append(other["id"])
    return out


def places_of(resource: dict, world: World) -> tuple[int, int]:
    """(places, places occupées) d'une ressource, d'après l'état du pas précédent."""
    places = operand_of(resource["places"], world.settings)
    total = int(places) if is_number(places) else 0
    used = sum(1 for state in world.states.values() if state in resource["held"])
    return total, used


def _arbitrate(decl: dict, world: World, changes: list[dict]) -> tuple[list[dict], list[dict]]:
    """Les changements qui prennent une place, servis selon la politique de leur ressource, au plus les
    places libres ; les autres attendent (refusés pour ce pas, réexaminés au suivant). Une place libérée dans
    ce pas ne sert qu'au pas suivant."""
    takes = {r["key"]: r.get("takes") for r in decl["rules"]}
    order = list(world.elements)
    refused: list[dict] = []
    for resource in decl.get("resources", []):
        asking = [c for c in changes if takes.get(c["rule"]) == resource["key"]]
        if resource["policy"] == "key":
            asking.sort(key=lambda c: c["id"])
        else:
            asking.sort(key=lambda c: order.index(c["id"]))
        places, used = places_of(resource, world)
        for change in asking[max(places - used, 0) :]:
            refused.append({"id": change["id"], "rule": change["rule"], "resource": resource["key"]})
    gone = {(r["id"], r["rule"]) for r in refused}
    return [c for c in changes if (c["id"], c["rule"]) not in gone], refused


def _next(decl: dict, world: World) -> list[dict]:
    """Ce que la table de règles change en un pas, après l'attribution des places."""
    return _arbitrate(decl, world, _proposed(decl, world))[0]


def _uses_since(decl: dict) -> bool:
    """Une règle tient-elle à une durée (`since`) ? Sinon le temps n'avance jamais seul."""
    return '"since"' in json.dumps([r["when"] for r in decl["rules"]])


def _next_step(decl: dict, world: World, timed: bool) -> tuple[list[dict], list[dict], int]:
    """Le pas suivant : chaque brique a passé un pas de plus dans son état, puis les règles jouent. Si rien ne
    bouge et qu'une règle tient à une durée, le temps avance, pas à pas (au plus MAX_WAIT), jusqu'à ce qu'une
    règle joue ; le troisième terme compte ces pas d'attente."""
    passes = MAX_WAIT + 1 if timed else 1
    refused: list[dict] = []
    for waited in range(passes):
        for key in world.elements:
            world.ages[key] = world.ages.get(key, 0) + 1
        changes, refused = _arbitrate(decl, world, _proposed(decl, world))
        if changes:
            return changes, refused, waited
    for key in world.elements:  # rien ne viendra : le temps n'a avancé que d'un pas
        world.ages[key] -= passes - 1
    return [], refused, 0


def run(decl: dict, situation: dict, default_status: str, start: dict | None = None) -> dict:
    """Déroule la situation jusqu'à ce que plus rien ne bouge.

    Rend {steps: [{states, changes}], end: stable | loop | limit}. Le premier pas est la situation de départ.
    `loop` : la situation revient à un état déjà vu ; `limit` : le nombre de pas permis est atteint."""
    world = world_of(decl, situation, default_status, start)
    steps = [{"states": dict(world.states), "changes": []}]
    seen = [dict(world.states)]
    end = "stable"
    timed = _uses_since(decl)
    while True:
        changes, refused, waited = _next_step(decl, world, timed)
        if not changes:
            break
        if len(steps) > decl["max_steps"]:
            end = "limit"
            break
        for change in changes:
            world.states[change["id"]] = change["to"]
            world.ages[change["id"]] = 0
        extras = ({"refused": refused} if refused else {}) | ({"waited": waited} if waited else {})
        steps.append({"states": dict(world.states), "changes": changes} | extras)
        if world.states in seen:
            end = "loop"
            break
        seen.append(dict(world.states))
    return {"steps": steps, "end": end, "world": world}


def outcome_of(decl: dict, world: World) -> dict | None:
    """Le résultat d'ensemble : le premier résultat déclaré dont la condition est satisfaite."""
    for item in decl.get("outcome") or []:
        if "when" not in item or holds(item["when"], world, None):
            return {k: v for k, v in item.items() if k != "when"}
    return None


# ---------------------------------------------------------------------------
# De la situation déroulée à un cas ordinaire
# ---------------------------------------------------------------------------


def outcome(decl: dict, result: dict) -> dict | None:
    """Le résultat d'ensemble d'un déroulé : aucun tant que la situation ne s'est pas stabilisée (le dernier
    pas n'est alors qu'un arrêt, pas un aboutissement)."""
    return outcome_of(decl, result["world"]) if result["end"] == "stable" else None


def plan(decl: dict) -> dict:
    """Ce que le dessin d'une situation doit savoir de plus : rien pour des éléments reliés."""
    return {}


SIDES = {
    "incoming": "ses liens entrants",
    "outgoing": "ses liens sortants",
    "upstream": "ce qui le précède",
    "downstream": "ce qui le suit",
    "elements": "l'ensemble des briques",
}


def _missing(key: str, expected, decl: dict, element: dict) -> str:
    """Ce qui manque, en une phrase, pour qu'un test d'une condition soit vrai."""
    if key == "event":
        return "l'évènement « " + " » ou « ".join(map(str, as_list(expected))) + " » n'a pas eu lieu"
    if key in ("option", "setting"):
        brick = next(b for b in decl["bricks"] if b["type"] == element["type"])
        declared = brick["options"] if key == "option" else decl.get("settings", [])
        labels = {item["key"]: item["label"] for item in declared}
        names = ", ".join(f"« {labels.get(name, name)} »" for name in expected)
        what = "l'option" if key == "option" else "le réglage"
        return f"{what} {names} n'a pas la valeur voulue"
    if key in SIDES:
        return f"la condition sur {SIDES[key]} n'est pas remplie"
    if key == "status":
        return "son état n'est pas celui que la règle attend"
    if key == "since":
        return "elle n'est pas encore restée assez longtemps dans cet état"
    return "la condition composée de la règle n'est pas remplie"


def _waiting_for_places(decl: dict, world: World) -> dict[str, dict]:
    """Les briques dont la règle jouerait, mais qui n'ont pas eu de place."""
    if not decl.get("resources"):
        return {}
    titles = {r["key"]: r["title"] for r in decl["rules"]}
    resources = {r["key"]: r for r in decl["resources"]}
    out = {}
    for refusal in _arbitrate(decl, world, _proposed(decl, world))[1]:
        resource = resources[refusal["resource"]]
        places, used = places_of(resource, world)
        out[refusal["id"]] = {
            "rule": refusal["rule"],
            "title": titles[refusal["rule"]],
            "test": "resource",
            "resource": resource["key"],
            "why": f"aucune place libre pour « {resource['label']} » ({used} sur {places} occupées)",
        }
    return out


def waiting(decl: dict, world: World) -> dict[str, dict]:
    """Pour chaque brique qu'une règle pourrait encore faire changer, la règle la plus proche de jouer et ce
    qui lui manque (la première condition fausse). Une brique qu'aucune règle ne fait sortir de son état n'y
    figure pas : rien ne l'attend. Au plus une raison par brique."""
    out = _waiting_for_places(decl, world)
    for key, element in world.elements.items():
        if key in out:
            continue
        state, best = world.states[key], None
        for rule in decl["rules"]:
            if element["type"] not in rule["on"] or rule["then"] == state:
                continue
            when = rule["when"]
            if "status" in when and state not in as_list(when["status"]):
                continue
            failing = [k for k, v in when.items() if not holds({k: v}, world, element)]
            if failing and (best is None or len(failing) < len(best[1])):
                best = (rule, failing)
        if best:
            rule, failing = best
            first = failing[0]
            out[key] = {
                "rule": rule["key"],
                "title": rule["title"],
                "test": first,
                "why": _missing(first, rule["when"][first], decl, element),
            }
    return out


def _asks(decl: dict, when: dict) -> bool:
    """La règle répond-elle à une demande : une condition sur un voisin direct, par un lien `request` ?"""
    requests = {link["type"] for link in decl["links"] if link.get("request")}
    return any(
        side in when and "link" in when[side] and set(as_list(when[side]["link"])) <= requests
        for side in ("incoming", "outgoing")
    )


def no_effect(decl: dict, world: World) -> dict[str, dict]:
    """Les demandes restées sans effet : une règle qui répond à une demande (lien `request`) a toutes ses
    conditions remplies sauf l'état de la brique, qui a déjà changé. Au plus une par brique."""
    out = {}
    for key, element in world.elements.items():
        state = world.states[key]
        for rule in decl["rules"]:
            when = rule["when"]
            if element["type"] not in rule["on"] or "status" not in when or state in as_list(when["status"]):
                continue
            rest = {k: v for k, v in when.items() if k != "status"}
            if _asks(decl, when) and holds(rest, world, element):
                out[key] = {
                    "rule": rule["key"],
                    "title": rule["title"],
                    "by": _by(when, world, element),
                    "state": state,
                    "why": "la demande n'a pas d'effet : la brique a déjà quitté l'état que la règle attend",
                }
                break
    return out


def extra(decl: dict, result: dict) -> dict:
    """Ce que cette famille ajoute à la réponse d'un déroulé : pour une situation stabilisée, ce qui retient
    chaque brique qui attend encore (`waiting`) et les demandes restées sans effet (`no_effect`)."""
    if result["end"] != "stable":
        return {}
    found = {"waiting": waiting(decl, result["world"]), "no_effect": no_effect(decl, result["world"])}
    return {name: value for name, value in found.items() if value}


END_NOTES = {
    "stable": "",
    "loop": "La situation revient à un état déjà vu : elle ne se stabilise pas. Le déroulé s'arrête là.",
    "limit": "Le nombre de pas permis est atteint sans que la situation se stabilise.",
}


def _step(decl: dict, situation: dict, step: dict) -> dict:
    """Un pas du déroulé, écrit comme une étape de cas : ce qui change, et la règle qui le fait changer."""
    rules = {r["key"]: r for r in decl["rules"]}
    labels = {e["id"]: e["label"] for e in situation["elements"]}
    used = list(dict.fromkeys(c["rule"] for c in step["changes"]))
    by_rule = {key: [labels[c["id"]] for c in step["changes"] if c["rule"] == key] for key in used}
    if len(used) == 1:
        title = rules[used[0]]["title"]
        note = f"Règle {used[0]}, appliquée à {_listed(by_rule[used[0]])}."
    else:
        title = f"{len(used)} règles s'appliquent en même temps"
        note = " ".join(f"Règle {key}, pour {_listed(by_rule[key])} : {rules[key]['title']}." for key in used)
    if step.get("waited"):
        note = f"Après {step['waited']} pas sans changement. " + note
    if step.get("refused"):
        resources = {r["key"]: r["label"] for r in decl.get("resources", [])}
        waiting = {}
        for refusal in step["refused"]:
            waiting.setdefault(resources[refusal["resource"]], []).append(labels[refusal["id"]])
        note += "".join(
            f" {_listed(names)} attend{'ent' if len(names) > 1 else ''} une place : {label} au complet."
            for label, names in waiting.items()
        )
    return {"title": title[:200], "note": note[:1900], "changes": {c["id"]: c["to"] for c in step["changes"]}}


def _listed(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " et " + names[-1]


def to_case(decl: dict, situation: dict, result: dict, default_status: str) -> dict:
    """La situation construite et son déroulé, sous la forme d'un cas que le site sait valider et dessiner."""
    first = result["steps"][0]["states"]
    steps = [{"title": "Situation de départ", "note": "Aucune règle n'a encore été appliquée."}]
    steps += [_step(decl, situation, step) for step in result["steps"][1:]]
    if result["end"] != "stable":
        steps[-1]["note"] = (steps[-1].get("note", "") + " " + END_NOTES[result["end"]]).strip()
    elif len(steps) == 1:
        steps[0]["note"] = "Aucune règle ne s'applique à cette situation : rien ne bouge."
    case = {
        "key": "atelier",
        "title": decl.get("title") or "Situation construite",
        "family": "Atelier",
        "config": {key: value for key, value in situation["settings"].items()},
        "entities": [
            {"id": e["id"], "label": e["label"], "type": e["type"], "attrs": dict(e["options"])}
            for e in situation["elements"]
        ],
        "links": [dict(link) for link in situation["links"]],
        "initial": {key: status for key, status in first.items() if status != default_status},
        "steps": steps,
    }
    found = outcome(decl, result)
    if found:
        case["outcome"] = found
    return case
