"""Cas paramétré : un cas dont certaines étapes dépendent de paramètres déclarés.

L'auteur déclare des paramètres (`params`) et pose une condition (`when`) sur des étapes, ou donne plusieurs
résultats possibles (`outcome` en liste). Le site évalue ces conditions — égalité, comparaison, et / ou / non,
rien d'autre — et rejoue le cas pour **chaque** combinaison de paramètres : toutes doivent donner un cas
valide.

Forme rangée en base : la variante par défaut, qui est un cas ordinaire (tout ce qui lit un cas la comprend),
plus `params` et `source` (les étapes avec leurs conditions, les résultats possibles, les options qui suivent
un paramètre). `source_of` rend la forme déposée, `resolve` une variante.

Pur : aucun accès à la base.
"""

from __future__ import annotations

import copy
import json
import re
from itertools import product
from typing import Any

from .casemodel import ID_RE, Report, StudyContext, _is_str

MAX_PARAMS = 6
MAX_PARAM_VALUES = 8
MAX_COMBOS = 64
MAX_DEPTH = 4
COMPARISONS = ("eq", "ne", "in", "gt", "gte", "lt", "lte")
COMBINATORS = ("all", "any", "not")
EXAMPLE_PARAM = {
    "key": "always_run",
    "label": "C toujours exécutée",
    "values": [True, False],
    "default": False,
}
EXAMPLE_WHEN = {"always_run": True}


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _same(a, b) -> bool:
    """Égalité stricte : true ne vaut pas 1, « 1 » ne vaut pas 1 ; un entier et un décimal égaux se valent."""
    if _num(a) and _num(b):
        return a == b
    return type(a) is type(b) and a == b


def _among(value, values: list) -> bool:
    return any(_same(value, v) for v in values)


