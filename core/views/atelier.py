"""Atelier : construire une situation avec les briques de l'étude et la voir se dérouler d'après ses règles.

La page part vide. La personne pose des briques, les relie, règle leurs options, provoque un évènement ; le
site applique la table de règles que l'étude déclare et redessine le déroulé. Aucun cas déposé n'est montré.

Tout l'état tient dans l'adresse : une situation se partage par son lien et ne laisse rien en base tant qu'un
humain ne l'enregistre pas comme cas. La page est rendue par le serveur et marche sans script ; le script ne
fait que redemander le fragment quand un réglage change.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, parse_qsl, urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe

from .. import families, workshop
from .. import services as svc
from ..casemodel import Report
from ..models import Role, Study
from ..render import status_map
from .commun import _steps_context, actor, legend_of, study_nav, wants_json, web

YES_NO = {"true": "Oui", "false": "Non"}
# Les mots de l'écran, selon la famille d'atelier que l'étude déclare.
WORDS = {
    "linked": {
        "palette": "Briques de l'étude",
        "drop": "Glissez ici une brique de la palette, ou cliquez-la.",
        "placed": "Briques posées",
        "none": "Aucune pour l'instant. Posez-en une : elle apparaît ici avec ses options.",
        "empty": "Posez des briques, reliez-les, réglez leurs options. Le site applique les règles que "
        "l'étude déclare et montre ici ce qui se passe, pas après pas. Aucun cas déposé n'intervient.",
        "counts": "Briques par état final",
        "rules": "règles que l'étude déclare",
        "rules_hint": "Chaque brique suit, à chaque pas, la première règle de cette liste qui lui "
        "correspond.",
        "hint": "Tirez d'une brique à une autre pour les relier. Cliquez un lien pour le retirer.",
        "hint_fine": "Glissez ici une brique de la palette pour l'ajouter ; déposée sur une brique, elle s'y "
        "enchaîne.",
    },
    "periods": {
        "palette": "Sources de l'étude",
        "drop": "Glissez ici une source de la palette, ou cliquez-la : une période se pose.",
        "placed": "Périodes posées",
        "none": "Aucune pour l'instant. Posez-en une : elle apparaît ici avec ses bornes et ses champs.",
        "empty": "Posez des périodes, donnez-leur un début, une fin et des valeurs. Le site les combine "
        "comme l'étude le déclare et montre ici l'historique obtenu. Aucun cas déposé n'intervient.",
        "counts": "Périodes posées par état final",
        "rules": "règles que la déclaration de l'étude revient à poser",
        "rules_hint": "Le site les applique dans cet ordre à chaque pas de l'axe du temps.",
        "hint": "Glissez une période pour la déplacer ; tirez un de ses bords pour changer son début ou sa "
        "fin.",
        "hint_fine": "",
    },
}
END_TEXT = {
    "loop": "La situation revient à un état déjà vu : elle ne se stabilise pas. Le déroulé s'arrête là.",
    "limit": "Le nombre de pas permis est atteint avant que la situation se stabilise.",
}


def _is_switch(choice: dict) -> bool:
    """Une option ou un réglage à deux valeurs, vrai et faux : il se coche."""
    return len(choice["values"]) == 2 and all(isinstance(v, bool) for v in choice["values"])


def _asked(request, decl: dict) -> dict[str, list[str]]:
    """Ce que l'adresse demande, gestes compris : poser, retirer, relier, délier une brique.

    Un formulaire envoyé (« f ») porte toutes les cases : une case absente y vaut « non », alors que dans une
    adresse ordinaire une option absente garde sa valeur par défaut."""
    query = {key: request.GET.getlist(key) for key in request.GET}
    placed = [raw.partition(":") for raw in query.get("e", [])]
    bricks = {b["type"]: b for b in decl["bricks"]}
    if "f" in query:
        for key, _, kind in placed:
            for option in bricks.get(kind, {"options": []})["options"]:
                if _is_switch(option):
                    query[f"o.{key}.{option['key']}"] = [
                        "true" if f"o.{key}.{option['key']}" in query else "false"
                    ]
        for item in decl["settings"]:
            if _is_switch(item):
                query[f"r.{item['key']}"] = ["true" if f"r.{item['key']}" in query else "false"]
    removed = set(query.get("del", []))
    query["e"] = [raw for raw in query.get("e", []) if raw.partition(":")[0] not in removed]
    taken = [raw.partition(":")[0] for raw in query["e"]]
    chained = []
    for kind in query.get("add", []):
        letter = workshop.next_id(taken)
        if kind in bricks and letter:
            chained += families.of(decl).placed(decl, query, letter, kind)
            query["e"].append(f"{letter}:{kind}")
            taken.append(letter)
    links = [
        raw
        for raw in query.get("l", [])
        if raw not in query.get("unlink", []) and not removed & {raw.split(":")[0], raw.split(":")[-1]}
    ]
    query["ev"] = [raw for raw in query.get("ev", []) if raw.partition(":")[0] not in removed]
    for key in [name for name in query if name.startswith(("o.", "n.")) and name.split(".")[1] in removed]:
        del query[key]
    for key in taken:
        side, _, rest = (query.get(f"lk.{key}") or [""])[-1].partition(":")
        kind, _, other = rest.partition(":")
        if side in ("in", "out") and kind and other:
            links.append(f"{other}:{kind}:{key}" if side == "in" else f"{key}:{kind}:{other}")
    query["l"] = links + chained
    return query


def _state(study: Study, sit: dict, step: int | None = None) -> list[tuple[str, str]]:
    query = families.of(study.workshop).to_query(study.workshop, sit)
    return query + ([("etape", str(step + 1))] if step is not None else [])


def _address(study: Study, sit: dict, step: int | None = None) -> str:
    query = _state(study, sit, step)
    base = reverse("study_workshop", args=[study.public_id])
    return f"{base}?{urlencode(query)}" if query else base


def _choice(item: dict, name: str, value) -> dict:
    """Une option ou un réglage, prêt à afficher : une case à cocher, ou une liste de valeurs."""
    return {
        "name": name,
        "label": item["label"],
        "switch": _is_switch(item),
        "on": value is True,
        "values": [
            {
                "value": workshop.text_of(v),
                "label": YES_NO.get(workshop.text_of(v), workshop.text_of(v)) if isinstance(v, bool) else v,
                "selected": workshop.same(v, value),
            }
            for v in item["values"]
        ],
    }


def _link_choices(decl: dict, sit: dict, element: dict, names: dict) -> list[dict]:
    """Ce qu'on peut encore relier à cette brique, rangé par sens de lecture (« dépend de », « précède »)."""
    placed = {(link["from"], link["type"], link["to"]) for link in sit["links"]}
    groups = []
    for link in decl["links"]:
        others = [e for e in sit["elements"] if e["id"] != element["id"]]
        sources = [
            {"value": f"in:{link['type']}:{o['id']}", "label": names[o["id"]]}
            for o in others
            if o["type"] in link["from"]
            and element["type"] in link["to"]
            and (o["id"], link["type"], element["id"]) not in placed
        ]
        targets = [
            {"value": f"out:{link['type']}:{o['id']}", "label": names[o["id"]]}
            for o in others
            if element["type"] in link["from"]
            and o["type"] in link["to"]
            and (element["id"], link["type"], o["id"]) not in placed
        ]
        if link["reverse"] and sources:
            groups.append({"label": link["reverse"], "options": sources})
        if targets:
            groups.append({"label": link["label"], "options": targets})
    return groups


