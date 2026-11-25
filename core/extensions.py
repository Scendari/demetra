"""Extensions du format : ce qu'une étude ou un cas peut porter au-delà des entités à statut.

Étude : tranches d'une dimension numérique, jeu de règles partagé par les cas, cycles de vie.
Cas : mesures, champs d'entité, et pour chaque étape des valeurs chiffrées, des champs modifiés,
des messages entre entités et les règles examinées.

Tout est facultatif. Un cas qui n'utilise rien de cela garde exactement sa forme normalisée et
son empreinte : il se redépose « unchanged » et les avis rendus restent valables.
"""

from __future__ import annotations

from typing import Any

from .casemodel import ID_RE, Report, _is_str, _scalar

OPS = ["=", "+", "-", "×", "÷", "%", "min", "max", "arrondi"]
OP_LABELS = {
    "=": "Valeur de départ",
    "+": "Ajout",
    "-": "Retrait",
    "×": "Multiplication",
    "÷": "Division",
    "%": "Pourcentage",
    "min": "Plafond",
    "max": "Plancher",
    "arrondi": "Arrondi",
}
POLICIES = {
    "unique": "Une seule règle peut correspondre",
    "first": "La première règle qui correspond l'emporte",
    "priority": "La règle la plus prioritaire l'emporte",
    "any": "Plusieurs règles peuvent correspondre si elles concluent pareil",
    "collect": "Toutes les règles qui correspondent s'appliquent",
}
RULE_RESULTS = {
    "selected": "Retenue",
    "discarded": "Écartée",
    "failed": "Ne correspond pas",
    "none": "Non examinée",
}
MESSAGE_STATUSES = {"received": "Reçu", "lost": "Perdu"}

MAX_BANDS = 12
MAX_CONDITIONS = 8
MAX_RULE_ROWS = 60
MAX_LIFECYCLES = 8
MAX_TRANSITIONS = 60
MAX_STEP_VALUES = 12
MAX_STEP_MESSAGES = 8
MAX_FIELDS = 16

EXAMPLE_BANDS = [
    {"value": "< 50 €", "to": 50, "result": "Refusée"},
    {"value": "≥ 50 €", "from": 50, "result": "Acceptée"},
]
EXAMPLE_RULESET = {
    "policy": "first",
    "conditions": [{"key": "client", "label": "Type de client"}, {"key": "gravite", "label": "Gravité"}],
    "rows": [
        {"key": "L1", "when": {"client": "Premium", "gravite": "Bloquant"}, "then": "Astreinte immédiate"},
        {"key": "L2", "when": {"gravite": "Bloquant"}, "then": "Prise en charge sous 4 h"},
    ],
}
EXAMPLE_LIFECYCLE = {
    "type": "commande",
    "initial": "BROUILLON",
    "transitions": [
        {"from": "BROUILLON", "to": "PAYEE", "label": "payer"},
        {"from": "PAYEE", "to": "EXPEDIEE", "label": "expédier"},
    ],
}
EXAMPLE_VALUE = {"label": "Remise fidélité", "op": "-", "value": 12, "unit": "€", "result": 108}
EXAMPLE_MESSAGE = {"from": "boutique", "to": "banque", "label": "Demande d'autorisation"}


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _text(value) -> str | None:
    """Texte court tiré d'une valeur simple (les nombres et booléens sont écrits tels qu'on les lit)."""
    if isinstance(value, bool):
        return "oui" if value else "non"
    if _num(value):
        return f"{value:g}".replace(".", ",") if isinstance(value, float) else str(value)
    return value if isinstance(value, str) else None


# ---------------------------------------------------------------------------
# Étude : tranches d'une dimension numérique
# ---------------------------------------------------------------------------


def _band_inclusive(item: dict, report: Report, p: str) -> str:
    inclusive = item.get("inclusive") or "from"
    if inclusive not in ("from", "to"):
        report.error(
            f"{p}.inclusive",
            "enum",
            "« inclusive » dit quelle borne appartient à la tranche : "
            "from (borne basse incluse) ou to (borne haute incluse).",
            received=inclusive,
            expected=["from", "to"],
        )
        inclusive = "from"
    return inclusive


def _normalize_band(
    band, j: int, last: int, known: list, seen: set, previous_to, report: Report, bp: str
) -> dict | None:
    """Une tranche {value, from, to, result} ; None si elle est inutilisable. `seen` reçoit la valeur lue."""
    if not isinstance(band, dict):
        report.error(
            bp, "type", "Une tranche est un objet {value, from, to, result}.", example=EXAMPLE_BANDS[0]
        )
        return None
    value = _text(band.get("value"))
    if value not in known:
        report.error(
            f"{bp}.value",
            "unknown_value",
            "La tranche désigne une valeur que la dimension ne déclare pas.",
            received=band.get("value"),
            expected=known,
        )
        return None
    if value in seen:
        report.error(f"{bp}.value", "duplicate", f"La valeur « {value} » a déjà sa tranche.", received=value)
        return None
    seen.add(value)
    low, high = band.get("from"), band.get("to")
    bad = False
    for name, bound in (("from", low), ("to", high)):
        if bound is not None and not _num(bound):
            report.error(
                f"{bp}.{name}", "type", "Une borne de tranche est un nombre.", received=bound, example=50
            )
            bad = True
    if bad:
        return None
    if low is None and j > 0:
        report.error(
            f"{bp}.from",
            "required",
            "Seule la première tranche peut ne pas avoir de borne basse.",
            example=previous_to,
        )
    if high is None and j < last:
        report.error(f"{bp}.to", "required", "Seule la dernière tranche peut ne pas avoir de borne haute.")
    if low is not None and high is not None and low >= high:
        report.error(
            f"{bp}.to",
            "order",
            "La borne haute doit dépasser la borne basse.",
            received=high,
            expected=f"> {low}",
        )
    if j > 0 and previous_to is not None and low is not None and low != previous_to:
        report.error(
            f"{bp}.from",
            "gap",
            "Les tranches se suivent sans trou ni recouvrement : chacune commence où la précédente finit.",
            received=low,
            expected=previous_to,
        )
    entry: dict = {"value": value}
    if low is not None:
        entry["from"] = low
    if high is not None:
        entry["to"] = high
    result = band.get("result")
    if result:
        if _is_str(result, 80):
            entry["result"] = result
        else:
            report.error(
                f"{bp}.result",
                "type",
                "Le résultat d'une tranche est un texte de 80 caractères au plus.",
                received=result,
            )
    return entry


