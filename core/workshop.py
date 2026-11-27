"""Atelier : les règles qu'une étude déclare pour des éléments reliés, et le moteur qui les exécute.

L'étude déclare un vocabulaire (des types de briques, leurs options, les évènements qu'on peut y provoquer,
les liens permis, des réglages) et une table de règles : « quand telle condition sur l'élément, ses voisins,
ses options ou les réglages, alors tel état ». Le site applique cette table à chaque élément, pas après pas,
jusqu'à ce que plus rien ne bouge.

Pur : aucun accès à la base. Aucun code fourni par l'étude n'est exécuté : les conditions sont un
vocabulaire fermé que ce module compare à des valeurs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .casemodel import ID_RE, Report, _is_str
from .rules import among, as_list, check_count, matches, pairs_hold, same, text_of
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
ELEMENT_TESTS = ("status", "type", "option", "event", *NEIGHBOURS)
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
        out.append(
            {
                "type": kind,
                "label": label,
                "reverse": _label(item, report, p, "", 40, "reverse"),
                "from": _ends(item, "from", types, report, p),
                "to": _ends(item, "to", types, report, p),
            }
        )
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
    if counted:
        ok = check_count(expected["count"], report, f"{p}.count", voc.settings) and ok
        if "where" in expected:
            ok = check_condition(expected["where"], voc, report, f"{p}.where", depth + 1, True) and ok
        return ok
    return check_condition(expected[used[0]], voc, report, f"{p}.{used[0]}", depth + 1, True) and ok


def check_condition(
    cond, voc: Vocabulary, report: Report, path: str, depth: int = 0, element: bool = True
) -> bool:
    """Vérifie une condition. `element` : la condition porte sur un élément (sinon, sur la situation)."""
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
        elif key in (*NEIGHBOURS, "elements"):
            ok &= _check_quantified(expected, voc, report, p, depth, key)
        elif key in ("all", "any"):
            fine = isinstance(expected, list) and 1 <= len(expected) <= 12
            if not fine:
                report.error(p, "type", f"« {key} » prend une liste de 1 à 12 conditions.")
            for i, item in enumerate(expected if fine else []):
                ok &= check_condition(item, voc, report, f"{p}[{i}]", depth + 1, element)
            ok &= fine
        elif key == "not":
            ok &= check_condition(expected, voc, report, p, depth + 1, element)
        else:
            report.error(p, "unknown_test", "Test inconnu.", expected=[*ELEMENT_TESTS, *SHARED_TESTS])
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


def normalize(raw: Any, status_keys: set[str], report: Report, path: str = "workshop") -> dict:
    """La déclaration d'atelier d'une étude, validée. Rend {} quand l'étude n'en déclare pas."""
    if raw in (None, {}):
        return {}
    if not isinstance(raw, dict):
        report.error(
            path, "type", "« workshop » est un objet {bricks, links, rules, outcome}.", example=EXAMPLE
        )
        return {}
    unknown = set(raw) - {"family", "title", "bricks", "links", "settings", "rules", "outcome", "max_steps"}
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
    return {
        "title": _label(raw, report, path, "", 80, "title"),
        "bricks": bricks,
        "links": links,
        "settings": settings,
        "rules": _rules(raw.get("rules"), voc, report, f"{path}.rules") if bricks else [],
        "outcome": _outcomes(raw.get("outcome"), voc, report, f"{path}.outcome"),
        "max_steps": limit,
    }


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
        return {"from": a, "to": b, "type": kind}
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
    for raw in query.get("l", []):
        parts = raw.split(":")
        if len(parts) == 3:
            links.append({"from": parts[0], "type": parts[1], "to": parts[2]})
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
    out += [("l", f"{link['from']}:{link['type']}:{link['to']}") for link in sit["links"]]
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


def _quantified(expected: dict, world: World, items: list[dict]) -> bool:
    if "count" in expected:
        where = expected.get("where")
        found = sum(1 for item in items if where is None or holds(where, world, item))
        return matches(found, expected["count"], world.settings)
    if "all" in expected:
        return all(holds(expected["all"], world, item) for item in items)
    if "any" in expected:
        return any(holds(expected["any"], world, item) for item in items)
    return not any(holds(expected["none"], world, item) for item in items)


def _neighbours(world: World, element: dict, side: str, expected: dict) -> list[dict]:
    """Les voisins d'un élément : directs (`incoming`, `outgoing`) ou de proche en proche (`upstream`,
    `downstream`), par les liens du type demandé. Un circuit fermé ne fait pas tourner en rond."""
    wanted = as_list(expected["link"]) if "link" in expected else None
    pairs = world.incoming if side in ("incoming", "upstream") else world.outgoing
    found: list[str] = []
    queue = [element["id"]]
    while queue:
        for other, kind in pairs.get(queue.pop(0), []):
            if (wanted is None or kind in wanted) and other not in found and other != element["id"]:
                found.append(other)
                if side in ("upstream", "downstream"):
                    queue.append(other)
    return [world.elements[key] for key in found]


def holds(cond: dict, world: World, element: dict | None) -> bool:
    """Vrai si la condition est satisfaite. `element` vaut None quand elle porte sur toute la situation."""
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
                expected, world, [e for e in world.elements.values() if wanted is None or e["type"] in wanted]
            )
        elif key == "all":
            fine = all(holds(c, world, element) for c in expected)
        elif key == "any":
            fine = any(holds(c, world, element) for c in expected)
        else:  # not
            fine = not holds(expected, world, element)
        if not fine:
            return False
    return True


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
    )


def _next(decl: dict, world: World) -> list[dict]:
    """Ce que la table de règles change en un pas. Chaque élément suit la première règle qui lui correspond ;
    toutes les règles lisent l'état du pas précédent."""
    changes = []
    for key, element in world.elements.items():
        for rule in decl["rules"]:
            if element["type"] in rule["on"] and holds(rule["when"], world, element):
                if rule["then"] != world.states[key]:
                    changes.append(
                        {"id": key, "from": world.states[key], "to": rule["then"], "rule": rule["key"]}
                    )
                break
    return changes