def _links_of(decl: dict, sit: dict, element: dict, names: dict) -> list[dict]:
    """Les liens déjà posés sur cette brique, dits depuis elle."""
    kinds = {link["type"]: link for link in decl["links"]}
    out = []
    for link in sit["links"]:
        kind, value = kinds[link["type"]], f"{link['from']}:{link['type']}:{link['to']}"
        if link["to"] == element["id"] and kind["reverse"]:
            out.append({"text": kind["reverse"], "other": names[link["from"]], "value": value})
        elif link["from"] == element["id"]:
            out.append({"text": kind["label"], "other": names[link["to"]], "value": value})
        elif link["to"] == element["id"]:
            out.append(
                {"text": f"{names[link['from']]} {kind['label']}", "other": "cette brique", "value": value}
            )
    return out


def _cards(study: Study, sit: dict, final: dict, feeds: dict | None = None) -> list[dict]:
    """Une fiche par brique posée : son nom, ses options, ce qu'on y provoque, ses liens, son état final —
    ou, pour une période, les lignes de l'historique qu'elle alimente (`feeds`)."""
    decl, smap = study.workshop, status_map(study.statuses)
    bricks = {b["type"]: b for b in decl["bricks"]}
    names = {e["id"]: e["label"] for e in sit["elements"]}
    cards = []
    for element in sit["elements"]:
        key, brick = element["id"], bricks[element["type"]]
        happened = sit["events"].get(key, [])
        status = smap.get(final.get(key), {})
        cards.append(
            {
                "id": key,
                "feeds": (feeds or {}).get(key),
                "bounds": _bounds(decl, element),
                "kind": element["type"],
                "label": element["label"],
                "placeholder": f"{brick['label']} {key}",
                "brick": brick["label"],
                "options": [
                    _choice(o, f"o.{key}.{o['key']}", element["options"][o["key"]]) for o in brick["options"]
                ],
                "events": [
                    {"value": f"{key}:{e['key']}", "label": e["label"], "on": e["key"] in happened}
                    for e in brick["events"]
                ],
                "links": _links_of(decl, sit, element, names),
                "link_choices": _link_choices(decl, sit, element, names),
                "final": {
                    "key": final.get(key),
                    "label": status.get("label", ""),
                    "role": status.get("role"),
                },
            }
        )
    return cards


