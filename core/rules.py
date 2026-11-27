"""Le socle commun des familles d'atelier : ce que toute famille partage, et rien de propre à l'une d'elles.

Valeurs (égalité stricte, écriture dans une adresse), briques de déclaration (noms, libellés, options et
réglages, évènements, briques), comparaison d'une valeur déclarée (`check_pairs`, `pairs_hold`). Chaque
famille (`workshop`, `periods`) y prend ce qu'elle déclare ; une amélioration du socle les sert toutes.
Pur : aucun accès à la base, aucun code fourni par une étude n'est exécuté.
"""

from __future__ import annotations

from .casemodel import ID_RE, Report, _is_str

MAX_BRICKS = 8
MAX_OPTIONS = 8
MAX_VALUES = 8
MAX_EVENTS = 6
EXAMPLE_BRICK = {
    "type": "task",
    "label": "Tâche",
    "options": [{"key": "always_run", "label": "Toujours exécutée", "values": [False, True]}],
    "events": [{"key": "echec", "label": "Échoue"}],
}


def pairs_hold(expected: dict, values: dict) -> bool:
    """Vrai si chaque nom cité a la valeur attendue (`option`, `setting`)."""
    return all(name in values and same(values[name], wanted) for name, wanted in expected.items())


def same(a, b) -> bool:
    """Égalité stricte : true ne vaut pas 1, « 1 » ne vaut pas 1 ; un entier et un décimal égaux se valent."""
    numbers = (int, float)
    if isinstance(a, numbers) and isinstance(b, numbers) and not isinstance(a, bool | type(None)):
        return not isinstance(b, bool) and a == b
    return type(a) is type(b) and a == b


def among(value, values) -> bool:
    return any(same(value, v) for v in values)


def as_list(value) -> list:
    return list(value) if isinstance(value, list) else [value]


def text_of(value) -> str:
    """Une valeur d'option telle qu'elle s'écrit dans une adresse : true, false, 3, « rapide »."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return f"{value:g}" if isinstance(value, float) else str(value)


def item_key(item, name: str, seen: set, report: Report, p: str, what: str) -> str | None:
    key = item.get(name) if isinstance(item, dict) else None
    if not (isinstance(key, str) and ID_RE.match(key)):
        report.error(f"{p}.{name}", "format", f"{what} : un nom court sans espace.", received=key)
        return None
    if key in seen:
        report.error(f"{p}.{name}", "duplicate", f"{what} « {key} » est déclaré deux fois.", received=key)
        return None
    seen.add(key)
    return key


def item_label(item: dict, report: Report, p: str, fallback: str, size: int = 60, name: str = "label") -> str:
    label = item.get(name) or fallback
    if not _is_str(label, size):
        report.error(f"{p}.{name}", "type", f"Un libellé est un texte de {size} caractères au plus.")
        return fallback
    return label.strip() or fallback


def dimension_binding(raw, values: list, report: Report, p: str) -> dict | None:
    """Un réglage lu dans une dimension de l'étude : {key, values: {valeur de la dimension: valeur du
    réglage}}. Sert à rejouer un cas, qui dit ses dimensions sans nommer les réglages de l'atelier."""
    example = {"key": "arret_sur_erreur", "values": {"oui": True, "non": False}}
    pairs = raw.get("values") if isinstance(raw, dict) else None
    if (
        not isinstance(raw, dict)
        or set(raw) - {"key", "values"}
        or not (isinstance(raw.get("key"), str) and ID_RE.match(raw["key"]))
        or not isinstance(pairs, dict)
        or not pairs
    ):
        report.error(p, "type", "Un objet {key, values} : la dimension, puis ses valeurs.", example=example)
        return None
    for name, value in pairs.items():
        if not among(value, values):
            report.error(f"{p}.values.{name}", "unknown_value", "Une valeur du réglage.", received=value)
            return None
    return {
        "key": raw["key"],
        "values": {name: next(v for v in values if same(v, value)) for name, value in pairs.items()},
    }


def bound_dimensions(decl: dict, dimensions: list[dict], report: Report, path: str = "workshop") -> None:
    """Un réglage ne se lit que dans une dimension que l'étude déclare, et parmi ses valeurs."""
    known = {d["key"]: {v["value"] for v in d["values"]} for d in dimensions}
    for i, item in enumerate(decl.get("settings") or []):
        binding = item.get("dimension")
        if not binding:
            continue
        p = f"{path}.settings[{i}].dimension"
        if binding["key"] not in known:
            report.error(
                f"{p}.key",
                "unknown_dimension",
                "Dimension inconnue de l'étude.",
                received=binding["key"],
                expected=sorted(known),
            )
            continue
        for name in binding["values"]:
            if name not in known[binding["key"]]:
                report.error(
                    f"{p}.values.{name}",
                    "unknown_value",
                    "Valeur inconnue de cette dimension.",
                    received=name,
                    expected=sorted(known[binding["key"]]),
                )