def normalize_bands(item: dict, values: list[dict], report: Report, p: str) -> dict:
    """Champs facultatifs d'une dimension numérique : unité, tranches, borne incluse."""
    out: dict = {}
    unit = item.get("unit")
    if unit is not None:
        if _is_str(unit, 12) and unit:
            out["unit"] = unit
        else:
            report.error(
                f"{p}.unit",
                "type",
                "L'unité est un texte court (12 caractères au plus).",
                received=unit,
                example="€",
            )
    raw = item.get("bands")
    if raw is None:
        return out
    if not isinstance(raw, list) or not raw:
        report.error(
            f"{p}.bands",
            "type",
            "« bands » donne, pour chaque valeur de la dimension, la tranche de nombres qu'elle couvre.",
            example=EXAMPLE_BANDS,
        )
        return out
    if len(raw) > MAX_BANDS:
        report.error(
            f"{p}.bands", "max_items", f"{MAX_BANDS} tranches au plus par dimension.", received=len(raw)
        )
    inclusive = _band_inclusive(item, report, p)
    known = [v["value"] for v in values]
    before = len(report.errors)
    bands, seen, previous_to = [], set(), None
    for j, band in enumerate(raw[:MAX_BANDS]):
        entry = _normalize_band(band, j, len(raw) - 1, known, seen, previous_to, report, f"{p}.bands[{j}]")
        if entry is None:
            continue
        previous_to = entry.get("to")
        bands.append(entry)
    if len(report.errors) == before and set(known) - seen:
        report.error(
            f"{p}.bands",
            "missing_band",
            "Chaque valeur de la dimension doit avoir sa tranche.",
            received=sorted(seen),
            expected=known,
        )
    if len(report.errors) == before:
        out["bands"] = bands
        if inclusive == "to":
            out["inclusive"] = "to"
    return out


def band_index(dim: dict, x: float) -> int | None:
    """Rang de la tranche qui contient x, ou None si x est hors de l'échelle."""
    upper = dim.get("inclusive") == "to"
    for i, band in enumerate(dim.get("bands") or []):
        low, high = band.get("from"), band.get("to")
        if upper:
            inside = (low is None or x > low) and (high is None or x <= high)
        else:
            inside = (low is None or x >= low) and (high is None or x < high)
        if inside:
            return i
    return None


def band_text(dim: dict, band: dict) -> str:
    """Tranche écrite en clair, avec ses bornes : « de 50 à 200 € (200 exclu) »."""
    unit = f" {dim['unit']}" if dim.get("unit") else ""
    low, high = band.get("from"), band.get("to")
    upper = dim.get("inclusive") == "to"
    if low is None and high is None:
        return "toute valeur"
    if low is None:
        return f"jusqu'à {_text(high)}{unit} {'inclus' if upper else 'exclu'}"
    if high is None:
        return f"{'plus de' if upper else 'à partir de'} {_text(low)}{unit}"
    return f"de {_text(low)} à {_text(high)}{unit} ({_text(high) if not upper else _text(low)} exclu)"


# ---------------------------------------------------------------------------
# Étude : jeu de règles partagé
# ---------------------------------------------------------------------------


RULESET_FIELDS = ["title", "policy", "conditions", "rows"]


def _ruleset_conditions(raw: dict, report: Report, path: str) -> tuple[list[dict], set[str]]:
    """Les conditions du jeu de règles et l'ensemble de leurs clés."""
    conditions, cond_keys = [], set()
    raw_conditions = raw.get("conditions")
    if not isinstance(raw_conditions, list) or not raw_conditions:
        report.error(
            f"{path}.conditions",
            "min_items",
            "Un jeu de règles déclare au moins une condition.",
            example=EXAMPLE_RULESET["conditions"],
        )
        raw_conditions = []
    if len(raw_conditions) > MAX_CONDITIONS:
        report.error(
            f"{path}.conditions",
            "max_items",
            f"{MAX_CONDITIONS} conditions au plus : au-delà, la table ne se lit plus.",
            received=len(raw_conditions),
        )
    for i, item in enumerate(raw_conditions[:MAX_CONDITIONS]):
        p = f"{path}.conditions[{i}]"
        if isinstance(item, str):
            item = {"key": item}
        key = item.get("key") if isinstance(item, dict) else None
        if not (isinstance(key, str) and ID_RE.match(key)):
            report.error(f"{p}.key", "format", "Clé de condition invalide.", received=key, example="gravite")
            continue
        if key in cond_keys:
            report.error(
                f"{p}.key", "duplicate", f"La condition « {key} » est déclarée deux fois.", received=key
            )
            continue
        cond_keys.add(key)
        label = item.get("label") or key
        if not _is_str(label, 60):
            report.error(
                f"{p}.label",
                "type",
                "Le libellé d'une condition est un texte de 60 caractères au plus.",
                received=label,
            )
            label = key
        conditions.append({"key": key, "label": label})
    return conditions, cond_keys


