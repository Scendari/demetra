"""Modèle de cas générique : validation, rejeu des étapes, empreinte sémantique.

Un cas décrit des entités, des liens et une suite d'étapes ; chaque étape ne déclare que
les changements d'état. Le même format couvre les workflows (tâches et dépendances),
les règles de décision (conditions et résultat) et les règles temporelles (périodes,
échéances, étapes datées).

Les erreurs sont conçues pour être corrigées par une IA : chemin précis, règle violée,
valeur reçue, valeur attendue et exemple valide.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

ROLES = ["neutral", "waiting", "active", "success", "warning", "error", "blocked", "disabled", "info"]
ROLE_LABELS = {
    "neutral": "Neutre",
    "waiting": "En attente",
    "active": "En cours",
    "success": "Réussite",
    "warning": "Avertissement",
    "error": "Erreur",
    "blocked": "Bloqué",
    "disabled": "Désactivé",
    "info": "Information",
}
KINDS = ["workflow", "decision", "temporal"]
ACYCLIC_LINK_TYPES = {"prerequisite", "dependency", "depends_on"}
PROOF_LEVELS = ["asserted", "observed"]

KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_.\-]{0,79}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,39}$")

MAX_ENTITIES = 60
MAX_LINKS = 200
MAX_STEPS = 60
MAX_HIGHLIGHTS = 4
MAX_FOCUS = 3
MAX_COMPARE = 3
MAX_TEXT = 4000


@dataclass
class Issue:
    path: str
    code: str
    message: str
    received: Any = None
    expected: Any = None
    example: Any = None
    severity: str = "error"

    def as_dict(self) -> dict:
        out = {"path": self.path, "code": self.code, "message": self.message, "severity": self.severity}
        if self.received is not None:
            out["received"] = self.received
        if self.expected is not None:
            out["expected"] = self.expected
        if self.example is not None:
            out["example"] = self.example
        return out


@dataclass
class Report:
    issues: list[Issue] = field(default_factory=list)

    def error(self, path, code, message, **kw):
        self.issues.append(Issue(path, code, message, **kw))

    def warn(self, path, code, message, **kw):
        self.issues.append(Issue(path, code, message, severity="warning", **kw))

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------------------
# Définitions portées par l'étude : statuts, dimensions, règles
# ---------------------------------------------------------------------------

EXAMPLE_STATUS = {"key": "RUNNING", "label": "En cours", "role": "active"}
EXAMPLE_DIMENSION = {"key": "stop_on_error", "label": "Arrêt sur erreur", "values": ["oui", "non"]}
EXAMPLE_RULE = {
    "key": "R1",
    "title": "Une tâche attend ses prérequis",
    "text": "B ne démarre que si A a réussi.",
}


def _is_str(value, max_len=MAX_TEXT) -> bool:
    return isinstance(value, str) and len(value) <= max_len


def normalize_statuses(raw, report: Report, path="statuses") -> list[dict]:
    out = []
    if raw is None:
        return out
    if not isinstance(raw, list):
        report.error(
            path,
            "type",
            "La liste des statuts doit être un tableau.",
            received=type(raw).__name__,
            example=[EXAMPLE_STATUS],
        )
        return out
    seen = set()
    for i, item in enumerate(raw):
        p = f"{path}[{i}]"
        if not isinstance(item, dict):
            report.error(p, "type", "Un statut est un objet.", example=EXAMPLE_STATUS)
            continue
        key = item.get("key")
        if not (isinstance(key, str) and ID_RE.match(key)):
            report.error(
                f"{p}.key",
                "format",
                "Clé de statut invalide (lettres, chiffres, _ . -, 40 caractères au plus).",
                received=key,
                example="RUNNING",
            )
            continue
        if key in seen:
            report.error(f"{p}.key", "duplicate", f"Le statut « {key} » est déclaré deux fois.", received=key)
            continue
        seen.add(key)
        role = item.get("role", "neutral")
        if role not in ROLES:
            report.error(
                f"{p}.role", "enum", "Rôle visuel inconnu.", received=role, expected=ROLES, example="success"
            )
            role = "neutral"
        label = item.get("label") or key
        if not _is_str(label, 60):
            report.error(
                f"{p}.label",
                "type",
                "Le libellé d'un statut est un texte de 60 caractères au plus.",
                received=label,
            )
            label = key
        entry = {"key": key, "label": label, "role": role}
        if item.get("short"):
            if _is_str(item["short"], 14):
                entry["short"] = item["short"]
            else:
                report.error(
                    f"{p}.short",
                    "type",
                    "Le libellé abrégé fait 14 caractères au plus.",
                    received=item["short"],
                )
        if item.get("description"):
            entry["description"] = str(item["description"])[:300]
        if item.get("default"):
            entry["default"] = True
        out.append(entry)
    return out


def _dimension_values(values: list, report: Report, p: str) -> list[dict]:
    """Les valeurs possibles d'une dimension, en {value, label} ; booléens et nombres deviennent du texte."""
    norm_values, seen_values = [], set()
    for j, value in enumerate(values):
        if isinstance(value, dict):
            val, lab = value.get("value"), value.get("label")
        else:
            val, lab = value, None
        if isinstance(val, bool):
            val = "oui" if val else "non"
        if isinstance(val, (int, float)):
            val = str(val)
        if not (isinstance(val, str) and 0 < len(val) <= 60):
            report.error(
                f"{p}.values[{j}]",
                "type",
                "Une valeur de dimension est un texte court.",
                received=value,
                example="oui",
            )
            continue
        if val in seen_values:
            report.error(f"{p}.values[{j}]", "duplicate", f"Valeur « {val} » en double.", received=val)
            continue
        seen_values.add(val)
        norm_values.append({"value": val, "label": lab if _is_str(lab, 80) and lab else val})
    return norm_values


def normalize_dimensions(raw, report: Report, path="dimensions") -> list[dict]:
    out = []
    if raw is None:
        return out
    if not isinstance(raw, list):
        report.error(
            path, "type", "La liste des dimensions doit être un tableau.", example=[EXAMPLE_DIMENSION]
        )
        return out
    seen = set()
    for i, item in enumerate(raw):
        p = f"{path}[{i}]"
        if not isinstance(item, dict):
            report.error(p, "type", "Une dimension est un objet.", example=EXAMPLE_DIMENSION)
            continue
        key = item.get("key")
        if not (isinstance(key, str) and ID_RE.match(key)):
            report.error(
                f"{p}.key", "format", "Clé de dimension invalide.", received=key, example="stop_on_error"
            )
            continue
        if key in seen:
            report.error(
                f"{p}.key", "duplicate", f"La dimension « {key} » est déclarée deux fois.", received=key
            )
            continue
        seen.add(key)
        values = item.get("values")
        if not isinstance(values, list) or len(values) < 2:
            report.error(
                f"{p}.values",
                "min_items",
                "Une dimension déclare au moins deux valeurs possibles.",
                received=values,
                example=["oui", "non"],
            )
            continue
        norm_values = _dimension_values(values, report, p)
        if "highlight" in item and not isinstance(item["highlight"], bool):
            report.error(
                f"{p}.highlight",
                "type",
                "« highlight » vaut true ou false : true garde la dimension visible sur tous les cas de "
                "l'étude.",
                received=item["highlight"],
                example=True,
            )
            continue
        if len(norm_values) >= 2:
            dim = {"key": key, "label": item.get("label") or key, "values": norm_values}
            if item.get("highlight"):
                dim["highlight"] = True  # mise en avant sur tous les cas de l'étude
            if any(name in item for name in ("bands", "unit", "inclusive")):
                from .extensions import normalize_bands

                dim.update(normalize_bands(item, norm_values, report, p))
            out.append(dim)
    return out


