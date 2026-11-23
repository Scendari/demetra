"""Présélection déterministe des représentations adaptées à une étude.

Le site calcule la forme des cas (taille, liens, temps, dimensions, groupes) et la
confronte à la fiche de chaque représentation. L'IA peut ensuite reclasser et
expliquer, mais part d'une liste sûre ; le produit reste utilisable sans elle.
"""

from __future__ import annotations

from collections import Counter

from .casemodel import shape_of
from .models import Representation, Study


def study_shape(study: Study) -> dict:
    shapes, kinds = [], Counter()
    for case in study.cases.filter(retired_at__isnull=True).only("content"):
        shapes.append(shape_of(case.content))
        kinds[case.content.get("kind", "workflow")] += 1
    n = len(shapes)
    ruleset, lifecycles = study.ruleset or {}, study.lifecycles or []
    declared = {
        "dimensions": len(study.dimensions),
        "banded_dimensions": sum(1 for d in study.dimensions if d.get("bands")),
        "rule_rows": len(ruleset.get("rows", [])), "rule_conditions": len(ruleset.get("conditions", [])),
        "lifecycle_states": max((len(c["states"]) for c in lifecycles), default=0),
        "lifecycle_transitions": max((len(c["transitions"]) for c in lifecycles), default=0),
    }
    if not n:
        return {"cases": 0, "kinds": {}, "main_kind": study.kind if study.kind != "mixed" else None, "max_entities": 0, "max_steps": 0,
                "with_links": 0, "with_time": 0, "with_dated_steps": 0, "with_groups": 0, "with_outcome": 0,
                "with_values": 0, "with_fields": 0, "with_messages": 0, "with_rule_rows": 0, "with_measures": 0, "with_lifecycle": 0, **declared}
    cycle_types = {c["type"] for c in lifecycles}
    return {
        **declared,
        "with_values": sum(1 for s in shapes if s["uses"]["values"]),
        "with_fields": sum(1 for s in shapes if s["uses"]["fields"]),
        "with_messages": sum(1 for s in shapes if s["uses"]["messages"]),
        "with_rule_rows": sum(1 for s in shapes if s["uses"]["rules"]),
        "with_measures": sum(1 for s in shapes if s["uses"]["measures"]),
        "with_lifecycle": sum(1 for s in shapes if cycle_types & set(s["entity_types"])),
        "cases": n,
        "kinds": dict(kinds),
        "main_kind": kinds.most_common(1)[0][0],
        "max_entities": max(s["entities"] for s in shapes),
        "max_steps": max(s["steps"] for s in shapes),
        "with_links": sum(1 for s in shapes if s["links"]),
        "with_time": sum(1 for s in shapes if s["has_time_attrs"]),
        "with_dated_steps": sum(1 for s in shapes if s["dated_steps"]),
        "with_groups": sum(1 for s in shapes if len(s["groups"]) >= 2),
        "with_outcome": sum(1 for s in shapes if s["has_outcome"]),
    }


# Ce qu'une représentation du catalogue élargi demande aux cas : (compteur de forme, ce qui convient, ce qui manque)
_NEEDS = {
    "values": ("with_values", "{k} cas sur {n} portent des lignes de calcul : chaque opération a sa ligne.",
               "Les cas ne portent pas de lignes de calcul (steps[].values)."),
    "fields": ("with_fields", "{k} cas sur {n} portent des champs : on voit ce qui change, champ par champ.",
               "Les cas ne portent pas de champs (entities[].fields, steps[].fields)."),
    "messages": ("with_messages", "{k} cas sur {n} portent des messages entre acteurs : la séquence les met dans l'ordre.",
                 "Les cas ne portent pas de messages (steps[].messages)."),
    "ruleset": ("with_rule_rows", "L'étude déclare un jeu de règles et {k} cas sur {n} disent le sort de ses lignes.",
                "Il faut un jeu de règles sur l'étude (ruleset) et le sort des lignes dans les cas (steps[].rows)."),
    "lifecycle": ("with_lifecycle", "L'étude déclare un cycle de vie et {k} cas sur {n} suivent une entité de ce type.",
                  "L'étude ne déclare pas de cycle de vie (lifecycles) pour les entités de ses cas."),
    "bands": ("with_measures", "Une dimension est découpée en tranches et {k} cas sur {n} portent une mesure : les seuils se voient.",
              "Il faut une dimension à tranches (bands) et une mesure par cas (measures)."),
}