def _row_conditions(item: dict, cond_keys: set[str], report: Report, p: str) -> dict:
    """« when » d'une ligne : condition -> valeur attendue ; « - » et « * » valent « indifférent »."""
    when: dict = {}
    raw_when = item.get("when") or {}
    if not isinstance(raw_when, dict):
        report.error(
            f"{p}.when",
            "type",
            "« when » associe à des conditions la valeur attendue ; une condition absente est indifférente.",
            example={"gravite": "Bloquant"},
        )
        raw_when = {}
    for cond, value in raw_when.items():
        text = _text(value)
        if cond not in cond_keys:
            report.error(
                f"{p}.when.{cond}",
                "unknown_condition",
                f"La ligne teste une condition non déclarée « {cond} ».",
                received=cond,
                expected=sorted(cond_keys),
            )
        elif text is None or not (0 < len(text) <= 60):
            report.error(
                f"{p}.when.{cond}",
                "type",
                "La valeur attendue d'une condition est un texte court (60 caractères au plus).",
                received=value,
            )
        elif text not in ("-", "*"):
            when[cond] = text
    return when


def _ruleset_row(
    item, cond_keys: set[str], row_keys: set[str], status_keys: set[str], report: Report, p: str
) -> dict | None:
    """Une ligne {key, when, then, status} ; None si elle est inutilisable."""
    if not isinstance(item, dict):
        report.error(
            p,
            "type",
            "Une ligne de règle est un objet {key, when, then}.",
            example=EXAMPLE_RULESET["rows"][0],
        )
        return None
    key = item.get("key")
    if not (isinstance(key, str) and ID_RE.match(key)):
        report.error(f"{p}.key", "format", "Clé de ligne invalide.", received=key, example="L1")
        return None
    if key in row_keys:
        report.error(f"{p}.key", "duplicate", f"La ligne « {key} » est déclarée deux fois.", received=key)
        return None
    row_keys.add(key)
    when = _row_conditions(item, cond_keys, report, p)
    then = item.get("then")
    if not (_is_str(then, 120) and then):
        report.error(
            f"{p}.then",
            "required",
            "Chaque ligne a une conclusion (« then »), en texte court.",
            received=then,
            example="Prise en charge sous 4 h",
        )
        return None
    row = {"key": key, "when": when, "then": then}
    status = item.get("status")
    if status is not None:
        if status in status_keys:
            row["status"] = status
        else:
            report.error(
                f"{p}.status",
                "unknown_status",
                f"Statut « {status} » non déclaré dans l'étude.",
                received=status,
                expected=sorted(status_keys),
            )
    return row


def _ruleset_rows(raw: dict, cond_keys: set[str], status_keys: set[str], report: Report, path: str) -> list:
    rows: list[dict] = []
    row_keys: set[str] = set()
    raw_rows = raw.get("rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        report.error(
            f"{path}.rows",
            "min_items",
            "Un jeu de règles a au moins une ligne.",
            example=EXAMPLE_RULESET["rows"],
        )
        raw_rows = []
    if len(raw_rows) > MAX_RULE_ROWS:
        report.error(f"{path}.rows", "max_items", f"{MAX_RULE_ROWS} lignes au plus.", received=len(raw_rows))
    for i, item in enumerate(raw_rows[:MAX_RULE_ROWS]):
        row = _ruleset_row(item, cond_keys, row_keys, status_keys, report, f"{path}.rows[{i}]")
        if row:
            rows.append(row)
    return rows


def normalize_ruleset(raw: Any, status_keys: set[str], report: Report, path: str = "ruleset") -> dict:
    if raw is None or raw == {}:
        return {}
    if not isinstance(raw, dict):
        report.error(
            path, "type", "Le jeu de règles est un objet {policy, conditions, rows}.", example=EXAMPLE_RULESET
        )
        return {}
    for extra in sorted(set(raw) - set(RULESET_FIELDS)):
        report.warn(
            f"{path}.{extra}",
            "unknown_field",
            f"Champ « {extra} » inconnu : il est ignoré.",
            expected=RULESET_FIELDS,
        )
    policy = raw.get("policy") or "unique"
    if policy not in POLICIES:
        report.error(
            f"{path}.policy",
            "enum",
            "Politique de résolution inconnue : elle dit quelle règle l'emporte quand plusieurs "
            "correspondent.",
            received=policy,
            expected=list(POLICIES),
        )
        policy = "unique"
    title = raw.get("title") or ""
    if not _is_str(title, 120):
        report.error(
            f"{path}.title",
            "type",
            "Le titre du jeu de règles est un texte de 120 caractères au plus.",
            received=title,
        )
        title = ""
    conditions, cond_keys = _ruleset_conditions(raw, report, path)
    rows = _ruleset_rows(raw, cond_keys, status_keys, report, path)
    return {"title": title, "policy": policy, "conditions": conditions, "rows": rows}


