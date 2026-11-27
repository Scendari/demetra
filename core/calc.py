"""Atelier, famille « calcul » : des briques posées (un panier, un trajet…), des lignes de calcul appliquées
dans l'ordre à un cumul, comme les étapes `values` d'un cas.

L'étude déclare ses briques (dont les options peuvent être des nombres), ses réglages, ses lignes de calcul
(`lines` : une opération, une valeur, une condition) et le sort de chaque ligne (`states`). Les valeurs et
les conditions sont écrites dans un vocabulaire fermé, en JSON : aucune chaîne n'est interprétée, aucun code
fourni par l'étude n'est exécuté. Pur : aucun accès à la base. Rien ici ne nomme une étude.
"""

from __future__ import annotations

import itertools
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from .casemodel import Report
from .rules import (
    Numbers,
    as_list,
    check_count,
    check_pairs,
    comparison_issue,
    is_number,
    matches,
    pairs_hold,
    same,
    text_of,
    values_of,
)
from .rules import bricks as _bricks
from .rules import choices as _choices
from .rules import chosen as _chosen
from .rules import item_key as _key
from .rules import item_label as _label
from .workshop import LETTERS, MAX_ELEMENTS, MAX_OUTCOMES, MAX_SETTINGS, next_id
from .workshop import from_query as _linked_query
from .workshop import to_query as _linked_to_query

FAMILY = "calc"
MAX_LINES = 24
MAX_DEPTH = 5
MAX_TERMS = 8
OPS = ("=", "+", "-", "×", "÷", "min", "max", "arrondi")
OP_WORDS = {
    "=": "vaut",
    "+": "ajoute",
    "-": "retire",
    "×": "multiplie par",
    "÷": "divise par",
    "min": "plafonne à",
    "max": "relève au moins à",
    "arrondi": "arrondit au pas de",
}
STATES = ("applied", "skipped", "blocked")
FIELDS = {"family", "title", "bricks", "settings", "lines", "result", "states", "outcome"}
SITUATION_TESTS = ("setting", "elements", "total", "line", "all", "any", "not")
ELEMENT_TESTS = ("type", "option", "all", "any", "not")
LINE_PREFIX = "ligne-"  # l'entité d'une ligne, dans le cas produit : elle ne croise jamais une brique (A, B…)
__all__ = ["LETTERS", "MAX_ELEMENTS", "next_id", "same", "text_of"]  # ce que l'écran lit dans toute famille

EXAMPLE = {
    "family": "calc",
    "title": "Composer une facture",
    "bricks": [
        {
            "type": "article",
            "label": "Article",
            "options": [
                {
                    "key": "prix",
                    "label": "Prix unitaire",
                    "number": {"min": 0, "max": 500, "step": 0.5},
                    "unit": "€",
                },
                {"key": "quantite", "label": "Quantité", "number": {"min": 1, "max": 20, "step": 1}},
            ],
        }
    ],
    "lines": [
        {
            "key": "articles",
            "label": "Total des articles",
            "op": "=",
            "value": {
                "sum": {"type": "article", "of": {"mul": [{"option": "prix"}, {"option": "quantite"}]}}
            },
            "unit": "€",
        },
        {
            "key": "remise",
            "label": "Remise de 5 % dès 100 €",
            "when": {"total": {"gte": 100}},
            "op": "-",
            "value": {"pct": [{"total": True}, 5]},
            "unit": "€",
        },
        {"key": "arrondi", "label": "Arrondi au centime", "op": "arrondi", "value": 0.01},
    ],
    "states": {"applied": "APPLIQUEE", "skipped": "SANS_OBJET", "blocked": "BLOQUEE"},
}
EXAMPLE_SITUATION = {
    "elements": [{"id": "A", "type": "article", "options": {"prix": 12.5, "quantite": 2}}],
    "settings": {},
}


class Blocked(Exception):
    """Une ligne qui ne se calcule pas (division par zéro…) : elle est bloquée, le cumul ne bouge pas."""


def neat(value: float) -> int | float:
    """Un résultat sans bruit de calcul binaire : 0.1 + 0.2 donne 0.3 ; un entier reste un entier."""
    value = round(value, 9)
    return int(value) if value == int(value) else value


# ---------------------------------------------------------------------------
# Déclaration
# ---------------------------------------------------------------------------


