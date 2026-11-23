"""Rendu des représentations élargies : matrice croisée, calcul, axe à bandes, avant/après,
table de règles, arbre de décision, table d'états, diagramme d'états, diagramme de séquence.

Mêmes principes que core/render.py : tout ce qui peut apparaître à une étape quelconque est
dessiné une fois pour toutes, à sa place ; d'une étape à l'autre, seuls des classes, des statuts
et des textes changent. Le schéma ne bouge donc jamais.

  data-cls='[…]'      classes par étape (data-cls-on : celles de l'étape rendue)
"""

from __future__ import annotations

import json
from html import escape

from . import extensions as ext
from .bricks import with_defaults
from .render import (
    RADIUS,
    Context,
    _fit,
    _fmt_number,
    _matches,
    _node_shape_path,
    _order_ranks,
    _ranks,
    _state_attrs,
    _status_svg,
    _text_width,
    entity_flag_items,
    fill_template,
    flag_classes,
)

RULE_ROLES = {"selected": "success", "discarded": "warning", "failed": "disabled", "none": "waiting"}
OP_SIGNS = {"=": "", "+": "+", "-": "−", "×": "×", "÷": "÷", "%": "", "min": "plafond", "max": "plancher", "arrondi": "≈"}
NBSP, THIN = " ", " "


def pseudo_statuses() -> dict:
    """Statuts internes (sort d'une ligne de règle) : ils passent par le même mécanisme que ceux de l'étude."""
    return {f"~{k}": {"label": ext.RULE_RESULTS[k], "short": ext.RULE_RESULTS[k], "role": RULE_ROLES[k]} for k in RULE_ROLES}


def amount(value, unit: str = "") -> str:
    """Nombre écrit à la française : espace fine des milliers, virgule décimale, unité insécable."""
    if isinstance(value, float) and not value.is_integer():
        text = f"{value:,.2f}" if abs(value * 100 - round(value * 100)) < 1e-6 else f"{value:,.4f}".rstrip("0")
    else:
        text = f"{int(value):,}"
    text = text.replace(",", THIN).replace(".", ",").replace("-", "−")
    return f"{text}{NBSP}{unit}" if unit else text


def _attr_json(value) -> str:
    return escape(json.dumps(value, ensure_ascii=False, separators=(",", ":")), quote=True)


def dyn_cls(per_step: list[str], ctx: Context, fixed: int | None) -> tuple[str, str]:
    """Classes de l'étape rendue et attributs qui portent celles des autres étapes."""
    if not per_step:
        return "", ""
    step = ctx.step if fixed is None else fixed
    now = per_step[min(step, len(per_step) - 1)]
    if fixed is not None or len(set(per_step)) <= 1:
        return now, ""
    return now, f" data-cls='{_attr_json(per_step)}' data-cls-on=\"{now}\""


def pill(ctx: Context, key: str, mode: str = "full") -> str:
    role, label = ctx.role(key), ctx.label(key, "full")
    return (f'<span class="st" data-role="{role}" title="{escape(label, quote=True)}"><svg class="st-ic" width="14" height="14" aria-hidden="true">'
            f'<use href="#ic-{role}"/></svg><span class="st-tx">{escape(ctx.label(key, mode))}</span></span>')


def pill_series(ctx: Context, keys: list[str], fixed: int | None) -> str:
    """Pastille dont le statut change d'une étape à l'autre ; la case réserve la place du libellé le plus long."""
    step = ctx.step if fixed is None else fixed
    key = keys[min(step, len(keys) - 1)] if keys else ""
    if fixed is not None or len(set(keys)) <= 1:
        return pill(ctx, key)
    role, label = ctx.role(key), ctx.label(key, "full")
    main = (f'<span class="st" data-role="{role}" data-status="{escape(key, quote=True)}" data-st="{escape("|".join(keys), quote=True)}" title="{escape(label, quote=True)}">'
            f'<svg class="st-ic" width="14" height="14" aria-hidden="true"><use data-si="" href="#ic-{role}"/></svg><span class="st-tx" data-sl="full">{escape(label)}</span></span>')
    sizers = "".join(f'<span class="st tx-size" aria-hidden="true"><svg class="st-ic" width="14" height="14"></svg><span class="st-tx">{escape(ctx.label(k, "full"))}</span></span>'
                     for k in dict.fromkeys(keys))
    return f'<span class="tx-stack">{main}{sizers}</span>'


def _fixed_step(ctx: Context, time: dict) -> int | None:
    if time["brick"] == "time.static":
        return 0 if time.get("step") == "first" else max(0, ctx.n_steps - 1)
    return None


def _canvas(view: dict, svg: str, fallback: str) -> str:
    label = escape(view.get("title") or fallback, quote=True)
    return f'<div class="rep-canvas rep-scroll" tabindex="0" role="region" aria-label="{label} — défilement possible">{svg}</div>'


def _svg(view: dict, width: float, height: float, body: str, cls: str, fallback: str, time: dict | None = None) -> str:
    hl = " tm-highlight" if (time or {}).get("highlight_changes", True) else ""
    label = escape(view.get("title") or fallback, quote=True)
    return (f'<svg class="rep-svg {cls}{hl}" style="--w:{width:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" height="{height:.0f}" '
            f'role="group" aria-label="{label}">{body}</svg>')


def _wrap2(text: str, max_width: float, size: float) -> list[str]:
    """Coupe un libellé en deux lignes au plus, sur une espace."""
    if _text_width(text, size, True) <= max_width or " " not in text:
        return [text]
    words = text.split(" ")
    best = min(range(1, len(words)), key=lambda i: max(len(" ".join(words[:i])), len(" ".join(words[i:]))))
    return [" ".join(words[:best]), " ".join(words[best:])]


def _empty(sv: dict, message: str, hint: str) -> str:
    sv["warnings"].append(hint)
    return f'<p class="rep-empty">{escape(message)}</p>'


def _case_number(sib: dict) -> str:
    return sib.get("label") or f"{sib['number']:02d}"


def _dim_label(dim: dict, value) -> str:
    return next((v["label"] for v in dim["values"] if v["value"] == value), str(value))


def lifecycle_for(ctx: Context, wanted: str) -> tuple[dict | None, dict | None]:
    """Cycle de vie et entité suivie : l'entité demandée, sinon la première dont le type en déclare un."""
    by_type = {c["type"]: c for c in ctx.lifecycles or []}
    entities = ctx.case.get("entities", [])
    if wanted and wanted != "auto":
        ent = next((e for e in entities if e["id"] == wanted), None)
        return (by_type.get(ent["type"]), ent) if ent else (None, None)
    for ent in entities:
        if ent["type"] in by_type:
            return by_type[ent["type"]], ent
    return None, None


def _state_series(ctx: Context, ent: dict) -> tuple[str, list[str], list[tuple[str, str] | None]]:
    """État de départ, état après chaque étape, et transition empruntée à chaque étape (ou None)."""
    start = ctx.initial_status(ent["id"])
    series = ctx.series(ent["id"])
    taken, previous = [], start
    steps = ctx.case.get("steps", [])
    for i, status in enumerate(series):
        # Une étape qui redonne à l'entité le statut qu'elle a déjà emprunte une boucle sur soi.
        stated = i < len(steps) and ent["id"] in steps[i].get("changes", {})
        taken.append((previous, status) if status != previous or stated else None)
        previous = status
    return start, series, taken


# ---------------------------------------------------------------------------
# Grilles : calcul, champs, règles, états
# ---------------------------------------------------------------------------

def grid_rows(ctx: Context, view: dict, layout: dict, marks: list[dict], fixed: int | None, sv: dict, th, cell_class) -> dict:
    kind = layout["rows"]
    out = {"head": [], "body": [], "cls": f" grid-{kind}", "before": ""}
    if kind == "values":
        _grid_values(ctx, marks, fixed, sv, th, cell_class, out)
    elif kind == "fields":
        _grid_fields(ctx, layout, marks, fixed, sv, th, cell_class, out)
    elif kind == "rules":
        _grid_rules(ctx, marks, fixed, sv, th, cell_class, out)
    else:
        _grid_states(ctx, layout, marks, fixed, sv, th, cell_class, out)
    if out["body"]:
        sv["drawn"] = {"rows": len(out["body"]), "columns": len(out["head"])}
    return out