def _row_fate(row: dict, order: list[str], values: dict, labels: dict) -> dict:
    """Une ligne face aux valeurs données : failed (et sur quelle condition), unknown ou matched."""
    unknown = False
    for cond in order:
        if cond not in row["when"]:
            continue
        value = values.get(cond)
        if value is None:
            unknown = True
        elif row["when"][cond] not in (value, (labels.get(cond) or {}).get(value)):
            return {"result": "failed", "on": cond}
    return {"result": "unknown" if unknown else "matched"}


def _apply_policy(policy: str, matched: list[dict]) -> tuple[list[dict], str | None]:
    """Les lignes retenues parmi celles qui correspondent, et l'anomalie éventuelle."""
    if not matched:
        return [], "none_matches"
    if policy in ("first", "priority"):
        return matched[:1], None
    if policy == "unique":
        return matched, "several_unique" if len(matched) > 1 else None
    if policy == "any":
        return matched, "conflict_any" if len({r["then"] for r in matched}) > 1 else None
    return matched, None  # collect


RULESET_ISSUES = {
    "none_matches": "Aucune ligne ne correspond à ces valeurs.",
    "several_unique": "Plusieurs lignes correspondent, alors que la politique n'en admet qu'une.",
    "conflict_any": "Les lignes qui correspondent ne concluent pas toutes pareil.",
}


def evaluate_ruleset(ruleset: dict, values: dict, labels: dict | None = None) -> dict:
    """Ce que le jeu de règles conclut pour des valeurs de conditions données.

    `values` : condition → valeur (None si elle n'est pas connue). `labels` : condition → {valeur: libellé},
    pour qu'une ligne écrite avec le libellé d'une valeur de dimension corresponde aussi.
    Tant qu'une ligne dépend d'une condition sans valeur, rien n'est conclu (`complete` faux)."""
    order = [c["key"] for c in ruleset.get("conditions", [])]
    rows = {r["key"]: _row_fate(r, order, values, labels or {}) for r in ruleset.get("rows", [])}
    missing = [
        c
        for c in order
        if values.get(c) is None
        and any(c in r["when"] and rows[r["key"]]["result"] == "unknown" for r in ruleset["rows"])
    ]
    out = {"rows": rows, "complete": not missing, "missing": missing, "selected": [], "issue": None}
    out.update(conclusion=None, status=None)
    if missing:
        return out
    matched = [r for r in ruleset["rows"] if rows[r["key"]]["result"] == "matched"]
    selected, issue = _apply_policy(ruleset.get("policy") or "unique", matched)
    keys = [r["key"] for r in selected]
    for row in matched:
        rows[row["key"]] = {"result": "selected" if row["key"] in keys else "discarded"}
    out.update(selected=keys, issue=issue)
    if selected:
        out["conclusion"] = " ; ".join(dict.fromkeys(r["then"] for r in selected))
        out["status"] = selected[0].get("status")
    return out


def ruleset_values(ruleset: dict, dimensions: dict, config: dict) -> dict:
    """Les valeurs d'un cas pour les conditions du jeu de règles : sa dimension, sinon son réglage."""
    values = {}
    for cond in ruleset.get("conditions", []):
        key = cond["key"]
        value = dimensions.get(key)
        values[key] = value if value is not None else _text(config.get(key))
    return values


def dimension_labels(dimensions: list[dict]) -> dict:
    return {d["key"]: {v["value"]: v.get("label") or v["value"] for v in d["values"]} for d in dimensions}


def check_ruleset_agreement(case: dict, ruleset: dict, dimensions: list[dict], report: Report, path: str):
    """Écart entre le sort des lignes annoncé par le cas et celui que le jeu de règles calcule : un
    avertissement, jamais un refus (le cas peut justement montrer un comportement contesté)."""
    if not ruleset or not any(s.get("rows") for s in case["steps"]):
        return
    values = ruleset_values(ruleset, case["dimensions"], case["config"])
    verdict = evaluate_ruleset(ruleset, values, dimension_labels(dimensions))
    if not verdict["complete"]:
        return
    declared: dict[str, tuple[int, str]] = {}
    for i, step in enumerate(case["steps"]):
        for key, entry in (step.get("rows") or {}).items():
            declared[key] = (i, entry["result"])
    for key, (i, result) in declared.items():
        expected = verdict["rows"][key]["result"]
        if result != expected:
            report.warn(
                f"{path}.steps[{i}].rows.{key}",
                "model_mismatch",
                f"Le cas annonce la ligne « {key} » {RULE_RESULTS[result].lower()}, mais le jeu de règles "
                f"de l'étude la donne {RULE_RESULTS[expected].lower()} pour les valeurs de ce cas.",
                received=result,
                expected=expected,
            )


# ---------------------------------------------------------------------------
# Étude : cycles de vie
# ---------------------------------------------------------------------------


def _lifecycle_transition(tr, status_keys: set[str], events: set, report: Report, tp: str) -> dict | None:
    """Une transition {from, to, label, guard} ; None si elle est inutilisable."""
    if not isinstance(tr, dict):
        report.error(
            tp,
            "type",
            "Une transition est un objet {from, to, label}.",
            example=EXAMPLE_LIFECYCLE["transitions"][0],
        )
        return None
    bad = False
    for side in ("from", "to"):
        if tr.get(side) not in status_keys:
            report.error(
                f"{tp}.{side}",
                "unknown_status",
                f"Statut « {tr.get(side)} » non déclaré dans l'étude.",
                received=tr.get(side),
                expected=sorted(status_keys),
            )
            bad = True
    label = tr.get("label")
    if not (_is_str(label, 40) and label and label.strip()):
        report.error(
            f"{tp}.label",
            "required",
            "Chaque transition porte le nom de l'évènement qui la déclenche.",
            received=label,
            example="payer",
        )
        bad = True
    if bad:
        return None
    label = label.strip()
    if (tr["from"], label) in events:
        report.error(
            tp,
            "ambiguous",
            f"Depuis « {tr['from']} », l'évènement « {label} » mène déjà à un autre état.",
            received=tr["to"],
        )
        return None
    events.add((tr["from"], label))
    entry = {"from": tr["from"], "to": tr["to"], "label": label}
    guard = tr.get("guard")
    if guard:
        if _is_str(guard, 80):
            entry["guard"] = guard
        else:
            report.error(
                f"{tp}.guard",
                "type",
                "La garde d'une transition est un texte de 80 caractères au plus.",
                received=guard,
            )
    return entry