def normalize_exclusions(raw, dimensions: list[dict], report: Report, path="exclusions") -> list[dict]:
    """Combinaisons déclarées impossibles : elles ne sont pas comptées comme manquantes."""
    out = []
    if raw is None:
        return out
    if not isinstance(raw, list):
        report.error(path, "type", "Les exclusions sont un tableau d'objets {combinaison, raison}.")
        return out
    dims = {d["key"]: {v["value"] for v in d["values"]} for d in dimensions}
    for i, item in enumerate(raw):
        p = f"{path}[{i}]"
        combo = item.get("when") if isinstance(item, dict) else None
        if not isinstance(combo, dict) or not combo:
            report.error(
                p,
                "type",
                'Une exclusion est {"when": {dimension: valeur, …}, "reason": "…"}.',
                received=item,
                example={
                    "when": {"delai": ">30 j", "etat": "intact"},
                    "reason": "Hors délai : l'état n'est pas examiné.",
                },
            )
            continue
        ok = True
        for key, value in combo.items():
            if key not in dims:
                report.error(
                    f"{p}.when.{key}",
                    "unknown_dimension",
                    f"Dimension « {key} » non déclarée.",
                    received=key,
                    expected=sorted(dims),
                )
                ok = False
            elif str(value) not in dims[key]:
                report.error(
                    f"{p}.when.{key}",
                    "unknown_value",
                    f"Valeur inconnue pour « {key} ».",
                    received=value,
                    expected=sorted(dims[key]),
                )
                ok = False
        if ok:
            out.append(
                {"when": {k: str(v) for k, v in combo.items()}, "reason": str(item.get("reason", ""))[:300]}
            )
    return out


MAX_ATTRIBUTES = 40
EXAMPLE_ATTRIBUTE = {
    "key": "always_run",
    "label": "Toujours exécutée",
    "text": "La tâche s'exécute même si un de ses prérequis a échoué.",
}


def normalize_attributes(raw, report: Report, path="attributes") -> list[dict]:
    """Options que portent les entités (« attrs ») : un libellé lisible et une définition, déclarés une fois
    pour l'étude."""
    out = []
    if raw is None:
        return out
    if not isinstance(raw, list):
        report.error(
            path,
            "type",
            "« attributes » est la liste des options portées par les entités.",
            example=[EXAMPLE_ATTRIBUTE],
        )
        return out
    if len(raw) > MAX_ATTRIBUTES:
        report.error(path, "max_items", f"{MAX_ATTRIBUTES} options au plus par étude.", received=len(raw))
    seen = set()
    for i, item in enumerate(raw[:MAX_ATTRIBUTES]):
        p = f"{path}[{i}]"
        if not isinstance(item, dict):
            report.error(p, "type", "Une option est un objet {key, label, text}.", example=EXAMPLE_ATTRIBUTE)
            continue
        for extra in sorted(set(item) - {"key", "label", "text", "show"}):
            report.warn(
                f"{p}.{extra}",
                "unknown_field",
                f"Champ « {extra} » inconnu : il est ignoré.",
                expected=["key", "label", "show", "text"],
            )
        show = item.get("show", "key")
        if show not in ("key", "label"):
            report.error(
                f"{p}.show",
                "enum",
                "« show » vaut key (le nom technique, par défaut) ou label (le libellé lisible).",
                received=show,
                expected=["key", "label"],
            )
            show = "key"
        key = item.get("key")
        if not (isinstance(key, str) and ID_RE.match(key)):
            report.error(
                f"{p}.key",
                "format",
                "Nom d'option invalide : le même que dans les « attrs » des entités.",
                received=key,
                example="always_run",
            )
            continue
        if key in seen:
            report.error(f"{p}.key", "duplicate", f"L'option « {key} » est déclarée deux fois.", received=key)
            continue
        seen.add(key)
        label, text = item.get("label") or "", item.get("text") or ""
        if not (_is_str(label, 60) and label.strip()):
            report.error(
                f"{p}.label",
                "required",
                "Une option a un libellé lisible, 60 caractères au plus.",
                received=label,
                example=EXAMPLE_ATTRIBUTE["label"],
            )
            continue
        if not _is_str(text, 300):
            report.error(
                f"{p}.text",
                "type",
                "La définition est un texte de 300 caractères au plus.",
                received=type(text).__name__,
            )
            text = ""
        out.append(
            {
                "key": key,
                "label": label.strip(),
                **({"text": text.strip()} if text.strip() else {}),
                **({"show": "label"} if show == "label" else {}),
            }
        )
    return out


def normalize_rules(raw, report: Report, path="rules") -> list[dict]:
    out = []
    if raw is None:
        return out
    if not isinstance(raw, list):
        report.error(path, "type", "Les règles de gestion sont un tableau.", example=[EXAMPLE_RULE])
        return out
    seen = set()
    for i, item in enumerate(raw):
        p = f"{path}[{i}]"
        if not isinstance(item, dict):
            report.error(p, "type", "Une règle est un objet.", example=EXAMPLE_RULE)
            continue
        key = item.get("key")
        if not (isinstance(key, str) and ID_RE.match(key)):
            report.error(f"{p}.key", "format", "Clé de règle invalide.", received=key, example="R1")
            continue
        if key in seen:
            report.error(f"{p}.key", "duplicate", f"La règle « {key} » est déclarée deux fois.", received=key)
            continue
        seen.add(key)
        title = item.get("title")
        if not (_is_str(title, 200) and title):
            report.error(
                f"{p}.title",
                "required",
                "Une règle a un titre.",
                received=title,
                example=EXAMPLE_RULE["title"],
            )
            continue
        entry = {"key": key, "title": title, "text": str(item.get("text", ""))[:MAX_TEXT]}
        if item.get("source"):
            entry["source"] = str(item["source"])[:300]
        out.append(entry)
    return out


MAX_INVENTORY = 500
INVENTORY_STATES = ("open", "excluded", "to_confirm")
EXAMPLE_POINT = {
    "key": "P1",
    "label": "Montant négatif refusé",
    "source": {"ref": "facturation.py:120", "excerpt": "if montant < 0: raise MontantInvalide"},
    "kind": "erreur",
}


def _inventory_point(item, seen: set, report: Report, p: str) -> dict | None:
    """Un point de décision : clé, libellé, source vérifiable, sort déclaré (ouvert par défaut)."""
    if not isinstance(item, dict):
        report.error(p, "type", "Un point d'inventaire est un objet.", example=EXAMPLE_POINT)
        return None
    key, label = item.get("key"), item.get("label")
    if not (isinstance(key, str) and ID_RE.match(key)) or key in seen:
        code = "duplicate" if key in seen else "format"
        report.error(f"{p}.key", code, "Clé de point invalide ou déjà prise.", received=key, example="P1")
        return None
    seen.add(key)
    source = item.get("source")
    ref = source.get("ref") if isinstance(source, dict) else None
    if not (_is_str(label, 200) and label) or not (_is_str(ref, 300) and ref):
        report.error(
            p,
            "required",
            "Un point a un libellé et une source (« source.ref » : fichier et ligne, paragraphe d'un "
            "document…) : un point sans source ne se vérifie pas.",
            received=item,
            example=EXAMPLE_POINT,
        )
        return None
    state = item.get("state", "open")
    reason = item.get("reason")
    if state not in INVENTORY_STATES:
        report.error(
            f"{p}.state", "enum", "Sort de point inconnu.", received=state, expected=INVENTORY_STATES
        )
        return None
    if state != "open" and not (_is_str(reason, 1000) and reason):
        report.error(f"{p}.reason", "required", "Un point exclu ou à confirmer dit pourquoi (« reason »).")
        return None
    out = {"key": key, "label": label, "source": {"ref": ref}, "state": state}
    if _is_str(source.get("excerpt"), 500) and source.get("excerpt"):
        out["source"]["excerpt"] = source["excerpt"]
    if _is_str(item.get("kind"), 40) and item.get("kind"):
        out["kind"] = item["kind"]
    if state != "open":
        out["reason"] = reason
    return out