def _bounds(decl: dict, element: dict) -> dict | None:
    """Le début et la fin d'une période, pour les familles qui en ont."""
    if "start" not in element:
        return None
    axis = decl["axis"]
    return {
        "start": "" if element["start"] is None else workshop.text_of(element["start"]),
        "end": "" if element["end"] is None else workshop.text_of(element["end"]),
        "min": workshop.text_of(axis["min"]),
        "max": workshop.text_of(axis["max"]),
        "step": workshop.text_of(axis["step"]),
        "grain": workshop.text_of(axis.get("grain", axis["step"])),
        "axis": axis["label"],
    }


def _palette(decl: dict, sit: dict) -> dict:
    full = workshop.next_id([e["id"] for e in sit["elements"]]) is None
    return {
        "bricks": [{"type": b["type"], "label": b["label"]} for b in decl["bricks"]],
        "full": full,
        "max": workshop.MAX_ELEMENTS,
        "settings": [_choice(s, f"r.{s['key']}", sit["settings"][s["key"]]) for s in decl["settings"]],
        # Ce que le script doit savoir pour tirer un lien sur le schéma ; le serveur revérifie tout.
        "links": json.dumps(
            [
                {"type": k["type"], "label": k["label"], "from": k["from"], "to": k["to"]}
                for k in decl["links"]
            ],
            ensure_ascii=False,
        ),
    }


def _drawn(request, study: Study, content: dict, step: int) -> dict:
    """Le schéma et le déroulé de la situation, dessinés par la représentation de l'étude."""
    rep = svc.current_representation(request.user, study)
    plan = families.of(study.workshop).plan(study.workshop)
    html, summary, frames = svc.render_content(
        study, content, svc.resolved_spec(rep), step=step, handles=True, span=plan.get("span")
    )
    smap = status_map(study.statuses)
    return {
        "rep": rep,
        "rep_html": mark_safe(html),
        "drew": any(any(view.get("drawn", {}).values()) for view in summary.get("views", [])),
        **_steps_context(content, frames, study.statuses, smap, step),
        "legend": legend_of(frames, study.statuses),
    }


def _result(study: Study, run: dict) -> dict:
    """Le résultat d'ensemble, et le compte des briques par état final."""
    smap = status_map(study.statuses)
    counts: dict[str, int] = {}
    for status in run["final"].values():
        counts[status] = counts.get(status, 0) + 1
    outcome = run["outcome"] or {}
    status = smap.get(outcome.get("status"), {}).get("label", "")  # tu quand le libellé le dit déjà
    return {
        "label": outcome.get("label", ""),
        "role": smap.get(outcome.get("status"), {}).get("role", ""),
        "status": status if status.lower() not in outcome.get("label", "").lower() else "",
        "counts": [
            {
                "n": n,
                "label": smap.get(key, {}).get("label", key),
                "role": smap.get(key, {}).get("role", "neutral"),
            }
            for key, n in sorted(
                counts.items(), key=lambda kv: [s["key"] for s in study.statuses].index(kv[0])
            )
        ],
        "end": END_TEXT.get(run["end"], ""),
        "steps": len(run["steps"]) - 1,
        **_history(study, run["extra"]),
    }


def _history_row(image: dict, smap: dict) -> dict:
    """Une ligne de l'historique, avec de quoi dire d'où elle vient et la comparer à celle d'avant."""
    start, end = workshop.text_of(image["start"]), workshop.text_of(image["end"])
    values = ["" if v is None else workshop.text_of(v) for v in image["fields"].values()]
    status = smap.get(image["status"], {}).get("label", image["status"] or "")
    rules = image["rules"]
    said = " et ".join(filter(None, [", ".join(rules[:-1]), rules[-1]]))
    return {
        "id": image["id"],
        "start": start,
        "end": end,
        "values": values,
        "status": status,
        "role": smap.get(image["status"], {}).get("role", "neutral"),
        "sources": " ".join(image["sources"]),
        "rules": " ".join(rules),
        "why": f"{image['why']} Règle{'s' if len(rules) > 1 else ''} {said}.",
        # Ce qui fait qu'une ligne est « la même » d'un geste à l'autre, et ce qu'on en dit si elle disparaît.
        "sig": "|".join([end, *values, status]),
        "text": " · ".join([f"du {start} au {end}", *(v or "vide" for v in values), status]),
    }