class Scope:
    """Ce qu'une valeur ou une condition peut nommer à cet endroit : les réglages, les lignes déjà calculées,
    et, dans `sum.of` ou `where`, les options des briques visées."""

    def __init__(self, decl: dict, earlier: list[str], types: list[str] | None = None):
        self.decl, self.earlier, self.types = decl, earlier, types
        self.settings = {s["key"]: values_of(s) for s in decl["settings"]}

    def inside(self, types: list[str]) -> Scope:
        return Scope(self.decl, self.earlier, types)

    @property
    def options(self) -> dict:
        """Les options communes aux types visés : chaque brique comptée doit en avoir une valeur."""
        bricks = [b for b in self.decl["bricks"] if b["type"] in (self.types or [])]
        if not bricks:
            return {}
        names = set.intersection(*({o["key"] for o in b["options"]} for b in bricks))
        out: dict[str, list] = {}
        for brick in bricks:
            for option in brick["options"]:
                if option["key"] in names:
                    out.setdefault(option["key"], values_of(option))
        return out


def _numeric(allowed) -> bool:
    return isinstance(allowed, Numbers) or (bool(allowed) and all(is_number(v) for v in allowed))


def _types(raw, decl: dict, report: Report, p: str) -> list[str] | None:
    known = [b["type"] for b in decl["bricks"]]
    if raw is None:
        return known
    wanted = as_list(raw)
    if not wanted or any(t not in known for t in wanted):
        report.error(p, "unknown_brick", "Type de brique inconnu.", received=raw, expected=known)
        return None
    return wanted


def _check_terms(name: str, terms, scope: Scope, report: Report, p: str, depth: int) -> bool:
    pair = name in ("sub", "div", "pct")
    fine = isinstance(terms, list) and (len(terms) == 2 if pair else 2 <= len(terms) <= MAX_TERMS)
    if not fine:
        size = "deux valeurs" if pair else f"de 2 à {MAX_TERMS} valeurs"
        report.error(p, "type", f"« {name} » prend une liste de {size}.", received=terms)
        return False
    ok = True
    for i, term in enumerate(terms):
        ok &= check_value(term, scope, report, f"{p}[{i}]", depth + 1)
    return ok


def _check_gather(name: str, raw, scope: Scope, report: Report, p: str, depth: int) -> bool:
    """`sum` (une valeur par brique, additionnées) et `count` (le nombre de briques posées)."""
    allowed = {"type", "where", *(["of"] if name == "sum" else [])}
    if scope.types is not None:
        report.error(p, "type", f"« {name} » porte sur toute la situation, pas sur une brique.")
        return False
    if not isinstance(raw, dict) or set(raw) - allowed or (name == "sum" and "of" not in raw):
        example = {"type": "article", "of": {"option": "prix"}} if name == "sum" else {"type": "article"}
        report.error(p, "type", f"« {name} » s'écrit {{{', '.join(sorted(allowed))}}}.", example=example)
        return False
    types = _types(raw.get("type"), scope.decl, report, f"{p}.type")
    if types is None:
        return False
    inner = scope.inside(types)
    ok = True
    if "where" in raw:
        ok &= check_condition(raw["where"], inner, report, f"{p}.where", depth + 1)
    if name == "sum":
        ok &= check_value(raw["of"], inner, report, f"{p}.of", depth + 1)
    return ok


MAX_BRACKETS = 8
EXAMPLE_SCALE = {
    "of": {"total": True},
    "brackets": [{"upto": 15, "amount": 6.9}, {"upto": 35, "amount": 4.9}, {"amount": 0}],
}


def _check_scale(raw, scope: Scope, report: Report, p: str, depth: int) -> bool:
    """Un barème : une base (`of`) et des tranches croissantes (`upto`, sauf la dernière), toutes à taux
    (`rate`, en %, appliqué part par part) ou toutes à montant (`amount`, celui de la tranche où tombe la
    base)."""
    brackets = raw.get("brackets") if isinstance(raw, dict) else None
    shaped = isinstance(raw, dict) and set(raw) <= {"of", "brackets"} and "of" in raw
    shaped = shaped and isinstance(brackets, list) and 1 <= len(brackets) <= MAX_BRACKETS
    shaped = shaped and all(isinstance(b, dict) and set(b) <= {"upto", "rate", "amount"} for b in brackets)
    kinds = {k for b in brackets for k in ("rate", "amount") if k in b} if shaped else set()
    bounds = [b.get("upto") for b in brackets] if shaped else []
    fine = shaped and len(kinds) == 1 and all(len({"rate", "amount"} & set(b)) == 1 for b in brackets)
    fine = fine and all(is_number(b[next(iter(kinds))]) for b in brackets)
    fine = fine and bounds[-1] is None and all(is_number(u) for u in bounds[:-1])
    fine = fine and all(a < b for a, b in itertools.pairwise(bounds[:-1]))
    if not fine:
        report.error(
            p,
            "type",
            f"« scale » : {{of, brackets}}, de 1 à {MAX_BRACKETS} tranches croissantes (« upto », sauf la "
            "dernière), toutes à taux (« rate ») ou toutes à montant (« amount »).",
            received=raw,
            example=EXAMPLE_SCALE,
        )
        return False
    return check_value(raw["of"], scope, report, f"{p}.of", depth + 1)