def _lifecycle_transitions(item: dict, status_keys: set[str], report: Report, p: str) -> list[dict]:
    transitions: list[dict] = []
    events: set = set()
    raw_transitions = item.get("transitions")
    if not isinstance(raw_transitions, list) or not raw_transitions:
        report.error(
            f"{p}.transitions",
            "min_items",
            "Un cycle de vie déclare au moins une transition permise.",
            example=EXAMPLE_LIFECYCLE["transitions"],
        )
        raw_transitions = []
    if len(raw_transitions) > MAX_TRANSITIONS:
        report.error(
            f"{p}.transitions",
            "max_items",
            f"{MAX_TRANSITIONS} transitions au plus par cycle de vie.",
            received=len(raw_transitions),
        )
    for j, tr in enumerate(raw_transitions[:MAX_TRANSITIONS]):
        entry = _lifecycle_transition(tr, status_keys, events, report, f"{p}.transitions[{j}]")
        if entry:
            transitions.append(entry)
    return transitions


def _lifecycle(item, types: set[str], status_keys: set[str], report: Report, p: str) -> dict | None:
    """Un cycle de vie {type, title, initial, transitions} ; None s'il est inutilisable."""
    if not isinstance(item, dict):
        report.error(
            p,
            "type",
            "Un cycle de vie est un objet {type, initial, transitions}.",
            example=EXAMPLE_LIFECYCLE,
        )
        return None
    ent_type = item.get("type")
    if not (isinstance(ent_type, str) and 0 < len(ent_type.strip()) <= 40):
        report.error(
            f"{p}.type",
            "required",
            "Un cycle de vie vaut pour un type d'entité (le champ « type » des entités).",
            received=ent_type,
            example="commande",
        )
        return None
    if ent_type in types:
        report.error(
            f"{p}.type",
            "duplicate",
            f"Le type « {ent_type} » a déjà son cycle de vie.",
            received=ent_type,
        )
        return None
    types.add(ent_type)
    title = item.get("title") or ""
    if not _is_str(title, 80):
        report.error(
            f"{p}.title",
            "type",
            "Le titre d'un cycle de vie est un texte de 80 caractères au plus.",
            received=title,
        )
        title = ""
    initial = item.get("initial")
    if initial not in status_keys:
        report.error(
            f"{p}.initial",
            "unknown_status",
            "L'état de départ doit être un statut déclaré dans l'étude.",
            received=initial,
            expected=sorted(status_keys),
        )
        initial = None
    transitions = _lifecycle_transitions(item, status_keys, report, p)
    states = list(
        dict.fromkeys(([initial] if initial else []) + [s for t in transitions for s in (t["from"], t["to"])])
    )
    return {
        "type": ent_type.strip(),
        "title": title,
        "initial": initial,
        "states": states,
        "transitions": transitions,
    }


def normalize_lifecycles(
    raw: Any, status_keys: set[str], report: Report, path: str = "lifecycles"
) -> list[dict]:
    if raw is None:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        report.error(
            path,
            "type",
            "« lifecycles » est la liste des cycles de vie, un par type d'entité.",
            example=[EXAMPLE_LIFECYCLE],
        )
        return []
    if len(raw) > MAX_LIFECYCLES:
        report.error(
            path, "max_items", f"{MAX_LIFECYCLES} cycles de vie au plus par étude.", received=len(raw)
        )
    out: list[dict] = []
    types: set[str] = set()
    for i, item in enumerate(raw[:MAX_LIFECYCLES]):
        cycle = _lifecycle(item, types, status_keys, report, f"{path}[{i}]")
        if cycle:
            out.append(cycle)
    return out


# ---------------------------------------------------------------------------
# Cas : mesures, champs, extras d'étape
# ---------------------------------------------------------------------------


def normalize_measures(raw: Any, dimensions: list[dict], case_dims: dict, report: Report, path: str) -> dict:
    """Valeur chiffrée du cas sur une dimension à tranches ; elle doit tomber dans la tranche déclarée."""
    if raw is None:
        return {}
    banded = {d["key"]: d for d in dimensions if d.get("bands")}
    if not isinstance(raw, dict):
        report.error(
            path,
            "type",
            "« measures » associe un nombre à des dimensions à tranches.",
            example={"montant": 49.9},
        )
        return {}
    out = {}
    for key, x in raw.items():
        p = f"{path}.{key}"
        dim = banded.get(key)
        if dim is None:
            report.error(
                p,
                "unknown_measure",
                "Une mesure porte sur une dimension de l'étude qui déclare des tranches (« bands »).",
                received=key,
                expected=sorted(banded)
                or "aucune dimension à tranches : ajoutez « bands » à la dimension (PATCH /studies/{id})",
            )
            continue
        if not _num(x):
            report.error(p, "type", "Une mesure est un nombre.", received=x, example=49.9)
            continue
        index = band_index(dim, x)
        if index is None:
            report.error(
                p,
                "out_of_scale",
                "La mesure est en dehors de toutes les tranches de la dimension.",
                received=x,
                expected=[band_text(dim, b) for b in dim["bands"]],
            )
            continue
        band = dim["bands"][index]
        declared = case_dims.get(key)
        if declared is not None and declared != band["value"]:
            wanted = next((b for b in dim["bands"] if b["value"] == declared), None)
            report.error(
                p,
                "out_of_band",
                f"La mesure tombe dans la tranche « {band['value']} », mais le cas déclare « {declared} ».",
                received=x,
                expected=band_text(dim, wanted) if wanted else declared,
            )
            continue
        out[key] = x
    return out