def normalize_inventory(raw, report: Report, path="inventory") -> list[dict]:
    """Les points de décision relevés dans les sources (code, documents), avant d'écrire les cas."""
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > MAX_INVENTORY:
        report.error(
            path,
            "type",
            f"L'inventaire est un tableau de {MAX_INVENTORY} points au plus.",
            example=[EXAMPLE_POINT],
        )
        return []
    seen: set[str] = set()
    points = (_inventory_point(item, seen, report, f"{path}[{i}]") for i, item in enumerate(raw))
    return [point for point in points if point]


def default_status(statuses: list[dict]) -> str | None:
    for status in statuses:
        if status.get("default"):
            return status["key"]
    return statuses[0]["key"] if statuses else None


# ---------------------------------------------------------------------------
# Cas
# ---------------------------------------------------------------------------

EXAMPLE_CASE = {
    "key": "chaine-simple",
    "family": "Bases",
    "title": "B attend la réussite de A",
    "summary": "B dépend de A : B ne démarre qu'après la réussite de A.",
    "kind": "workflow",
    "rules": ["R1"],
    "dimensions": {"issue_de_a": "réussite"},
    "entities": [
        {"id": "A", "label": "source", "type": "task"},
        {"id": "B", "label": "suite", "type": "task"},
    ],
    "links": [{"from": "A", "to": "B", "type": "prerequisite"}],
    "steps": [
        {"title": "A démarre", "note": "B attend.", "changes": {"A": "RUNNING"}},
        {"title": "A réussit, B démarre", "changes": {"A": "FINISHED_OK", "B": "RUNNING"}},
        {"title": "Fin", "changes": {"B": "FINISHED_OK"}, "global": "FINISHED_OK"},
    ],
}


@dataclass
class StudyContext:
    statuses: list[dict]
    dimensions: list[dict]
    rules: list[dict]
    kind: str = "mixed"
    ruleset: dict = field(default_factory=dict)
    lifecycles: list = field(default_factory=list)
    attributes: list = field(default_factory=list)
    workshop: dict = field(default_factory=dict)
    inventory: list = field(default_factory=list)

    @property
    def status_keys(self) -> set[str]:
        return {s["key"] for s in self.statuses}

    @property
    def dimension_values(self) -> dict[str, set[str]]:
        return {d["key"]: {v["value"] for v in d["values"]} for d in self.dimensions}

    @property
    def rule_keys(self) -> set[str]:
        return {r["key"] for r in self.rules}

    @property
    def point_keys(self) -> set[str]:
        return {point["key"] for point in self.inventory}


def _scalar(value) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


FLAG_TONES = ["ink", "muted", "accent", *ROLES]
FLAG_STYLE_DEFAULT = {"weight": "bold", "italic": False, "tone": "ink"}


def _clean_flag_style(raw, report: Report, path: str) -> dict:
    """Style d'une option mise en avant : graisse, italique, teinte. Les teintes sont celles du site (encre,
    rôles des
    statuts) : jamais une couleur libre, pour garder le contraste dans les deux thèmes. Ne garde que ce qui
    diffère du défaut."""
    if raw is None:
        return {}
    example = {"weight": "bold", "italic": False, "tone": "warning"}
    if not isinstance(raw, dict):
        report.error(
            path, "type", "« style » est un objet {weight, italic, tone}.", received=raw, example=example
        )
        return {}
    out = {}
    for key in sorted(set(raw) - set(FLAG_STYLE_DEFAULT)):
        report.error(
            f"{path}.{key}",
            "unknown_field",
            "Style inconnu : weight, italic ou tone.",
            received=key,
            expected=sorted(FLAG_STYLE_DEFAULT),
        )
    if "weight" in raw:
        if raw["weight"] in ("bold", "normal"):
            out["weight"] = raw["weight"]
        else:
            report.error(
                f"{path}.weight",
                "enum",
                "« weight » vaut bold ou normal.",
                received=raw["weight"],
                expected=["bold", "normal"],
            )
    if "italic" in raw:
        if isinstance(raw["italic"], bool):
            out["italic"] = raw["italic"]
        else:
            report.error(
                f"{path}.italic",
                "type",
                "« italic » vaut true ou false.",
                received=raw["italic"],
                example=True,
            )
    if "tone" in raw:
        if raw["tone"] in FLAG_TONES:
            out["tone"] = raw["tone"]
        else:
            report.error(
                f"{path}.tone",
                "enum",
                "Teinte inconnue : choisissez une teinte du site, pas une couleur libre.",
                received=raw["tone"],
                expected=FLAG_TONES,
            )
    return {k: v for k, v in out.items() if FLAG_STYLE_DEFAULT[k] != v}


def _clean_attrs(raw, report: Report, path: str) -> dict:
    out = {}
    if raw is None:
        return out
    if not isinstance(raw, dict):
        report.error(
            path, "type", "Les attributs sont un objet de valeurs simples.", example={"always_run": True}
        )
        return out
    if len(raw) > 24:
        report.error(path, "max_items", "24 attributs au plus par élément.", received=len(raw))
    for key, value in list(raw.items())[:24]:
        if not (isinstance(key, str) and ID_RE.match(key)):
            report.error(
                f"{path}.{key}", "format", "Nom d'attribut invalide.", received=key, example="always_run"
            )
            continue
        if not _scalar(value) or (isinstance(value, str) and len(value) > 300):
            report.error(
                f"{path}.{key}",
                "type",
                "Un attribut est un texte court, un nombre ou un booléen.",
                received=type(value).__name__,
            )
            continue
        out[key] = value
    return out


KNOWN_CASE_FIELDS = {
    "key",
    "number",
    "label",
    "family",
    "title",
    "summary",
    "kind",
    "rules",
    "dimensions",
    "tags",
    "config",
    "highlights",
    "measures",
    "entities",
    "links",
    "initial",
    "steps",
    "outcome",
    "references",
    "caution",
    "proof",
    "question",
    "compare_with",
    "params",
    "covers",
}


def _warn_unknown_fields(raw: dict, report: Report, path: str):
    for extra in sorted(set(raw) - KNOWN_CASE_FIELDS):
        report.warn(
            f"{path}.{extra}",
            "unknown_field",
            f"Champ « {extra} » inconnu : il est ignoré.",
            expected=sorted(KNOWN_CASE_FIELDS),
        )


def normalize_case(raw: Any, ctx: StudyContext, path: str = "case") -> tuple[dict | None, Report]:
    """Valide un cas et renvoie sa forme normalisée (ou None si des erreurs le rendent inutilisable).

    Un cas paramétré est rejoué pour chacune de ses combinaisons (`parametric`). Pour un cas ordinaire, le
    site signale en plus, sans refuser, un sort des lignes que le jeu de règles de l'étude ne donne pas."""
    from . import extensions as ext
    from . import parametric

    if isinstance(raw, dict) and raw.get("params") not in (None, []):
        return parametric.normalize(raw, ctx, path)
    case, report = _plain_case(raw, ctx, path)
    if case is not None:
        ext.check_ruleset_agreement(case, ctx.ruleset, ctx.dimensions, report, path)
        _check_workshop_agreement(case, ctx, report, path)
    return case, report


