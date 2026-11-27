"""Couverture sur dimensions déclarées et contrôles de structure à l'échelle de l'étude.

Le site ne sait pas si « tous les cas » existent ; il sait compter les combinaisons de
valeurs de dimensions qu'aucun cas n'illustre. La couverture ne vaut que ce que vaut la
liste des dimensions déclarées par l'étude.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations, product

MAX_MISSING_LISTED = 200


def _excluded(combo: dict, exclusions: list[dict]) -> str | None:
    for exclusion in exclusions:
        when = exclusion["when"]
        if all(combo.get(k) == v for k, v in when.items()):
            return exclusion.get("reason") or "exclue"
    return None


def coverage(dimensions: list[dict], exclusions: list[dict], cases: list[dict], strength: int = 2) -> dict:
    """Combinaisons de `strength` dimensions couvertes et manquantes.

    `cases` : liste de {key, number, dimensions}. Une exclusion ne s'applique à une
    combinaison que si elle porte sur des dimensions toutes présentes dans la combinaison.
    """
    dims = {d["key"]: [v["value"] for v in d["values"]] for d in dimensions}
    labels = {d["key"]: d.get("label") or d["key"] for d in dimensions}
    keys = list(dims)
    strength = max(1, min(strength, 3, len(keys))) if keys else 0
    result = {
        "strength": strength,
        "dimensions": [{"key": k, "label": labels[k], "values": dims[k]} for k in keys],
        "cases_counted": 0,
        "cases_without_dimensions": [],
        "total": 0,
        "covered": 0,
        "excluded": 0,
        "missing_count": 0,
        "ratio": None,
        "missing": [],
        "truncated": False,
        "by_dimension": [],
        "note": "La couverture mesure les combinaisons de valeurs déclarées qu'au moins un cas illustre. "
        "Elle ne dit rien des situations que les dimensions ne décrivent pas.",
    }
    if not keys:
        result["note"] = (
            "Aucune dimension n'est déclarée : la couverture ne peut pas être mesurée. "
            "Déclarez les facteurs qui varient d'un cas à l'autre (PATCH /studies/{id}, champ dimensions)."
        )
        return result

    seen: dict[tuple, list[str]] = defaultdict(list)
    counted: set[str] = set()
    for case in cases:
        cdims = case.get("dimensions") or {}
        if not cdims:
            result["cases_without_dimensions"].append(case["key"])
            continue
        if case["key"] not in counted:  # un cas paramétré donne plusieurs lignes : il compte une fois
            counted.add(case["key"])
            result["cases_counted"] += 1
        for group in combinations(keys, strength):
            if all(k in cdims for k in group):
                seen[(group, tuple(cdims[k] for k in group))].append(case["key"])

    missing = []
    total = covered = excluded = 0
    for group in combinations(keys, strength):
        for values in product(*(dims[k] for k in group)):
            combo = dict(zip(group, values))
            applicable = [e for e in exclusions if set(e["when"]) <= set(group)]
            reason = _excluded(combo, applicable)
            if reason is not None:
                excluded += 1
                continue
            total += 1
            if (group, values) in seen:
                covered += 1
            else:
                missing.append(combo)
    result.update(total=total, covered=covered, excluded=excluded, missing_count=len(missing))
    result["ratio"] = round(covered / total, 4) if total else None
    result["missing"] = missing[:MAX_MISSING_LISTED]
    result["truncated"] = len(missing) > MAX_MISSING_LISTED

    result["by_dimension"] = [_by_dimension(key, labels[key], dims[key], cases) for key in keys]
    return result


def _by_dimension(key: str, label: str, values: list[str], cases: list[dict]) -> dict:
    """Nombre de cas par valeur d'une dimension ; un cas paramétré compte une fois par valeur illustrée."""
    users: dict[str, set[str]] = {value: set() for value in values}
    for case in cases:
        value = (case.get("dimensions") or {}).get(key)
        if value in users:
            users[value].add(case["key"])
    counts = {value: len(found) for value, found in users.items()}
    return {
        "key": key,
        "label": label,
        "values": [{"value": v, "cases": n} for v, n in counts.items()],
        "unused": [v for v, n in counts.items() if n == 0],
    }


def matrix(
    dimensions: list[dict], exclusions: list[dict], cases: list[dict], row_key: str, col_key: str
) -> dict:
    """Matrice de couverture pour deux dimensions : chaque cellule liste les cas qui l'illustrent."""
    dims = {d["key"]: d for d in dimensions}
    if row_key not in dims or col_key not in dims or row_key == col_key:
        return {}
    rows = [v["value"] for v in dims[row_key]["values"]]
    cols = [v["value"] for v in dims[col_key]["values"]]
    cells: dict[tuple, list[dict]] = defaultdict(list)
    for case in cases:
        cdims = case.get("dimensions") or {}
        if row_key in cdims and col_key in cdims:
            cell = cells[(cdims[row_key], cdims[col_key])]
            if any(c["key"] == case["key"] for c in cell):
                continue
            entry = {
                "key": case["key"],
                "number": case.get("number"),
                "label": case.get("label") or f"{case.get('number') or 0:02d}",
                "title": case.get("title", ""),
            }
            if case.get("parametric"):
                entry["parametric"] = True
            cell.append(entry)
    applicable = [e for e in exclusions if set(e["when"]) <= {row_key, col_key}]
    grid = []
    for row in rows:
        line = []
        for col in cols:
            reason = _excluded({row_key: row, col_key: col}, applicable)
            line.append({"cases": cells.get((row, col), []), "excluded": reason})
        grid.append({"value": row, "cells": line})
    return {
        "row": {"key": row_key, "label": dims[row_key].get("label") or row_key},
        "col": {"key": col_key, "label": dims[col_key].get("label") or col_key, "values": cols},
        "rows": grid,
    }