def clean_fields(raw: Any, report: Report, path: str) -> dict:
    """Champs d'une entité : nom → valeur simple."""
    out: dict = {}
    if raw is None:
        return out
    if not isinstance(raw, dict):
        report.error(
            path,
            "type",
            "« fields » associe une valeur simple à des noms de champ.",
            example={"adresse": "12 rue des Lilas"},
        )
        return out
    if len(raw) > MAX_FIELDS:
        report.error(path, "max_items", f"{MAX_FIELDS} champs au plus par entité.", received=len(raw))
    for name, value in list(raw.items())[:MAX_FIELDS]:
        if not (isinstance(name, str) and 0 < len(name) <= 60 and name.isprintable()):
            report.error(
                f"{path}.{name}",
                "format",
                "Nom de champ invalide (60 caractères au plus).",
                received=name,
                example="adresse",
            )
        elif not _scalar(value) or (isinstance(value, str) and len(value) > 200):
            report.error(
                f"{path}.{name}",
                "type",
                "La valeur d'un champ est un texte court, un nombre ou un booléen.",
                received=type(value).__name__,
            )
        else:
            out[name] = value
    return out


def _expected_total(previous: float, op: str, value: float) -> float | None:
    if op == "+":
        return previous + value
    if op == "-":
        return previous - value
    if op == "×":
        return previous * value
    if op == "÷" and value:
        return previous / value
    if op == "min":
        return min(previous, value)
    if op == "max":
        return max(previous, value)
    return None


def _value_result(item: dict, entry: dict, op: str, running: dict, report: Report, vp: str) -> bool:
    """Le cumul annoncé après la ligne : vérifié contre l'opération, puis retenu dans `running`."""
    result = item.get("result")
    if result is None:
        if op == "=":
            running["total"] = item["value"]
        return True
    if not _num(result):
        report.error(
            f"{vp}.result",
            "type",
            "« result » est le cumul après cette ligne : un nombre.",
            received=result,
            example=108,
        )
        return False
    entry["result"] = result
    previous = running.get("total")
    expected = _expected_total(previous, op, item["value"]) if previous is not None else None
    if expected is not None and abs(expected - result) > max(0.005, abs(expected) * 1e-6):
        report.warn(
            f"{vp}.result",
            "inconsistent_total",
            "Le cumul annoncé ne correspond pas à l'opération : "
            f"{_text(previous)} {op} {_text(item['value'])} donne {_text(round(expected, 4))}.",
            received=result,
            expected=round(expected, 4),
        )
    running["total"] = result
    return True


def _step_value(item, running: dict, report: Report, vp: str) -> dict | None:
    """Une ligne de calcul {label, op, value, unit, result, note} ; met à jour le cumul `running`."""
    if not isinstance(item, dict):
        report.error(
            vp,
            "type",
            "Une ligne de calcul est un objet {label, op, value, unit, result}.",
            example=EXAMPLE_VALUE,
        )
        return None
    label = item.get("label")
    if not (_is_str(label, 80) and label and label.strip()):
        report.error(
            f"{vp}.label",
            "required",
            "Chaque ligne de calcul a un libellé.",
            received=label,
            example="Remise fidélité",
        )
        return None
    if not _num(item.get("value")):
        report.error(
            f"{vp}.value",
            "type",
            "« value » est le nombre de cette ligne.",
            received=item.get("value"),
            example=12,
        )
        return None
    op = item.get("op") or "="
    if op not in OPS:
        report.error(f"{vp}.op", "enum", "Opération inconnue.", received=op, expected=OPS)
        return None
    entry = {"label": label.strip(), "op": op, "value": item["value"]}
    unit = item.get("unit")
    if unit:
        if _is_str(unit, 12):
            entry["unit"] = unit
        else:
            report.error(
                f"{vp}.unit",
                "type",
                "L'unité est un texte court (12 caractères au plus).",
                received=unit,
                example="€",
            )
    if not _value_result(item, entry, op, running, report, vp):
        return None
    note = item.get("note")
    if note:
        if _is_str(note, 120):
            entry["note"] = note
        else:
            report.error(
                f"{vp}.note",
                "type",
                "La note d'une ligne de calcul est un texte de 120 caractères au plus.",
            )
    return entry


def _step_values(raw_values, running: dict, report: Report, p: str) -> list[dict]:
    if not isinstance(raw_values, list):
        report.error(
            f"{p}.values",
            "type",
            "« values » est la liste des lignes de calcul de l'étape.",
            example=[EXAMPLE_VALUE],
        )
        raw_values = []
    if len(raw_values) > MAX_STEP_VALUES:
        report.error(
            f"{p}.values",
            "max_items",
            f"{MAX_STEP_VALUES} lignes de calcul au plus par étape.",
            received=len(raw_values),
        )
    values = []
    for j, item in enumerate(raw_values[:MAX_STEP_VALUES]):
        entry = _step_value(item, running, report, f"{p}.values[{j}]")
        if entry:
            values.append(entry)
    return values