def _scale(raw: dict, ctx: dict, element: dict | None) -> float:
    """Le montant d'un barème, et son détail par tranche, noté dans `ctx["detail"]` pour la ligne."""
    base = value_of(raw["of"], ctx, element)
    detail = ctx.setdefault("detail", [])
    low = 0.0
    if "amount" in raw["brackets"][0]:
        for bracket in raw["brackets"]:
            if bracket.get("upto") is None or base < bracket["upto"]:
                below = f"sous {text_of(bracket['upto'])}" if bracket.get("upto") is not None else "au-delà"
                detail.append(f"Base {text_of(neat(base))} → tranche {below} → {text_of(bracket['amount'])}")
                return bracket["amount"]
    total = 0.0
    for bracket in raw["brackets"]:
        high = bracket.get("upto")
        part = max(0.0, (base if high is None else min(base, high)) - low)
        if part > 0:
            amount = part * bracket["rate"] / 100
            total += amount
            span = (
                f"{text_of(neat(low))} à {text_of(high)}"
                if high is not None
                else f"au-delà de {text_of(neat(low))}"
            )
            detail.append(
                f"{span} : {text_of(bracket['rate'])} % de {text_of(neat(part))} = {text_of(neat(amount))}"
            )
        if high is None or base <= high:
            break
        low = high
    return total


def _check_named(name: str, raw, scope: Scope, report: Report, p: str) -> bool:
    """`setting`, `option`, `line`, `total` : une valeur nommée de la situation."""
    if name == "total":
        if raw is not True:
            report.error(p, "type", "« total » vaut true : le cumul avant cette ligne.", received=raw)
        return raw is True
    if name == "line":
        if raw not in scope.earlier:
            report.error(
                p, "unknown_line", "Une ligne déclarée plus haut.", received=raw, expected=scope.earlier
            )
        return raw in scope.earlier
    if name == "option" and scope.types is None:
        report.error(p, "type", "« option » se lit dans `sum.of`, sur chaque brique comptée.", received=raw)
        return False
    known = scope.settings if name == "setting" else scope.options
    if raw not in known:
        report.error(p, f"unknown_{name}", "Nom inconnu.", received=raw, expected=sorted(known))
        return False
    if not _numeric(known[raw]):
        report.error(p, "not_numeric", "Ces valeurs ne sont pas des nombres : elles ne se calculent pas.")
        return False
    return True


def check_value(raw, scope: Scope, report: Report, p: str, depth: int = 0) -> bool:
    """Une valeur : un nombre, une valeur nommée, ou une opération sur des valeurs."""
    if is_number(raw):
        return True
    if depth > MAX_DEPTH:
        report.error(p, "too_deep", f"Une valeur s'emboîte sur {MAX_DEPTH} niveaux au plus.")
        return False
    if not isinstance(raw, dict) or len(raw) != 1:
        report.error(
            p, "type", "Une valeur est un nombre ou un objet d'une seule entrée.", example={"total": True}
        )
        return False
    name, inner = next(iter(raw.items()))
    if name in ("setting", "option", "line", "total"):
        return _check_named(name, inner, scope, report, f"{p}.{name}")
    if name in ("add", "sub", "mul", "div", "min", "max", "pct"):
        return _check_terms(name, inner, scope, report, f"{p}.{name}", depth)
    if name in ("sum", "count"):
        return _check_gather(name, inner, scope, report, f"{p}.{name}", depth)
    if name == "scale":
        return _check_scale(inner, scope, report, f"{p}.scale", depth)
    report.error(
        p,
        "unknown_value",
        "Valeur inconnue.",
        received=name,
        expected=[
            "setting",
            "option",
            "line",
            "total",
            "add",
            "sub",
            "mul",
            "div",
            "min",
            "max",
            "pct",
            "sum",
            "count",
            "scale",
        ],
    )
    return False


