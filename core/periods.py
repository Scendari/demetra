"""Atelier, famille « périodes » : des périodes datées que le site combine en un historique.

L'étude déclare des sources de périodes (une brique par source, avec ses champs), un axe de temps et son pas,
puis comment une image se compose à chaque pas : une source de base, des sources rattachées (jointure gardée
ou non, rattachement par un champ, départage quand plusieurs périodes sont en vigueur), les champs restitués,
la fusion des images identiques qui se suivent, le sort des périodes invalides.

Le site calcule l'image de chaque pas — les périodes en vigueur à la fin du pas, bornes [début, fin[ — puis
réunit les pas qui se suivent en périodes d'historique.

Pur : aucun accès à la base. Aucun code fourni par l'étude n'est exécuté : la déclaration ne contient que des
noms et des valeurs que ce module compare.
"""

from __future__ import annotations

import itertools
import math
from typing import Any

from .casemodel import Report
from .rules import among, as_list, comparison_issue, pairs_hold, same, text_of
from .rules import bricks as _bricks
from .rules import choices as _choices
from .rules import chosen as _chosen
from .rules import item_key as _key
from .rules import item_label as _label
from .workshop import LETTERS, MAX_ELEMENTS, MAX_OUTCOMES, MAX_SETTINGS, _listed, _typed, next_id

FAMILY = "periods"
MAX_GRAINS = 400
MAX_FIELDS = 8
MAX_STATUS_RULES = 12
MAX_SITUATION_LINKS = 0
DEFAULT_RUN_STEPS = MAX_GRAINS
SEVERAL = ("latest_start", "earliest_start", "block")
TIES = ("block", "first")
STATES = ("active", "past", "ignored", "invalid", "blocked")
INVALID = {"zero": "ignore", "missing": "block", "inverted": "block"}
WRITES = ("differences", "all")
MAX_RUNS = 6
CHANGES = {
    "added": "ajoutée",
    "closed": "fermée",
    "changed": "modifiée",
    "same": "inchangée",
    "removed": "retirée",
}
FIELDS = {
    *("family", "title", "axis", "bricks", "settings", "image", "merge", "invalid", "states", "outcome"),
    "runs",
}
EPSILON = 1e-9
__all__ = ["LETTERS", "MAX_ELEMENTS", "next_id", "same", "text_of"]  # ce que l'écran lit dans toute famille

EXAMPLE = {
    "family": "periods",
    "axis": {"label": "Jour", "min": 1, "max": 10, "grain": 1},
    "bricks": [
        {"type": "contrat", "label": "Contrat", "options": [{"key": "offre", "values": ["A", "B"]}]},
        {"type": "remise", "label": "Remise", "options": [{"key": "taux", "values": [10, 20]}]},
    ],
    "image": {
        "sources": [{"brick": "contrat"}, {"brick": "remise", "mode": "left"}],
        "fields": [{"key": "offre", "from": "contrat.offre"}, {"key": "taux", "from": "remise.taux"}],
        "status": [{"when": {"missing": "remise"}, "then": "SANS_REMISE"}, {"then": "REMISE"}],
    },
    "states": {"active": "EN_COURS", "past": "FINIE", "ignored": "IGNOREE", "invalid": "KO", "blocked": "KO"},
}
EXAMPLE_SITUATION = {
    "elements": [
        {"id": "A", "type": "contrat", "start": 1, "end": 6, "options": {"offre": "A"}},
        {"id": "B", "type": "remise", "start": 3, "end": 5},
    ]
}


def _number(value) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _neat(value: float) -> int | float:
    """4.0 s'écrit 4 : une borne tombée juste se lit comme un entier."""
    return int(value) if float(value).is_integer() else round(float(value), 6)


# ---------------------------------------------------------------------------
# Déclaration
# ---------------------------------------------------------------------------


def _axis(raw, report: Report, p: str) -> dict:
    out = {"label": "Temps", "min": 0, "max": 10, "grain": 1, "step": 1}
    if not isinstance(raw, dict):
        report.error(
            p,
            "required",
            "« axis » décrit l'axe du temps : {label, min, max, grain}.",
            example=EXAMPLE["axis"],
        )
        return out
    numbers = {key: raw.get(key, out[key]) for key in ("min", "max", "grain")}
    numbers["step"] = raw.get("step", numbers["grain"])
    fine = all(_number(v) for v in numbers.values()) and numbers["grain"] > 0 and numbers["step"] > 0
    fine = fine and numbers["min"] < numbers["max"]
    if not fine or (numbers["max"] - numbers["min"]) / numbers["grain"] > MAX_GRAINS:
        report.error(
            p,
            "type",
            f"L'axe va de « min » à « max » par pas « grain » positifs, {MAX_GRAINS} pas au plus.",
            received=raw,
            example=EXAMPLE["axis"],
        )
        return out
    return {"label": _label(raw, report, p, "Temps", 40), **{k: _neat(v) for k, v in numbers.items()}}


def _ref(text, sources: list[str], bricks: dict, report: Report, p: str) -> list[str] | None:
    """« brique.champ » : un champ d'une source déjà nommée."""
    brick, _, option = text.partition(".") if isinstance(text, str) else ("", "", "")
    if brick not in sources or option not in [o["key"] for o in bricks[brick]["options"]]:
        report.error(
            p,
            "unknown_option",
            "Un champ s'écrit « brique.champ », la brique étant une source déjà nommée.",
            received=text,
            expected=[f"{b}.{o['key']}" for b in sources for o in bricks[b]["options"]],
        )
        return None
    return [brick, option]


def _mode(raw, settings: list[dict], report: Report, p: str):
    """« left » garde l'image quand la source manque, « inner » la retire ; ou cela dépend d'un réglage."""
    if raw in (None, "left", "inner"):
        return raw or "left"
    known = {s["key"]: s for s in settings}
    if isinstance(raw, dict) and raw.get("setting") in known:
        inner = as_list(raw.get("inner"))
        if inner and all(among(v, known[raw["setting"]]["values"]) for v in inner):
            return {"setting": raw["setting"], "inner": inner}
    report.error(
        p,
        "type",
        "« left », « inner », ou {setting, inner} : le réglage et ses valeurs qui retirent l'image.",
        received=raw,
        example={"setting": "jointure", "inner": ["interne"]},
    )
    return "left"