def shown(value) -> str:
    """Une valeur de paramètre telle qu'on l'écrit : true, false, 3, « Premium »."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return f"{value:g}" if isinstance(value, float) else str(value)


# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------


def _param_values(item: dict, dim_values: set | None, report: Report, p: str) -> list:
    raw = item.get("values")
    if not isinstance(raw, list) or not (2 <= len(raw) <= MAX_PARAM_VALUES):
        report.error(
            f"{p}.values",
            "min_items",
            f"Un paramètre a de 2 à {MAX_PARAM_VALUES} valeurs possibles.",
            received=raw,
            example=EXAMPLE_PARAM["values"],
        )
        return []
    values: list = []
    for j, value in enumerate(raw):
        simple = isinstance(value, bool) or _num(value) or (_is_str(value, 60) and value)
        if not simple:
            report.error(
                f"{p}.values[{j}]",
                "type",
                "Une valeur de paramètre est un texte court, un nombre ou un booléen.",
                received=value,
            )
        elif _among(value, values):
            report.error(f"{p}.values[{j}]", "duplicate", "Valeur de paramètre répétée.", received=value)
        elif dim_values is not None and value not in dim_values:
            report.error(
                f"{p}.values[{j}]",
                "unknown_value",
                "Ce paramètre porte le nom d'une dimension de l'étude : ses valeurs sont celles de la "
                "dimension.",
                received=value,
                expected=sorted(dim_values),
            )
        else:
            values.append(value)
    return values


def _param(item, ctx: StudyContext, seen: set[str], report: Report, p: str) -> dict | None:
    if not isinstance(item, dict):
        report.error(
            p, "type", "Un paramètre est un objet {key, label, values, default}.", example=EXAMPLE_PARAM
        )
        return None
    key = item.get("key")
    if not (isinstance(key, str) and ID_RE.match(key)) or key in COMBINATORS:
        report.error(f"{p}.key", "format", "Nom de paramètre invalide.", received=key, example="always_run")
        return None
    if key in seen:
        report.error(f"{p}.key", "duplicate", f"Le paramètre « {key} » est déclaré deux fois.", received=key)
        return None
    seen.add(key)
    before = len(report.errors)
    values = _param_values(item, ctx.dimension_values.get(key), report, p)
    label = item.get("label") or key
    if not _is_str(label, 80):
        report.error(f"{p}.label", "type", "Le libellé d'un paramètre est un texte de 80 caractères au plus.")
        label = key
    if len(report.errors) > before:
        return None
    default = item.get("default", values[0])
    if not _among(default, values):
        report.error(
            f"{p}.default",
            "unknown_value",
            "La valeur par défaut d'un paramètre est une de ses valeurs.",
            received=default,
            expected=values,
        )
        return None
    return {"key": key, "label": label, "values": values, "default": default}


def normalize_params(raw, ctx: StudyContext, report: Report, path: str) -> list[dict]:
    if not isinstance(raw, list) or not raw:
        report.error(path, "type", "« params » est la liste des paramètres du cas.", example=[EXAMPLE_PARAM])
        return []
    if len(raw) > MAX_PARAMS:
        report.error(path, "max_items", f"{MAX_PARAMS} paramètres au plus par cas.", received=len(raw))
    params, seen = [], set()
    for i, item in enumerate(raw[:MAX_PARAMS]):
        param = _param(item, ctx, seen, report, f"{path}[{i}]")
        if param:
            params.append(param)
    count = 1
    for param in params:
        count *= len(param["values"])
    if count > MAX_COMBOS:
        report.error(
            path,
            "too_many_combinations",
            f"Ces paramètres donnent {count} combinaisons ; le site en rejoue {MAX_COMBOS} au plus par cas. "
            "Retirez un paramètre ou des valeurs, ou découpez en plusieurs cas.",
            received=count,
        )
    return params


def default_combo(params: list[dict]) -> dict:
    return {p["key"]: p["default"] for p in params}


def combos(params: list[dict]) -> list[dict]:
    """Toutes les combinaisons de valeurs, celle par défaut en premier."""
    first = default_combo(params)
    keys = [p["key"] for p in params]
    rest = [dict(zip(keys, values, strict=True)) for values in product(*(p["values"] for p in params))]
    return [first, *[c for c in rest if not all(_same(c[k], first[k]) for k in keys)]]


def combo_key(combo: dict) -> str:
    return json.dumps(combo, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def combo_text(combo: dict) -> str:
    return ", ".join(f"{key} = {shown(value)}" for key, value in combo.items())


# ---------------------------------------------------------------------------
# Conditions : égalité, comparaison, et / ou / non
# ---------------------------------------------------------------------------


def _check_comparison(expected: dict, param: dict, report: Report, p: str) -> bool:
    ok = bool(expected)
    for op, value in expected.items():
        if op not in COMPARISONS:
            report.error(
                f"{p}.{op}", "enum", "Comparaison inconnue.", received=op, expected=list(COMPARISONS)
            )
            ok = False
        elif op in ("gt", "gte", "lt", "lte"):
            if not _num(value) or not all(_num(v) for v in param["values"]):
                report.error(
                    f"{p}.{op}",
                    "type",
                    "Une comparaison d'ordre porte sur un paramètre dont toutes les valeurs sont des "
                    "nombres.",
                    received=value,
                )
                ok = False
        elif op == "in":
            if not isinstance(value, list) or not all(_among(v, param["values"]) for v in value):
                report.error(
                    f"{p}.in", "unknown_value", "« in » liste des valeurs du paramètre.", received=value
                )
                ok = False
        elif not _among(value, param["values"]):
            report.error(
                f"{p}.{op}",
                "unknown_value",
                "Valeur inconnue du paramètre.",
                received=value,
                expected=param["values"],
            )
            ok = False
    return ok


def _check_test(expected, param: dict, report: Report, p: str) -> bool:
    if isinstance(expected, dict):
        return _check_comparison(expected, param, report, p)
    wanted = expected if isinstance(expected, list) else [expected]
    if not wanted or not all(_among(v, param["values"]) for v in wanted):
        report.error(
            p,
            "unknown_value",
            f"Le paramètre « {param['key']} » ne prend pas cette valeur.",
            received=expected,
            expected=param["values"],
        )
        return False
    return True


def check_condition(cond, params: dict[str, dict], report: Report, path: str, depth: int = 0) -> bool:
    """Vérifie une condition : {paramètre: valeur}, {paramètre: {gt: 3}}, {all: […]}, {any: […]}, {not: …}."""
    if not isinstance(cond, dict) or not cond or depth > MAX_DEPTH:
        report.error(
            path,
            "type",
            "Une condition associe à des paramètres la valeur attendue ; « all », « any » et « not » "
            f"les combinent, sur {MAX_DEPTH} niveaux au plus.",
            received=cond,
            example=EXAMPLE_WHEN,
        )
        return False
    ok = True
    for key, expected in cond.items():
        p = f"{path}.{key}"
        if key in ("all", "any"):
            if not isinstance(expected, list) or not (1 <= len(expected) <= 8):
                report.error(p, "type", f"« {key} » liste de 1 à 8 conditions.", received=expected)
                ok = False
            else:
                for i, sub in enumerate(expected):
                    ok = check_condition(sub, params, report, f"{p}[{i}]", depth + 1) and ok
        elif key == "not":
            ok = check_condition(expected, params, report, p, depth + 1) and ok
        elif key not in params:
            report.error(
                p,
                "unknown_param",
                f"La condition porte sur un paramètre non déclaré « {key} ».",
                received=key,
                expected=sorted(params),
            )
            ok = False
        else:
            ok = _check_test(expected, params[key], report, p) and ok
    return ok


def _test(actual, expected) -> bool:
    if isinstance(expected, list):
        return _among(actual, expected)
    if not isinstance(expected, dict):
        return _same(actual, expected)
    checks = {
        "eq": lambda v: _same(actual, v),
        "ne": lambda v: not _same(actual, v),
        "in": lambda v: _among(actual, v),
        "gt": lambda v: actual > v,
        "gte": lambda v: actual >= v,
        "lt": lambda v: actual < v,
        "lte": lambda v: actual <= v,
    }
    return all(checks[op](value) for op, value in expected.items())


def holds(cond: dict | None, values: dict) -> bool:
    """Vrai si la condition (déjà vérifiée) est satisfaite par ces valeurs de paramètres."""
    for key, expected in (cond or {}).items():
        if key == "all":
            ok = all(holds(sub, values) for sub in expected)
        elif key == "any":
            ok = any(holds(sub, values) for sub in expected)
        elif key == "not":
            ok = not holds(expected, values)
        else:
            ok = _test(values[key], expected)
        if not ok:
            return False
    return True


# ---------------------------------------------------------------------------
# Du cas déposé à ses variantes
# ---------------------------------------------------------------------------


def _attr_refs(raw: dict, params: dict, report: Report, path: str) -> dict:
    """Options d'entité qui suivent un paramètre : {entité: {option: paramètre}}."""
    refs: dict = {}
    for i, ent in enumerate(raw.get("entities") or []):
        attrs = ent.get("attrs") if isinstance(ent, dict) else None
        for name, value in (attrs or {}).items() if isinstance(attrs, dict) else []:
            if not isinstance(value, dict):
                continue
            key = value.get("param")
            if set(value) != {"param"} or key not in params:
                report.error(
                    f"{path}.entities[{i}].attrs.{name}",
                    "unknown_param",
                    'Une option qui suit un paramètre s\'écrit {"param": "nom"}, avec un paramètre déclaré.',
                    received=value,
                    expected=sorted(params),
                )
            else:
                refs.setdefault(ent.get("id"), {})[name] = key
    return refs