def _check_number_test(expected, report: Report, p: str, settings: dict | None = None) -> bool:
    fine = isinstance(expected, dict) and not comparison_issue(expected, Numbers(), settings)
    if is_number(expected) or fine:
        return True
    report.error(
        p,
        "type",
        "Un nombre, ou une comparaison à un nombre ou à un réglage numérique.",
        received=expected,
        example={"lt": {"setting": "seuil"}},
    )
    return False


def _check_lines_test(expected, scope: Scope, report: Report, p: str) -> bool:
    if not isinstance(expected, dict) or not expected:
        report.error(
            p, "type", "« line » compare des lignes : {ligne: nombre ou comparaison}.", received=expected
        )
        return False
    ok = True
    for key, value in expected.items():
        if key not in scope.earlier:
            report.error(
                f"{p}.{key}", "unknown_line", "Une ligne déclarée plus haut.", expected=scope.earlier
            )
            ok = False
        else:
            ok &= _check_number_test(value, report, f"{p}.{key}", scope.settings)
    return ok


def _check_elements(expected, scope: Scope, report: Report, p: str, depth: int) -> bool:
    quantifiers = [q for q in ("all", "any", "none", "count") if isinstance(expected, dict) and q in expected]
    extra = {"type", *(["where"] if quantifiers == ["count"] else [])}
    if len(quantifiers) != 1 or set(expected) - {quantifiers[0], *extra}:
        report.error(
            p,
            "type",
            "S'écrit {type?, all | any | none: condition} ou {type?, count, where?}.",
            example={"count": {"gte": 2}},
        )
        return False
    types = _types(expected.get("type"), scope.decl, report, f"{p}.type")
    if types is None:
        return False
    inner = scope.inside(types)
    if quantifiers == ["count"]:
        ok = check_count(expected["count"], report, f"{p}.count", scope.settings)
        if "where" in expected:
            ok &= check_condition(expected["where"], inner, report, f"{p}.where", depth + 1)
        return ok
    return check_condition(expected[quantifiers[0]], inner, report, f"{p}.{quantifiers[0]}", depth + 1)


def check_condition(cond, scope: Scope, report: Report, path: str, depth: int = 0) -> bool:
    """Une condition sur la situation (`setting`, `elements`, `total`, `line`), ou, dans `where`, sur une
    brique (`type`, `option`). Toutes ses entrées doivent être vraies."""
    if not isinstance(cond, dict) or not cond:
        report.error(path, "type", "Une condition est un objet non vide.", example={"total": {"gte": 100}})
        return False
    if depth > MAX_DEPTH:
        report.error(path, "too_deep", f"Une condition s'emboîte sur {MAX_DEPTH} niveaux au plus.")
        return False
    tests = ELEMENT_TESTS if scope.types is not None else SITUATION_TESTS
    ok = True
    for key, expected in cond.items():
        p = f"{path}.{key}"
        if key not in tests:
            report.error(p, "unknown_test", "Test inconnu ici.", expected=list(tests))
            ok = False
        elif key == "setting":
            ok &= check_pairs(expected, scope.settings, report, p, "setting", scope.settings)
        elif key == "option":
            ok &= check_pairs(expected, scope.options, report, p, "option", scope.settings)
        elif key == "type":
            ok &= _types(expected, scope.decl, report, p) is not None
        elif key == "total":
            ok &= _check_number_test(expected, report, p, scope.settings)
        elif key == "line":
            ok &= _check_lines_test(expected, scope, report, p)
        elif key == "elements":
            ok &= _check_elements(expected, scope, report, p, depth)
        elif key in ("all", "any"):
            fine = isinstance(expected, list) and 1 <= len(expected) <= 12
            if not fine:
                report.error(p, "type", f"« {key} » prend une liste de 1 à 12 conditions.")
            for i, item in enumerate(expected if fine else []):
                ok &= check_condition(item, scope, report, f"{p}[{i}]", depth + 1)
            ok &= fine
        else:  # not
            ok &= check_condition(expected, scope, report, p, depth + 1)
    return ok