def _history(study: Study, extra: dict) -> dict:
    """Pour un atelier de périodes : l'historique obtenu, ligne par ligne, et ce qui bloque le traitement."""
    if "images" not in extra:
        return {}
    smap = status_map(study.statuses)
    return {
        "history": {
            "axis": study.workshop["axis"]["label"],
            "fields": [f["label"] for f in study.workshop["image"]["fields"]],
            "rows": [_history_row(image, smap) for image in extra["images"]],
        },
        "blocking": extra["blocking"],
    }


def _feeds(decl: dict, extra: dict, final: dict) -> dict | None:
    """Pour un atelier de périodes, ce que chaque période posée devient dans l'historique : les lignes qu'elle
    alimente, sinon pourquoi elle n'en alimente aucune (invalide, ignorée). None pour une autre famille."""
    if "images" not in extra:
        return None
    lines: dict[str, list[str]] = {}
    for image in extra["images"]:
        for key in image["sources"]:
            span = f"du {workshop.text_of(image['start'])} au {workshop.text_of(image['end'])}"
            lines.setdefault(key, []).append(span)
    apart = (decl["states"]["invalid"], decl["states"]["ignored"])
    return {
        key: {"lines": lines.get(key, []), "apart": status in apart and key not in lines}
        for key, status in final.items()
    }


def _rules(decl: dict, run: dict | None) -> list[dict]:
    used = {c["rule"] for step in (run["steps"] if run else []) for c in step["changes"]}
    used |= set(run["used"] if run else [])
    return [{"key": r["key"], "title": r["title"], "used": r["key"] in used} for r in decl["rules"]]


def _save(request, study: Study):
    """Le seul geste qui laisse une trace : enregistrer la situation comme cas. Il est réservé aux humains ;
    la situation est relue depuis son adresse et recalculée ici, jamais reprise du navigateur."""
    etat = request.POST.get("etat", "")
    query = {key: values for key, values in parse_qs(etat).items() if key != "f"}
    family = families.of(study.workshop)
    sit = family.situation(study.workshop, family.from_query(study.workshop, query), Report())
    key = svc.save_built_case(actor(request), study, sit, request.POST.get("title", ""))
    messages.success(request, "La situation est enregistrée comme cas : il attend un avis.")
    return redirect(reverse("workspace", args=[study.public_id]) + "?" + urlencode({"cas": key}))


def _step_asked(request, last: int) -> tuple[int, bool]:
    """Le pas demandé par l'adresse (« etape=2 »), sinon le dernier : on arrive sur le résultat."""
    try:
        wanted = int(request.GET.get("etape", "")) - 1
    except ValueError:
        return last, False
    return max(0, min(wanted, last)), True


@login_required
@web
def study_workshop(request, sid: str):
    study = svc.get_study(actor(request), sid, Role.VIEWER)
    context = {**study_nav(study, "workshop"), "nav": "studies"}
    decl = svc.workshop_of(study)
    if decl is None:
        return render(request, "core/workshop.html", {**context, "declared": False})
    if request.method == "POST":
        return _save(request, study)
    asked = _asked(request, decl)
    family = families.of(decl)
    sit = family.situation(decl, family.from_query(decl, asked), Report())
    run = svc.workshop_run(study, sit) if sit["elements"] else None
    last = len(run["steps"]) - 1 if run else 0
    step, chosen = _step_asked(request, last)
    kept = step if chosen and run else None
    final = run["final"] if run else {}
    if parse_qsl(request.META.get("QUERY_STRING", ""), keep_blank_values=True) != _state(study, sit, kept):
        # L'adresse ne garde que la situation : un geste (poser, relier) n'y reste pas.
        return redirect(_address(study, sit, kept))
    context.update(
        declared=True,
        title=decl["title"],
        palette=_palette(decl, sit),
        cards=_cards(study, sit, final, _feeds(decl, run["extra"], final) if run else None),
        hidden=[(name, value) for name, value in family.to_query(decl, sit) if name in ("e", "l")],
        words=WORDS[families.name_of(decl)],
        rules=_rules(decl, run),
        state_qs=urlencode(family.to_query(decl, sit)),
        reset_url=reverse("study_workshop", args=[study.public_id]),
        steps_urls=[_address(study, sit, n) for n in range(last + 1)] if run else [],
        prev_url=_address(study, sit, max(step - 1, 0)),
        next_url=_address(study, sit, min(step + 1, last)),
        step=step,
    )
    if run:
        context["result"] = _result(study, run)
        if run["content"]:
            context["shown"] = _drawn(request, study, run["content"], step)
    template = "core/_workshop.html" if wants_json(request) else "core/workshop.html"
    return render(request, template, context)