def _source(item, n: int, named: list[str], bricks: dict, settings: list[dict], report: Report, p: str):
    kind = item.get("brick") if isinstance(item, dict) else None
    if kind not in bricks or kind in named:
        report.error(
            f"{p}.brick",
            "unknown_brick",
            "Chaque source est un type de brique, nommé une seule fois.",
            received=kind,
            expected=[b for b in bricks if b not in named],
        )
        return None
    source = {"brick": kind, "mode": "inner", "match": {}, "several": "latest_start", "tie": "block"}
    for name, allowed in (("several", SEVERAL), ("tie", TIES)):
        if item.get(name, source[name]) not in allowed:
            report.error(f"{p}.{name}", "enum", "Valeur inconnue.", received=item.get(name), expected=allowed)
        else:
            source[name] = item.get(name, source[name])
    if n == 0:
        if item.get("match") or item.get("mode") not in (None, "inner"):
            report.error(p, "type", "La première source est la base : ni « match » ni « mode ».")
        return source
    source["mode"] = _mode(item.get("mode"), settings, report, f"{p}.mode")
    match = item.get("match") or {}
    own = [o["key"] for o in bricks[kind]["options"]]
    if not isinstance(match, dict) or any(key not in own for key in match):
        report.error(
            f"{p}.match", "unknown_option", "« match » : {champ de cette brique: brique.champ}.", expected=own
        )
        return source
    for key, text in match.items():
        ref = _ref(text, named, bricks, report, f"{p}.match.{key}")
        if ref:
            source["match"][key] = ref
    return source


def _sources(raw, bricks: dict, settings: list[dict], report: Report, p: str) -> list[dict]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= len(bricks):
        report.error(
            p,
            "type",
            "« sources » : la base d'abord, puis les sources rattachées {brick, mode, match, several, tie}.",
            example=EXAMPLE["image"]["sources"],
        )
        return []
    out: list[dict] = []
    for n, item in enumerate(raw):
        source = _source(item, n, [s["brick"] for s in out], bricks, settings, report, f"{p}[{n}]")
        if source:
            out.append(source)
    return out


def _fields(raw, named: list[str], bricks: dict, report: Report, p: str) -> list[dict]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_FIELDS:
        report.error(
            p,
            "type",
            f"« fields » : de 1 à {MAX_FIELDS} champs restitués {{key, label, from}}.",
            example=EXAMPLE["image"]["fields"],
        )
        return []
    out, seen = [], set()
    for i, item in enumerate(raw):
        key = _key(item, "key", seen, report, f"{p}[{i}]", "Un champ restitué")
        ref = _ref(item.get("from"), named, bricks, report, f"{p}[{i}].from") if key else None
        if ref:
            out.append({"key": key, "label": _label(item, report, f"{p}[{i}]", key), "from": ref})
    return out


def _check_when(when, known: dict, report: Report, p: str) -> dict:
    """Une condition : chaque entrée nomme un test connu ; toutes doivent être vraies."""
    if when in (None, {}):
        return {}
    if not isinstance(when, dict) or set(when) - set(known):
        report.error(p, "unknown_test", "Test inconnu.", received=when, expected=sorted(known))
        return {}
    out = {}
    for test, expected in when.items():
        allowed = known[test]
        if allowed is bool:
            fine = isinstance(expected, bool)
        elif isinstance(allowed, dict):  # {réglage: valeur, ou comparaison}
            fine = isinstance(expected, dict) and all(
                key in allowed
                and (
                    among(value, allowed[key])
                    or isinstance(value, dict)
                    and not comparison_issue(value, allowed[key], allowed)
                )
                for key, value in expected.items()
            )
        else:
            expected = as_list(expected)
            fine = bool(expected) and all(value in allowed for value in expected)
        if fine:
            out[test] = expected
        else:
            report.error(
                f"{p}.{test}", "unknown_value", "Valeur inconnue.", received=expected, expected=allowed
            )
    return out


def _status_rules(raw, named: list[str], settings: list[dict], statuses: set[str], report: Report, p: str):
    """Le statut d'une image : la première entrée dont la condition est vraie."""
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_STATUS_RULES:
        report.error(
            p,
            "type",
            f"« status » : de 1 à {MAX_STATUS_RULES} entrées {{when, then}}.",
            example=EXAMPLE["image"]["status"],
        )
        return []
    known = {"missing": named, "present": named, "setting": {s["key"]: s["values"] for s in settings}}
    out = []
    for i, item in enumerate(raw):
        then = item.get("then") if isinstance(item, dict) else None
        if then not in statuses:
            report.error(
                f"{p}[{i}].then",
                "unknown_status",
                "Statut inconnu.",
                received=then,
                expected=sorted(statuses),
            )
            continue
        out.append({"when": _check_when(item.get("when"), known, report, f"{p}[{i}].when"), "then": then})
    return out


def _image(raw, bricks: dict, settings: list[dict], statuses: set[str], report: Report, p: str) -> dict:
    out: dict[str, list] = {"sources": [], "fields": [], "status": []}
    if not isinstance(raw, dict) or set(raw) - set(out):
        report.error(
            p,
            "required",
            "« image » dit comment une image se compose : {sources, fields, status}.",
            example=EXAMPLE["image"],
        )
        return out
    out["sources"] = _sources(raw.get("sources"), bricks, settings, report, f"{p}.sources")
    named = [s["brick"] for s in out["sources"]]
    if named:
        out["fields"] = _fields(raw.get("fields"), named, bricks, report, f"{p}.fields")
        out["status"] = _status_rules(raw.get("status"), named, settings, statuses, report, f"{p}.status")
    return out


def _states(raw, statuses: set[str], report: Report, p: str) -> dict:
    """Le statut de l'étude qui dit chaque situation d'une période : en vigueur, passée, écartée…"""
    if not isinstance(raw, dict) or set(raw) != set(STATES) or any(v not in statuses for v in raw.values()):
        report.error(
            p,
            "unknown_status",
            "« states » donne un statut de l'étude pour chacune de ces situations.",
            received=raw,
            expected=list(STATES),
            example=EXAMPLE["states"],
        )
        return {}
    return dict(raw)


def _invalid(raw, report: Report, p: str) -> dict:
    out = dict(INVALID)
    if raw is None:
        return out
    if (
        not isinstance(raw, dict)
        or set(raw) - set(out)
        or any(v not in ("ignore", "block") for v in raw.values())
    ):
        report.error(
            p,
            "enum",
            "« invalid » : {zero, missing, inverted}, chacun « ignore » ou « block ».",
            received=raw,
        )
        return out
    return {**out, **raw}