def _step_fields(raw_fields, ids: set[str], report: Report, p: str) -> dict:
    if not isinstance(raw_fields, dict):
        report.error(
            f"{p}.fields",
            "type",
            "« fields » associe à des entités les champs que l'étape modifie.",
            example={"client": {"adresse": "3 avenue du Port"}},
        )
        raw_fields = {}
    fields = {}
    for ent_id, changes in raw_fields.items():
        if ent_id not in ids:
            report.error(
                f"{p}.fields.{ent_id}",
                "unknown_entity",
                f"L'étape modifie les champs d'une entité inconnue « {ent_id} ».",
                received=ent_id,
                expected=sorted(ids),
            )
            continue
        cleaned = clean_fields(changes, report, f"{p}.fields.{ent_id}")
        if cleaned:
            fields[ent_id] = cleaned
    return fields


def _step_message(item, ids: set[str], report: Report, mp: str) -> dict | None:
    if not isinstance(item, dict):
        report.error(
            mp, "type", "Un message est un objet {from, to, label, status}.", example=EXAMPLE_MESSAGE
        )
        return None
    bad = False
    for side in ("from", "to"):
        if item.get(side) not in ids:
            report.error(
                f"{mp}.{side}",
                "unknown_entity",
                f"Le message cite une entité inconnue « {item.get(side)} » : "
                "émetteur et destinataire sont des entités du cas.",
                received=item.get(side),
                expected=sorted(ids),
            )
            bad = True
    label = item.get("label")
    if not (_is_str(label, 80) and label and label.strip()):
        report.error(
            f"{mp}.label",
            "required",
            "Chaque message a un libellé court.",
            received=label,
            example="Demande d'autorisation",
        )
        bad = True
    status = item.get("status") or "received"
    if status not in MESSAGE_STATUSES:
        report.error(
            f"{mp}.status",
            "enum",
            "Un message est reçu (received) ou perdu (lost).",
            received=status,
            expected=list(MESSAGE_STATUSES),
        )
        bad = True
    if bad:
        return None
    return {"from": item["from"], "to": item["to"], "label": label.strip(), "status": status}


def _step_messages(raw_messages, ids: set[str], report: Report, p: str) -> list[dict]:
    if not isinstance(raw_messages, list):
        report.error(
            f"{p}.messages",
            "type",
            "« messages » est la liste des messages échangés à cette étape.",
            example=[EXAMPLE_MESSAGE],
        )
        raw_messages = []
    if len(raw_messages) > MAX_STEP_MESSAGES:
        report.error(
            f"{p}.messages",
            "max_items",
            f"{MAX_STEP_MESSAGES} messages au plus par étape.",
            received=len(raw_messages),
        )
    messages = []
    for j, item in enumerate(raw_messages[:MAX_STEP_MESSAGES]):
        entry = _step_message(item, ids, report, f"{p}.messages[{j}]")
        if entry:
            messages.append(entry)
    return messages


def _step_row(key, value, row_keys: list, cond_keys: list, report: Report, rp: str) -> dict | None:
    """Le sort d'une ligne du jeu de règles pour ce cas : {result, on}."""
    if key not in row_keys:
        report.error(
            rp,
            "unknown_rule",
            f"La ligne « {key} » n'existe pas dans le jeu de règles de l'étude.",
            received=key,
            expected=row_keys,
        )
        return None
    if isinstance(value, str):
        value = {"result": value}
    result = value.get("result") if isinstance(value, dict) else None
    if result not in ("selected", "discarded", "failed"):
        report.error(
            rp,
            "enum",
            "Résultat d'une ligne pour ce cas : selected (retenue), discarded (correspond mais écartée) "
            "ou failed (ne correspond pas).",
            received=result,
            expected=["selected", "discarded", "failed"],
        )
        return None
    entry = {"result": result}
    failed_on = value.get("on")
    if failed_on is not None:
        if result != "failed":
            report.error(
                f"{rp}.on",
                "incompatible",
                "« on » désigne la condition en échec : il n'a de sens que pour result = failed.",
                received=failed_on,
            )
            return None
        if failed_on not in cond_keys:
            report.error(
                f"{rp}.on",
                "unknown_condition",
                f"Condition « {failed_on} » non déclarée dans le jeu de règles.",
                received=failed_on,
                expected=cond_keys,
            )
            return None
        entry["on"] = failed_on
    return entry


def _step_rows(raw_rules, ruleset: dict, report: Report, p: str) -> dict:
    row_keys = [r["key"] for r in (ruleset or {}).get("rows", [])]
    cond_keys = [c["key"] for c in (ruleset or {}).get("conditions", [])]
    if not isinstance(raw_rules, dict):
        report.error(
            f"{p}.rows",
            "type",
            "« rows » associe à des lignes du jeu de règles leur résultat pour ce cas.",
            example={"L1": {"result": "failed", "on": "client"}, "L2": "selected"},
        )
        raw_rules = {}
    if raw_rules and not row_keys:
        report.error(
            f"{p}.rows",
            "no_ruleset",
            "L'étude ne déclare pas de jeu de règles : ajoutez « ruleset » à l'étude (PATCH /studies/{id}) "
            "avant de citer ses lignes.",
            example=EXAMPLE_RULESET,
        )
        raw_rules = {}
    rules = {}
    for key, value in raw_rules.items():
        entry = _step_row(key, value, row_keys, cond_keys, report, f"{p}.rows.{key}")
        if entry:
            rules[key] = entry
    return rules