def _check_sources(raw: dict, params: dict, ctx: StudyContext, report: Report, path: str) -> dict:
    """Vérifie tout ce qui dépend des paramètres ; rend les options d'entité qui en suivent un."""
    for field in ("dimensions", "config"):
        for key in set(raw.get(field) or {}) & set(params) if isinstance(raw.get(field), dict) else []:
            report.error(
                f"{path}.{field}.{key}",
                "duplicate",
                f"« {key} » est un paramètre du cas : sa valeur ne se fixe pas aussi dans « {field} ».",
            )
    for i, step in enumerate(raw.get("steps") or [] if isinstance(raw.get("steps"), list) else []):
        if isinstance(step, dict) and step.get("when") is not None:
            check_condition(step["when"], params, report, f"{path}.steps[{i}].when")
    outcome = raw.get("outcome")
    if isinstance(outcome, list):
        if not (1 <= len(outcome) <= 12) or not all(isinstance(o, dict) for o in outcome):
            report.error(
                f"{path}.outcome",
                "type",
                "« outcome » en liste donne de 1 à 12 résultats possibles {when, label, status} ; le premier "
                "dont la condition est satisfaite vaut.",
            )
        else:
            for i, item in enumerate(outcome):
                if item.get("when") is not None:
                    check_condition(item["when"], params, report, f"{path}.outcome[{i}].when")
    return _attr_refs(raw, params, report, path)