def _check_workshop_agreement(case: dict, ctx: StudyContext, report: Report, path: str):
    """Rejoué dans l'atelier de l'étude, le cas ne donne pas ce qu'il annonce : un avertissement, jamais un
    refus. Un cas que l'atelier ne sait pas rejouer n'est pas signalé ici : les contrôles d'étude le
    disent."""
    from .workshopcheck import agreement

    found = agreement(ctx.workshop, case, ctx.statuses)
    if not found or found["status"] != "differ":
        return
    report.warn(
        path,
        "workshop_mismatch",
        "Rejoué dans l'atelier de l'étude, ce cas ne donne pas ce qu'il annonce : "
        + " ; ".join(found["differences"][:4])
        + ". Soit le cas se trompe, soit les règles de l'atelier sont incomplètes : dites-le à l'utilisateur "
        "au lieu de corriger l'un pour faire taire l'autre.",
        received=found["differences"][:8],
    )


def _plain_case(raw: Any, ctx: StudyContext, path: str) -> tuple[dict | None, Report]:
    """Chaque partie du cas est lue par une fonction `_case_*` ; l'ordre des appels est l'ordre des messages
    rendus à l'IA, du plus structurant (clé, titre, entités) au plus accessoire (question, comparaison)."""
    report = Report()
    if not isinstance(raw, dict):
        report.error(
            path, "type", "Un cas est un objet JSON.", received=type(raw).__name__, example=EXAMPLE_CASE
        )
        return None, report

    from . import extensions as ext

    _warn_unknown_fields(raw, report, path)
    head = _case_header(raw, ctx, report, path)
    rules = _case_rules(raw, ctx, report, path)
    covers = _case_covers(raw, ctx, report, path)
    dims = _case_dimensions(raw, ctx, report, path)
    tags = _case_tags(raw, report, path)
    config = _clean_attrs(raw.get("config"), report, f"{path}.config")
    highlights, pending = _case_highlights(raw, dims, config, report, path)
    entities, ids = _case_entities(raw, ctx, report, path)
    link_highlights = _entity_highlights(pending, entities, highlights, report, path)
    links = _case_links(raw, ids, report, path)
    _link_highlights(link_highlights, links, highlights, report, path)
    _check_cycles(ids, links, report, path)

    check_status = _status_checker(ctx, report)
    fallback = default_status(ctx.statuses)
    initial = _case_initial(raw, ids, check_status, report, path)
    steps = _case_steps(raw, ids, ctx, check_status, report, path)
    measures = ext.normalize_measures(raw.get("measures"), ctx.dimensions, dims, report, f"{path}.measures")
    if report.ok:
        ext.check_lifecycles(entities, initial, steps, ctx.lifecycles, fallback, report, path)
    if entities and fallback is None and not report.errors:
        report.error(
            f"{path}.entities",
            "no_status",
            "L'étude ne déclare aucun statut : impossible de donner un état aux entités.",
            example=[EXAMPLE_STATUS],
        )
    outcome = _case_outcome(raw, check_status, report, path)
    references = _case_references(raw, report, path)
    caution, proof = _case_caution_and_proof(raw, report, path)
    if not report.ok:
        return None, report

    _warn_never_changing(entities, initial, steps, report, path)
    case = {
        **head,
        "rules": rules,
        "dimensions": dims,
        "tags": tags,
        "config": config,
        "entities": entities,
        "links": links,
        "initial": initial,
        "steps": steps,
        "references": references,
        "caution": caution,
        "proof": proof,
    }
    if outcome:
        case["outcome"] = outcome
    if covers:  # absent sinon : le contenu des cas sans inventaire ne change pas d'un octet
        case["covers"] = covers
    if highlights:
        case["highlights"] = highlights
    question = _case_question(raw, report, path)
    if question:
        case["question"] = question
    compare = _case_compare_with(raw, report, path)
    if compare:
        case["compare_with"] = compare
    if measures:
        case["measures"] = measures
    if not report.ok:  # « question » et « compare_with » sont vérifiés après l'assemblage
        return None, report
    return case, report


def _case_header(raw: dict, ctx: StudyContext, report: Report, path: str) -> dict:
    """Clé, numéro, libellé, famille, titre, résumé et nature du cas, déjà nettoyés."""
    key = raw.get("key")
    if not (isinstance(key, str) and KEY_RE.match(key)):
        report.error(
            f"{path}.key",
            "format",
            "La clé d'un cas est stable et en minuscules : lettres, chiffres, _ . - (80 caractères au plus).",
            received=key,
            example="chaine-simple",
        )
        key = None

    title = raw.get("title")
    if not (_is_str(title, 300) and title and title.strip()):
        report.error(
            f"{path}.title",
            "required",
            "Un cas a un titre (300 caractères au plus).",
            received=title,
            example=EXAMPLE_CASE["title"],
        )
        title = ""

    number = raw.get("number")
    if number is not None and not (
        isinstance(number, int) and not isinstance(number, bool) and 0 < number < 100000
    ):
        report.error(
            f"{path}.number",
            "type",
            "Le numéro d'affichage est un entier positif (facultatif).",
            received=number,
            example=12,
        )
        number = None
    case_label = raw.get("label") or None
    if case_label is not None and not (_is_str(case_label, 12) and case_label.strip()):
        report.error(
            f"{path}.label",
            "type",
            "Le libellé de numéro est un texte de 12 caractères au plus (facultatif).",
            received=case_label,
            example="16-A",
        )
        case_label = None

    family = raw.get("family") or "Général"
    if not _is_str(family, 120):
        report.error(
            f"{path}.family", "type", "La famille est un texte de 120 caractères au plus.", received=family
        )
        family = "Général"

    summary = raw.get("summary") or ""
    if not _is_str(summary):
        report.error(f"{path}.summary", "type", "Le résumé est un texte.", received=type(summary).__name__)
        summary = ""

    kind = raw.get("kind") or (ctx.kind if ctx.kind in KINDS else "workflow")
    if kind not in KINDS:
        report.error(f"{path}.kind", "enum", "Nature de cas inconnue.", received=kind, expected=KINDS)
        kind = "workflow"
    return {
        "key": key,
        "number": number,
        "label": case_label.strip() if case_label else "",
        "family": family.strip(),
        "title": title.strip(),
        "summary": summary,
        "kind": kind,
    }


def _case_rules(raw: dict, ctx: StudyContext, report: Report, path: str) -> list[str]:
    """Clés des règles de gestion illustrées par le cas, toutes déclarées dans l'étude."""
    rules: list[str] = []
    raw_rules = raw.get("rules") or []
    if not isinstance(raw_rules, list):
        report.error(
            f"{path}.rules", "type", "« rules » est la liste des clés de règles illustrées.", example=["R1"]
        )
        raw_rules = []
    for i, rule_key in enumerate(raw_rules):
        if rule_key not in ctx.rule_keys:
            report.error(
                f"{path}.rules[{i}]",
                "unknown_rule",
                f"La règle « {rule_key} » n'est pas déclarée dans l'étude.",
                received=rule_key,
                expected=sorted(ctx.rule_keys)
                or "aucune règle déclarée : ajoutez-la à l'étude (PATCH /studies/{id}, champ rules)",
            )
        elif rule_key not in rules:
            rules.append(rule_key)
    return rules


def _case_covers(raw: dict, ctx: StudyContext, report: Report, path: str) -> list[str]:
    """Les points de l'inventaire que le cas couvre, tous déclarés dans l'étude."""
    raw_covers = raw.get("covers") or []
    if not isinstance(raw_covers, list):
        report.error(f"{path}.covers", "type", "« covers » est la liste des clés de points.", example=["P1"])
        return []
    covers: list[str] = []
    for i, point in enumerate(raw_covers):
        if point not in ctx.point_keys:
            report.error(
                f"{path}.covers[{i}]",
                "unknown_inventory_point",
                f"Le point « {point} » n'est pas dans l'inventaire de l'étude.",
                received=point,
                expected=sorted(ctx.point_keys)[:50]
                or "aucun inventaire : déclarez-le d'abord (PATCH /studies/{id}, champ inventory)",
            )
        elif point not in covers:
            covers.append(point)
    return covers


