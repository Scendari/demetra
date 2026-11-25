"""Conversion du catalogue d'exemple (sources/catalogue) vers le format de cas de Demetra.

Le fichier catalogue_lancelot.json est l'extraction fidèle des données du prototype
(sources/catalogue/catalogue-runs-data.js), produite par scripts/dump_catalogue.mjs.
Rien n'est inventé ici : chaque champ du prototype est rangé dans le modèle générique.
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURE = Path(__file__).parent / "catalogue_lancelot.json"

STATUSES = [
    {
        "key": "WAITING",
        "label": "WAITING",
        "short": "WAIT",
        "role": "waiting",
        "default": True,
        "description": "En attente de ses prérequis ou d'une place.",
    },
    {
        "key": "RUNNING",
        "label": "RUNNING",
        "short": "RUN",
        "role": "active",
        "description": "En cours d'exécution.",
    },
    {
        "key": "RUNNING_KO",
        "label": "RUNNING_KO",
        "short": "RUN_KO",
        "role": "active",
        "description": "Encore en cours, alors qu'une erreur est déjà enregistrée.",
    },
    {
        "key": "FINISHED_OK",
        "label": "FINISHED_OK",
        "short": "OK",
        "role": "success",
        "description": "Terminé avec succès.",
    },
    {
        "key": "FINISHED_KO",
        "label": "FINISHED_KO",
        "short": "KO",
        "role": "error",
        "description": "Terminé en échec.",
    },
    {
        "key": "KO_IGNORED",
        "label": "KO_IGNORED",
        "short": "KO_IGN",
        "role": "warning",
        "description": "En échec, mais l'erreur est ignorée : la suite peut partir.",
    },
    {
        "key": "WARNING",
        "label": "WARNING",
        "short": "WARN",
        "role": "warning",
        "description": "Terminé avec avertissement.",
    },
    {
        "key": "BLOCKED",
        "label": "BLOCKED",
        "short": "BLOCK",
        "role": "blocked",
        "description": "Ne pourra pas démarrer : un prérequis a échoué.",
    },
    {
        "key": "DEACTIVATED",
        "label": "DEACTIVATED",
        "short": "DEACT",
        "role": "disabled",
        "description": "Désactivé.",
    },
    {
        "key": "DEACTIVATED_PG",
        "label": "DEACTIVATED_PG",
        "short": "DEACT_PG",
        "role": "disabled",
        "description": "Désactivé par propagation.",
    },
    {"key": "ABORTED", "label": "ABORTED", "short": "ABORT", "role": "error", "description": "Interrompu."},
    {
        "key": "NON_DEMARRE",
        "label": "NON_DÉMARRÉ",
        "short": "NON_DÉM.",
        "role": "neutral",
        "description": "Le Workflow n'a pas démarré (cas de configuration).",
    },
    {
        "key": "CONTROLE_KO",
        "label": "CONTRÔLE_KO",
        "short": "CTRL_KO",
        "role": "error",
        "description": "La configuration est refusée au contrôle : rien ne s'exécute.",
    },
]

# Atelier : les règles d'ordonnancement des Tasks, déclarées dans le vocabulaire fermé du site. Elles viennent
# du catalogue : chaque règle cite le comportement que ses scénarios décrivent. Ce que le vocabulaire ne dit
# pas reste hors de l'atelier : le nombre de places d'exécution, les actions d'une Task sur une autre, un
# blocage prononcé avant la fin d'une Task déjà en erreur.
_DONE = ["FINISHED_OK", "WARNING", "KO_IGNORED", "FINISHED_KO", "BLOCKED", "DEACTIVATED"]
_PASSED = ["FINISHED_OK", "WARNING", "KO_IGNORED"]
WORKSHOP = {
    "title": "Composer un Workflow",
    "bricks": [
        {
            "type": "task",
            "label": "Task",
            "options": [
                {"key": "active", "label": "Active", "values": [True, False]},
                {"key": "always_run", "label": "Toujours exécutée", "values": [False, True]},
                {"key": "ignore_on_error", "label": "Erreur ignorée", "values": [False, True]},
            ],
            "events": [
                {"key": "echec", "label": "Échoue"},
                {"key": "avertissement", "label": "Termine avec un avertissement"},
            ],
        }
    ],
    "links": [{"type": "prerequisite", "label": "précède", "reverse": "dépend de"}],
    "settings": [
        {"key": "stop_on_error", "label": "Arrêt sur erreur (stop_on_error)", "values": [False, True]}
    ],
    "rules": [
        {
            "key": "T1",
            "title": "Une Task inactive est désactivée et ne s'exécute pas",
            "when": {"status": "WAITING", "option": {"active": False}},
            "then": "DEACTIVATED",
        },
        {
            "key": "T2",
            "title": "Une Task est désactivée quand un de ses prérequis, direct ou indirect, l'est",
            "when": {
                "status": ["WAITING", "BLOCKED"],
                "option": {"always_run": False},
                "upstream": {"any": {"status": "DEACTIVATED"}},
            },
            "then": "DEACTIVATED",
        },
        {
            "key": "T3",
            "title": "Une Task toujours exécutée démarre quand tous ses prérequis, même indirects, ont fini",
            "when": {
                "status": "WAITING",
                "option": {"always_run": True},
                "upstream": {"all": {"status": _DONE}},
            },
            "then": "RUNNING",
        },
        {
            "key": "T4",
            "title": "Avec l'arrêt sur erreur, un échec bloque les Tasks ordinaires encore en attente",
            "when": {
                "status": "WAITING",
                "option": {"always_run": False},
                "setting": {"stop_on_error": True},
                "elements": {"any": {"status": "FINISHED_KO"}},
            },
            "then": "BLOCKED",
        },
        {
            "key": "T5",
            "title": "Une Task est bloquée quand un de ses prérequis, direct ou indirect, a échoué",
            "when": {
                "status": "WAITING",
                "option": {"always_run": False},
                "upstream": {"any": {"status": "FINISHED_KO"}},
            },
            "then": "BLOCKED",
        },
        {
            "key": "T6",
            "title": "Une Task démarre quand tous ses prérequis ont réussi",
            "when": {
                "status": "WAITING",
                "option": {"always_run": False},
                "incoming": {"all": {"status": _PASSED}},
            },
            "then": "RUNNING",
        },
        {
            "key": "T7",
            "title": "Une Task qui échoue reste en cours le temps d'enregistrer son erreur",
            "when": {"status": "RUNNING", "event": "echec"},
            "then": "RUNNING_KO",
        },
        {
            "key": "T8",
            "title": "Une erreur ignorée termine la Task en KO_IGNORED",
            "when": {"status": "RUNNING_KO", "option": {"ignore_on_error": True}},
            "then": "KO_IGNORED",
        },
        {
            "key": "T9",
            "title": "Une Task en erreur termine en échec",
            "when": {"status": "RUNNING_KO"},
            "then": "FINISHED_KO",
        },
        {
            "key": "T10",
            "title": "Une Task peut terminer avec un avertissement",
            "when": {"status": "RUNNING", "event": "avertissement"},
            "then": "WARNING",
        },
        {
            "key": "T11",
            "title": "Une Task en cours termine avec succès",
            "when": {"status": "RUNNING"},
            "then": "FINISHED_OK",
        },
    ],
    "outcome": [
        {
            "when": {"elements": {"any": {"status": "FINISHED_KO"}}},
            "label": "Workflow FINISHED_KO",
            "status": "FINISHED_KO",
        },
        {
            "when": {"elements": {"any": {"status": "WARNING"}}},
            "label": "Workflow WARNING",
            "status": "WARNING",
        },
        {"label": "Workflow FINISHED_OK", "status": "FINISHED_OK"},
    ],
}

# Statuts d'ensemble du prototype dont la clé n'est pas en ASCII : on garde le libellé, on normalise la clé.
GLOBAL_KEYS = {"NON_DÉMARRÉ": "NON_DEMARRE", "CONTRÔLE_KO": "CONTROLE_KO"}

DECISIONS = {"WAIT": "décision : attendre", "LAUNCH": "décision : lancer", "BLOCK": "décision : bloquer"}
PROBABILITY = {1: "très rare", 2: "faible", 3: "commun"}
SCOPE_VALUES = {"workflow": "Workflow", "task": "Task", "iteration": "Itération", "step": "Step"}


def load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _has_cycle(edges: list[list[str]]) -> bool:
    graph: dict[str, list[str]] = {}
    for src, dst in edges:
        graph.setdefault(src, []).append(dst)
    state: dict[str, int] = {}

    def visit(node) -> bool:
        state[node] = 1
        for nxt in graph.get(node, []):
            if state.get(nxt) == 1 or (state.get(nxt) is None and visit(nxt)):
                return True
        state[node] = 2
        return False

    return any(state.get(n) is None and visit(n) for n in list(graph))


def study_definition(data: dict) -> dict:
    rules = [
        {
            "key": key,
            "title": function,
            "text": f"Comportement porté par « {function} » dans le moteur d'exécution.",
            "source": f"{file} · ligne {line}",
        }
        for key, (file, function, line) in data["sources"].items()
    ]
    return {
        "title": data["title"],
        "description": (
            f"Catalogue importé du prototype (version {data['version']}) : tous les cas d'exécution d'un "
            "moteur de workflows, "
            "famille par famille, avec leur déroulé étape par étape."
        ),
        "kind": "workflow",
        "statuses": STATUSES,
        "dimensions": [
            {
                "key": "portee",
                "label": "Niveau concerné",
                "values": [{"value": k, "label": v} for k, v in data["scopes"].items()],
            },
            # L'option dont dépendent presque tous les cas : sa valeur reste sous les yeux du relecteur, sur
            # chaque cas.
            {
                "key": "arret_sur_erreur",
                "label": "Arrêt sur erreur (stop_on_error)",
                "values": ["non", "oui"],
                "highlight": True,
            },
            {
                "key": "mode",
                "label": "Nature du cas",
                "values": ["parcours", "état ciblé", "configuration", "observation réelle"],
            },
            {"key": "niveau", "label": "Complexité", "values": ["simple", "composé", "limite", "avancé"]},
        ],
        "rules": rules,
        "exclusions": [],
        "workshop": WORKSHOP,
        # Options des Tasks, définies d'après le catalogue d'origine (repères de lecture et légende des
        # statuts).
        "attributes": [
            {
                "key": "always_run",
                "label": "Toujours exécutée",
                "text": "La Task attend la fin de tous ses prérequis, directs et indirects, puis peut "
                "démarrer même si l'un d'eux a échoué.",
            },
            {
                "key": "ignore_on_error",
                "label": "Erreur ignorée",
                "text": "Si la Task échoue, son erreur est ignorée (KO_IGNORED) : ses dépendantes peuvent "
                "démarrer et le Workflow n'est pas mis en KO.",
            },
            {
                "key": "active",
                "label": "Active",
                "text": "Une Task inactive est désactivée par configuration (DEACTIVATED). Valeur par défaut "
                ": active.",
            },
            {
                "key": "missing",
                "label": "Absente de settings.yml",
                "text": "La Task n'est pas déclarée dans settings.yml.",
            },
            {"key": "context", "label": "Contexte", "text": "Le contexte d'une Itération ou d'un Step."},
        ],
    }


def _catalogue_entities(nodes: list[dict]) -> list[dict]:
    entities = []
    for node in nodes:
        attrs = {
            "always_run": node["always_run"],
            "ignore_on_error": node["ignore_on_error"],
            "active": node["active"],
        }
        if node.get("missing"):
            attrs["missing"] = True
        if node.get("context"):
            attrs["context"] = node["context"]
        entities.append({"id": node["id"], "label": node["name"], "type": node["kind"], "attrs": attrs})
    return entities


def _catalogue_links(raw: dict, ids: set[str], cyclic: bool) -> list[dict]:
    links = [
        {
            "from": a,
            "to": b,
            "type": "declared_dependency" if cyclic else "prerequisite",
            "label": "dépendance déclarée" if cyclic else "",
        }
        for a, b in raw["edges"]
        if a in ids and b in ids
    ]
    links += [
        {"from": a, "to": b, "type": "action", "label": "agit sur"}
        for a, b in raw["actions"]
        if a in ids and b in ids
    ]
    return links


def _catalogue_step(frame: dict, ids: set[str], previous: dict) -> dict:
    """Une étape du catalogue : changements d'état depuis l'étape précédente, annotations, entité à
    regarder."""
    changes, annotations = {}, {}
    for ent_id, state in frame["states"].items():
        if ent_id not in ids:
            continue
        if state["status"] != previous.get(ent_id):
            changes[ent_id] = state["status"]
            previous[ent_id] = state["status"]
        notes = []
        if (frame.get("decisions") or {}).get(ent_id):
            notes.append(DECISIONS.get(frame["decisions"][ent_id], frame["decisions"][ent_id]))
        if state.get("causes"):
            notes.append("cause : " + ", ".join(state["causes"]))
        if state.get("reserved"):
            notes.append("place réservée")
        if state.get("launched"):
            notes.append("lancé")
        if state.get("threadPending"):
            notes.append("thread en attente")
        if notes:
            annotations[ent_id] = " · ".join(notes)[:120]
    step = {
        "title": frame["title"],
        "note": frame.get("note", ""),
        "changes": changes,
        "global": GLOBAL_KEYS.get(frame["workflow"], frame["workflow"]),
    }
    if annotations:
        step["annotations"] = annotations
    # La Task sur laquelle le moteur prend une décision à cette étape (attendre, lancer…) est celle à
    # regarder.
    decided = [ent_id for ent_id in (frame.get("decisions") or {}) if ent_id in ids][:3]
    if decided:
        step["focus"] = decided
    return step


def _catalogue_references(raw: dict, sources: dict) -> list[dict]:
    references = [{"kind": "test", "label": t} for t in raw.get("tests", [])]
    references += [
        {"kind": "tnr", "label": f"{t['kind']} · {t['id']}" if isinstance(t, dict) else t}
        for t in raw.get("tnr", [])
    ]
    for key in raw.get("sources", []):
        if key in sources:
            file, function, line = sources[key]
            references.append({"kind": "source", "label": f"{file} · {function} · ligne {line}"})
    return references


def convert_case(raw: dict, sources: dict, order: int) -> dict:
    nodes = raw["nodes"]
    ids = {n["id"] for n in nodes}
    entities = _catalogue_entities(nodes)
    # Les options qui s'écartent du défaut changent le déroulé : on les garde sous les yeux, sur la tâche
    # concernée.
    unusual = {"always_run": True, "ignore_on_error": True, "active": False}
    highlights = [
        {"entity": e["id"], "attr": k} for e in entities for k, v in unusual.items() if e["attrs"].get(k) is v
    ][:4]
    previous = {n["id"]: "WAITING" for n in nodes}
    steps = [_catalogue_step(frame, ids, previous) for frame in raw["frames"]]
    tags = [f"probabilité : {PROBABILITY[raw['probability']]}"]
    if raw.get("proposal"):
        tags.append("proposition d'évolution")
    last = GLOBAL_KEYS.get(raw["frames"][-1]["workflow"], raw["frames"][-1]["workflow"])
    last_label = raw["frames"][-1]["workflow"]
    return {
        "key": raw["id"],
        "number": order,
        "label": raw["displayNumber"],
        "family": raw["family"],
        "title": raw["title"],
        "summary": raw["summary"],
        "kind": "workflow",
        "rules": [k for k in raw.get("sources", []) if k in sources],
        "dimensions": {
            "portee": raw["scope"],
            "arret_sur_erreur": "oui" if raw["stop_on_error"] else "non",
            "mode": raw["mode"],
            "niveau": raw["level"],
        },
        "tags": tags,
        "config": {"capacity": raw["capacity"]},
        **({"highlights": highlights} if highlights else {}),
        "entities": entities,
        "links": _catalogue_links(raw, ids, _has_cycle(raw["edges"])),
        "steps": steps,
        "outcome": {"label": f"Workflow {last_label}", "status": last},
        "references": _catalogue_references(raw, sources),
        "caution": raw.get("caution", ""),
        "proof": "observed"
        if raw.get("tests") or raw.get("tnr") or raw["mode"] == "observation réelle"
        else "asserted",
    }


def cases(data: dict | None = None) -> list[dict]:
    data = data or load()
    return [convert_case(raw, data["sources"], order) for order, raw in enumerate(data["cases"], start=1)]