def statuses_used(content: dict) -> set[str]:
    """Les statuts qu'un cas emploie ; pour un cas paramétré, ceux de toutes ses variantes."""
    source = content.get("source") if content.get("params") else None
    steps = [*content.get("steps", []), *((source or {}).get("steps") or [])]
    outcomes = [content.get("outcome") or {}, *((source or {}).get("outcome") or [])]
    used = set(content.get("initial", {}).values())
    for step in steps:
        used.update(c["status"] for c in step.get("changes", {}).values())
        if step.get("global"):
            used.add(step["global"])
    used.update(o["status"] for o in outcomes if o.get("status"))
    return used


def _usage(cases: list[dict]) -> tuple[dict, set[str], set[str], list[dict]]:
    """Cas par empreinte, statuts et règles utilisés, et constats « une seule étape »."""
    findings = []
    by_hash: dict[str, list[str]] = defaultdict(list)
    used_statuses: set[str] = set()
    used_rules: set[str] = set()
    for case in cases:
        by_hash[case["content_hash"]].append(case["key"])
        content = case["content"]
        used_rules.update(content.get("rules", []))
        used_statuses.update(statuses_used(content))
        if len(content.get("steps", [])) == 1:
            findings.append(
                {
                    "code": "single_step",
                    "severity": "info",
                    "cases": [case["key"]],
                    "message": f"Le cas « {case['key']} » ne montre qu'une étape : aucune évolution à "
                    "suivre.",
                }
            )
    return by_hash, used_statuses, used_rules, findings


def _definition_findings(
    statuses: list[dict], rules: list[dict], cases: list[dict], used_statuses: set[str], used_rules: set[str]
) -> list[dict]:
    """Statuts jamais atteints, règles sans cas, comparaisons vers un cas absent, cas sans règle."""
    findings = []
    fallback = next(
        (s["key"] for s in statuses if s.get("default")), statuses[0]["key"] if statuses else None
    )
    unused = [s["key"] for s in statuses if s["key"] not in used_statuses and s["key"] != fallback]
    if unused:
        findings.append(
            {
                "code": "unused_status",
                "severity": "info",
                "statuses": unused,
                "message": "Statuts déclarés mais jamais atteints par un cas : " + ", ".join(unused) + ".",
            }
        )
    orphan_rules = [r["key"] for r in rules if r["key"] not in used_rules]
    if orphan_rules:
        findings.append(
            {
                "code": "rule_without_case",
                "severity": "warning",
                "rules": orphan_rules,
                "message": "Règles de gestion qu'aucun cas n'illustre : " + ", ".join(orphan_rules) + ".",
            }
        )
    # « compare_with » vers un cas absent ou retiré : la comparaison ne peut pas s'afficher.
    keys = {c["key"] for c in cases}
    dangling = [
        f"{c['key']} → {other}"
        for c in cases
        for other in c["content"].get("compare_with", [])
        if other not in keys
    ]
    if dangling:
        findings.append(
            {
                "code": "compare_missing_case",
                "severity": "warning",
                "cases": [d.split(" → ")[0] for d in dangling][:50],
                "message": "Comparaisons vers un cas absent ou retiré : " + ", ".join(dangling[:20]) + ".",
            }
        )
    if rules:
        unlinked = [c["key"] for c in cases if not c["content"].get("rules")]
        if unlinked:
            findings.append(
                {
                    "code": "case_without_rule",
                    "severity": "info",
                    "cases": unlinked[:50],
                    "message": f"{len(unlinked)} cas ne sont rattachés à aucune règle de gestion.",
                }
            )
    return findings


MIN_ECHO_VALUES = 5  # en dessous, une valeur par cas est banale : deux ou trois cas, deux ou trois valeurs


def dimension_echoes(dimensions: list[dict], cases: list[dict]) -> list[dict]:
    """Dimensions qui décrivent les cas un par un : chaque valeur portée par exactement un cas, autant de
    valeurs que de cas. La couverture y est de 100 % par construction : elle ne mesure rien."""
    counted = {c["key"] for c in cases if c.get("dimensions")}
    findings = []
    for dim in dimensions:
        values = [v["value"] for v in dim["values"]]
        if len(values) < MIN_ECHO_VALUES or len(values) != len(counted):
            continue
        users: dict[str, set[str]] = {value: set() for value in values}
        for case in cases:
            value = (case.get("dimensions") or {}).get(dim["key"])
            if value in users:
                users[value].add(case["key"])
        if all(len(found) == 1 for found in users.values()):
            label = dim.get("label") or dim["key"]
            findings.append(
                {
                    "code": "dimension_echoes_cases",
                    "severity": "warning",
                    "dimension": dim["key"],
                    "message": f"La dimension « {label} » semble décrire les cas un par un : chacune de ses "
                    f"{len(values)} valeurs n'est portée que par un cas. Une couverture de 100 % n'y mesure "
                    "pas l'exhaustivité ; déclarez plutôt les facteurs qui font varier les cas.",
                }
            )
    return findings


def study_checks(statuses: list[dict], rules: list[dict], cases: list[dict]) -> list[dict]:
    """Contrôles de structure à l'échelle de l'étude (niveau 0) : doublons, éléments jamais utilisés."""
    by_hash, used_statuses, used_rules, findings = _usage(cases)
    for keys in by_hash.values():
        if len(keys) > 1:
            findings.append(
                {
                    "code": "duplicate_content",
                    "severity": "warning",
                    "cases": keys,
                    "message": "Ces cas ont exactement le même déroulé (même structure, mêmes changements) : "
                    + ", ".join(keys)
                    + ".",
                }
            )
    if cases:
        findings += _definition_findings(statuses, rules, cases, used_statuses, used_rules)
    return findings