def _extended(manifest: dict, shape: dict, n: int) -> tuple[int, list[str], list[str]]:
    """Points apportés par les besoins et préférences du catalogue élargi."""
    score, pros, cons = 0, [], []
    need = manifest.get("needs")
    if need == "two_dimensions":
        if shape["dimensions"] == 2 and shape["with_outcome"] / n >= 0.5:
            score += 50
            pros.append("L'étude croise exactement deux dimensions et ses cas ont un résultat : la matrice les montre toutes d'un regard.")
        elif shape["dimensions"] > 2:
            score -= 25
            cons.append(f"L'étude a {shape['dimensions']} dimensions : une matrice n'en croise que deux, ses cases mélangeraient des cas différents.")
        else:
            score -= 60
            cons.append("Une matrice croise deux dimensions et demande un résultat par cas.")
    elif need in _NEEDS:
        counter, good, bad = _NEEDS[need]
        declared = {"ruleset": shape["rule_rows"], "lifecycle": shape["lifecycle_states"], "bands": shape["banded_dimensions"]}.get(need, 1)
        if declared and shape[counter] / n >= 0.5:
            score += 50
            pros.append(good.format(k=shape[counter], n=shape["cases"]))
        else:
            score -= 60
            cons.append(bad)
            return score, pros, cons
    prefers = manifest.get("prefers")
    if prefers == "small_ruleset":
        if shape["rule_rows"] <= 8 and shape["rule_conditions"] <= 3:
            score += 8
            pros.append(f"Jeu de règles court ({shape['rule_rows']} lignes, {shape['rule_conditions']} conditions) : il se lit comme une suite de questions.")
        else:
            score -= 15
            cons.append(f"{shape['rule_rows']} lignes et {shape['rule_conditions']} conditions : l'arbre deviendrait touffu, la table de règles se lit mieux.")
    elif prefers in ("dense_lifecycle", "sparse_lifecycle"):
        dense = shape["lifecycle_transitions"] > 2 * shape["lifecycle_states"]
        if dense == (prefers == "dense_lifecycle"):
            score += 8
            pros.append("Beaucoup de transitions par état : une table montre aussi tout ce qui n'est pas permis." if dense
                        else "Peu de transitions par état : le dessin du cycle reste lisible, boucles et retours compris.")
        else:
            score -= 8
            cons.append("Peu de transitions : le diagramme d'états suffit et se lit plus vite." if not dense
                        else f"{shape['lifecycle_transitions']} transitions pour {shape['lifecycle_states']} états : les flèches se croiseraient, la table d'états se lit mieux.")
    return score, pros, cons