def _line(item, decl: dict, earlier: list[str], seen: set, report: Report, p: str) -> dict | None:
    key = _key(item, "key", seen, report, p, "Une ligne")
    if key is None:
        return None
    if set(item) - {"key", "label", "op", "value", "when", "unit"}:
        report.error(
            p, "unknown_field", "Une ligne : {key, label, op, value, when, unit}.", received=sorted(item)
        )
    op = item.get("op")
    if op not in OPS:
        report.error(f"{p}.op", "enum", "Opération inconnue.", received=op, expected=list(OPS))
        return None
    scope = Scope(decl, earlier)
    value = item.get("value")
    if op == "arrondi" and not (is_number(value) and value > 0):
        report.error(f"{p}.value", "type", "Le pas d'arrondi : un nombre positif (0.01).", received=value)
        return None
    if not check_value(value, scope, report, f"{p}.value"):
        return None
    out = {"key": key, "label": _label(item, report, p, key, 80), "op": op, "value": value}
    if "when" in item and check_condition(item["when"], scope, report, f"{p}.when"):
        out["when"] = item["when"]
    unit = item.get("unit")
    if unit is not None:
        if isinstance(unit, str) and 0 < len(unit) <= 12:
            out["unit"] = unit
        else:
            report.error(f"{p}.unit", "type", "Une unité : un texte de 12 caractères au plus.", received=unit)
    return out


def _lines(raw, decl: dict, report: Report, path: str) -> list[dict]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_LINES:
        report.error(
            path, "type", f"« lines » : de 1 à {MAX_LINES} lignes de calcul.", example=EXAMPLE["lines"]
        )
        return []
    out: list[dict] = []
    seen: set = set()
    for i, item in enumerate(raw):
        line = _line(item, decl, [x["key"] for x in out], seen, report, f"{path}[{i}]")
        if line:
            out.append(line)
    return out


def _states(raw, statuses: set[str], report: Report, p: str) -> dict:
    if not isinstance(raw, dict) or set(raw) != set(STATES) or any(v not in statuses for v in raw.values()):
        report.error(
            p,
            "unknown_status",
            "« states » donne un statut de l'étude à une ligne appliquée, sans objet et bloquée.",
            received=raw,
            expected=list(STATES),
            example=EXAMPLE["states"],
        )
        return {}
    return dict(raw)


def _result(raw, report: Report, p: str) -> dict:
    out = {"label": "Résultat"}
    if raw is None:
        return out
    if not isinstance(raw, dict) or set(raw) - {"label", "unit"}:
        report.error(p, "type", "« result » : {label, unit}.", received=raw)
        return out
    out["label"] = _label(raw, report, p, "Résultat", 60)
    if isinstance(raw.get("unit"), str) and 0 < len(raw["unit"]) <= 12:
        out["unit"] = raw["unit"]
    return out


def _outcomes(raw, decl: dict, statuses: set[str], report: Report, p: str) -> list[dict]:
    if raw in (None, []):
        return []
    if not isinstance(raw, list) or len(raw) > MAX_OUTCOMES:
        report.error(p, "type", f"« outcome » : {MAX_OUTCOMES} résultats au plus {{when, label, status}}.")
        return []
    scope = Scope(decl, [line["key"] for line in decl["lines"]])
    out = []
    for i, item in enumerate(raw):
        q = f"{p}[{i}]"
        if not isinstance(item, dict) or not item.get("label"):
            report.error(q, "required", "Un résultat : {when, label, status}.")
            continue
        entry = {"label": _label(item, report, q, "", 80)}
        if "when" in item and check_condition(item["when"], scope, report, f"{q}.when"):
            entry["when"] = item["when"]
        if "status" in item:
            if item["status"] in statuses:
                entry["status"] = item["status"]
            else:
                report.error(f"{q}.status", "unknown_status", "Statut inconnu.", received=item["status"])
        out.append(entry)
    return out