def run(decl: dict, situation: dict, default_status: str, start: dict | None = None) -> dict:
    """Déroule la situation jusqu'à ce que plus rien ne bouge.

    Rend {steps: [{states, changes}], end: stable | loop | limit}. Le premier pas est la situation de départ.
    `loop` : la situation revient à un état déjà vu ; `limit` : le nombre de pas permis est atteint."""
    world = world_of(decl, situation, default_status, start)
    steps = [{"states": dict(world.states), "changes": []}]
    seen = [dict(world.states)]
    end = "stable"
    while True:
        changes = _next(decl, world)
        if not changes:
            break
        if len(steps) > decl["max_steps"]:
            end = "limit"
            break
        for change in changes:
            world.states[change["id"]] = change["to"]
        steps.append({"states": dict(world.states), "changes": changes})
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
    return "la condition composée de la règle n'est pas remplie"


def waiting(decl: dict, world: World) -> dict[str, dict]:
    """Pour chaque brique qu'une règle pourrait encore faire changer, la règle la plus proche de jouer et ce
    qui lui manque (la première condition fausse). Une brique qu'aucune règle ne fait sortir de son état n'y
    figure pas : rien ne l'attend. Au plus une raison par brique."""
    out = {}
    for key, element in world.elements.items():
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


def extra(decl: dict, result: dict) -> dict:
    """Ce que cette famille ajoute à la réponse d'un déroulé : pour une situation stabilisée, ce qui retient
    chaque brique qui attend encore (`waiting`)."""
    if result["end"] != "stable":
        return {}
    found = waiting(decl, result["world"])
    return {"waiting": found} if found else {}


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