def _grid_values(ctx, marks, fixed, sv, th, cell_class, out):
    lines = [(i, v) for i, frame in enumerate(ctx.frames) for v in frame.get("values", [])]
    if not lines:
        sv["warnings"].append("Ce cas ne porte aucune ligne de calcul (steps[].values).")
        return
    for mark in marks:
        if mark["brick"] == "mark.cell":
            out["head"].append(th(mark["header"], cls=cell_class(mark)))
        elif mark["brick"] == "mark.value":
            out["head"].append(th(mark["header"], cls="al-end col-num"))
    for i, v in lines:
        unit = v.get("unit", "")
        values = {"label": v["label"], "op": v["op"], "operation": ext.OP_LABELS[v["op"]], "note": v.get("note", ""), "unit": unit, "step": i + 1}
        cells = []
        for mark in marks:
            if mark["brick"] == "mark.cell":
                tag = "th" if mark.get("weight") == "strong" and not any(c.startswith("<th") for c in cells) else "td"
                scope = ' scope="row"' if tag == "th" else ""
                cells.append(f'<{tag}{scope} class="{cell_class(mark)}">{escape(fill_template(mark["text"], values))}</{tag}>')
            elif mark["brick"] == "mark.value":
                if mark["show"] == "result":
                    number = v.get("result", v["value"] if v["op"] == "=" else None)
                    text = amount(number, unit) if number is not None else ""
                    cells.append(f'<td class="al-end col-num col-total">{escape(text)}</td>')
                else:
                    text = amount(v["value"], "%" if v["op"] == "%" else unit)
                    sign = OP_SIGNS[v["op"]] if mark["signed"] else ""
                    sign_html = f'<span class="val-op" title="{escape(ext.OP_LABELS[v["op"]], quote=True)}">{escape(sign)}</span>{NBSP}' if sign else ""
                    cells.append(f'<td class="al-end col-num">{sign_html}{escape(text)}</td>')
        per_step = ["is-future" if s < i else "" for s in range(ctx.n_steps)]
        now, dyn = dyn_cls(per_step, ctx, fixed)
        current = " is-current" if fixed is None and i == ctx.step else ""
        step_attr = f' data-step-is="{i}"' if fixed is None else ""
        out["body"].append(f'<tr class="row-step row-val {now}{current}"{step_attr}{dyn}>{"".join(cells)}</tr>')
    last = next((v for _, v in reversed(lines) if "result" in v or v["op"] == "="), None)
    if last:
        sv["notes"].append(f"Résultat du calcul : {amount(last.get('result', last['value']), last.get('unit', ''))} (ligne « {last['label']} »).")
    sv["notes"].append("Lignes : " + " ; ".join(
        f"{i + 1}. {v['label']} {OP_SIGNS[v['op']]} {amount(v['value'], '%' if v['op'] == '%' else v.get('unit', ''))}"
        + (f" → {amount(v['result'], v.get('unit', ''))}" if "result" in v else "") for i, v in lines[:24]) + ".")


def _fmt_field(value) -> str:
    return "—" if value is None or value == "" else _fmt_number(value)


def _grid_fields(ctx, layout, marks, fixed, sv, th, cell_class, out):
    rows = []
    for ent in ctx.case.get("entities", []):
        if not _matches(layout.get("where"), ent):
            continue
        names = list(ent.get("fields") or {})
        for frame in ctx.frames:
            for name in (frame.get("fields") or {}).get(ent["id"], {}):
                if name not in names:
                    names.append(name)
        rows.extend((ent, name) for name in names)
    if not rows:
        sv["warnings"].append("Ce cas ne porte aucun champ (entities[].fields, steps[].fields).")
        return
    for mark in marks:
        out["head"].append(th(mark["header"], cls=cell_class(mark) if mark["brick"] == "mark.cell" else "col-field"))
    changed_names = []
    for ent, name in rows:
        initial = (ent.get("fields") or {}).get(name)
        series = [(frame.get("fields") or {}).get(ent["id"], {}).get(name) for frame in ctx.frames]
        changed = "".join("1" if [ent["id"], name] in (frame.get("fields_changed") or []) else "0" for frame in ctx.frames)
        if series and series[-1] != initial:
            changed_names.append(f"{ent['label'] or ent['id']}.{name} : {_fmt_field(initial)} → {_fmt_field(series[-1])}")
        values = {"entity": ent["id"], "entity_label": ent["label"] or ent["id"], "field": name}
        cells = []
        for mark in marks:
            if mark["brick"] == "mark.cell":
                tag = "th" if mark.get("weight") == "strong" else "td"
                scope = ' scope="row"' if tag == "th" else ""
                cells.append(f'<{tag}{scope} class="{cell_class(mark)}">{escape(fill_template(mark["text"], values))}</{tag}>')
                continue
            at = mark["at"]
            tag_html = '<span class="fd-tag">modifié</span>' if mark["mark_changes"] and at != "initial" else ""
            if at == "initial":
                cells.append(f'<td class="col-field">{escape(_fmt_field(initial))}</td>')
            elif at == "final" or fixed is not None:
                value = series[-1 if at == "final" else fixed] if series else initial
                diff = " is-diff" if mark["mark_changes"] and value != initial else ""
                cells.append(f'<td class="col-field{diff}"><span class="fd-val">{escape(_fmt_field(value))}</span>{tag_html}</td>')
            else:
                texts = [_fmt_field(v) for v in series]
                per_step = ["is-diff" if mark["mark_changes"] and v != initial else "" for v in series]
                now, dyn = dyn_cls(per_step, ctx, None)
                current = texts[ctx.step] if texts else ""
                sizers = "".join(f'<span class="tx-size" aria-hidden="true">{escape(t)}</span>' for t in dict.fromkeys(texts))
                cells.append(f'<td class="col-field {now}"{dyn}><span class="tx-stack fd-val"><span data-tx=\'{_attr_json(texts)}\' data-tx-target="">{escape(current)}</span>{sizers}</span>{tag_html}</td>')
        is_changed = " is-changed" if fixed is None and changed and changed[ctx.step] == "1" else ""
        dyn_row = f' data-ch="{changed}"' if fixed is None else ""
        out["body"].append(f'<tr class="row-field{is_changed}"{dyn_row}>{"".join(cells)}</tr>')
    sv["notes"].append(("Champs modifiés à la fin du cas : " + " ; ".join(changed_names[:16]) + ".") if changed_names else "Aucun champ n'est modifié par ce cas.")


def case_value(ctx: Context, key: str) -> str | None:
    """Valeur du cas pour une condition : dans ses dimensions (libellé), sinon dans sa configuration."""
    dims = ctx.case.get("dimensions") or {}
    if key in dims:
        dim = next((d for d in ctx.dimensions if d["key"] == key), None)
        return _dim_label(dim, dims[key]) if dim else str(dims[key])
    config = ctx.case.get("config") or {}
    if key in config:
        return _fmt_number(config[key])
    return None


def case_candidates(ctx: Context, key: str) -> set[str]:
    """Écritures possibles de la valeur du cas pour une condition : la valeur déclarée et son libellé."""
    out = set()
    dims = ctx.case.get("dimensions") or {}
    if key in dims:
        out.add(str(dims[key]))
    label = case_value(ctx, key)
    if label is not None:
        out.add(label)
    return out


def _grid_rules(ctx, marks, fixed, sv, th, cell_class, out):
    ruleset = ctx.ruleset or {}
    rows, conditions = ruleset.get("rows", []), ruleset.get("conditions", [])
    if not rows:
        sv["warnings"].append("L'étude ne déclare pas de jeu de règles (champ « ruleset » de l'étude).")
        return
    frames = ctx.frames
    for mark in marks:
        if mark["brick"] == "mark.cell":
            out["head"].append(th(mark["header"], cls=cell_class(mark)))
        elif mark["brick"] == "mark.rule_result":
            out["head"].append(th(mark["header"], cls="col-result"))
        else:
            for cond in conditions:
                value = case_value(ctx, cond["key"]) if mark["case_values"] else None
                chip = f'<span class="cond-case"><span class="cond-case-k">Ce cas</span> {escape(value)}</span>' if value is not None else ""
                out["head"].append(f'<th scope="col" class="col-cond">{escape(cond["label"])}{chip}</th>')
    final = {}
    for n, row in enumerate(rows):
        series = [(f.get("rules") or {}).get(row["key"], {}).get("result", "none") for f in frames]
        final[row["key"]] = series[-1] if series else "none"
        cells = []
        for mark in marks:
            if mark["brick"] == "mark.cell":
                tag = "th" if mark is marks[0] else "td"
                scope = ' scope="row"' if tag == "th" else ""
                cells.append(f'<{tag}{scope} class="{cell_class(mark)}">{escape(fill_template(mark["text"], {"key": row["key"], "then": row["then"], "n": n + 1}))}</{tag}>')
            elif mark["brick"] == "mark.rule_result":
                cells.append(f'<td class="col-result">{pill_series(ctx, [f"~{r}" for r in series], fixed)}</td>')
            else:
                for cond in conditions:
                    expected = row["when"].get(cond["key"])
                    miss = ["is-miss" if (f.get("rules") or {}).get(row["key"], {}).get("on") == cond["key"] else "" for f in frames]
                    now, dyn = dyn_cls(miss, ctx, fixed)
                    marker = ('<span class="rl-miss"><svg class="st-ic" width="14" height="14" aria-hidden="true"><use href="#ic-error"/></svg>'
                              '<span class="rl-miss-tx">diffère</span></span>') if any(miss) else ""
                    text = escape(expected) if expected is not None else '<span aria-hidden="true">—</span><span class="sr-only">indifférent</span>'
                    cells.append(f'<td class="col-cond {now}"{dyn}><span class="rl-exp">{text}</span>{marker}</td>')
        examined = [("is-" + s) + (" is-now" if row["key"] in (f.get("rules_examined") or []) else "") for s, f in zip(series, frames, strict=True)]
        now, dyn = dyn_cls(examined, ctx, fixed)
        out["body"].append(f'<tr class="row-rule {now}"{dyn}>{"".join(cells)}</tr>')
    policy = ruleset.get("policy", "unique")
    out["before"] = f'<p class="rep-note"><span class="rep-note-k">Résolution</span> {escape(ext.POLICIES[policy])}.</p>'
    names = {"selected": "retenue", "discarded": "écartée", "failed": "ne correspond pas"}
    listed = [f"{key} {names[result]}" for key, result in final.items() if result != "none"]
    sv["notes"].append(f"Politique de résolution : {ext.POLICIES[policy]}.")
    sv["notes"].append(("Sort des lignes pour ce cas : " + ", ".join(listed) + ".") if listed else "Ce cas ne dit le sort d'aucune ligne (steps[].rows).")
    untouched = [key for key, result in final.items() if result == "none"]
    if untouched and listed:
        sv["notes"].append("Lignes non examinées : " + ", ".join(untouched) + ".")