def _case_dimensions(raw: dict, ctx: StudyContext, report: Report, path: str) -> dict[str, str]:
    """Valeur du cas pour chaque dimension déclarée ; une dimension absente ne compte pas dans la
    couverture."""
    dims: dict[str, str] = {}
    raw_dims = raw.get("dimensions") or {}
    dim_values = ctx.dimension_values
    if not isinstance(raw_dims, dict):
        report.error(
            f"{path}.dimensions",
            "type",
            "« dimensions » associe une valeur à chaque dimension déclarée.",
            example={"stop_on_error": "non"},
        )
        raw_dims = {}
    for dim_key, value in raw_dims.items():
        if isinstance(value, bool):
            value = "oui" if value else "non"
        value = str(value)
        if dim_key not in dim_values:
            report.error(
                f"{path}.dimensions.{dim_key}",
                "unknown_dimension",
                f"La dimension « {dim_key} » n'est pas déclarée dans l'étude.",
                received=dim_key,
                expected=sorted(dim_values)
                or "aucune dimension déclarée : ajoutez-la à l'étude (PATCH /studies/{id}, champ dimensions)",
            )
        elif value not in dim_values[dim_key]:
            report.error(
                f"{path}.dimensions.{dim_key}",
                "unknown_value",
                f"Valeur non déclarée pour la dimension « {dim_key} ».",
                received=value,
                expected=sorted(dim_values[dim_key]),
            )
        else:
            dims[dim_key] = value
    for dim_key in dim_values:
        if dim_key not in raw_dims:
            report.warn(
                f"{path}.dimensions.{dim_key}",
                "missing_dimension",
                f"Le cas ne renseigne pas la dimension « {dim_key} » : "
                "il ne comptera pas dans la couverture de cette dimension.",
                expected=sorted(dim_values[dim_key]),
            )
    return dims


def _case_tags(raw: dict, report: Report, path: str) -> list[str]:
    tags: list[str] = []
    for i, tag in enumerate(raw.get("tags") or []):
        if _is_str(tag, 40) and tag:
            tags.append(tag)
        else:
            report.error(
                f"{path}.tags[{i}]",
                "type",
                "Une étiquette est un texte de 40 caractères au plus.",
                received=tag,
            )
    return tags


def _case_highlights(
    raw: dict, dims: dict, config: dict, report: Report, path: str
) -> tuple[list, list[tuple[int, dict]]]:
    """Caractéristiques que l'auteur veut garder sous les yeux du relecteur : clés de « dimensions » ou de
    « config », retenues tout de suite ; les options d'entité ou de lien (objets) sont rendues pour être
    vérifiées une fois entités et liens lus."""
    highlights: list = []
    raw_high = raw.get("highlights") or []
    if not isinstance(raw_high, list):
        report.error(
            f"{path}.highlights",
            "type",
            "« highlights » est la liste des caractéristiques à mettre en avant.",
            example=["stop_on_error"],
        )
        raw_high = []
    if len(raw_high) > MAX_HIGHLIGHTS:
        report.error(
            f"{path}.highlights",
            "max_items",
            f"{MAX_HIGHLIGHTS} caractéristiques mises en avant au plus : au-delà, plus rien ne ressort.",
            received=len(raw_high),
        )
    pending: list[tuple[int, dict]] = []
    for i, name in enumerate(raw_high[:MAX_HIGHLIGHTS]):
        if isinstance(name, dict):
            pending.append((i, name))
        elif isinstance(name, str) and (name in dims or name in config):
            if name not in highlights:
                highlights.append(name)
        else:
            report.error(
                f"{path}.highlights[{i}]",
                "unknown_highlight",
                "Une caractéristique mise en avant est une clé de « dimensions » ou de « config » de ce cas, "
                'ou une option d\'entité {"entity", "attr"}.',
                received=name,
                expected=sorted({*dims, *config})
                or "aucune : renseignez d'abord « dimensions » ou « config »",
            )
    return highlights, pending


def _case_entity(ent: dict, p: str, report: Report) -> dict:
    """Une entité dont l'identifiant est déjà vérifié : libellé, type, groupe, attributs, champs."""
    from . import extensions as ext

    label = ent.get("label", "")
    if not _is_str(label, 120):
        report.error(
            f"{p}.label",
            "type",
            "Le libellé d'une entité est un texte de 120 caractères au plus.",
            received=label,
        )
        label = ""
    ent_type = ent.get("type") or "item"
    if not (isinstance(ent_type, str) and 0 < len(ent_type.strip()) <= 40 and ent_type.isprintable()):
        report.error(
            f"{p}.type",
            "format",
            "Le type d'une entité est un texte court (40 caractères au plus).",
            received=ent_type,
            example="task",
        )
        ent_type = "item"
    group = ent.get("group") or ""
    if not _is_str(group, 80):
        report.error(f"{p}.group", "type", "Le groupe est un texte de 80 caractères au plus.", received=group)
        group = ""
    entity = {
        "id": ent["id"],
        "label": label,
        "type": ent_type,
        "group": group,
        "attrs": _clean_attrs(ent.get("attrs"), report, f"{p}.attrs"),
    }
    ent_fields = ext.clean_fields(ent.get("fields"), report, f"{p}.fields")
    if ent_fields:
        entity["fields"] = ent_fields
    return entity


def _case_entities(raw: dict, ctx: StudyContext, report: Report, path: str) -> tuple[list[dict], set[str]]:
    """Les entités du cas et l'ensemble de leurs identifiants."""
    entities: list[dict] = []
    ids: set[str] = set()
    raw_entities = raw.get("entities") or []
    if not isinstance(raw_entities, list):
        report.error(
            f"{path}.entities", "type", "« entities » est un tableau.", example=EXAMPLE_CASE["entities"]
        )
        raw_entities = []
    if len(raw_entities) > MAX_ENTITIES:
        report.error(
            f"{path}.entities",
            "max_items",
            f"{MAX_ENTITIES} entités au plus par cas : un cas illustre une situation, pas tout le système.",
            received=len(raw_entities),
        )
    for i, ent in enumerate(raw_entities[:MAX_ENTITIES]):
        p = f"{path}.entities[{i}]"
        if not isinstance(ent, dict):
            report.error(p, "type", "Une entité est un objet.", example=EXAMPLE_CASE["entities"][0])
            continue
        ent_id = ent.get("id")
        if not (isinstance(ent_id, str) and ID_RE.match(ent_id)):
            report.error(
                f"{p}.id",
                "format",
                "Identifiant d'entité invalide (lettres, chiffres, _ . -, 40 caractères au plus).",
                received=ent_id,
                example="A",
            )
            continue
        if ent_id in ids:
            report.error(
                f"{p}.id", "duplicate", f"L'entité « {ent_id} » est déclarée deux fois.", received=ent_id
            )
            continue
        ids.add(ent_id)
        entities.append(_case_entity(ent, p, report))

    # Options déclarées par l'étude : un nom d'option inconnu est probablement une faute de frappe.
    declared = {a["key"] for a in ctx.attributes}
    if declared:
        for e_i, ent in enumerate(entities):
            for attr_key in ent["attrs"]:
                if attr_key not in declared:
                    report.warn(
                        f"{path}.entities[{e_i}].attrs.{attr_key}",
                        "undeclared_attr",
                        f"Option « {attr_key} » non déclarée dans l'étude (« attributes ») : "
                        "vérifiez l'orthographe, ou déclarez-la.",
                        received=attr_key,
                        expected=sorted(declared),
                    )
    return entities, ids