def normalize_step_extras(
    step: dict, ids: set[str], ruleset: dict, report: Report, p: str, running: dict
) -> dict:
    """Valeurs chiffrées, champs modifiés, messages et règles examinées d'une étape.

    `running` porte le cumul d'une étape à l'autre."""
    out: dict = {}
    if step.get("values") is not None:
        values = _step_values(step["values"], running, report, p)
        if values:
            out["values"] = values
    if step.get("fields") is not None:
        fields = _step_fields(step["fields"], ids, report, p)
        if fields:
            out["fields"] = fields
    if step.get("messages") is not None:
        messages = _step_messages(step["messages"], ids, report, p)
        if messages:
            out["messages"] = messages
    if step.get("rows") is not None:
        rules = _step_rows(step["rows"], ruleset, report, p)
        if rules:
            out["rows"] = rules
    return out


def check_lifecycles(
    entities: list[dict],
    initial: dict,
    steps: list[dict],
    lifecycles: list[dict],
    fallback: str | None,
    report: Report,
    path: str,
):
    """Tout changement d'état d'une entité dont le type a un cycle de vie doit emprunter une transition
    permise."""
    by_type = {l["type"]: l for l in lifecycles or []}
    for ent in entities:
        cycle = by_type.get(ent["type"])
        if not cycle:
            continue
        allowed = {(t["from"], t["to"]) for t in cycle["transitions"]}
        current = initial.get(ent["id"], fallback)
        if current not in cycle["states"]:
            report.error(
                f"{path}.initial.{ent['id']}",
                "outside_lifecycle",
                f"L'état de départ de « {ent['id']} » n'appartient pas au cycle de vie du type « "
                f"{ent['type']} ».",
                received=current,
                expected=cycle["states"],
                example={ent["id"]: cycle["initial"]},
            )
            continue
        for i, step in enumerate(steps):
            change = step["changes"].get(ent["id"])
            if not change or change["status"] == current:
                continue
            if (current, change["status"]) not in allowed:
                report.error(
                    f"{path}.steps[{i}].changes.{ent['id']}",
                    "forbidden_transition",
                    f"Le cycle de vie du type « {ent['type']} » ne permet pas de passer de « {current} » à « "
                    f"{change['status']} ».",
                    received=f"{current} → {change['status']}",
                    expected=sorted(t["to"] for t in cycle["transitions"] if t["from"] == current)
                    or "aucune transition depuis cet état",
                )
            current = change["status"]


# ---------------------------------------------------------------------------
# Rejeu et empreinte
# ---------------------------------------------------------------------------

STEP_EXTRAS = ("values", "fields", "messages", "rows")


def uses(case: dict) -> dict:
    """Ce que le cas utilise parmi les extensions."""
    steps = case.get("steps", [])
    return {
        "values": any(s.get("values") for s in steps),
        "fields": any(s.get("fields") for s in steps)
        or any(e.get("fields") for e in case.get("entities", [])),
        "messages": any(s.get("messages") for s in steps),
        "rules": any(s.get("rows") for s in steps),
        "measures": bool(case.get("measures")),
    }


def extend_frames(case: dict, frames: list[dict]) -> list[dict]:
    """Ajoute aux états rejoués ce que le cas utilise : lignes de calcul, champs, messages, règles
    examinées."""
    used = uses(case)
    if not any(used.values()):
        return frames
    fields = {e["id"]: dict(e.get("fields") or {}) for e in case.get("entities", [])}
    rules: dict[str, dict] = {}
    for frame, step in zip(frames, case.get("steps", []), strict=True):
        if used["values"]:
            frame["values"] = step.get("values", [])
        if used["fields"]:
            changed = []
            fields = {ent: dict(values) for ent, values in fields.items()}
            for ent, changes in (step.get("fields") or {}).items():
                for name, value in changes.items():
                    if fields.setdefault(ent, {}).get(name) != value or name not in fields[ent]:
                        changed.append([ent, name])
                    fields[ent][name] = value
            frame["fields"] = fields
            frame["fields_changed"] = changed
        if used["messages"]:
            frame["messages"] = step.get("messages", [])
        if used["rules"]:
            rules = {**rules, **(step.get("rows") or {})}
            frame["rules"] = rules
            frame["rules_examined"] = sorted(step.get("rows") or {})
    return frames


def semantic_extras(case: dict) -> dict:
    """Part des extensions qui entre dans l'empreinte du déroulé. Vide si le cas n'en utilise aucune."""
    out: dict = {}
    if case.get("measures"):
        out["measures"] = case["measures"]
    fields = {e["id"]: e["fields"] for e in case.get("entities", []) if e.get("fields")}
    if fields:
        out["fields"] = fields
    steps = []
    for step in case.get("steps", []):
        entry: dict = {}
        if step.get("values"):
            entry["values"] = [
                [v["op"], v["value"], v.get("result"), v.get("unit", "")] for v in step["values"]
            ]
        if step.get("fields"):
            entry["fields"] = step["fields"]
        if step.get("messages"):
            entry["messages"] = [[m["from"], m["to"], m["status"]] for m in step["messages"]]
        if step.get("rows"):
            entry["rows"] = {k: v["result"] for k, v in step["rows"].items()}
        steps.append(entry)
    if any(steps):
        out["steps"] = steps
    return out