def _variant_raw(
    raw: dict, params: list[dict], combo: dict, dim_keys: set, refs: dict
) -> tuple[dict, list[int], int]:
    """Le cas ordinaire qu'une combinaison donne. Rend (cas, rang d'origine de chaque étape gardée, rang du
    résultat retenu ou -1)."""
    out = {k: copy.deepcopy(v) for k, v in raw.items() if k not in ("params", "source")}
    kept = [
        (i, step)
        for i, step in enumerate(raw["steps"] if isinstance(raw.get("steps"), list) else [])
        if not isinstance(step, dict) or holds(step.get("when"), combo)
    ]
    if isinstance(raw.get("steps"), list):
        out["steps"] = [
            {k: v for k, v in step.items() if k != "when"} if isinstance(step, dict) else step
            for _, step in kept
        ]
    chosen = -1
    if isinstance(raw.get("outcome"), list):
        chosen = next((i for i, o in enumerate(raw["outcome"]) if holds(o.get("when"), combo)), -1)
        out.pop("outcome", None)
        if chosen >= 0:
            out["outcome"] = {k: v for k, v in raw["outcome"][chosen].items() if k != "when"}
    dims, config = dict(raw.get("dimensions") or {}), dict(raw.get("config") or {})
    for param in params:
        target = dims if param["key"] in dim_keys else config
        target[param["key"]] = combo[param["key"]]
    out["dimensions"], out["config"] = dims, config
    for ent in out["entities"] if refs else []:
        for name, key in refs.get(ent.get("id") if isinstance(ent, dict) else None, {}).items():
            ent["attrs"][name] = combo[key]
    return out, [i for i, _ in kept], chosen


def _carry_issues(report: Report, sub: Report, path: str, kept: list[int], combo: dict, seen: set):
    """Reporte les constats d'une variante sur le cas déposé : rang d'étape d'origine, combinaison nommée."""
    pattern = re.compile(rf"^{re.escape(path)}\.steps\[(\d+)\]")
    for issue in sub.issues:
        where = pattern.sub(
            lambda m: f"{path}.steps[{kept[int(m.group(1))] if int(m.group(1)) < len(kept) else m.group(1)}]",
            issue.path,
        )
        if (where, issue.code, issue.message) in seen:
            continue
        seen.add((where, issue.code, issue.message))
        issue.path = where
        issue.message = f"{issue.message} (avec {combo_text(combo)})"
        report.issues.append(issue)


def _source(raw: dict, variants: list, refs: dict, report: Report, path: str) -> dict | None:
    """Les étapes et résultats du cas déposé, sous forme normalisée, avec leurs conditions."""
    steps: dict[int, dict] = {}
    outcomes: dict[int, dict] = {}
    for _, case, kept, chosen in variants:
        for position, origin in enumerate(kept):
            steps.setdefault(origin, case["steps"][position])
        if chosen >= 0 and case.get("outcome"):
            outcomes.setdefault(chosen, case["outcome"])
    raw_steps = raw["steps"]
    for i in sorted(set(range(len(raw_steps))) - set(steps)):
        report.error(
            f"{path}.steps[{i}].when",
            "never_true",
            "Aucune combinaison de paramètres ne retient cette étape : sa condition n'est jamais satisfaite.",
            received=raw_steps[i].get("when"),
        )
    if not report.ok:
        return None
    source: dict[str, Any] = {
        "steps": [
            {**steps[i], **({"when": raw_steps[i]["when"]} if raw_steps[i].get("when") is not None else {})}
            for i in range(len(raw_steps))
        ],
        "dimensions": variants[0][1]["dimensions"],
        "config": variants[0][1]["config"],
    }
    if isinstance(raw.get("outcome"), list):
        source["outcome"] = [
            {**outcomes[i], **({"when": item["when"]} if item.get("when") is not None else {})}
            for i, item in enumerate(raw["outcome"])
            if i in outcomes
        ]
    if refs:
        source["attrs"] = refs
    return source


def normalize(raw: dict, ctx: StudyContext, path: str) -> tuple[dict | None, Report]:
    """Valide un cas paramétré : ses paramètres, ses conditions, puis chaque combinaison comme un cas
    ordinaire. Rend la forme rangée en base (variante par défaut + `params` + `source`)."""
    from . import casemodel

    if isinstance(raw.get("source"), dict) and isinstance(raw["source"].get("steps"), list):
        raw = source_of(raw)  # un cas relu par l'API et redéposé tel quel
    report = Report()
    params = normalize_params(raw.get("params"), ctx, report, f"{path}.params")
    by_key = {p["key"]: p for p in params}
    refs = _check_sources(raw, by_key, ctx, report, path) if report.ok else {}
    if not report.ok:
        return None, report
    dim_keys = set(ctx.dimension_values)
    variants, seen, failed = [], set(), 0
    for combo in combos(params):
        variant, kept, chosen = _variant_raw(raw, params, combo, dim_keys, refs)
        case, sub = casemodel.normalize_case(variant, ctx, path)
        _carry_issues(report, sub, path, kept, combo, seen)
        if case is None:
            failed += 1
            if failed >= 3:  # trois combinaisons en échec suffisent à situer le problème
                break
        else:
            variants.append((combo, case, kept, chosen))
    if not report.ok:
        return None, report
    source = _source(raw, variants, refs, report, path)
    if source is None:
        return None, report
    default = variants[0][1]
    source["dimensions"] = {k: v for k, v in default["dimensions"].items() if k not in by_key}
    source["config"] = {k: v for k, v in default["config"].items() if k not in by_key}
    return {**default, "params": params, "source": source}, report