def _grid_states(ctx, layout, marks, fixed, sv, th, cell_class, out):
    cycle, ent = lifecycle_for(ctx, layout.get("entity", "auto"))
    if not cycle:
        sv["warnings"].append("Aucune entité de ce cas n'a de cycle de vie déclaré (champ « lifecycles » de l'étude, par type d'entité).")
        return
    events = list(dict.fromkeys(t["label"] for t in cycle["transitions"]))
    _, series, taken = _state_series(ctx, ent)
    for mark in marks:
        if mark["brick"] == "mark.cell":
            out["head"].append(th(mark["header"], cls=cell_class(mark)))
        else:
            out["head"].extend(th(event, cls="col-event") for event in events)
    order = list(ctx.statuses)
    for state in sorted(cycle["states"], key=lambda s: order.index(s) if s in order else len(order)):
        cells = []
        for mark in marks:
            if mark["brick"] == "mark.cell":
                if mark["content"] == "status":
                    start = '<span class="sd-start">départ</span>' if state == cycle["initial"] else ""
                    cells.append(f'<th scope="row" class="{cell_class(mark)} col-state">{pill(ctx, state)}{start}</th>')
                else:
                    cells.append(f'<td class="{cell_class(mark)}">{escape(fill_template(mark["text"], {"state": ctx.label(state), "key": state}))}</td>')
                continue
            for event in events:
                target = next((t for t in cycle["transitions"] if t["from"] == state and t["label"] == event), None)
                per_step = ["is-taken" if target and move == (state, target["to"]) else "" for move in taken]
                now, dyn = dyn_cls(per_step, ctx, fixed)
                inner = pill(ctx, target["to"]) if target else f'<span aria-hidden="true">{escape(mark["empty"])}</span><span class="sr-only">non permis</span>'
                guard = f'<span class="ev-guard">si {escape(target["guard"])}</span>' if target and target.get("guard") else ""
                cells.append(f'<td class="col-event{"" if target else " is-none"} {now}"{dyn}>{inner}{guard}</td>')
        now, dyn = dyn_cls(["is-here" if s == state else "" for s in series], ctx, fixed)
        out["body"].append(f'<tr class="row-state {now}"{dyn}>{"".join(cells)}</tr>')
    sv["notes"].append(f"Entité suivie : {ent['label'] or ent['id']} ; parcours : " + " → ".join(ctx.label(s) for s in _path(ctx, ent)) + ".")
    holes = sum(1 for s in cycle["states"] for e in events if not any(t["from"] == s and t["label"] == e for t in cycle["transitions"]))
    sv["notes"].append(f"{len(cycle['states'])} états, {len(events)} évènements ; {holes} case(s) vide(s) : évènement non permis depuis cet état.")


def _path(ctx: Context, ent: dict) -> list[str]:
    start, series, _ = _state_series(ctx, ent)
    out = [start]
    for status in series:
        if status != out[-1]:
            out.append(status)
    return out


# ---------------------------------------------------------------------------
# Matrice croisée
# ---------------------------------------------------------------------------

def render_matrix(ctx: Context, view: dict, sv: dict) -> str:
    layout = with_defaults(view["layout"])
    mark = with_defaults(next(m for m in view["marks"] if m["brick"] == "mark.tally"))
    dims = {d["key"]: d for d in ctx.dimensions}
    keys = list(dims)
    row_key = layout["rows"] if layout["rows"] != "auto" else (keys[0] if keys else None)
    col_key = layout["columns"] if layout["columns"] != "auto" else next((k for k in keys if k != row_key), None)
    if row_key not in dims or col_key not in dims:
        return _empty(sv, "La matrice croise deux dimensions de l'étude : il en manque au moins une.",
                      f"La matrice demande deux dimensions déclarées dans l'étude ; reçu lignes = {row_key}, colonnes = {col_key} ; dimensions de l'étude : {', '.join(keys) or 'aucune'}.")
    rows, cols = dims[row_key], dims[col_key]
    scope = layout["cases_scope"]
    siblings = [s for s in ctx.siblings if scope == "study" or s["family"] == ctx.case.get("family")]
    cells: dict[tuple, list[dict]] = {}
    for sib in siblings:
        cells.setdefault((sib["dimensions"].get(row_key), sib["dimensions"].get(col_key)), []).append(sib)
    mine = ctx.case.get("dimensions") or {}
    this = (mine.get(row_key), mine.get(col_key))
    head = (f'<tr><th scope="col" rowspan="2" class="mx-corner">{escape(rows["label"])}</th>'
            f'<th scope="colgroup" colspan="{len(cols["values"])}" class="mx-coldim">{escape(cols["label"])}</th></tr><tr>'
            + "".join(f'<th scope="col" class="mx-col{" is-this-col" if v["value"] == this[1] else ""}">{escape(v["label"])}</th>' for v in cols["values"]) + "</tr>")
    body, empty = [], 0
    for rv in rows["values"]:
        tds = []
        for cv in cols["values"]:
            group = cells.get((rv["value"], cv["value"]), [])
            is_this = (rv["value"], cv["value"]) == this
            if not group:
                empty += 1
                tds.append('<td class="mx-cell is-none"><span class="mx-none">Aucun cas</span></td>')
                continue
            if mark["show"] == "count":
                inner = f'<span class="mx-count">{len(group)}</span> cas'
                numbers = group
                inner += _numbers(ctx, numbers) if mark["list_cases"] else ""
            else:
                by_outcome: dict[tuple, list[dict]] = {}
                for sib in group:
                    by_outcome.setdefault((sib.get("outcome") or "", sib.get("outcome_status") or ""), []).append(sib)
                parts = []
                for (label, status), members in by_outcome.items():
                    shown = pill(ctx, status) if status else f'<b class="mx-text">{escape(label or "Sans résultat déclaré")}</b>'
                    if status and label and label != ctx.label(status):
                        shown += f'<span class="mx-label">{escape(label)}</span>'
                    parts.append(f'<div class="mx-out">{shown}{_numbers(ctx, members) if mark["list_cases"] else ""}</div>')
                inner = "".join(parts)
            current = ' aria-current="true"' if is_this else ""
            tag = '<span class="mx-here">Cas affiché</span>' if is_this else ""
            tds.append(f'<td class="mx-cell{" is-this-case" if is_this else ""}{" is-mixed" if mark["show"] == "outcome" and len(by_outcome) > 1 else ""}"{current}>{tag}{inner}</td>')
        row_cls = ' class="is-this-row"' if rv["value"] == this[0] else ""
        body.append(f'<tr{row_cls}><th scope="row" class="mx-row">{escape(rv["label"])}</th>{"".join(tds)}</tr>')
    sv["drawn"] = {"rows": len(rows["values"]), "columns": len(cols["values"])}
    if this[0] is not None and this[1] is not None:
        sv["notes"].append(f"Cas affiché : ligne « {_dim_label(rows, this[0])} », colonne « {_dim_label(cols, this[1])} ».")
    else:
        sv["warnings"].append("Le cas affiché ne porte pas les deux dimensions croisées : aucune case n'est mise en avant.")
    sv["notes"].append(f"{len(rows['values']) * len(cols['values']) - empty} combinaison(s) couvertes sur {len(rows['values']) * len(cols['values'])} ; {empty} sans cas.")
    if len(dims) > 2:
        sv["warnings"].append(f"L'étude déclare {len(dims)} dimensions : une case peut regrouper des cas qui diffèrent sur les autres.")
    caption = escape(view.get("title") or "Matrice croisée")
    return (f'<div class="rep-scroll" tabindex="0" role="region" aria-label="{escape(view.get("title") or "Matrice croisée", quote=True)} — défilement possible">'
            f'<table class="rep-grid rep-matrix"><caption class="sr-only">{caption} : {escape(rows["label"])} en lignes, {escape(cols["label"])} en colonnes</caption>'
            f'<thead>{head}</thead><tbody>{"".join(body)}</tbody></table></div>')