def _score(rep: Representation, shape: dict) -> tuple[int, list[str], list[str]]:
    """Note sur 100, raisons favorables, réserves."""
    manifest = rep.manifest or {}
    n = shape["cases"] or 1
    score, pros, cons = 40, [], []
    families = manifest.get("families") or []
    kind = shape["main_kind"]
    labels = {"workflow": "workflows et états", "decision": "règles de décision", "temporal": "règles temporelles"}
    if kind and families:
        if kind in families:
            score += 25
            pros.append(f"Conçue pour les {labels[kind]}, famille dominante de cette étude.")
        else:
            score -= 15
            cons.append(f"Pensée pour d'autres familles que les {labels[kind]}.")
    if manifest.get("needs_time"):
        share = shape["with_time"] / n
        if share >= 0.5:
            score += 30
            pros.append(f"{shape['with_time']} cas sur {shape['cases']} portent des périodes ou des échéances datées.")
        else:
            score -= 60
            cons.append("Les cas ne portent pas de données de temps (attrs.start/end ou attrs.at).")
    if manifest.get("needs_dimensions"):
        if shape["dimensions"]:
            score += 20
            pros.append(f"L'étude déclare {shape['dimensions']} dimension(s) : la table peut comparer les combinaisons.")
        else:
            score -= 40
            cons.append("L'étude ne déclare aucune dimension : la table n'aurait pas de colonnes de conditions.")
    if manifest.get("needs_groups"):
        share = shape["with_groups"] / n
        if share >= 0.5:
            score += 25
            pros.append("Les entités sont rangées en plusieurs groupes : les couloirs les séparent.")
        else:
            score -= 45
            cons.append("Les entités n'ont pas de groupe (champ group) : il n'y aurait qu'un couloir.")
    layouts = {v["layout"]["brick"] for v in (rep.spec or {}).get("views", []) if isinstance(v, dict) and isinstance(v.get("layout"), dict)}
    uses_graph = bool(layouts & {"layout.layers", "layout.lanes"})
    if uses_graph:
        share = shape["with_links"] / n
        if share >= 0.5:
            score += 15
            pros.append("La plupart des cas ont des liens entre entités : un graphe les montre.")
        elif shape["cases"]:
            score -= 30
            cons.append("Peu de cas ont des liens entre entités : un graphe n'apporterait rien.")
    max_entities = manifest.get("max_entities")
    if max_entities and shape["max_entities"] > max_entities:
        score -= 25
        cons.append(f"Le plus gros cas a {shape['max_entities']} entités ; cette représentation reste lisible jusqu'à {max_entities}.")
    max_steps = manifest.get("max_steps")
    if max_steps and shape["max_steps"] > max_steps:
        score -= 20
        cons.append(f"Certains cas ont {shape['max_steps']} étapes ; au-delà de {max_steps}, les vignettes deviennent petites.")
    extra, extra_pros, extra_cons = _extended(manifest, shape, n)
    score += extra
    pros += extra_pros
    cons += extra_cons
    if rep.slug == "table-trace":
        if shape["max_entities"] > 12 or shape["max_steps"] > 6:
            score += 20
            pros.append("Cas volumineux : la trace reste lisible quand un graphe ne l'est plus.")
        else:
            pros.append("Fonctionne pour toutes les familles ; montre tout le déroulé d'un regard.")
    return score, pros, cons


def recommend(study: Study, candidates=None, limit: int = 4) -> dict:
    shape = study_shape(study)
    if candidates is None:
        candidates = Representation.objects.filter(scope=Representation.Scope.SYSTEM, archived_at__isnull=True)
    scored = []
    for rep in candidates:
        if rep.scope != Representation.Scope.SYSTEM and not rep.manifest:
            continue
        raw, pros, cons = _score(rep, shape)
        score = max(0, min(100, raw))   # la note affichée est bornée ; le classement garde l'écart réel
        scored.append({"id": rep.public_id, "slug": rep.slug, "name": rep.name, "description": rep.description, "score": score, "_raw": raw,
                       "reasons": pros, "reservations": cons, "shows_time": (rep.manifest or {}).get("shows_time", ""),
                       "limits": (rep.manifest or {}).get("limits", "")})
    scored.sort(key=lambda r: (-r["_raw"], r["name"]))
    for row in scored:
        del row["_raw"]
    recommended = [r for r in scored if r["score"] >= 50][:limit]
    if not recommended and scored:
        recommended = scored[:1]
    rest = [r for r in scored if r not in recommended]
    return {"shape": shape, "recommended": recommended, "others": rest,
            "note": "Présélection calculée par le site à partir de la forme des cas. C'est l'utilisateur qui choisit, dans l'interface."}