# ---------------------------------------------------------------------------
# Lecture d'un cas paramétré rangé en base
# ---------------------------------------------------------------------------


def is_parametric(content: dict) -> bool:
    return bool(content.get("params")) and isinstance(content.get("source"), dict)


def resolve(content: dict, combo: dict) -> dict:
    """La variante d'un cas paramétré pour une combinaison : un cas ordinaire, sans `params` ni `source`."""
    source = content["source"]
    dim_keys = set(content["dimensions"]) - set(source["dimensions"])
    out = {k: v for k, v in content.items() if k not in ("params", "source", "outcome")}
    out["steps"] = [
        {k: v for k, v in step.items() if k != "when"}
        for step in source["steps"]
        if holds(step.get("when"), combo)
    ]
    if "outcome" in source:
        chosen = next((o for o in source["outcome"] if holds(o.get("when"), combo)), None)
        if chosen:
            out["outcome"] = {k: v for k, v in chosen.items() if k != "when"}
    elif content.get("outcome"):
        out["outcome"] = content["outcome"]
    out["dimensions"] = {**source["dimensions"], **{k: v for k, v in combo.items() if k in dim_keys}}
    out["config"] = {**source["config"], **{k: v for k, v in combo.items() if k not in dim_keys}}
    refs = source.get("attrs") or {}
    out["entities"] = [
        {**ent, "attrs": {**ent.get("attrs", {}), **{n: combo[k] for n, k in refs[ent["id"]].items()}}}
        if ent["id"] in refs
        else ent
        for ent in content.get("entities", [])
    ]
    return out


def expand(content: dict) -> list[tuple[dict | None, dict]]:
    """(combinaison, cas ordinaire) pour chaque variante ; un cas ordinaire rend (None, lui-même)."""
    if not is_parametric(content):
        return [(None, content)]
    return [(combo, resolve(content, combo)) for combo in combos(content["params"])]


def read_combo(content: dict, raw: dict) -> dict:
    """La combinaison que désignent des valeurs écrites en texte ; une valeur absente ou inconnue prend la
    valeur par défaut du paramètre."""
    combo = {}
    for param in content["params"]:
        wanted = raw.get(param["key"])
        combo[param["key"]] = next((v for v in param["values"] if shown(v) == wanted), param["default"])
    return combo


def source_of(content: dict) -> dict:
    """Le cas tel qu'il se dépose : étapes avec leurs conditions, résultats possibles, options qui suivent un
    paramètre."""
    if not is_parametric(content):
        return content
    source = content["source"]
    out = {k: copy.deepcopy(v) for k, v in content.items() if k != "source"}
    out["steps"] = copy.deepcopy(source["steps"])
    out["dimensions"], out["config"] = dict(source["dimensions"]), dict(source["config"])
    if "outcome" in source:
        out["outcome"] = copy.deepcopy(source["outcome"])
    for ent in out.get("entities", []):
        for name, key in (source.get("attrs") or {}).get(ent["id"], {}).items():
            ent.setdefault("attrs", {})[name] = {"param": key}
    return out


def dimension_rows(content: dict) -> list[dict]:
    """Les combinaisons de dimensions qu'un cas illustre : une seule pour un cas ordinaire, une par variante
    distincte pour un cas paramétré."""
    if not is_parametric(content):
        return [content.get("dimensions") or {}]
    rows: list[dict] = []
    for _, variant in expand(content):
        if variant["dimensions"] not in rows:
            rows.append(variant["dimensions"])
    return rows


def semantic_material(content: dict, variant_hash) -> dict:
    """Ce qui entre dans l'empreinte d'un cas paramétré : ses paramètres et le déroulé de chaque variante.
    Réécrire une condition sans changer ce qu'une combinaison montre ne touche pas aux avis."""
    return {
        "params": [[p["key"], p["values"], p["default"]] for p in content["params"]],
        "variants": {combo_key(combo): variant_hash(variant) for combo, variant in expand(content)},
    }