def choices(raw, report: Report, path: str, what: str, limit: int, bindable: bool = False) -> list[dict]:
    """Options d'une brique ou réglages de la situation : {key, label, values, default}. Un réglage
    (`bindable`) peut dire dans quelle dimension de l'étude il se lit (`dimension`)."""
    if raw in (None, []):
        return []
    if not isinstance(raw, list) or len(raw) > limit:
        report.error(path, "type", f"{what} : une liste de {limit} entrées au plus {{key, label, values}}.")
        return []
    out, seen = [], set()
    for i, item in enumerate(raw):
        p = f"{path}[{i}]"
        key = item_key(item, "key", seen, report, p, what)
        if key is None:
            continue
        values = item.get("values")
        scalar = (bool, int, float, str)
        fine = isinstance(values, list) and 2 <= len(values) <= MAX_VALUES
        fine = fine and all(
            isinstance(v, scalar) and (not isinstance(v, str) or 0 < len(v) <= 40) for v in values
        )
        if not fine or any(among(v, values[:n]) for n, v in enumerate(values)):
            report.error(
                f"{p}.values",
                "type",
                f"De 2 à {MAX_VALUES} valeurs distinctes : textes courts, nombres ou booléens.",
                received=values,
                example=[False, True],
            )
            continue
        default = item.get("default", values[0])
        if not among(default, values):
            report.error(f"{p}.default", "unknown_value", "La valeur par défaut est une des valeurs.")
            continue
        out.append(
            {"key": key, "label": item_label(item, report, p, key), "values": values, "default": default}
        )
        if bindable and item.get("dimension") is not None:
            binding = dimension_binding(item["dimension"], values, report, f"{p}.dimension")
            if binding:
                out[-1]["dimension"] = binding
    return out


def events(raw, report: Report, path: str) -> list[dict]:
    if raw in (None, []):
        return []
    if not isinstance(raw, list) or len(raw) > MAX_EVENTS:
        report.error(path, "type", f"« events » : {MAX_EVENTS} évènements au plus {{key, label}}.")
        return []
    out, seen = [], set()
    for i, item in enumerate(raw):
        key = item_key(item, "key", seen, report, f"{path}[{i}]", "Un évènement")
        if key:
            out.append({"key": key, "label": item_label(item, report, f"{path}[{i}]", key)})
    return out


def bricks(raw, status_keys: set[str], report: Report, path: str) -> list[dict]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_BRICKS:
        report.error(
            path,
            "type",
            f"« bricks » : de 1 à {MAX_BRICKS} types de briques {{type, label, options, events}}.",
            example=[EXAMPLE_BRICK],
        )
        return []
    out, seen = [], set()
    for i, item in enumerate(raw):
        p = f"{path}[{i}]"
        kind = item_key(item, "type", seen, report, p, "Un type de brique")
        if kind is None:
            continue
        brick = {
            "type": kind,
            "label": item_label(item, report, p, kind, 40),
            "options": choices(item.get("options"), report, f"{p}.options", "Une option", MAX_OPTIONS),
            "events": events(item.get("events"), report, f"{p}.events"),
        }
        initial = item.get("initial")
        if initial is not None:
            if initial not in status_keys:
                report.error(
                    f"{p}.initial",
                    "unknown_status",
                    "L'état de départ d'une brique est un statut déclaré dans l'étude.",
                    received=initial,
                    expected=sorted(status_keys),
                )
            else:
                brick["initial"] = initial
        out.append(brick)
    return out


def check_pairs(expected, allowed: dict, report: Report, p: str, what: str) -> bool:
    if not isinstance(expected, dict) or not expected:
        report.error(p, "type", f"« {what} » compare des valeurs : {{nom: valeur}}.", received=expected)
        return False
    ok = True
    for key, value in expected.items():
        if key not in allowed:
            report.error(
                f"{p}.{key}", f"unknown_{what}", "Nom inconnu.", received=key, expected=sorted(allowed)
            )
            ok = False
        elif not among(value, allowed[key]):
            report.error(
                f"{p}.{key}", "unknown_value", "Valeur inconnue.", received=value, expected=allowed[key]
            )
            ok = False
    return ok


def chosen(declared: list[dict], raw, report: Report, p: str) -> dict:
    """Valeurs d'options ou de réglages : celles qu'on donne, complétées par les valeurs par défaut."""
    out = {item["key"]: item["default"] for item in declared}
    if raw in (None, {}):
        return out
    if not isinstance(raw, dict):
        report.error(p, "type", "Un objet {nom: valeur}.", received=raw)
        return out
    known = {item["key"]: item for item in declared}
    for key, value in raw.items():
        if key not in known:
            report.error(f"{p}.{key}", "unknown_option", "Nom inconnu.", received=key, expected=sorted(known))
        elif not among(value, known[key]["values"]):
            report.error(
                f"{p}.{key}",
                "unknown_value",
                "Valeur inconnue.",
                received=value,
                expected=known[key]["values"],
            )
        else:
            out[key] = next(v for v in known[key]["values"] if same(v, value))
    return out