def _entity_highlights(
    pending: list[tuple[int, dict]], entities: list[dict], highlights: list, report: Report, path: str
) -> list[tuple[int, dict]]:
    """Option d'une entité mise en avant : {"entity": "C", "attr": "always_run"}. Forme objet, car un
    identifiant
    d'entité comme un nom d'attribut peuvent contenir des points. Rend les mises en avant de liens, à vérifier
    une fois les liens lus."""
    by_id = {e["id"]: e for e in entities}
    link_highlights = [(i, item) for i, item in pending if "link" in item]
    for i, item in [(i, item) for i, item in pending if "link" not in item]:
        p = f"{path}.highlights[{i}]"
        ent_id, attr = item.get("entity"), item.get("attr")
        style = _clean_flag_style(item.get("style"), report, f"{p}.style")
        if (
            set(item) - {"entity", "attr", "style"}
            or not isinstance(ent_id, str)
            or not isinstance(attr, str)
        ):
            report.error(
                p,
                "type",
                'Une option d\'entité mise en avant s\'écrit {"entity": <id>, "attr": <nom d\'attribut>}.',
                received=item,
                example={"entity": "C", "attr": "always_run"},
            )
        elif ent_id not in by_id:
            report.error(
                p,
                "unknown_entity",
                "Cette entité n'existe pas dans le cas.",
                received=ent_id,
                expected=sorted(by_id) or "aucune entité",
            )
        elif attr not in by_id[ent_id]["attrs"]:
            report.error(
                p,
                "unknown_attr",
                "Cette entité ne porte pas cet attribut : déclarez-le d'abord dans ses « attrs ».",
                received=attr,
                expected=sorted(by_id[ent_id]["attrs"]) or "aucun attribut",
            )
        elif not any(isinstance(h, dict) and (h["entity"], h["attr"]) == (ent_id, attr) for h in highlights):
            highlights.append({"entity": ent_id, "attr": attr, **({"style": style} if style else {})})
    return link_highlights


def _case_links(raw: dict, ids: set[str], report: Report, path: str) -> list[dict]:
    """Liens entre entités : {from, to, type, label}, ou la forme courte [from, to]."""
    links: list[dict] = []
    raw_links = raw.get("links") or []
    if not isinstance(raw_links, list):
        report.error(f"{path}.links", "type", "« links » est un tableau.", example=EXAMPLE_CASE["links"])
        raw_links = []
    if len(raw_links) > MAX_LINKS:
        report.error(
            f"{path}.links", "max_items", f"{MAX_LINKS} liens au plus par cas.", received=len(raw_links)
        )
    for i, link in enumerate(raw_links[:MAX_LINKS]):
        p = f"{path}.links[{i}]"
        if isinstance(link, list) and len(link) == 2:
            link = {"from": link[0], "to": link[1]}
        if not isinstance(link, dict):
            report.error(
                p, "type", "Un lien est un objet {from, to, type}.", example=EXAMPLE_CASE["links"][0]
            )
            continue
        src, dst = link.get("from"), link.get("to")
        bad = False
        for side, value in (("from", src), ("to", dst)):
            if value not in ids:
                report.error(
                    f"{p}.{side}",
                    "unknown_entity",
                    f"Le lien référence une entité inconnue « {value} ».",
                    received=value,
                    expected=sorted(ids),
                )
                bad = True
        if bad:
            continue
        link_type = link.get("type") or "prerequisite"
        if not (isinstance(link_type, str) and ID_RE.match(link_type)):
            report.error(
                f"{p}.type", "format", "Type de lien invalide.", received=link_type, example="prerequisite"
            )
            link_type = "prerequisite"
        label = link.get("label") or ""
        if not _is_str(label, 80):
            report.error(
                f"{p}.label",
                "type",
                "Le libellé d'un lien est un texte de 80 caractères au plus.",
                received=label,
            )
            label = ""
        links.append({"from": src, "to": dst, "type": link_type, "label": label})
    return links


def _link_highlights(
    link_highlights: list[tuple[int, dict]], links: list[dict], highlights: list, report: Report, path: str
):
    """Lien mis en avant : {"link": ["A", "C"], "style": {...}} — la règle tient à cette dépendance."""
    for i, item in link_highlights:
        p = f"{path}.highlights[{i}]"
        pair = item.get("link")
        style = _clean_flag_style(item.get("style"), report, f"{p}.style")
        if set(item) - {"link", "style"} or not (
            isinstance(pair, list) and len(pair) == 2 and all(isinstance(x, str) for x in pair)
        ):
            report.error(
                p,
                "type",
                'Un lien mis en avant s\'écrit {"link": [<de>, <vers>]}.',
                received=item,
                example={"link": ["A", "C"]},
            )
        elif not any((l["from"], l["to"]) == tuple(pair) for l in links):
            report.error(
                p,
                "unknown_link",
                "Aucun lien de ce cas ne va de cette entité à celle-ci.",
                received=pair,
                expected=[[l["from"], l["to"]] for l in links][:20] or "aucun lien",
            )
        elif not any(isinstance(h, dict) and h.get("link") == pair for h in highlights):
            highlights.append({"link": pair, **({"style": style} if style else {})})


def _check_cycles(ids: set[str], links: list[dict], report: Report, path: str):
    cycle = _find_cycle(ids, [l for l in links if l["type"] in ACYCLIC_LINK_TYPES])
    if cycle:
        report.error(
            f"{path}.links",
            "cycle",
            "Les liens de prérequis forment un cycle : "
            + " → ".join(cycle)
            + ". Pour un cycle voulu (machine à états), utilisez un autre type de lien, par exemple « "
            "transition ».",
            received=cycle,
        )


def _status_checker(ctx: StudyContext, report: Report):
    """Fonction (valeur, chemin) -> bool qui signale un statut non déclaré dans l'étude."""
    status_keys = ctx.status_keys

    def check_status(value, p) -> bool:
        if value not in status_keys:
            report.error(
                p,
                "unknown_status",
                f"Statut « {value} » non déclaré dans l'étude.",
                received=value,
                expected=sorted(status_keys)
                or "aucun statut déclaré : ajoutez-les à l'étude (PATCH /studies/{id}, champ statuses)",
                example=EXAMPLE_STATUS,
            )
            return False
        return True

    return check_status


def _case_initial(raw: dict, ids: set[str], check_status, report: Report, path: str) -> dict[str, str]:
    """États de départ : entité -> statut."""
    initial: dict[str, str] = {}
    raw_initial = raw.get("initial") or {}
    if not isinstance(raw_initial, dict):
        report.error(
            f"{path}.initial",
            "type",
            "« initial » associe un statut de départ à des entités.",
            example={"A": "WAITING"},
        )
        raw_initial = {}
    for ent_id, value in raw_initial.items():
        if ent_id not in ids:
            report.error(
                f"{path}.initial.{ent_id}",
                "unknown_entity",
                f"Entité inconnue « {ent_id} ».",
                received=ent_id,
                expected=sorted(ids),
            )
        elif check_status(value, f"{path}.initial.{ent_id}"):
            initial[ent_id] = value
    return initial


def _case_steps(
    raw: dict, ids: set[str], ctx: StudyContext, check_status, report: Report, path: str
) -> list[dict]:
    """Les étapes du cas, dans l'ordre ; `running` porte les totaux courants d'une étape à l'autre."""
    steps: list[dict] = []
    raw_steps = raw.get("steps") or []
    if not isinstance(raw_steps, list):
        report.error(
            f"{path}.steps", "type", "« steps » est un tableau d'étapes.", example=EXAMPLE_CASE["steps"]
        )
        raw_steps = []
    if not raw_steps:
        report.error(
            f"{path}.steps", "min_items", "Un cas montre au moins une étape.", example=EXAMPLE_CASE["steps"]
        )
    if len(raw_steps) > MAX_STEPS:
        report.error(
            f"{path}.steps", "max_items", f"{MAX_STEPS} étapes au plus par cas.", received=len(raw_steps)
        )
    previous_at = None
    running: dict = {}
    for i, step in enumerate(raw_steps[:MAX_STEPS]):
        p = f"{path}.steps[{i}]"
        if not isinstance(step, dict):
            report.error(p, "type", "Une étape est un objet.", example=EXAMPLE_CASE["steps"][0])
            continue
        entry, previous_at = _case_step(step, i, ids, ctx, check_status, report, p, running, previous_at)
        steps.append(entry)
    return steps


