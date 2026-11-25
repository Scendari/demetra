"""Ce que le jeu de règles déclaré par l'étude conclut pour un cas, et l'écart avec ce que le cas annonce.

Pur : aucun accès à la base. Le site n'exécute aucun code fourni par l'IA : il compare des valeurs et évalue
une déclaration au vocabulaire fermé.
"""

from __future__ import annotations

from . import extensions as ext


def text_of(value) -> str:
    """Une valeur de réglage telle qu'elle est écrite dans les données (true / false, pas oui / non)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return f"{value:g}" if isinstance(value, float) else str(value)


def condition_values(ruleset: dict, content: dict) -> dict:
    """Valeur de chaque condition du jeu de règles pour un cas : sa dimension, sinon son réglage (None :
    le cas ne la fixe pas)."""
    dims, config = content.get("dimensions") or {}, content.get("config") or {}
    values = {}
    for key in (c["key"] for c in ruleset.get("conditions", [])):
        values[key] = dims[key] if key in dims else text_of(config[key]) if key in config else None
    return values


def agreement(ruleset: dict, dimensions: list[dict], content: dict) -> list[dict]:
    """Écarts entre le sort des lignes annoncé par un cas et celui que calcule le jeu de règles."""
    if not (ruleset or {}).get("rows"):
        return []
    values, labels = condition_values(ruleset, content), ext.dimension_labels(dimensions)
    verdict = ext.evaluate_ruleset(ruleset, values, labels)
    if not verdict["complete"]:
        return []
    declared = {}
    for step in content.get("steps", []):
        declared.update({k: v["result"] for k, v in (step.get("rows") or {}).items()})
    return [
        {
            "row": key,
            "declared": ext.RULE_RESULTS[result],
            "expected": ext.RULE_RESULTS[verdict["rows"][key]["result"]],
        }
        for key, result in declared.items()
        if key in verdict["rows"] and verdict["rows"][key]["result"] != result
    ]