def normalize(raw: Any, status_keys: set[str], report: Report, path: str = "workshop") -> dict:
    """La déclaration d'un atelier de calcul, validée."""
    if set(raw) - FIELDS:
        report.error(
            path, "unknown_field", "Champ inconnu dans « workshop ».", received=sorted(set(raw) - FIELDS)
        )
    bricks = _bricks(raw.get("bricks"), status_keys, report, f"{path}.bricks", numeric=True)
    for i, brick in enumerate(bricks):
        if brick["events"]:
            report.error(
                f"{path}.bricks[{i}].events", "unknown_field", "Une brique de calcul n'a pas d'évènements."
            )
    settings = _choices(
        raw.get("settings"), report, f"{path}.settings", "Un réglage", MAX_SETTINGS, True, True
    )
    decl: dict[str, Any] = {
        "family": FAMILY,
        "title": _label(raw, report, path, "", 80, "title"),
        "bricks": bricks,
        "links": [],
        "settings": settings,
    }
    decl["lines"] = _lines(raw.get("lines"), decl, report, f"{path}.lines") if bricks else []
    decl["result"] = _result(raw.get("result"), report, f"{path}.result")
    decl["states"] = _states(raw.get("states"), status_keys, report, f"{path}.states")
    decl["outcome"] = _outcomes(raw.get("outcome"), decl, status_keys, report, f"{path}.outcome")
    decl["rules"] = [{"key": line["key"], "title": rule_text(line)} for line in decl["lines"]]
    return decl


def declared(decl: dict | None) -> bool:
    return bool(decl and decl.get("bricks") and decl.get("lines") and decl.get("states"))


def rule_text(line: dict) -> str:
    """La phrase qu'un relecteur lit pour une ligne : son libellé, et ce qu'elle fait du cumul."""
    return line["label"][:200]


# ---------------------------------------------------------------------------
# Situation : les briques posées et leurs valeurs
# ---------------------------------------------------------------------------


def situation(decl: dict, raw: Any, report: Report, path: str = "situation") -> dict:
    """Des briques posées, vérifiées contre ce que l'étude déclare. L'invalide est signalé et écarté."""
    out: dict[str, Any] = {"elements": [], "links": [], "events": {}, "settings": {}}
    if not isinstance(raw, dict):
        report.error(
            path, "type", "Une situation est un objet {elements, settings}.", example=EXAMPLE_SITUATION
        )
        raw = {}
    if raw.get("links"):
        report.error(f"{path}.links", "unknown_field", "Un atelier de calcul ne relie pas ses briques.")
    out["settings"] = _chosen(decl["settings"], raw.get("settings"), report, f"{path}.settings")
    items = raw.get("elements") or []
    if not isinstance(items, list) or len(items) > MAX_ELEMENTS:
        report.error(
            f"{path}.elements", "max_items", f"{MAX_ELEMENTS} briques au plus.", example=EXAMPLE_SITUATION
        )
        items = items[:MAX_ELEMENTS] if isinstance(items, list) else []
    bricks = {b["type"]: b for b in decl["bricks"]}
    seen: set = set()
    for i, item in enumerate(items):
        p = f"{path}.elements[{i}]"
        key = _key(item, "id", seen, report, p, "Une brique")
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
            }
        )
    return out


def from_query(decl: dict, query: dict[str, list[str]]) -> dict:
    """La situation écrite dans une adresse : `e=A:article`, `n.A=…`, `o.A.prix=12.5`, `r.reglage=valeur`."""
    sit = _linked_query(decl, query)
    return {"elements": sit["elements"], "settings": sit["settings"]}


def to_query(decl: dict, sit: dict) -> list[tuple[str, str]]:
    return _linked_to_query(decl, {**sit, "events": {}, "links": []})


def placed(decl: dict, query: dict[str, list[str]], letter: str, kind: str) -> list[str]:
    """Une brique posée n'est reliée à rien."""
    return []


# ---------------------------------------------------------------------------
# Moteur : les lignes, l'une après l'autre
# ---------------------------------------------------------------------------


def _items(ctx: dict, raw: dict) -> list[dict]:
    types = as_list(raw["type"]) if "type" in raw else None
    where = raw.get("where")
    return [
        e
        for e in ctx["elements"]
        if (types is None or e["type"] in types) and (where is None or holds(where, ctx, e))
    ]


def _divide(a: float, b: float) -> float:
    if b == 0:
        raise Blocked("division par zéro")
    return a / b