def _case_step(
    step: dict,
    i: int,
    ids: set[str],
    ctx: StudyContext,
    check_status,
    report: Report,
    p: str,
    running: dict,
    previous_at,
) -> tuple[dict, Any]:
    """Une étape : titre, note, changements d'état, statut global, date, annotations, focus, champs étendus.
    Rend l'étape normalisée et la date courante (pour vérifier l'ordre des étapes datées)."""
    from . import extensions as ext

    for extra in sorted(
        set(step) - {"title", "note", "changes", "global", "at", "annotations", "focus", *ext.STEP_EXTRAS}
    ):
        report.warn(f"{p}.{extra}", "unknown_field", f"Champ d'étape « {extra} » inconnu : il est ignoré.")
    step_title = step.get("title")
    if not (_is_str(step_title, 200) and step_title and step_title.strip()):
        report.error(
            f"{p}.title",
            "required",
            "Chaque étape a un titre court.",
            received=step_title,
            example="A démarre",
        )
        step_title = f"Étape {i + 1}"
    note = step.get("note") or ""
    if not _is_str(note):
        report.error(f"{p}.note", "type", "La note d'étape est un texte.", received=type(note).__name__)
        note = ""
    entry = {
        "title": step_title.strip(),
        "note": note,
        "changes": _step_changes(step, ids, check_status, report, p),
    }
    if step.get("global") is not None and check_status(step["global"], f"{p}.global"):
        entry["global"] = step["global"]
    if step.get("at") is not None:
        at = step["at"]
        if isinstance(at, bool) or not isinstance(at, (int, float)):
            report.error(
                f"{p}.at",
                "type",
                "« at » situe l'étape sur l'axe du temps : c'est un nombre (jours, heures… selon l'étude).",
                received=at,
                example=30,
            )
        else:
            if previous_at is not None and at < previous_at:
                report.error(
                    f"{p}.at",
                    "order",
                    "Les étapes datées doivent être dans l'ordre du temps.",
                    received=at,
                    expected=f">= {previous_at}",
                )
            previous_at = at
            entry["at"] = at
    annotations = _step_annotations(step, ids, report, p)
    if annotations:
        entry["annotations"] = annotations
    focus = _step_focus(step, ids, report, p)
    if focus:
        entry["focus"] = focus
    entry.update(ext.normalize_step_extras(step, ids, ctx.ruleset, report, p, running))
    return entry, previous_at


def _step_changes(step: dict, ids: set[str], check_status, report: Report, p: str) -> dict:
    """« changes » : entité -> {status, note}."""
    changes: dict = {}
    raw_changes = step.get("changes") or {}
    if not isinstance(raw_changes, dict):
        report.error(
            f"{p}.changes",
            "type",
            "« changes » associe à chaque entité modifiée son nouveau statut.",
            example={"A": "RUNNING"},
        )
        raw_changes = {}
    for ent_id, change in raw_changes.items():
        cp = f"{p}.changes.{ent_id}"
        if ent_id not in ids:
            report.error(
                cp,
                "unknown_entity",
                f"L'étape modifie une entité inconnue « {ent_id} ».",
                received=ent_id,
                expected=sorted(ids),
            )
            continue
        if isinstance(change, str):
            change = {"status": change}
        if not isinstance(change, dict) or "status" not in change:
            report.error(
                cp,
                "type",
                "Un changement est un statut ou un objet {status, note}.",
                received=change,
                example={"status": "RUNNING", "note": "occupe une place"},
            )
            continue
        if not check_status(change["status"], f"{cp}.status" if "note" in change else cp):
            continue
        entry = {"status": change["status"]}
        if change.get("note"):
            if _is_str(change["note"], 300):
                entry["note"] = change["note"]
            else:
                report.error(
                    f"{cp}.note",
                    "type",
                    "La note d'un changement est un texte de 300 caractères au plus.",
                )
        changes[ent_id] = entry
    return changes


def _step_annotations(step: dict, ids: set[str], report: Report, p: str) -> dict[str, str]:
    """« annotations » : un texte court attaché à des entités pour cette étape."""
    annotations: dict[str, str] = {}
    raw_annotations = step.get("annotations") or {}
    if not isinstance(raw_annotations, dict):
        report.error(
            f"{p}.annotations",
            "type",
            "« annotations » associe un texte court à des entités pour cette étape.",
            example={"B": "attend A"},
        )
        raw_annotations = {}
    for ent_id, text in raw_annotations.items():
        if ent_id not in ids:
            report.error(
                f"{p}.annotations.{ent_id}",
                "unknown_entity",
                f"Entité inconnue « {ent_id} ».",
                received=ent_id,
                expected=sorted(ids),
            )
        elif not (_is_str(text, 120) and text):
            report.error(
                f"{p}.annotations.{ent_id}",
                "type",
                "Une annotation est un texte de 120 caractères au plus.",
                received=text,
            )
        else:
            annotations[ent_id] = text
    return annotations


def _step_focus(step: dict, ids: set[str], report: Report, p: str) -> list[str]:
    """« focus » : les entités que le relecteur doit regarder à cette étape, même si elles ne changent pas."""
    raw_focus = step.get("focus")
    if raw_focus is None:
        return []
    if isinstance(raw_focus, str):
        raw_focus = [raw_focus]
    if not isinstance(raw_focus, list):
        report.error(
            f"{p}.focus",
            "type",
            "« focus » est la liste des entités à regarder à cette étape.",
            received=raw_focus,
            example=["C"],
        )
        raw_focus = []
    if len(raw_focus) > MAX_FOCUS:
        report.error(
            f"{p}.focus",
            "max_items",
            f"{MAX_FOCUS} entités au plus : au-delà, plus rien ne ressort.",
            received=len(raw_focus),
        )
    focus: list[str] = []
    for f_i, ent_id in enumerate(raw_focus[:MAX_FOCUS]):
        if ent_id not in ids:
            report.error(
                f"{p}.focus[{f_i}]",
                "unknown_entity",
                f"Entité inconnue « {ent_id} ».",
                received=ent_id,
                expected=sorted(ids),
            )
        elif ent_id not in focus:
            focus.append(ent_id)
    return focus


def _case_outcome(raw: dict, check_status, report: Report, path: str) -> dict | None:
    """« outcome » : le résultat du cas, {label, status}, ou un simple texte."""
    raw_outcome = raw.get("outcome")
    if raw_outcome is None:
        return None
    if isinstance(raw_outcome, str):
        raw_outcome = {"label": raw_outcome}
    if (
        not isinstance(raw_outcome, dict)
        or not _is_str(raw_outcome.get("label"), 200)
        or not raw_outcome.get("label")
    ):
        report.error(
            f"{path}.outcome",
            "type",
            "« outcome » décrit le résultat du cas : {label, status}.",
            received=raw_outcome,
            example={"label": "Remboursement accordé", "status": "ACCORDE"},
        )
        return None
    outcome = {"label": raw_outcome["label"]}
    if raw_outcome.get("status") is not None and check_status(
        raw_outcome["status"], f"{path}.outcome.status"
    ):
        outcome["status"] = raw_outcome["status"]
    return outcome