def _outcomes(raw, statuses: set[str], report: Report, p: str) -> list[dict]:
    if raw in (None, []):
        return []
    if not isinstance(raw, list) or len(raw) > MAX_OUTCOMES:
        report.error(p, "type", f"« outcome » : {MAX_OUTCOMES} résultats au plus {{when, label, status}}.")
        return []
    known = {"blocked": bool, "empty": bool, "status": sorted(statuses)}
    out = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or not item.get("label"):
            report.error(f"{p}[{i}].label", "required", "Un résultat a un libellé.")
            continue
        entry = {
            "when": _check_when(item.get("when"), known, report, f"{p}[{i}].when"),
            "label": _label(item, report, f"{p}[{i}]", "", 120),
        }
        if item.get("status") is not None:
            if item["status"] not in statuses:
                report.error(f"{p}[{i}].status", "unknown_status", "Statut inconnu.", received=item["status"])
            else:
                entry["status"] = item["status"]
        out.append(entry)
    return out


def _whole(value, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _runs(raw, report: Report, p: str) -> dict | None:
    """Les exécutions successives que l'étude déclare : leur nom, leur nombre au plus, et ce qu'une exécution
    écrit par rapport à ce qui était publié. None quand l'étude n'en déclare pas."""
    if raw is None:
        return None
    example = {"label": "Exécution", "max": 3, "write": "differences"}
    if not isinstance(raw, dict) or set(raw) - set(example):
        report.error(p, "type", "« runs » est un objet {label, max, write}.", example=example)
        return None
    most = raw.get("max", 3)
    if not _whole(most, 2, MAX_RUNS):
        report.error(f"{p}.max", "out_of_range", f"De 2 à {MAX_RUNS} exécutions.", received=most)
        most = 3
    write = raw.get("write", "differences")
    if write not in WRITES:
        report.error(f"{p}.write", "enum", "Valeur inconnue.", received=write, expected=list(WRITES))
        write = "differences"
    return {"label": _label(raw, report, p, "Exécution", 40), "max": most, "write": write}


def normalize(raw: Any, status_keys: set[str], report: Report, path: str = "workshop") -> dict:
    """La déclaration d'un atelier de périodes, validée."""
    if set(raw) - FIELDS:
        report.error(
            path, "unknown_field", "Champ inconnu dans « workshop ».", received=sorted(set(raw) - FIELDS)
        )
    bricks = _bricks(raw.get("bricks"), status_keys, report, f"{path}.bricks")
    for i, brick in enumerate(bricks):
        if brick["events"] or "initial" in brick:
            report.error(
                f"{path}.bricks[{i}]", "unknown_field", "Une période n'a ni « events » ni « initial »."
            )
        if {"start", "end"} & {o["key"] for o in brick["options"]}:
            report.error(f"{path}.bricks[{i}].options", "duplicate", "« start » et « end » sont les bornes.")
    settings = _choices(raw.get("settings"), report, f"{path}.settings", "Un réglage", MAX_SETTINGS, True)
    by_type = {b["type"]: b for b in bricks}
    merge = raw.get("merge", True)
    if not isinstance(merge, bool):
        report.error(f"{path}.merge", "type", "« merge » vaut true ou false.", received=merge)
        merge = True
    decl = {
        "family": FAMILY,
        "title": _label(raw, report, path, "", 80, "title"),
        "axis": _axis(raw.get("axis"), report, f"{path}.axis"),
        "bricks": bricks,
        "links": [],
        "settings": settings,
        "image": _image(raw.get("image"), by_type, settings, status_keys, report, f"{path}.image"),
        "merge": merge,
        "invalid": _invalid(raw.get("invalid"), report, f"{path}.invalid"),
        "states": _states(raw.get("states"), status_keys, report, f"{path}.states"),
        "outcome": _outcomes(raw.get("outcome"), status_keys, report, f"{path}.outcome"),
    }
    runs = _runs(raw.get("runs"), report, f"{path}.runs")
    if (
        runs
    ):  # la clé n'existe que si l'étude en déclare : une déclaration sans exécutions reste ce qu'elle était
        decl["runs"] = runs
    decl["rules"] = principles(decl) if declared(decl) else []
    return decl


def declared(decl: dict | None) -> bool:
    image = (decl or {}).get("image") or {}
    return bool(
        decl and decl.get("bricks") and image.get("sources") and image.get("fields") and decl.get("states")
    )


# ---------------------------------------------------------------------------
# Ce que la déclaration dit, en phrases : c'est ce que le relecteur lit à côté du résultat
# ---------------------------------------------------------------------------

HOW_SEVERAL = {
    "latest_start": "celle qui a commencé le plus tard l'emporte",
    "earliest_start": "celle qui a commencé le plus tôt l'emporte",
    "block": "le traitement est bloqué",
}
HOW_INVALID = {
    "zero": "une période de durée nulle",
    "missing": "une période dont une borne manque",
    "inverted": "une période qui finit avant de commencer",
}
NOTHING_WRITTEN = "rien n'est écrit"
WRITING = "à l'écriture : "
HOW_WRITE = {
    "differences": "Seules les lignes qui diffèrent sont écrites ; sans différence, rien n'est écrit.",
    "all": "Tout l'historique est réécrit à chaque exécution, même sans différence.",
}


def _join_sentence(decl: dict, source: dict, labels: dict) -> str:
    name = labels[source["brick"]]
    parts = []
    if source["match"]:
        named = {(b["type"], o["key"]): o["label"] for b in decl["bricks"] for o in b["options"]}
        how = [
            f"« {named[source['brick'], key]} » vaut « {named[b, o]} » de « {labels[b]} »"
            for key, (b, o) in source["match"].items()
        ]
        parts.append("on retient la période dont " + _listed(how))
    if source["mode"] == "left":
        parts.append("faute de période en vigueur, l'image est gardée et ses champs restent vides")
    elif source["mode"] == "inner":
        parts.append("faute de période en vigueur, aucune image")
    else:
        setting = next(s for s in decl["settings"] if s["key"] == source["mode"]["setting"])
        values = _listed([f"« {text_of(v)} »" for v in source["mode"]["inner"]])
        parts.append(
            f"faute de période en vigueur, l'image est gardée avec ses champs vides, sauf quand "
            f"« {setting['label']} » vaut "
            f"{values} : alors aucune image"
        )
    sentence = f"{name} : " + " ; ".join(parts) + "."
    several = HOW_SEVERAL[source["several"]]
    if source["several"] != "block":
        tie = "le traitement est bloqué" if source["tie"] == "block" else "la première posée l'emporte"
        several += f" ; à égalité, {tie}"
    return f"{sentence} Si plusieurs le sont, {several}."


def principles(decl: dict) -> list[dict]:
    """Les règles que la déclaration revient à poser, dans l'ordre où le site les applique."""
    axis, labels = decl["axis"], {b["type"]: b["label"] for b in decl["bricks"]}
    base = decl["image"]["sources"][0]
    out: list[tuple[str, str]] = []
    grain = (
        f"Une image par pas de {text_of(axis['grain'])} sur l'axe « {axis['label']} » : elle montre les "
        "périodes en vigueur à la fin du pas. Un changement à l'intérieur d'un pas ne crée pas d'image."
    )
    out.append(("grain", grain))
    out.append(("bounds", "Une période vaut de son début inclus à sa fin exclue."))
    ignored = _listed([HOW_INVALID[k] for k, v in decl["invalid"].items() if v == "ignore"] or ["aucune"])
    blocking = _listed([HOW_INVALID[k] for k, v in decl["invalid"].items() if v == "block"] or ["aucune"])
    out.append(
        ("invalid", f"Périodes ignorées : {ignored}. Périodes qui bloquent le traitement : {blocking}.")
    )
    several = HOW_SEVERAL[base["several"]]
    first = f"{labels[base['brick']]} : faute de période en vigueur, aucune image."
    first += f" Si plusieurs le sont, {several}."
    out.append((f"source:{base['brick']}", first))
    out += [(f"source:{s['brick']}", _join_sentence(decl, s, labels)) for s in decl["image"]["sources"][1:]]
    fields = _listed([f"« {f['label']} »" for f in decl["image"]["fields"]])
    merged = (
        "Deux images identiques sur ces champs, sans trou entre elles, forment une seule période ; "
        "un trou ou une valeur intermédiaire les sépare."
    )
    apart = "Tout changement de période source ouvre une image."
    out.append(("merge", f"Champs restitués : {fields}. {merged if decl['merge'] else apart}"))
    if decl.get("runs"):
        successive = (
            f"Exécutions successives (« {decl['runs']['label']} ») : chacune recalcule l'historique avec les "
            "périodes connues à ce moment et le compare à ce qui était publié. "
            f"{HOW_WRITE[decl['runs']['write']]} Une exécution bloquée ne publie rien : ce qui était publié "
            "reste."
        )
        out.append(("runs", successive))
    return [{"key": f"P{n}", "role": role, "title": title} for n, (role, title) in enumerate(out, 1)]


def _rule(decl: dict, role: str) -> str:
    return next(r["key"] for r in decl["rules"] if r["role"] == role)


# ---------------------------------------------------------------------------
# Situation : les périodes qu'une personne (ou une IA) a posées
# ---------------------------------------------------------------------------


def _bound(value, axis: dict, report: Report, p: str):
    """Une borne : un nombre sur l'axe, ou rien (une borne absente doit pouvoir se voir dans l'atelier)."""
    if value in (None, ""):
        return None
    if not _number(value) or not axis["min"] <= value <= axis["max"]:
        report.error(
            p,
            "out_of_range",
            f"Une borne est un nombre de {text_of(axis['min'])} à {text_of(axis['max'])}.",
            received=value,
        )
        return None
    return _neat(value)


def _known_of(item: dict, count: int, report: Report, p: str) -> dict:
    """Les exécutions où une période est connue : à partir de `known_from` (la première, par défaut) et
    jusqu'à `known_until` comprise (toujours, par défaut)."""
    first, last = item.get("known_from", 1), item.get("known_until")
    if not _whole(first, 1, count):
        report.error(f"{p}.known_from", "out_of_range", f"Une exécution de 1 à {count}.", received=first)
        first = 1
    if last is not None and not _whole(last, first, count):
        report.error(
            f"{p}.known_until", "out_of_range", f"Une exécution de {first} à {count}, ou rien.", received=last
        )
        last = None
    return {"known_from": first, "known_until": last}


def _run_count(decl: dict, raw: dict, report: Report, p: str) -> int | None:
    """Le nombre d'exécutions d'une situation ; None quand l'étude n'en déclare pas."""
    runs, asked = decl.get("runs"), raw.get("runs")
    if not runs:
        if asked is not None:
            report.error(p, "unknown_field", "Cette étude ne déclare pas d'exécutions successives.")
        return None
    if asked is None:
        return 1
    if not _whole(asked, 1, runs["max"]):
        report.error(p, "out_of_range", f"De 1 à {runs['max']} exécutions.", received=asked)
        return 1
    return asked


def situation(decl: dict, raw: Any, report: Report, path: str = "situation") -> dict:
    """Des périodes posées, vérifiées contre ce que l'étude déclare. L'invalide est signalé et écarté :
    l'API refuse alors la demande, l'interface garde le reste."""
    out: dict[str, Any] = {"elements": [], "links": [], "events": {}, "settings": {}}
    if not isinstance(raw, dict):
        report.error(
            path, "type", "Une situation est un objet {elements, settings}.", example=EXAMPLE_SITUATION
        )
        raw = {}
    if raw.get("links"):
        report.error(f"{path}.links", "unknown_field", "Des périodes ne se relient pas : pas de « links ».")
    out["settings"] = _chosen(decl["settings"], raw.get("settings"), report, f"{path}.settings")
    count = _run_count(decl, raw, report, f"{path}.runs")
    if count:
        out["runs"] = count
    items = raw.get("elements") or []
    if not isinstance(items, list) or len(items) > MAX_ELEMENTS:
        report.error(
            f"{path}.elements", "max_items", f"{MAX_ELEMENTS} périodes au plus.", example=EXAMPLE_SITUATION
        )
        items = items[:MAX_ELEMENTS] if isinstance(items, list) else []
    bricks = {b["type"]: b for b in decl["bricks"]}
    seen: set = set()
    for i, item in enumerate(items):
        p = f"{path}.elements[{i}]"
        key = _key(item, "id", seen, report, p, "Une période")
        if key is None:
            continue
        brick = bricks.get(item.get("type"))
        if brick is None:
            seen.discard(key)
            report.error(
                f"{p}.type",
                "unknown_brick",
                "Type inconnu.",
                received=item.get("type"),
                expected=list(bricks),
            )
            continue
        out["elements"].append(
            {
                "id": key,
                "label": _label(item, report, p, f"{brick['label']} {key}", 40),
                "type": brick["type"],
                "options": _chosen(brick["options"], item.get("options"), report, f"{p}.options"),
                "start": _bound(item.get("start"), decl["axis"], report, f"{p}.start"),
                "end": _bound(item.get("end"), decl["axis"], report, f"{p}.end"),
            }
        )
        if count:
            out["elements"][-1].update(_known_of(item, count, report, p))
        elif "known_from" in item or "known_until" in item:
            report.error(p, "unknown_field", "Cette étude ne déclare pas d'exécutions successives.")
    return out


def _parsed(text: str):
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        return None
    return _neat(value) if math.isfinite(value) and abs(value) < 1e9 else None


def _asked_run(query: dict[str, list[str]], name: str, low: int, high: int) -> int | None:
    """Un numéro d'exécution lu dans une adresse, ramené entre `low` et `high` ; None s'il n'y est pas."""
    text = (query.get(name) or [""])[-1].strip()
    return min(max(int(text), low), high) if text.isdigit() else None


def _query_runs(decl: dict, query: dict[str, list[str]], out: dict) -> dict:
    """`x=3` : trois exécutions ; `c.A=2` : la période A n'est connue qu'à partir de la deuxième ; `j.A=2` :
    elle ne l'est plus après."""
    if not decl.get("runs"):
        return out
    out["runs"] = _asked_run(query, "x", 1, decl["runs"]["max"]) or 1
    for element in out["elements"]:
        first = _asked_run(query, f"c.{element['id']}", 1, out["runs"]) or 1
        last = _asked_run(query, f"j.{element['id']}", first, out["runs"])
        # « Jusqu'à la dernière » ne dit rien de plus que « toujours » : l'adresse ne le garde pas.
        element.update({"known_from": first} | ({"known_until": last} if last and last < out["runs"] else {}))
    return out


def from_query(decl: dict, query: dict[str, list[str]]) -> dict:
    """Les périodes écrites dans une adresse. `e=A:contrat` pose une période ; `de.A=1` et `a.A=4` la bornent
    (vides : borne absente) ; `n.A=…` la nomme ; `o.A.champ=valeur` fixe un champ ; `r.reglage=valeur` un
    réglage. Ce que l'adresse contient d'inconnu est ignoré."""
    bricks = {b["type"]: b for b in decl["bricks"]}
    axis, elements = decl["axis"], []
    for raw in query.get("e", []):
        key, _, kind = raw.partition(":")
        if kind not in bricks or not key.isalnum() or any(e["id"] == key for e in elements):
            continue
        element: dict[str, Any] = {"id": key, "type": kind, "options": {}}
        name = (query.get(f"n.{key}") or [""])[-1].strip()[:40]
        if name:
            element["label"] = name
        for side, param in (("start", "de"), ("end", "a")):
            value = _parsed((query.get(f"{param}.{key}") or [""])[-1])
            if value is not None:
                element[side] = min(max(value, axis["min"]), axis["max"])
        for option in bricks[kind]["options"]:
            text = (query.get(f"o.{key}.{option['key']}") or [""])[-1]
            value = _typed(bricks[kind]["options"], option["key"], text)
            if value is not None:
                element["options"][option["key"]] = value
        elements.append(element)
    settings = {}
    for item in decl["settings"]:
        value = _typed(decl["settings"], item["key"], (query.get(f"r.{item['key']}") or [""])[-1])
        if value is not None:
            settings[item["key"]] = value
    return _query_runs(decl, query, {"elements": elements, "settings": settings})


def to_query(decl: dict, sit: dict) -> list[tuple[str, str]]:
    """L'adresse d'une situation : les périodes, leurs bornes, puis ce qui s'écarte des valeurs par défaut."""
    bricks = {b["type"]: b for b in decl["bricks"]}
    out = [("e", f"{e['id']}:{e['type']}") for e in sit["elements"]]
    for element in sit["elements"]:
        brick, key = bricks[element["type"]], element["id"]
        out.append((f"de.{key}", "" if element["start"] is None else text_of(element["start"])))
        out.append((f"a.{key}", "" if element["end"] is None else text_of(element["end"])))
        if element["label"] != f"{brick['label']} {key}":
            out.append((f"n.{key}", element["label"]))
        out += [
            (f"o.{key}.{o['key']}", text_of(element["options"][o["key"]]))
            for o in brick["options"]
            if not same(element["options"][o["key"]], o["default"])
        ]
        if element.get("known_from", 1) != 1:
            out.append((f"c.{key}", str(element["known_from"])))
        if element.get("known_until"):
            out.append((f"j.{key}", str(element["known_until"])))
    out += [
        (f"r.{item['key']}", text_of(sit["settings"][item["key"]]))
        for item in decl["settings"]
        if not same(sit["settings"][item["key"]], item["default"])
    ]
    return out + ([("x", str(sit["runs"]))] if sit.get("runs", 1) != 1 else [])


def placed(decl: dict, query: dict[str, list[str]], letter: str, kind: str) -> list[str]:
    """Une période qu'on vient de poser : elle commence où finit la dernière de sa source, pour deux pas."""
    axis = decl["axis"]
    ends = [
        _parsed((query.get(f"a.{raw.partition(':')[0]}") or [""])[-1])
        for raw in query.get("e", [])
        if raw.partition(":")[2] == kind
    ]
    start = max([e for e in ends if e is not None], default=axis["min"])
    start = min(start, axis["max"] - axis["grain"])
    query[f"de.{letter}"] = [text_of(_neat(start))]
    query[f"a.{letter}"] = [text_of(_neat(min(start + 2 * axis["grain"], axis["max"])))]
    return []


# ---------------------------------------------------------------------------
# Moteur : l'image de chaque pas, puis les périodes d'historique
# ---------------------------------------------------------------------------


def _sorted(decl: dict, sit: dict) -> tuple[list[dict], dict[str, str], list[str]]:
    """Les périodes utilisables ; l'état de celles qui ne le sont pas ; ce qui bloque le traitement."""
    usable, states, blocking = [], {}, []
    for element in sit["elements"]:
        if element["start"] is None or element["end"] is None:
            kind = "missing"
        elif element["end"] < element["start"]:
            kind = "inverted"
        elif element["end"] == element["start"]:
            kind = "zero"
        else:
            usable.append(element)
            continue
        blocks = decl["invalid"][kind] == "block"
        states[element["id"]] = "invalid" if blocks else "ignored"
        if blocks:
            blocking.append(f"{element['label']} : {HOW_INVALID[kind]}")
    return usable, states, blocking


def _inner(source: dict, settings: dict) -> bool:
    mode = source["mode"]
    return mode == "inner" or (isinstance(mode, dict) and among(settings[mode["setting"]], mode["inner"]))


def _pick(source: dict, candidates: list[dict], picked: dict) -> tuple[dict | None, str, list[str]]:
    """La période retenue pour l'image ; comment (« missing », « several », « tie », ou rien) ; celles qu'elle
    a devancées."""
    for own, (brick, option) in source["match"].items():
        other = picked.get(brick)
        if other is None:
            return None, "missing", []
        candidates = [c for c in candidates if same(c["options"][own], other["options"][option])]
    if len(candidates) < 2:
        return (candidates[0], "", []) if candidates else (None, "missing", [])
    if source["several"] == "block":
        return None, "tie", []
    edge = (max if source["several"] == "latest_start" else min)(c["start"] for c in candidates)
    tied = [c for c in candidates if c["start"] == edge]
    if len(tied) > 1 and source["tie"] == "block":
        return None, "tie", []
    return tied[0], "several", [c["id"] for c in candidates if c is not tied[0]]


def _row(decl: dict, usable: list[dict], settings: dict, edge: float) -> tuple[dict | None, str | None]:
    """L'image d'un pas, dont `edge` est la fin : les périodes en vigueur juste avant. Quand rien ne sort :
    (None, la source dont l'absence retire l'image)."""
    picked: dict[str, dict | None] = {}
    how: dict[str, str] = {}
    lost: list[str] = []
    for n, source in enumerate(decl["image"]["sources"]):
        brick = source["brick"]
        active = [
            p for p in usable if p["type"] == brick and p["start"] < edge - EPSILON <= p["end"] - EPSILON
        ]
        picked[brick], how[brick], beaten = _pick(source, active, picked)
        lost += beaten
        if picked[brick] is None and how[brick] == "missing" and (n == 0 or _inner(source, settings)):
            return None, brick
    missing = [b for b, p in picked.items() if p is None]
    status = None
    for rule in decl["image"]["status"]:
        when = rule["when"]
        fine = not when.get("missing") or any(b in missing for b in when["missing"])
        fine = fine and all(b not in missing for b in when.get("present", []))
        fine = fine and pairs_hold(when.get("setting", {}), settings, settings)
        if fine:
            status = rule["then"]
            break
    fields = {
        f["key"]: picked[f["from"][0]]["options"][f["from"][1]] if picked[f["from"][0]] else None
        for f in decl["image"]["fields"]
    }
    row = {
        "picked": {b: p["id"] if p else None for b, p in picked.items()},
        "how": how,
        "lost": lost,
        "fields": fields,
        "status": status,
    }
    return row, None


def _grains(decl: dict, usable: list[dict], settings: dict) -> list[tuple[float, dict | None, str | None]]:
    """Pour chaque pas de l'axe : son début, son image (None quand rien ne sort) et, alors, la source dont
    l'absence la retire."""
    axis = decl["axis"]
    count = round((axis["max"] - axis["min"]) / axis["grain"])
    starts = [axis["min"] + i * axis["grain"] for i in range(count)]
    return [(start, *_row(decl, usable, settings, start + axis["grain"])) for start in starts]


def _images(decl: dict, grains: list, taken: set[str]) -> list[dict]:
    """Les périodes d'historique : les pas qui se suivent et donnent la même image, réunis. Une image dont une
    source n'a pas pu être départagée reste à part d'une image saine, même si leurs champs se valent."""
    grain = decl["axis"]["grain"]
    images: list[dict] = []
    previous = None
    for start, row, _ in grains:
        if row is None:
            previous = None
            continue
        tied = sorted(brick for brick, how in row["how"].items() if how == "tie")
        key = (row["fields"] if decl["merge"] else row["picked"], row["status"], tied)
        if previous is not None and key == previous:
            images[-1]["end"] = _neat(start + grain)
            images[-1]["steps"] += 1
        else:
            empty = {"sources": {b: [] for b in row["picked"]}, "hows": {b: [] for b in row["picked"]}}
            images.append({"start": _neat(start), "end": _neat(start + grain), "steps": 1, **row, **empty})
            images[-1]["beaten"] = []
        _gather(images[-1], row)
        previous = key
    names = (f"I{n}" for n in itertools.count(1))  # « I » n'est jamais la lettre d'une brique posée ici
    for image in images:
        image["id"] = next(name for name in names if name not in taken)
    return images


def _gather(image: dict, row: dict) -> None:
    """Ce qu'un pas de plus apporte à la provenance d'une image : les périodes retenues, comment, et celles
    qu'elles ont devancées."""
    for brick, picked in row["picked"].items():
        if picked and picked not in image["sources"][brick]:
            image["sources"][brick].append(picked)
        if row["how"][brick] not in image["hows"][brick]:
            image["hows"][brick].append(row["how"][brick])
    image["beaten"] += [key for key in row["lost"] if key not in image["beaten"]]


def _why(decl: dict, situation: dict, image: dict) -> tuple[str, list[str]]:
    """D'où vient une ligne de l'historique, en une phrase, et les règles qui l'expliquent."""
    labels = {b["type"]: b["label"] for b in decl["bricks"]}
    names = {e["id"]: e["label"] for e in situation["elements"]}
    kinds = {e["id"]: e["type"] for e in situation["elements"]}
    parts, rules = [], [_rule(decl, "grain")]
    for brick, keys in image["sources"].items():
        hows = image["hows"][brick]
        said = ", puis ".join(names[key] for key in keys)
        if "tie" in hows:
            said = "plusieurs en vigueur, à égalité"
        elif not keys:
            said = "aucune en vigueur, la ligne est gardée"
        else:
            beaten = [names[key] for key in image["beaten"] if kinds[key] == brick]
            said += f", retenue devant {_listed(beaten)}" if beaten else ""
            said += " ; aucune en vigueur une partie du temps" if "missing" in hows else ""
        if hows != [""]:
            rules.append(_rule(decl, f"source:{brick}"))
        parts.append(f"{labels[brick]} : {said}")
    text = " ; ".join(parts) + "."
    if image["steps"] > 1 and decl["merge"]:
        rules.append(_rule(decl, "merge"))
        text += f" {image['steps']} pas de l'axe aux mêmes valeurs, réunis en une période."
    return text, rules


def _state_at(period: dict, row: dict | None, edge: float) -> str | None:
    """L'état d'une période source à un pas : en vigueur, devancée, passée, ou pas encore commencée."""
    if row and row["picked"].get(period["type"]) == period["id"]:
        return "active"
    if period["start"] < edge - EPSILON <= period["end"] - EPSILON:
        return "ignored" if row and period["id"] in row["lost"] else "active"
    return "past" if period["end"] < edge - EPSILON else None


def _ties(decl: dict, images: list[dict]) -> list[str]:
    """Les images qu'une égalité entre deux périodes d'une même source empêche de composer."""
    labels = {b["type"]: b["label"] for b in decl["bricks"]}
    when = decl["axis"]["label"]
    return [
        f"{when} {text_of(image['start'])} : plusieurs « {labels[brick]} » en vigueur, à égalité"
        for image in images
        for brick, how in image["how"].items()
        if how == "tie"
    ]


def _known(situation: dict, n: int) -> list[dict]:
    """Les périodes que l'exécution `n` connaît."""
    return [
        e
        for e in situation["elements"]
        if e.get("known_from", 1) <= n and (e.get("known_until") is None or n <= e["known_until"])
    ]


def _compare(before: list[dict], after: list[dict]) -> tuple[list[dict], list[dict]]:
    """Ce qu'une exécution change à ce qui était publié. Une ligne se reconnaît à son début : elle est
    ajoutée, fermée (mêmes valeurs, fin avancée), modifiée ou inchangée ; celles qui n'ont plus lieu d'être
    sont retirées."""
    old = {line["start"]: line for line in before}
    lines = []
    for line in after:
        was = old.pop(line["start"], None)
        if was is None:
            change = "added"
        elif was == line:
            change = "same"
        elif (was["fields"], was["status"]) == (line["fields"], line["status"]) and line["end"] < was["end"]:
            change = "closed"
        else:
            change = "changed"
        lines.append({**line, "change": change} | ({"was": was} if change in ("closed", "changed") else {}))
    return lines, [{**line, "change": "removed"} for line in old.values()]


def _run_text(decl: dict, entry: dict) -> str:
    """Une exécution, en une phrase : ce qu'elle change, puis ce qu'elle écrit."""
    name = f"{decl['runs']['label']} {entry['run']}"
    if not entry["published"]:
        return f"{name} : traitement bloqué, rien n'est publié ; ce qui était publié reste."
    changes = [line["change"] for line in entry["lines"] + entry["removed"]]
    if not changes:
        return f"{name} : aucune ligne à publier."

    def lines(n: int, word: str) -> str:
        return f"{n} ligne{'s' if n > 1 else ''} {word}{'s' if n > 1 else ''}"

    said = [lines(changes.count(key), word) for key, word in CHANGES.items() if key in changes]
    deleted, appended = entry["written"]["deleted"], entry["written"]["appended"]
    wrote = [lines(n, word) for n, word in ((deleted, "supprimée"), (appended, "écrite")) if n]
    return f"{name} : {_listed(said)} ; {WRITING + _listed(wrote) if wrote else NOTHING_WRITTEN}."


def successive(decl: dict, situation: dict) -> list[dict]:
    """Les exécutions l'une après l'autre : chacune recalcule l'historique avec les périodes qu'elle connaît
    et le compare à ce qui était publié. Une exécution bloquée ne publie rien : ce qui était publié reste."""
    published: list[dict] = []
    out = []
    for n in range(1, situation.get("runs", 1) + 1):
        known = _known(situation, n)
        usable, _, refused = _sorted(decl, {**situation, "elements": known})
        images = _images(decl, _grains(decl, usable, situation["settings"]), set())
        blocking = list(dict.fromkeys(refused + _ties(decl, images)))
        lines, removed = [{**line, "change": "same"} for line in published], []
        written = {"deleted": 0, "appended": 0}
        if not blocking:
            after = [{k: image[k] for k in ("start", "end", "fields", "status")} for image in images]
            lines, removed = _compare(published, after)
            touched = sum(line["change"] in ("closed", "changed") for line in lines)
            added = sum(line["change"] == "added" for line in lines)
            written = {"deleted": touched + len(removed), "appended": touched + added}
            if decl["runs"]["write"] == "all":
                written = {"deleted": len(published), "appended": len(after)}
            published = after
        entry = {
            "run": n,
            "known": [e["id"] for e in known],
            "new": [e["id"] for e in known if e.get("known_from", 1) == n],
            "withdrawn": [e["id"] for e in situation["elements"] if n > 1 and e.get("known_until") == n - 1],
            "published": not blocking,
            "blocking": blocking,
            "lines": lines,
            "removed": removed,
            "written": written,
        }
        out.append({**entry, "text": _run_text(decl, entry)})
    return out


def run(decl: dict, situation: dict, default_status: str) -> dict:
    """Combine les périodes posées. Rend les périodes d'historique (`images`), ce qui bloque le traitement
    (`blocking`), et le déroulé : un pas chaque fois qu'une image commence ou qu'une période posée change
    d'état, jusqu'au bout de l'axe — une période finie avant la fin de l'axe finit donc « passée ». Quand
    l'étude déclare des exécutions successives, l'historique est celui de la dernière : une période qu'elle ne
    connaît pas (ou plus) est écartée, et `runs` dit ce que chaque exécution a publié."""
    seen = _known(situation, situation.get("runs", 1))
    apart = [e for e in situation["elements"] if e not in seen]
    usable, fixed, refused = _sorted(decl, {**situation, "elements": seen})
    grains = _grains(decl, usable, situation["settings"])
    images = _images(decl, grains, {e["id"] for e in situation["elements"]})
    for image in images:
        image["why"], image["rules"] = _why(decl, situation, image)
    states = decl["states"]
    blocking = list(dict.fromkeys(refused + _ties(decl, images)))
    if blocking:
        for image in images:
            image["status"] = states["blocked"]
    current = {e["id"]: default_status for e in situation["elements"]}
    current.update({image["id"]: default_status for image in images})
    steps: list[dict] = [{"states": dict(current), "changes": [], "at": None, "kind": "start"}]

    def step(changes: dict[str, tuple[str, str]], at, kind: str, **more) -> None:
        moved = [
            {"id": key, "from": current[key], "to": status, "rule": rule}
            for key, (status, rule) in changes.items()
            if current[key] != status
        ]
        current.update({c["id"]: c["to"] for c in moved})
        if moved:
            steps.append({"states": dict(current), "changes": moved, "at": at, "kind": kind, **more})

    invalid = {key: (states[state], _rule(decl, "invalid")) for key, state in fixed.items()}
    invalid.update({e["id"]: (states["ignored"], _rule(decl, "runs")) for e in apart})
    step(invalid, None, "check", reasons=refused, apart=[e["label"] for e in apart])
    by_start = {image["start"]: image for image in images}
    shown = None
    for start, row, absent in grains:
        moment = _neat(start)
        shown = by_start.get(moment, shown) if row else None
        changes = {}
        for period in usable:
            state = _state_at(period, row, start + decl["axis"]["grain"])
            role = "bounds" if state != "ignored" else f"source:{period['type']}"
            if state:
                changes[period["id"]] = (states[state], _rule(decl, role))
        if moment in by_start:
            changes[shown["id"]] = (shown["status"], _rule(decl, _image_role(shown)))
        kind = "image" if moment in by_start else ("inside" if row else "gap")
        step(changes, moment, kind, image=shown, row=row, absent=absent)
    used = [_rule(decl, "grain"), _rule(decl, "bounds")] if images else []
    used += [_rule(decl, "merge")] if any(image["steps"] > 1 for image in images) else []
    result = {"steps": steps, "end": "stable", "images": images, "blocking": blocking, "used": used}
    if decl.get("runs"):
        result["runs"] = successive(decl, situation)
        result["used"] += [_rule(decl, "runs")] if len(result["runs"]) > 1 else []
    return result


def _image_role(image: dict) -> str:
    """La règle qui explique le mieux cette image : un départage, une source manquante, sinon le pas."""
    for wanted in ("tie", "several", "missing"):
        brick = next((b for b, how in image["how"].items() if how == wanted), None)
        if brick:
            return f"source:{brick}"
    return "grain"


def outcome(decl: dict, result: dict) -> dict | None:
    """Le résultat d'ensemble : le premier résultat déclaré dont la condition est vraie."""
    images = result["images"]
    for item in decl["outcome"]:
        when = item["when"]
        fine = "blocked" not in when or when["blocked"] == bool(result["blocking"])
        fine = fine and ("empty" not in when or when["empty"] == (not images))
        fine = fine and ("status" not in when or any(image["status"] in when["status"] for image in images))
        if fine:
            return {"label": item["label"], **({"status": item["status"]} if "status" in item else {})}
    return None


def plan(decl: dict) -> dict:
    """Ce que le dessin d'une situation doit savoir de plus : l'axe du temps couvre tout l'axe déclaré, pour
    que la frise garde la même échelle d'un geste à l'autre."""
    return {"span": (decl["axis"]["min"], decl["axis"]["max"])}


def extra(decl: dict, result: dict) -> dict:
    """Ce que cette famille ajoute à la réponse : les périodes d'historique, d'où vient chacune, et ce qui
    bloque."""
    fields = decl["image"]["fields"]
    runs = {"runs": result["runs"]} if "runs" in result else {}
    return runs | {
        "images": [
            {
                "id": image["id"],
                "start": image["start"],
                "end": image["end"],
                "fields": {f["key"]: image["fields"][f["key"]] for f in fields},
                "status": image["status"],
                "from": image["picked"],
                "sources": [key for keys in image["sources"].values() for key in keys],
                "rules": image["rules"],
                "why": image["why"],
            }
            for image in result["images"]
        ],
        "blocking": result["blocking"],
    }


# ---------------------------------------------------------------------------
# Le même déroulé, sous la forme d'un cas que le site sait valider et dessiner
# ---------------------------------------------------------------------------


def image_label(decl: dict, image: dict) -> str:
    values = [image["fields"][f["key"]] for f in decl["image"]["fields"]]
    return " · ".join("∅" if v is None else text_of(v) for v in values)


def _notes(decl: dict, situation: dict, row: dict) -> str:
    """Pourquoi cette image : ce qui a été retenu pour chaque source, et comment."""
    labels = {b["type"]: b["label"] for b in decl["bricks"]}
    names = {e["id"]: e["label"] for e in situation["elements"]}
    parts = []
    for brick, key in row["picked"].items():
        how = row["how"][brick]
        if key is None:
            none = "plusieurs en vigueur, à égalité" if how == "tie" else "aucune en vigueur"
            parts.append(f"{labels[brick]} : {none}")
        else:
            several = ", retenue parmi plusieurs" if how == "several" else ""
            parts.append(f"{labels[brick]} : {names[key]}{several}")
    return " ; ".join(parts) + "."


def _step(decl: dict, situation: dict, step: dict, blocking: list[str]) -> dict:
    changes = {c["id"]: c["to"] for c in step["changes"]}
    if step["kind"] == "check":
        reasons = step["reasons"]
        note = "Bloque le traitement : " + " ; ".join(reasons) + "." if reasons else "Elles ne comptent pas."
        if step.get("apart"):
            note += " Inconnues de la dernière exécution : " + _listed(step["apart"]) + "."
        return {"title": "Contrôle des périodes posées", "note": note[:1900], "changes": changes}
    when = f"{decl['axis']['label']} {text_of(step['at'])}"
    if step["kind"] == "gap":
        label = next(b["label"] for b in decl["bricks"] if b["type"] == step["absent"])
        note = f"Aucune période « {label} » en vigueur."
        return {"title": f"{when} : aucune image", "note": note, "changes": changes, "at": step["at"]}
    title = f"{when} : {image_label(decl, step['image'])}"
    if step["kind"] == "inside":
        title += " — même image, d'autres périodes"
    elif blocking:
        title += " — non publiée"
    note = _notes(decl, situation, step["row"])[:1900]
    return {"title": title[:200], "note": note, "changes": changes, "at": step["at"]}


def to_case(decl: dict, situation: dict, result: dict, default_status: str) -> dict:
    """Les périodes posées et l'historique obtenu, sous la forme d'un cas : les sources puis la cible, sur
    l'axe du temps, un pas par moment où l'image change."""
    order = [b["type"] for b in decl["bricks"]]
    sources = sorted(situation["elements"], key=lambda e: (order.index(e["type"]), e["start"] or 0))
    entities = []
    for element in sources:
        bounds = {k: element[k] for k in ("start", "end") if element[k] is not None}
        if len(bounds) == 2 and bounds["end"] < bounds["start"]:
            bounds = {
                "start": bounds["end"],
                "end": bounds["start"],
            }  # dessinée à l'endroit, signalée invalide
        entities.append(
            {
                "id": element["id"],
                "label": element["label"],
                "type": element["type"],
                "group": "Périodes posées",
                "attrs": {**element["options"], **bounds},
            }
        )
    for image in result["images"]:
        entities.append(
            {
                "id": image["id"],
                "label": image_label(decl, image)[:80],
                "type": "image",
                "group": "Historique obtenu",
                "attrs": {"start": image["start"], "end": image["end"]},
            }
        )
    steps = [{"title": "Périodes posées", "note": "Rien n'est encore combiné."}]
    steps += [_step(decl, situation, step, result["blocking"]) for step in result["steps"][1:]]
    if len(steps) == 1:
        steps[0]["note"] = "Ces périodes ne donnent aucune image."
    case = {
        "key": "atelier",
        "title": decl.get("title") or "Situation construite",
        "family": "Atelier",
        "kind": "temporal",
        "config": dict(situation["settings"]),
        "entities": entities,
        "steps": steps,
    }
    found = outcome(decl, result)
    if found:
        case["outcome"] = found
    return case