def value_of(raw, ctx: dict, element: dict | None = None) -> float:
    """La valeur d'une expression déclarée ; `Blocked` si elle ne se calcule pas."""
    if is_number(raw):
        return raw
    name, inner = next(iter(raw.items()))
    if name == "total":
        return ctx["total"]
    if name == "setting":
        return ctx["settings"][inner]
    if name == "option":
        return element["options"][inner]
    if name == "line":
        amount = ctx["lines"].get(inner)
        return 0 if amount is None else amount  # une ligne sans objet compte pour zéro
    if name in ("sum", "count"):
        found = _items(ctx, inner)
        return len(found) if name == "count" else sum(value_of(inner["of"], ctx, e) for e in found)
    if name == "scale":
        return _scale(inner, ctx, element)
    terms = [value_of(term, ctx, element) for term in inner]
    if name == "add":
        return sum(terms)
    if name == "sub":
        return terms[0] - terms[1]
    if name == "mul":
        product = 1.0
        for term in terms:
            product *= term
        return product
    if name == "div":
        return _divide(terms[0], terms[1])
    if name == "pct":
        return terms[0] * terms[1] / 100
    return min(terms) if name == "min" else max(terms)


def holds(cond: dict, ctx: dict, element: dict | None = None) -> bool:
    for key, expected in cond.items():
        if key == "setting":
            fine = pairs_hold(expected, ctx["settings"], ctx["settings"])
        elif key == "option":
            fine = pairs_hold(expected, element["options"], ctx["settings"])
        elif key == "type":
            fine = element["type"] in as_list(expected)
        elif key == "total":
            fine = matches(ctx["total"], expected, ctx["settings"])
        elif key == "line":
            fine = all(
                ctx["lines"].get(k) is not None and matches(ctx["lines"][k], v, ctx["settings"])
                for k, v in expected.items()
            )
        elif key == "elements":
            fine = _elements_hold(expected, ctx)
        elif key == "all":
            fine = all(holds(c, ctx, element) for c in expected)
        elif key == "any":
            fine = any(holds(c, ctx, element) for c in expected)
        else:  # not
            fine = not holds(expected, ctx, element)
        if not fine:
            return False
    return True


def _elements_hold(expected: dict, ctx: dict) -> bool:
    types = as_list(expected["type"]) if "type" in expected else None
    pool = [e for e in ctx["elements"] if types is None or e["type"] in types]
    if "count" in expected:
        where = expected.get("where")
        found = sum(1 for e in pool if where is None or holds(where, ctx, e))
        return matches(found, expected["count"], ctx["settings"])
    if "all" in expected:
        return all(holds(expected["all"], ctx, e) for e in pool)
    if "any" in expected:
        return any(holds(expected["any"], ctx, e) for e in pool)
    return not any(holds(expected["none"], ctx, e) for e in pool)


def _rounded(total: float, step: float) -> float:
    try:
        units = (Decimal(str(total)) / Decimal(str(step))).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    except InvalidOperation:  # pragma: no cover - un total fini se divise toujours par un pas positif
        raise Blocked("arrondi impossible") from None
    return float(units * Decimal(str(step)))


def apply(op: str, total: float, amount: float) -> float:
    """Le cumul après une ligne."""
    if op == "=":
        return amount
    if op == "+":
        return total + amount
    if op == "-":
        return total - amount
    if op == "×":
        return total * amount
    if op == "÷":
        return _divide(total, amount)
    if op == "min":
        return min(total, amount)
    if op == "max":
        return max(total, amount)
    return _rounded(total, amount)


def _why(line: dict, status: str, amount, reason: str) -> str:
    if status == "skipped":
        return "Sa condition n'est pas remplie : la ligne est sans objet."
    if status == "blocked":
        return f"La ligne ne se calcule pas ({reason}) : le cumul ne bouge pas."
    unit = f" {line['unit']}" if line.get("unit") else ""
    said = text_of(neat(amount)).replace(".", ",")  # une phrase lue par une personne : virgule décimale
    return f"La ligne {OP_WORDS[line['op']]} {said}{unit}."