def _case_references(raw: dict, report: Report, path: str) -> list[dict]:
    """« references » : {kind, label}, ou un simple texte (source)."""
    references: list[dict] = []
    for i, ref in enumerate(raw.get("references") or []):
        p = f"{path}.references[{i}]"
        if isinstance(ref, str):
            ref = {"kind": "source", "label": ref}
        if not isinstance(ref, dict) or not _is_str(ref.get("label"), 300) or not ref.get("label"):
            report.error(
                p,
                "type",
                "Une référence est {kind, label}.",
                received=ref,
                example={"kind": "test", "label": "test_workflow.py::test_chain"},
            )
            continue
        references.append({"kind": str(ref.get("kind") or "source")[:24], "label": ref["label"]})
    return references


def _case_caution_and_proof(raw: dict, report: Report, path: str) -> tuple[str, str]:
    caution = raw.get("caution") or ""
    if not _is_str(caution, 1000):
        report.error(f"{path}.caution", "type", "« caution » est un texte de 1000 caractères au plus.")
        caution = ""
    proof = raw.get("proof") or "asserted"
    if proof not in PROOF_LEVELS:
        report.error(
            f"{path}.proof",
            "enum",
            "Niveau de preuve déclaré inconnu.",
            received=proof,
            expected=PROOF_LEVELS,
        )
        proof = "asserted"
    return caution, proof


def _warn_never_changing(entities: list[dict], initial: dict, steps: list[dict], report: Report, path: str):
    used = {e for s in steps for e in s["changes"]}
    for ent in entities:
        if ent["id"] not in used and ent["id"] not in initial and len(steps) > 1:
            report.warn(
                f"{path}.entities",
                "never_changes",
                f"L'entité « {ent['id']} » ne change jamais d'état et n'a pas d'état initial explicite.",
                received=ent["id"],
            )


def _case_question(raw: dict, report: Report, path: str) -> str | None:
    """« question » : ce que l'auteur demande au relecteur de vérifier."""
    question = raw.get("question")
    if question is None:
        return None
    if _is_str(question, 300) and question.strip():
        return question.strip()
    if question != "":
        report.error(
            f"{path}.question",
            "type",
            "« question » est ce que vous demandez au relecteur de vérifier : un texte de 300 caractères au "
            "plus.",
            received=question,
            example="C doit-elle attendre la fin de A même avec always_run ?",
        )
    return None


def _case_compare_with(raw: dict, report: Report, path: str) -> list[str]:
    """« compare_with » : clés des cas à comparer à celui-ci."""
    raw_compare = raw.get("compare_with")
    if raw_compare is None:
        return []
    if isinstance(raw_compare, str):
        raw_compare = [raw_compare]
    if not isinstance(raw_compare, list):
        report.error(
            f"{path}.compare_with",
            "type",
            "« compare_with » est la liste des clés des cas à comparer.",
            received=raw_compare,
            example=["always-echec"],
        )
        raw_compare = []
    if len(raw_compare) > MAX_COMPARE:
        report.error(
            f"{path}.compare_with",
            "max_items",
            f"{MAX_COMPARE} cas au plus à comparer.",
            received=len(raw_compare),
        )
    compare: list[str] = []
    for c_i, other in enumerate(raw_compare[:MAX_COMPARE]):
        if not (isinstance(other, str) and KEY_RE.match(other)):
            report.error(
                f"{path}.compare_with[{c_i}]",
                "format",
                "Clé de cas invalide.",
                received=other,
                example="always-echec",
            )
        elif other == raw.get("key"):
            report.error(
                f"{path}.compare_with[{c_i}]",
                "self_reference",
                "Un cas ne se compare pas à lui-même.",
                received=other,
            )
        elif other not in compare:
            compare.append(other)
    return compare


def _find_cycle(ids: set[str], links: list[dict]) -> list[str] | None:
    graph: dict[str, list[str]] = {i: [] for i in ids}
    for link in links:
        graph[link["from"]].append(link["to"])
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for nxt in graph[node]:
            if state.get(nxt) == 1:
                return stack[stack.index(nxt) :] + [nxt]
            if state.get(nxt) is None:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        state[node] = 2
        return None

    for node in sorted(ids):
        if state.get(node) is None:
            found = visit(node)
            if found:
                return found
    return None


def replay(case: dict, statuses: list[dict]) -> list[dict]:
    """Rejoue les changements et renvoie, pour chaque étape, l'état complet de chaque entité."""
    fallback = default_status(statuses)
    state = {
        e["id"]: {"status": case.get("initial", {}).get(e["id"], fallback)} for e in case.get("entities", [])
    }
    frames = []
    current_global = None
    for step in case.get("steps", []):
        changed = []
        new_state = {}
        for ent_id, entry in state.items():
            new_state[ent_id] = {"status": entry["status"]}
        for ent_id, change in step.get("changes", {}).items():
            if ent_id not in new_state:
                continue
            if new_state[ent_id]["status"] != change["status"]:
                changed.append(ent_id)
            new_state[ent_id] = dict(change)
        state = new_state
        if "global" in step:
            current_global = step["global"]
        frames.append(
            {
                "title": step["title"],
                "note": step.get("note", ""),
                "at": step.get("at"),
                "global": current_global,
                "states": state,
                "changed": changed,
                "annotations": step.get("annotations", {}),
                "focus": step.get("focus", []),
            }
        )
    from .extensions import extend_frames

    return extend_frames(case, frames)


def semantic_hash(case: dict) -> str:
    """Empreinte de la partie sémantique : structure, configuration et déroulé.

    Les titres, résumés, notes, libellés, références et caractéristiques mises en avant
    n'y entrent pas : les corriger n'invalide pas les avis déjà rendus.
    """
    material = {
        "kind": case.get("kind"),
        "dimensions": case.get("dimensions", {}),
        "config": case.get("config", {}),
        "entities": [
            {"id": e["id"], "type": e["type"], "group": e.get("group", ""), "attrs": e.get("attrs", {})}
            for e in case.get("entities", [])
        ],
        "links": sorted([l["from"], l["to"], l["type"]] for l in case.get("links", [])),
        "initial": case.get("initial", {}),
        "steps": [
            {
                "changes": {k: v["status"] for k, v in s.get("changes", {}).items()},
                "global": s.get("global"),
                "at": s.get("at"),
            }
            for s in case.get("steps", [])
        ],
        "outcome": (case.get("outcome") or {}).get("status") or (case.get("outcome") or {}).get("label"),
    }
    from .extensions import semantic_extras

    extras = semantic_extras(case)
    if extras:  # absent pour les cas qui n'utilisent aucune extension : leur empreinte ne change pas
        material["extras"] = extras
    if case.get("params") and isinstance(case.get("source"), dict):
        from . import parametric

        material["parametric"] = parametric.semantic_material(case, semantic_hash)
    blob = json.dumps(material, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def presentation_hash(case: dict) -> str:
    blob = json.dumps(case, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def shape_of(case: dict) -> dict:
    """Empreinte de forme d'un cas, utilisée pour recommander des représentations."""
    from .extensions import uses

    entities = case.get("entities", [])
    links = case.get("links", [])
    steps = case.get("steps", [])
    types = sorted({e["type"] for e in entities})
    has_span = any("start" in e.get("attrs", {}) and "end" in e.get("attrs", {}) for e in entities)
    has_point = any("at" in e.get("attrs", {}) for e in entities)
    return {
        "entities": len(entities),
        "links": len(links),
        "steps": len(steps),
        "entity_types": types,
        "groups": sorted({e["group"] for e in entities if e.get("group")}),
        "has_time_attrs": has_span or has_point,
        "dated_steps": sum(1 for s in steps if s.get("at") is not None),
        "has_cycle": bool(_find_cycle({e["id"] for e in entities}, links)),
        "has_outcome": bool(case.get("outcome")),
        "dimensions": len(case.get("dimensions", {})),
        "uses": uses(case),
        "has_self_loop": any(l["from"] == l["to"] for l in links),
    }