def _numbers(ctx: Context, members: list[dict]) -> str:
    key = ctx.case.get("key")
    items = ", ".join(f'<b class="mx-me">{escape(_case_number(s))}</b>' if s["key"] == key else escape(_case_number(s)) for s in members[:12])
    more = f" +{len(members) - 12}" if len(members) > 12 else ""
    return f'<span class="mx-cases"><span class="mx-cases-k">n°</span> {items}{more}</span>'


# ---------------------------------------------------------------------------
# Axe à bandes
# ---------------------------------------------------------------------------

def render_scale(ctx: Context, view: dict, sv: dict) -> str:
    layout = with_defaults(view["layout"])
    band_mark = with_defaults(next(m for m in view["marks"] if m["brick"] == "mark.band"))
    point_mark = next((with_defaults(m) for m in view["marks"] if m["brick"] == "mark.point"), None)
    banded = [d for d in ctx.dimensions if d.get("bands")]
    dim = next((d for d in banded if layout["dimension"] in ("auto", d["key"])), None)
    if not dim:
        return _empty(sv, "Aucune dimension de cette étude ne déclare de tranches.",
                      "L'axe à bandes demande une dimension avec « bands » (PATCH /studies/{id}) ; dimensions à tranches : " + (", ".join(d["key"] for d in banded) or "aucune") + ".")
    bands, unit = dim["bands"], dim.get("unit", "")
    n = len(bands)
    key = ctx.case.get("key")
    measure = (ctx.case.get("measures") or {}).get(dim["key"])
    points: dict[float, list[dict]] = {}
    if point_mark:
        if point_mark["others"]:
            for sib in ctx.siblings:
                x = (sib.get("measures") or {}).get(dim["key"])
                if x is not None and sib["key"] != key:
                    points.setdefault(x, []).append(sib)
        if measure is not None:
            points.setdefault(measure, []).insert(0, {"key": key, "me": True})

    # Échelle : chaque tranche a la même largeur ; à l'intérieur, les positions sont proportionnelles puis écartées pour rester lisibles.
    finite = sorted({b[k] for b in bands for k in ("from", "to") if k in b})
    spans = sorted(b["to"] - b["from"] for b in bands if "from" in b and "to" in b)
    typical = spans[len(spans) // 2] if spans else (abs(finite[0]) or 1)
    low = bands[0].get("from")
    if low is None:
        low = min([finite[0] - typical] + [p - typical * 0.2 for p in points if p < finite[0]])
    high = bands[-1].get("to")
    if high is None:
        high = max([finite[-1] + typical] + [p + typical * 0.2 for p in points if p > finite[-1]])
    edges = [low] + [b["to"] for b in bands[:-1]] + [high]
    bw = max(150.0, min(236.0, 780 / n))
    pad, gutter = 26.0, 26.0
    width = pad * 2 + n * bw

    def band_of(x: float) -> int:
        index = ext.band_index(dim, x)
        return index if index is not None else (0 if x < edges[0] else n - 1)

    placed: dict[float, float] = {}
    gap = 46.0
    for i in range(n):
        left, right = pad + i * bw, pad + (i + 1) * bw
        inside = sorted(p for p in points if band_of(p) == i and p not in (edges[i], edges[i + 1]))
        step = min(gap, bw / (len(inside) + 1))
        xs = [left + (p - edges[i]) / (edges[i + 1] - edges[i]) * bw for p in inside]
        # Une borne qui porte elle-même un point demande un écart entier ; sinon un demi suffit.
        room_left = step if edges[i] in points else step * 0.5
        room_right = step if edges[i + 1] in points else step * 0.5
        for k in range(len(xs)):
            xs[k] = max(xs[k], left + room_left if k == 0 else xs[k - 1] + step)
        for k in reversed(range(len(xs))):
            xs[k] = min(xs[k], right - room_right if k == len(xs) - 1 else xs[k + 1] - step)
        placed.update(dict(zip(inside, xs, strict=True)))
    for p in points:
        if p not in placed:
            placed[p] = pad + next((i for i, e in enumerate(edges) if e == p), 0) * bw

    # Étiquettes des points : étagées pour ne pas se recouvrir
    labels, levels = [], []
    for p in sorted(points):
        members = points[p]
        mine = any(m.get("me") for m in members)
        others = [m for m in members if not m.get("me")]
        text = amount(p, unit)
        sub = ("Ce cas" + (f" · n° {', '.join(_case_number(m) for m in others[:4])}" if others else "")) if mine else "n° " + ", ".join(_case_number(m) for m in others[:5])
        w = max(_text_width(text, 12, True), _text_width(sub, 10.5, mine)) + 12
        x0 = max(4.0, min(width - w - 4, placed[p] - w / 2))
        level = next((lv for lv, end in enumerate(levels) if x0 >= end + 6), len(levels))
        if level == len(levels):
            levels.append(0.0)
        levels[level] = x0 + w
        labels.append({"p": p, "x": placed[p], "x0": x0, "w": w, "level": level, "text": text, "sub": sub, "mine": mine})
    # La tige d'une étiquette placée plus haut ne doit pas traverser une étiquette placée plus bas : celle-ci se décale.
    for low in labels:
        for other in labels:
            if other["level"] > low["level"] and low["x0"] - 3 < other["x"] < low["x0"] + low["w"] + 3:
                if other["x"] > low["x"]:
                    low["x0"] = min(low["x0"], max(low["x"] - low["w"] + 8, other["x"] - 4 - low["w"]))
                else:
                    low["x0"] = max(low["x0"], min(low["x"] - 8, other["x"] + 4))
    label_h = 34.0
    top = 12.0 + max(1, len(levels)) * label_h if points else 14.0
    lines_in = 1 + int(band_mark["show_range"]) + int(band_mark["show_result"] and any(b.get("result") for b in bands))
    band_h = 20.0 + lines_in * 18
    my_band = band_of(measure) if measure is not None else next((i for i, b in enumerate(bands) if b["value"] == (ctx.case.get("dimensions") or {}).get(dim["key"])), None)

    parts = []
    for i, band in enumerate(bands):
        x = pad + i * bw
        this = " is-this" if i == my_band else ""
        y = top + 18
        inner = f'<rect class="sc-rect" x="{x:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{band_h:.1f}"/>'
        label = _fit(_dim_label(dim, band["value"]), bw - 16, 12.5, True, sv)
        inner += f'<text class="sc-name" x="{x + bw / 2:.1f}" y="{y:.1f}" text-anchor="middle">{escape(label)}</text>'
        if band_mark["show_range"]:
            y += 18
            inner += f'<text class="sc-range" x="{x + bw / 2:.1f}" y="{y:.1f}" text-anchor="middle">{escape(_fit(ext.band_text(dim, band), bw - 12, 10.5, False, sv))}</text>'
        if band_mark["show_result"] and band.get("result"):
            y += 18
            inner += f'<text class="sc-result" x="{x + bw / 2:.1f}" y="{y:.1f}" text-anchor="middle">{escape(_fit("→ " + band["result"], bw - 12, 12, True, sv))}</text>'
        if this:
            inner += f'<rect class="sc-ring" x="{x + 1.5:.1f}" y="{top + 1.5:.1f}" width="{bw - 3:.1f}" height="{band_h - 3:.1f}"/>'
        parts.append(f'<g class="sc-band sc-b{i % 2}{this}">{inner}</g>')
    upper = dim.get("inclusive") == "to"
    base = top + band_h
    for i in range(1, n):
        x = pad + i * bw
        hint = "← inclus" if upper else "inclus →"
        parts.append(f'<g class="sc-edge"><line x1="{x:.1f}" y1="{top - 4:.1f}" x2="{x:.1f}" y2="{base + 6:.1f}"/>'
                     f'<text class="sc-tick" x="{x:.1f}" y="{base + 20:.1f}" text-anchor="middle">{escape(amount(edges[i], unit))}</text>'
                     f'<text class="sc-incl" x="{x:.1f}" y="{base + 34:.1f}" text-anchor="middle">{hint}</text></g>')
    for name, x, anchor in (("from", pad, "start"), ("to", pad + n * bw, "end")):
        bound = bands[0 if name == "from" else -1].get(name)
        text = amount(bound, unit) if bound is not None else ("au-delà →" if name == "to" else "← en deçà")
        parts.append(f'<text class="sc-tick{" sc-open" if bound is None else ""}" x="{x:.1f}" y="{base + 20:.1f}" text-anchor="{anchor}">{escape(text)}</text>')
    for item in labels:
        y0 = 10.0 + (max(1, len(levels)) - 1 - item["level"]) * label_h
        cls = "sc-pt is-me" if item["mine"] else "sc-pt"
        marker = (f'<path class="sc-mark" d="M{item["x"]:.1f} {top - 1:.1f}l-6 -9h12z"/>' if item["mine"]
                  else f'<circle class="sc-mark" cx="{item["x"]:.1f}" cy="{top - 4:.1f}" r="3"/>')
        through = f'<line class="sc-through" x1="{item["x"]:.1f}" y1="{top:.1f}" x2="{item["x"]:.1f}" y2="{base:.1f}"/>' if item["mine"] else ""
        parts.append(f'<g class="{cls}"><line class="sc-stem" x1="{item["x"]:.1f}" y1="{y0 + 26:.1f}" x2="{item["x"]:.1f}" y2="{top - 8:.1f}"/>{through}{marker}'
                     f'<text class="sc-val" x="{item["x0"] + item["w"] / 2:.1f}" y="{y0 + 10:.1f}" text-anchor="middle">{escape(item["text"])}</text>'
                     f'<text class="sc-who" x="{item["x0"] + item["w"] / 2:.1f}" y="{y0 + 23:.1f}" text-anchor="middle">{escape(item["sub"])}</text></g>')
    height = base + 34 + gutter * 0.5
    sv["canvas"] = {"width": round(width), "height": round(height)}
    sv["drawn"] = {"bands": n, "points": len(points)}
    sv["notes"].append("Tranches : " + " ; ".join(f"« {_dim_label(dim, b['value'])} » {ext.band_text(dim, b)}" + (f" → {b['result']}" if b.get("result") else "") for b in bands) + ".")
    if measure is not None:
        band = bands[band_of(measure)]
        sv["notes"].append(f"Ce cas : {amount(measure, unit)}, dans la tranche « {_dim_label(dim, band['value'])} »" + (f" → {band['result']}" if band.get("result") else "") + ".")
    else:
        sv["warnings"].append(f"Ce cas ne porte pas de mesure pour « {dim['key']} » (champ « measures ») : seul le découpage est montré.")
    others = sorted(p for p, members in points.items() if any(not m.get("me") for m in members))
    if others:
        sv["notes"].append("Mesures des autres cas : " + ", ".join(amount(p, unit) for p in others[:20]) + ".")
    sv["notes"].append("Échelle schématique : chaque tranche a la même largeur, l'ordre des valeurs est respecté, pas les distances.")
    return _canvas(view, _svg(view, width, height, "".join(parts), "rep-scale", "Axe à bandes"), "Axe à bandes")


# ---------------------------------------------------------------------------
# Arbre de décision
# ---------------------------------------------------------------------------

def decision_tree(ruleset: dict, dimensions: list[dict]) -> dict:
    """Déplie le jeu de règles en arbre, en lisant les lignes dans l'ordre (la première qui correspond l'emporte)."""
    domains = {d["key"]: [(v["value"], v["label"]) for v in d["values"]] for d in dimensions}
    labels = {c["key"]: c["label"] for c in ruleset.get("conditions", [])}

    def build(rows: list[dict], conds: list[str]) -> dict:
        if not rows:
            return {"leaf": None}
        conds = [c for c in conds if any(c in r["when"] for r in rows)]
        if not conds or not any(c in rows[0]["when"] for c in conds):
            return {"leaf": rows[0]}
        cond = conds[0]
        values = list(dict.fromkeys(r["when"][cond] for r in rows if cond in r["when"]))
        branches = [(v, build([r for r in rows if r["when"].get(cond, v) == v], conds[1:])) for v in values]
        rest = [r for r in rows if cond not in r["when"]]
        domain = domains.get(cond)
        others = [label for value, label in domain or [] if value not in values and label not in values]
        node = {"cond": cond, "label": labels.get(cond, cond), "branches": branches}
        if rest or not domain or others:
            branches.append((None, build(rest, conds[1:])))
            # Quand l'étude déclare les valeurs possibles, la branche restante porte leur nom plutôt que « autre ».
            node["else"] = " ou ".join(others) if domain and 0 < len(others) <= 2 else "autre"
        return node

    return build(ruleset.get("rows", []), [c["key"] for c in ruleset.get("conditions", [])])


def _leaves(node: dict) -> int:
    return 1 if "leaf" in node else sum(_leaves(child) for _, child in node["branches"])


def _has_row(node: dict, key: str) -> bool:
    if "leaf" in node:
        return bool(node["leaf"]) and node["leaf"]["key"] == key
    return any(_has_row(child, key) for _, child in node["branches"])


def render_tree(ctx: Context, view: dict, sv: dict) -> str:
    layout = with_defaults(view["layout"])
    decision = next((with_defaults(m) for m in view["marks"] if m["brick"] == "mark.decision"), with_defaults({"brick": "mark.decision"}))
    conclusion = with_defaults(next(m for m in view["marks"] if m["brick"] == "mark.conclusion"))
    ruleset = ctx.ruleset or {}
    if not ruleset.get("rows"):
        return _empty(sv, "Cette étude ne déclare pas de jeu de règles : il n'y a pas d'arbre à dessiner.", "L'arbre de décision demande un jeu de règles sur l'étude (champ « ruleset »).")
    tree = decision_tree(ruleset, ctx.dimensions)
    count = _leaves(tree)
    if count > layout["max_leaves"]:
        return _empty(sv, f"Ce jeu de règles se déplie en {count} conclusions : l'arbre serait illisible. La table de règles le montre en entier.",
                      f"Arbre non dessiné : {count} feuilles pour un maximum de {layout['max_leaves']} (max_leaves). Proposez la table de règles.")
    selected = next((k for k, v in ((ctx.frames[-1].get("rules") or {}) if ctx.frames else {}).items() if v.get("result") == "selected"), None)

    # Chemin du cas : la valeur du cas pour chaque condition ; à défaut, la branche qui mène à la ligne retenue.
    on_path: set[int] = set()
    steps_text: list[str] = []
    node, reached = tree, None
    while node is not None:
        on_path.add(id(node))
        if "leaf" in node:
            reached = node["leaf"]
            break
        value = case_value(ctx, node["cond"])
        candidates = case_candidates(ctx, node["cond"])
        choice = next((b for b in node["branches"] if b[0] is not None and b[0] in candidates), None)
        if choice is None and value is None and selected:
            choice = next((b for b in node["branches"] if _has_row(b[1], selected)), None)
        if choice is None:
            choice = next((b for b in node["branches"] if b[0] is None), None)
        if choice is None:
            steps_text.append(f"{node['label']} : aucune branche pour la valeur du cas ({value if value is not None else 'inconnue'})")
            break
        steps_text.append(f"{node['label']} = {choice[0] if choice[0] is not None else node.get('else', 'autre')}")
        on_path.add(id(choice))
        node = choice[1]

    right = layout["direction"] == "right"
    dw, dh = 150.0, 38.0
    all_branches, all_leaves = [], []

    def walk(n):
        if "branches" in n:
            for b in n["branches"]:
                all_branches.append(b[0] if b[0] is not None else n.get("else", "autre"))
                walk(b[1])
        else:
            all_leaves.append(n["leaf"]["then"] if n["leaf"] else "Aucune ligne ne correspond")
    walk(tree)
    lw = max(170.0, min(270.0, max(_text_width(t, 13, True) for t in all_leaves) + 46))
    lh = 46.0 if conclusion["show_key"] else 32.0
    widest = max((_text_width(b, 11, True) for b in all_branches), default=40)
    gap = max(64.0, min(150.0, widest + 30)) if right else 62.0
    tag_w = 56.0
    slot = (lh + 14) if right else (lw + 18)
    cursor = [0.0]
    placed = []   # (node, depth, centre sur l'axe transversal)

    def place(n, depth) -> float:
        if "leaf" in n:
            centre = cursor[0] + slot / 2
            cursor[0] += slot
        else:
            centres = [place(child, depth + 1) for _, child in n["branches"]]
            centre = (centres[0] + centres[-1]) / 2
        n["_d"], n["_c"] = depth, centre
        placed.append(n)
        return centre

    place(tree, 0)
    pad = 14.0

    def box(n):
        w, h = (lw, lh) if "leaf" in n else (dw, dh)
        along = pad + n["_d"] * ((dw if right else dh) + gap)
        if right:
            return along, pad + n["_c"] - h / 2, w, h
        return pad + n["_c"] - w / 2, along, w, h

    radius = RADIUS[ctx.tokens.get("corners", "soft")]
    edges, nodes = [], []
    for n in placed:
        x, y, w, h = box(n)
        path_cls = " is-path" if id(n) in on_path else ""
        if "leaf" in n:
            row = n["leaf"]
            role = ctx.role(row["status"]) if row and row.get("status") else "neutral"
            text = row["then"] if row else "Aucune règle"
            body = f'<path class="n-shape" d="{_node_shape_path("rect", w, h, radius)}"/>'
            tx = 12.0
            if row and row.get("status"):
                body += f'<use class="st-ic" href="#ic-{role}" x="10" y="{(16 if conclusion["show_key"] else h / 2) - 7:.1f}" width="14" height="14"/>'
                tx = 30.0
            body += f'<text class="n-label" x="{tx:.1f}" y="{20 if conclusion["show_key"] else h / 2 + 4.5:.1f}">{escape(_fit(text, w - tx - 10, 13, True, sv))}</text>'
            if conclusion["show_key"]:
                body += f'<text class="n-sub" x="{tx:.1f}" y="37">{escape(("Ligne " + row["key"]) if row else "Aucune ligne ne correspond")}</text>'
            if path_cls:
                tag_x, tag_y, anchor = (w + 8, h / 2 + 4, "start") if right else (w / 2, h + 15, "middle")
                body += f'<text class="tr-here" x="{tag_x:.1f}" y="{tag_y:.1f}" text-anchor="{anchor}">ce cas</text>'
            nodes.append(f'<g class="n tr-leaf{path_cls}{"" if row else " tr-void"}" data-role="{role}" transform="translate({x:.1f} {y:.1f})"><title>{escape(text)}</title>{body}</g>')
            continue
        body = f'<path class="n-shape" d="{_node_shape_path(decision["shape"], w, h, radius)}"/>'
        inset = 22 if decision["shape"] == "hexagon" else 14
        body += f'<text class="n-label" x="{w / 2:.1f}" y="{h / 2 + 4.5:.1f}" text-anchor="middle">{escape(_fit(n["label"] + " ?", w - 2 * inset, 13, True, sv))}</text>'
        nodes.append(f'<g class="n tr-test{path_cls}" transform="translate({x:.1f} {y:.1f})"><title>{escape(n["label"])}</title>{body}</g>')
        for branch in n["branches"]:
            cx, cy, cw, ch = box(branch[1])
            text = branch[0] if branch[0] is not None else n.get("else", "autre")
            cls = "tr-edge" + (" is-path" if id(branch) in on_path else "") + (" tr-else" if branch[0] is None else "")
            if right:
                sx, sy, ex, ey = x + w, y + h / 2, cx, cy + ch / 2
                mx = sx + 14
                d = f"M{sx:.1f} {sy:.1f}H{mx:.1f}V{ey:.1f}H{ex - 6:.1f}"
                tip = f'<path class="lk-tip" d="M0 0L-7 -3.8L-7 3.8Z" transform="translate({ex:.1f} {ey:.1f})"/>'
                label = f'<text class="tr-val" x="{mx + 7:.1f}" y="{ey - 5:.1f}">{escape(_fit(text, ex - mx - 14, 11, True, sv))}</text>'
            else:
                sx, sy, ex, ey = x + w / 2, y + h, cx + cw / 2, cy
                my = sy + 16
                d = f"M{sx:.1f} {sy:.1f}V{my:.1f}H{ex:.1f}V{ey - 6:.1f}"
                tip = f'<path class="lk-tip" d="M0 0L-7 -3.8L-7 3.8Z" transform="translate({ex:.1f} {ey:.1f}) rotate(90)"/>'
                label = f'<text class="tr-val" x="{ex:.1f}" y="{ey - 12:.1f}" text-anchor="middle">{escape(_fit(text, slot - 10, 11, True, sv))}</text>'
            edges.append(f'<g class="{cls}"><path class="lk-path" d="{d}"/>{tip}{label}</g>')
    depth = max(n["_d"] for n in placed)
    if right:
        width = pad * 2 + depth * (dw + gap) + lw + tag_w
        height = pad * 2 + cursor[0]
    else:
        width = pad * 2 + max(cursor[0], lw)
        height = pad * 2 + depth * (dh + gap) + lh + 22
    sv["canvas"] = {"width": round(width), "height": round(height)}
    sv["drawn"] = {"tests": sum(1 for n in placed if "branches" in n), "conclusions": count}
    if reached:
        steps_text.append(f"ligne {reached['key']} « {reached['then']} »")
    elif node is not None and "leaf" in node:
        steps_text.append("aucune règle ne correspond")
    sv["notes"].append("Chemin du cas : " + " → ".join(steps_text) + ".")
    if selected and reached and reached["key"] != selected:
        sv["warnings"].append(f"Le chemin de l'arbre aboutit à la ligne {reached['key']}, alors que le cas déclare la ligne {selected} retenue : vérifiez les valeurs du cas ou l'ordre des règles.")
    if ruleset.get("policy") in ("collect", "any"):
        sv["warnings"].append("L'arbre lit les règles dans l'ordre (première qui correspond) ; avec la politique déclarée, plusieurs lignes peuvent s'appliquer : la table de règles est plus fidèle.")
    for n in placed:
        n.pop("_d", None)
        n.pop("_c", None)
    return _canvas(view, _svg(view, width, height, f'<g class="links">{"".join(edges)}</g>{"".join(nodes)}', "rep-tree", "Arbre de décision"), "Arbre de décision")


# ---------------------------------------------------------------------------
# Diagramme d'états
# ---------------------------------------------------------------------------

def render_states(ctx: Context, view: dict, sv: dict) -> str:
    layout = with_defaults(view["layout"])
    time = with_defaults(view.get("time") or {"brick": "time.stepper"})
    state_mark = with_defaults(next(m for m in view["marks"] if m["brick"] == "mark.state"))
    trans_mark = next((with_defaults(m) for m in view["marks"] if m["brick"] == "mark.transition"), None)
    cycle, ent = lifecycle_for(ctx, layout["entity"])
    if not cycle:
        return _empty(sv, "Aucune entité de ce cas n'a de cycle de vie déclaré.", "Le diagramme d'états demande un cycle de vie sur l'étude (champ « lifecycles », par type d'entité) et une entité de ce type dans le cas.")
    fixed = _fixed_step(ctx, time)
    start, series, taken = _state_series(ctx, ent)
    right = layout["direction"] == "right"
    states = cycle["states"]
    transitions = cycle["transitions"]
    nh = 34.0
    nodes = [{"id": s, "w": max(96.0, _text_width(ctx.label(s), 12.5, True) + 48), "h": nh} for s in states]
    by_id = {n["id"]: n for n in nodes}
    plain = [{"from": t["from"], "to": t["to"], "type": "transition"} for t in transitions if t["from"] != t["to"]]
    rank = _ranks(nodes, plain)
    layers = _order_ranks(nodes, plain, rank)

    # Coordonnées (u : sens de lecture, v : travers). P les ramène en x, y selon la direction.
    def size_u(n):
        return n["w"] if right else n["h"]

    def size_v(n):
        return n["h"] if right else n["w"]

    def P(u, v):
        return (u, v) if right else (v, u)

    def text_of(t):
        return t["label"] + (f" [{t['guard']}]" if trans_mark and trans_mark["show_guard"] and t.get("guard") else "")

    u = 0.0
    tallest = max(sum(size_v(n) for n in layer) + layout["node_gap"] * (len(layer) - 1) for layer in layers)
    for index, layer in enumerate(layers):
        thick = max(size_u(n) for n in layer)
        total = sum(size_v(n) for n in layer) + layout["node_gap"] * (len(layer) - 1)
        v = (tallest - total) / 2
        for n in layer:
            n["u"], n["v"] = u + (thick - size_u(n)) / 2, v
            v += size_v(n) + layout["node_gap"]
        gap = float(layout["rank_gap"])
        if right:   # de gauche à droite, le nom de l'évènement s'écrit dans l'intervalle : il doit y tenir
            crossing = [text_of(t) for t in transitions if rank[t["from"]] == index and rank[t["to"]] == index + 1]
            gap = max(gap, max((_text_width(text, 11, True) for text in crossing), default=0) + 22)
        u += thick + gap

    def centre(n):
        return n["u"] + size_u(n) / 2, n["v"] + size_v(n) / 2

    xs, ys = [], []

    def see(x, y):
        xs.append(x)
        ys.append(y)

    def pt(u_, v_):
        x, y = P(u_, v_)
        see(x, y)
        return f"{x:.1f} {y:.1f}"

    v_min = min(n["v"] for n in nodes)
    v_max = max(n["v"] + size_v(n) for n in nodes)
    lanes = {"over": 0, "under": 0}
    edge_svg = []
    pair_count: dict[tuple, int] = {}
    for t in transitions:
        src, dst = by_id[t["from"]], by_id[t["to"]]
        text = text_of(t)
        # Transition empruntée à cette étape, ou déjà empruntée plus tôt (la trace du parcours reste dessinée).
        per_step = ["is-taken" if move == (t["from"], t["to"]) else ("is-trail" if (t["from"], t["to"]) in taken[:i] else "")
                    for i, move in enumerate(taken)]
        now, dyn = dyn_cls(per_step, ctx, fixed)
        su, sv_ = centre(src)
        du, dv = centre(dst)
        anchor = "middle"
        if src is dst:
            a, b = su - 12, su + 12
            top = src["v"]
            d = f"M{pt(a, top)}C{pt(a - 16, top - 30)} {pt(b + 16, top - 30)} {pt(b + 1.5, top - 6)}"
            tip_at, tip_angle = (b - 2.6, top + 0.5), 121 if right else -31
            lu, lv = su, top - 27
            if not right:
                lu, lv, anchor = su + 4, top - 30, "end"
        elif rank[t["to"]] == rank[t["from"]] + 1:
            index = pair_count.get((t["from"], t["to"]), 0)
            pair_count[(t["from"], t["to"])] = index + 1
            a, b = src["u"] + size_u(src), dst["u"]
            bend = (b - a) * 0.45
            d = f"M{pt(a, sv_)}C{pt(a + bend, sv_)} {pt(b - bend, dv)} {pt(b - 7, dv)}"
            tip_at, tip_angle = (b, dv), 0 if right else 90
            lu, lv = (a + b) / 2, (sv_ + dv) / 2 - 6 - index * 13
            if not right:
                lu, lv, anchor = (a + b) / 2 + 3, (sv_ + dv) / 2 + 6 + index * 60, "start"
        else:
            side = "over" if rank[t["to"]] > rank[t["from"]] else "under"
            lane = lanes[side]
            lanes[side] += 1
            reach = 26 + 20 * lane
            if side == "over":
                a_v, b_v, apex = src["v"], dst["v"], v_min - reach
                tip_angle = 90 if right else 0
            else:
                a_v, b_v, apex = src["v"] + size_v(src), dst["v"] + size_v(dst), v_max + reach
                tip_angle = -90 if right else 180
            toward = 1 if du >= su else -1
            a_u = su + toward * size_u(src) * 0.22
            b_u = du - toward * size_u(dst) * 0.22
            end_v = b_v - 7 if side == "over" else b_v + 7
            d = f"M{pt(a_u, a_v)}C{pt(a_u, apex)} {pt(b_u, apex)} {pt(b_u, end_v)}"
            tip_at = (b_u, b_v)
            lu, lv = (a_u + b_u) / 2, apex + (reach * 0.25 if side == "over" else -reach * 0.25) + (-4 if side == "over" else 12)
            if not right:
                lu, lv, anchor = (a_u + b_u) / 2 + 4, apex + (reach * 0.25 - 6 if side == "over" else -reach * 0.25 + 6), "end" if side == "over" else "start"
        tx, ty = P(*tip_at)
        lx, ly = P(lu, lv)
        half = _text_width(text, 11, True) / 2
        see(lx - half if anchor == "middle" else (lx - half * 2 if anchor == "end" else lx), ly - 12)
        see(lx + half if anchor == "middle" else (lx if anchor == "end" else lx + half * 2), ly + 4)
        edge_svg.append(f'<g class="sd-edge {now}"{dyn}><path class="lk-path" d="{d}"/>'
                        f'<path class="lk-tip" d="M0 0L-8 -4.2L-8 4.2Z" transform="translate({tx:.1f} {ty:.1f}) rotate({tip_angle})"/>'
                        f'<text class="sd-ev" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}">{escape(text)}</text></g>')

    finals = {s for s in states if not any(t["from"] == s and t["to"] != s for t in transitions)}
    node_svg = []
    for n in nodes:
        x, y = P(n["u"], n["v"])
        w, h = n["w"], n["h"]
        see(x - 5, y - 5)
        see(x + w + 5, y + h + 5)
        role = ctx.role(n["id"])
        label = ctx.label(n["id"])
        per_step = []
        seen: set[str] = {start}
        for status in series:
            # État courant, déjà traversé, ou pas encore atteint : la trace se dessine au fil des étapes.
            mark = "is-seen" if n["id"] in seen else "is-ahead"
            per_step.append("is-here" if status == n["id"] else (mark if state_mark["show_visited"] else ""))
            seen.add(status)
        now, dyn = dyn_cls(per_step, ctx, fixed)
        shape = state_mark["shape"]
        body = f'<title>{escape(label)}</title><path class="sd-ring" d="{_node_shape_path(shape, w + 10, h + 10, 10)}" transform="translate(-5 -5)"/>'
        body += f'<path class="n-shape" d="{_node_shape_path(shape, w, h, 6)}"/>'
        if n["id"] in finals:
            body += f'<path class="sd-final" d="{_node_shape_path(shape, w - 7, h - 7, 4)}" transform="translate(3.5 3.5)"/>'
        body += f'<use class="st-ic" href="#ic-{role}" x="14" y="{h / 2 - 7:.1f}" width="14" height="14"/>'
        body += f'<text class="n-label" x="34" y="{h / 2 + 4.5:.1f}">{escape(label)}</text>'
        node_svg.append(f'<g class="n sd-node {now}"{dyn} data-role="{role}" transform="translate({x:.1f} {y:.1f})">{body}</g>')
    first = by_id.get(cycle["initial"] or states[0])
    fu, fv = centre(first)
    dot_u = first["u"] - 26
    dx, dy = P(dot_u, fv)
    ex, ey = P(first["u"] - 2, fv)
    see(dx - 7, dy - 7)
    marker = (f'<g class="sd-init"><circle cx="{dx:.1f}" cy="{dy:.1f}" r="5"/><path class="lk-path" d="M{dx:.1f} {dy:.1f}L{ex - (6 if right else 0):.1f} {ey - (0 if right else 6):.1f}"/>'
              f'<path class="lk-tip" d="M0 0L-7 -3.8L-7 3.8Z" transform="translate({ex:.1f} {ey:.1f}) rotate({0 if right else 90})"/><title>État de départ</title></g>')
    pad = 16.0
    ox, oy = pad - min(xs), pad - min(ys)
    width, height = max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad
    sv["canvas"] = {"width": round(width), "height": round(height)}
    sv["drawn"] = {"states": len(states), "transitions": len(transitions)}
    loops = [t["label"] for t in transitions if t["from"] == t["to"]]
    backs = [t["label"] for t in transitions if rank[t["to"]] < rank[t["from"]]]
    sv["notes"].append(f"Entité suivie : {ent['label'] or ent['id']} ; parcours : " + " → ".join(ctx.label(s) for s in _path(ctx, ent)) + ".")
    sv["notes"].append("Transitions : " + " ; ".join(f"{ctx.label(t['from'])} —{t['label']}→ {ctx.label(t['to'])}" for t in transitions[:30]) + ".")
    if loops or backs:
        sv["notes"].append(f"{len(loops)} boucle(s) sur soi ({', '.join(loops) or 'aucune'}) ; {len(backs)} retour(s) en arrière ({', '.join(backs) or 'aucun'}).")
    if len(states) > 10:
        sv["warnings"].append(f"{len(states)} états : au-delà d'une dizaine, la table d'états se lit mieux.")
    body = f'<g transform="translate({ox:.1f} {oy:.1f})">{marker}<g class="links">{"".join(edge_svg)}</g>{"".join(node_svg)}</g>'
    # L'état actuel est aussi écrit sous le schéma : l'anneau ne repose pas sur la couleur seule, et la ligne garde sa place.
    arrivals = []
    for move in taken:
        names = [text_of(t) for t in transitions if move and (t["from"], t["to"]) == move]
        arrivals.append(f"arrivé par « {' / '.join(names)} »" if names else ("état de départ" if not arrivals and move is None else "inchangé à cette étape"))
    shown = ctx.step if fixed is None else fixed
    dyn = f" data-tx='{_attr_json(arrivals)}'" if fixed is None else ""
    sizers = "".join(f'<span class="tx-size" aria-hidden="true">{escape(t)}</span>' for t in dict.fromkeys(arrivals)) if fixed is None else ""
    caption = (f'<p class="rep-note sd-now"><span class="rep-note-k">État actuel</span>{pill_series(ctx, series, fixed)}'
               f'<span class="tx-stack sd-how"><span{dyn} data-tx-target="">{escape(arrivals[shown] if arrivals else "")}</span>{sizers}</span></p>')
    return _canvas(view, _svg(view, width, height, body, "rep-states", "Diagramme d'états", time), "Diagramme d'états") + caption


# ---------------------------------------------------------------------------
# Diagramme de séquence
# ---------------------------------------------------------------------------

def render_lifelines(ctx: Context, view: dict, sv: dict) -> str:
    layout = with_defaults(view["layout"])
    time = with_defaults(view.get("time") or {"brick": "time.stepper"})
    life = with_defaults(next(m for m in view["marks"] if m["brick"] == "mark.lifeline"))
    msg_mark = next((with_defaults(m) for m in view["marks"] if m["brick"] == "mark.message"), None)
    fixed = _fixed_step(ctx, time)
    actors = [e for e in ctx.case.get("entities", []) if _matches(layout.get("where"), e)]
    sv["not_drawn"] = [e["id"] for e in ctx.case.get("entities", []) if e not in actors]
    if not actors:
        return _empty(sv, "Aucune entité à placer en colonne.", "Le diagramme de séquence demande au moins une entité (les acteurs) ; vérifiez le filtre « where ».")
    cw, rh = float(layout["column_width"]), float(layout["row_height"])
    gutter, pad = 38.0, 10.0
    titles = {e["id"]: _wrap2(fill_template(life["label"], e) or e["id"], cw - 42, 13) for e in actors}
    flags = {e["id"]: entity_flag_items(ctx.case, e["id"], ctx.attributes) for e in actors}   # options mises en avant, sous le nom de l'acteur
    extra = max(len(titles[i]) - 1 + len(flags[i]) for i in titles)
    head_h = (52.0 if life["show_status"] else 32.0) + 16.0 * extra
    col = {e["id"]: gutter + i * cw + cw / 2 for i, e in enumerate(actors)}
    width = gutter + len(actors) * cw + pad
    rows, number, skipped = [], 0, 0
    for i, frame in enumerate(ctx.frames):
        messages = []
        for m in frame.get("messages", []) if msg_mark else []:
            if m["from"] in col and m["to"] in col:
                number += 1
                messages.append((number, m))
            else:
                skipped += 1
        rows.append((i, messages or [None]))
    top = pad + head_h + 14
    parts, bands, y = [], [], top
    spoken: list[str] = []
    for i, messages in rows:
        band_h = rh * len(messages)
        per_step = ["is-future" if s < i else "" for s in range(ctx.n_steps)]
        now, dyn = dyn_cls(per_step, ctx, fixed)
        current = " is-current" if fixed is None and i == ctx.step else ""
        step_attr = f' data-step-is="{i}"' if fixed is None else ""
        bands.append(f'<rect class="sq-band{current}"{step_attr} x="0" y="{y:.1f}" width="{width:.1f}" height="{band_h:.1f}"/>')
        inner = f'<text class="sq-n" x="{gutter / 2:.1f}" y="{y + band_h / 2 + 4.5:.1f}" text-anchor="middle">{i + 1}</text>'
        for k, item in enumerate(messages):
            if item is None:
                continue
            n, m = item
            my = y + k * rh + rh * 0.7
            sx, dx = col[m["from"]], col[m["to"]]
            lost = m["status"] == "lost"
            base = fill_template(msg_mark["label"], {"label": m["label"], "from": m["from"], "to": m["to"], "n": n}) or m["label"]
            text = (f"{n}. " if msg_mark["numbered"] else "") + base + (" — perdu" if lost else "")
            names = {e["id"]: e["label"] or e["id"] for e in actors}
            spoken.append(f"{n}. {names[m['from']]} → {names[m['to']]} : {m['label']}" + (" (perdu)" if lost else "") + f" [étape {i + 1}]")
            cls = "sq-msg is-lost" if lost else "sq-msg"
            if sx == dx:
                d = f"M{sx:.1f} {my - 9:.1f}h30v15h-23"
                tip = f'<path class="lk-tip" d="M0 0L-7 -3.8L-7 3.8Z" transform="translate({sx + 1:.1f} {my + 6:.1f}) rotate(180)"/>'
                label = f'<text class="sq-tx" x="{sx + 38:.1f}" y="{my + 2:.1f}">{escape(_fit(text, width - sx - 46, 11.5, True, sv))}</text>'
                inner += f'<g class="{cls}"><path class="lk-path" d="{d}"/>{tip}{label}</g>'
                continue
            direction = 1 if dx > sx else -1
            end = sx + (dx - sx) * 0.6 if lost else dx - direction * 1.5
            line_end = end if lost else end - direction * 6
            d = f"M{sx:.1f} {my:.1f}H{line_end:.1f}"
            if lost:
                tip = f'<path class="sq-x" d="M{end - 4:.1f} {my - 4:.1f}l8 8m0 -8l-8 8"/>'
            else:
                tip = f'<path class="lk-tip" d="M0 0L-8 -4.2L-8 4.2Z" transform="translate({end:.1f} {my:.1f}) rotate({0 if direction > 0 else 180})"/>'
            # Le libellé peut déborder de la flèche (son liseré couvre les lignes de vie), tant qu'il reste dans le schéma.
            span = abs(dx - sx)
            room = min(span + cw * 0.9, width - gutter - 8)
            shown = _fit(text, room, 11.5, True, sv)
            half = _text_width(shown, 11.5, True) / 2
            lx = max(gutter + half, min(width - 6 - half, (sx + dx) / 2))
            label = f'<text class="sq-tx" x="{lx:.1f}" y="{my - (12 if lost else 9):.1f}" text-anchor="middle">{escape(shown)}</text>'
            inner += f'<g class="{cls}"><path class="lk-path" d="{d}"/>{tip}{label}</g>'
        parts.append(f'<g class="sq-step {now}{current}"{step_attr}{dyn}>{inner}</g>')
        y += band_h
    bottom = y + 8
    lines = "".join(f'<line class="sq-life" x1="{x:.1f}" y1="{pad + head_h:.1f}" x2="{x:.1f}" y2="{bottom:.1f}"/>' for x in col.values())
    heads = []
    radius = RADIUS[ctx.tokens.get("corners", "soft")]
    for ent in actors:
        w = cw - 18
        x = col[ent["id"]] - w / 2
        label = fill_template(life["label"], ent) or ent["id"]
        attrs, classes = _state_attrs(ctx, ent["id"], None, fixed) if life["show_status"] else ("", [])
        body = f'<title>{escape(label)}</title><path class="n-shape" d="{_node_shape_path("rect", w, head_h, radius)}"/>'
        lines_ = titles[ent["id"]]
        for li, line in enumerate(lines_):
            body += f'<text class="n-label" x="12" y="{20 + li * 16}">{escape(_fit(line, w - 24, 13, True, sv))}</text>'
        for fi, (flag, style, _definition) in enumerate(flags[ent["id"]]):
            body += (f'<text class="n-flag {flag_classes(style)}" x="12" y="{20 + (len(lines_) + fi) * 16}">'
                     f'{escape(_fit(flag, w - 24, 11.5, style.get("weight") != "normal", sv))}</text>')
        if life["show_status"]:
            body += f'<g class="n-status">{_status_svg(ctx, ent["id"], 12, head_h - 11, fixed)}</g>'
        heads.append(f'<g class="{" ".join(["n", "sq-head", *[c for c in classes if c != "is-changed"]])}"{attrs} transform="translate({x:.1f} {pad:.1f})">{body}</g>')
    height = bottom + pad
    sv["canvas"] = {"width": round(width), "height": round(height)}
    sv["drawn"] = {"lifelines": len(actors), "messages": number}
    if spoken:
        sv["notes"].append("Messages, dans l'ordre : " + " ; ".join(spoken[:40]) + ".")
    else:
        sv["warnings"].append("Ce cas ne porte aucun message (steps[].messages) : seules les lignes de vie sont dessinées.")
    if skipped:
        sv["warnings"].append(f"{skipped} message(s) non dessiné(s) : leur émetteur ou leur destinataire est filtré par « where ».")
    if len(actors) > 8:
        sv["warnings"].append(f"{len(actors)} acteurs : au-delà de huit, le schéma défile horizontalement.")
    # Calques : bandes d'étape, lignes de vie, messages, en-têtes — un libellé n'est jamais barré par une ligne de vie.
    body = f'{"".join(bands)}{lines}{"".join(parts)}{"".join(heads)}'
    return _canvas(view, _svg(view, width, height, body, "rep-seq", "Diagramme de séquence", time), "Diagramme de séquence")


LAYOUTS = {
    "layout.matrix": render_matrix,
    "layout.scale": render_scale,
    "layout.tree": render_tree,
    "layout.states": render_states,
    "layout.lifelines": render_lifelines,
}