def run(decl: dict, situation: dict, default_status: str) -> dict:
    """Applique les lignes dans l'ordre. Rend {steps, end, entries, total, used} : un pas par ligne ; `end`
    vaut `blocked` si une ligne n'a pas pu être calculée (le résultat d'ensemble n'est alors pas donné)."""
    states = {e["id"]: default_status for e in situation["elements"]}
    states |= {LINE_PREFIX + line["key"]: default_status for line in decl["lines"]}
    steps = [{"states": dict(states), "changes": []}]
    ctx = {"settings": situation["settings"], "elements": situation["elements"], "total": 0, "lines": {}}
    entries, used, blocked = [], [], False
    for line in decl["lines"]:
        before, amount, status, reason = ctx["total"], None, "applied", ""
        if "when" in line and not holds(line["when"], ctx):
            status = "skipped"
        else:
            try:
                ctx.pop("detail", None)
                amount = neat(value_of(line["value"], ctx))
                ctx["total"] = neat(apply(line["op"], before, amount))
            except Blocked as error:
                status, reason, amount, blocked = "blocked", str(error), None, True
        ctx["lines"][line["key"]] = amount if status == "applied" else None
        if status == "applied":
            used.append(line["key"])
        entity = LINE_PREFIX + line["key"]
        change = {"id": entity, "from": states[entity], "to": decl["states"][status]}
        if status == "applied":  # une ligne sans objet ou bloquée n'a rien appliqué
            change["rule"] = line["key"]
        states[entity] = decl["states"][status]
        steps.append({"states": dict(states), "changes": [change]})
        entries.append(
            {
                "key": line["key"],
                "label": line["label"],
                "op": line["op"],
                "unit": line.get("unit", ""),
                "status": status,
                "amount": amount,
                "before": before,
                "after": ctx["total"],
                "why": _why(line, status, amount, reason),
            }
            | ({"detail": ctx.pop("detail")} if ctx.get("detail") and status == "applied" else {})
        )
        ctx.pop("detail", None)
    return {
        "steps": steps,
        "end": "blocked" if blocked else "stable",
        "entries": entries,
        "total": ctx["total"],
        "used": used,
        "ctx": ctx,
    }


def outcome(decl: dict, result: dict) -> dict | None:
    """Le résultat d'ensemble : aucun si une ligne est bloquée ; sinon le premier déclaré dont la condition
    tient, avec le cumul final pour `total`."""
    if result["end"] != "stable":
        return None
    for item in decl["outcome"]:
        if "when" not in item or holds(item["when"], result["ctx"]):
            return {k: v for k, v in item.items() if k != "when"}
    return None


def plan(decl: dict) -> dict:
    return {}


def extra(decl: dict, result: dict) -> dict:
    """Ce que cette famille ajoute à la réponse d'un déroulé : les lignes, leur montant et le cumul."""
    return {
        "lines": result["entries"],
        "total": result["total"],
        "result": {**decl["result"], "value": result["total"] if result["end"] == "stable" else None},
    }


# ---------------------------------------------------------------------------
# Du calcul déroulé à un cas ordinaire
# ---------------------------------------------------------------------------


def _case_step(decl: dict, entry: dict) -> dict:
    status = decl["states"][entry["status"]]
    step = {
        "title": entry["label"]
        + (
            ""
            if entry["status"] == "applied"
            else " — sans objet"
            if entry["status"] == "skipped"
            else " — bloquée"
        ),
        "note": entry["why"],
        "changes": {LINE_PREFIX + entry["key"]: status},
    }
    if entry["status"] == "applied":
        value = {
            "label": entry["label"][:80],
            "op": entry["op"],
            "value": entry["amount"],
            "result": entry["after"],
        }
        if entry["unit"]:
            value["unit"] = entry["unit"]
        step["values"] = [value]
    return step


def to_case(decl: dict, situation: dict, result: dict, default_status: str) -> dict:
    """Les briques posées et le calcul, sous la forme d'un cas : une entité par ligne, un pas par ligne, et
    les lignes appliquées dans `values` (lisibles dans la représentation « calcul pas à pas »)."""
    entities = [
        {
            "id": e["id"],
            "label": e["label"],
            "type": e["type"],
            "group": "Briques posées",
            "attrs": dict(e["options"]),
        }
        for e in situation["elements"]
    ]
    entities += [
        {
            "id": LINE_PREFIX + line["key"],
            "label": line["label"][:80],
            "type": "ligne",
            "group": "Lignes de calcul",
        }
        for line in decl["lines"]
    ]
    steps = [{"title": "Briques posées", "note": "Aucune ligne n'est encore calculée."}]
    steps += [_case_step(decl, entry) for entry in result["entries"]]
    case = {
        "key": "atelier",
        "title": decl.get("title") or "Situation construite",
        "family": "Atelier",
        "kind": "decision",
        "config": dict(situation["settings"]),
        "entities": entities,
        # Une brique posée garde son état : il est dit, pour qu'on ne la croie pas oubliée.
        "initial": {e["id"]: default_status for e in situation["elements"]},
        "steps": steps,
    }
    found = outcome(decl, result)
    if found:
        case["outcome"] = found
    return case
