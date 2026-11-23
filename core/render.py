"""Moteur de rendu : dessine une représentation (assemblage de briques) pour un cas.

Entrée : la représentation validée, le cas normalisé, ses états rejoués, les statuts de
l'étude. Sortie : un fragment HTML/SVG et un résumé structurel en texte (utile à une IA
qui ne voit pas l'image).

Le fragment est statique et correct sans JavaScript pour l'étape demandée. Les éléments
qui évoluent portent leurs états par étape dans des attributs data-* ; le script de
l'application ne fait que les appliquer quand l'utilisateur change d'étape :

  data-st="K0|K1|…"   statut par étape → data-role, icône (use[data-si]) et libellé ([data-sl])
  data-ch="0101"      a changé à cette étape → classe is-changed
  data-tx='[…]'       texte par étape → contenu, classe is-empty si vide
  data-step-is="i"    élément propre à l'étape i → classe is-current
  data-xs / data-ws   position x / largeur par étape (curseur temporel)
  data-emph='[…]'     règles de mise en évidence → classes fx-halo, fx-bold, fx-fade
  data-cls='[…]'      classes par étape (voir core/render_ext.py)
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from html import escape

from .bricks import with_defaults
from .casemodel import ACYCLIC_LINK_TYPES, ROLE_LABELS

ICONS = {
    "neutral": '<circle cx="8" cy="8" r="5.6"/>',
    "waiting": '<circle cx="8" cy="8" r="6"/><path d="M8 4.6V8l2.3 1.5"/>',
    "active": '<path d="M5.4 3.6v8.8L12.4 8z" fill="currentColor"/>',
    "success": '<path d="M3 8.5l3.2 3.2L13 4.6"/>',
    "warning": '<path d="M8 2.4l6.2 10.8H1.8z"/><path d="M8 6.5v3.3M8 11.3v.3"/>',
    "error": '<path d="M4 4l8 8M12 4l-8 8"/>',
    "blocked": '<rect x="3.6" y="7.2" width="8.8" height="6.2" rx="1.3"/><path d="M5.5 7.2V5.3a2.5 2.5 0 015 0v1.9"/>',
    "disabled": '<circle cx="8" cy="8" r="6"/><path d="M3.8 12.2l8.4-8.4"/>',
    "info": '<circle cx="8" cy="8" r="6"/><path d="M8 7.3v3.6M8 5v.3"/>',
}


def icon_sprite() -> str:
    symbols = "".join(
        f'<symbol id="ic-{role}" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.7" '
        f'stroke-linecap="round" stroke-linejoin="round">{body}</symbol>'
        for role, body in ICONS.items()
    )
    return f'<svg class="sprite" width="0" height="0" aria-hidden="true" focusable="false">{symbols}</svg>'


_PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
NODE_WIDTH = {"s": 132, "m": 176, "l": 220}
DENSITY = {"compact": 0.8, "comfortable": 1.0, "spacious": 1.3}
RADIUS = {"sharp": 0, "soft": 6, "round": 12}


def _fmt_number(value) -> str:
    if isinstance(value, bool):   # écrit tel qu'il est dans les données : true / false
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:g}".replace(".", ",")
    return str(value)


def fill_template(template: str, values: dict) -> str:
    def sub(match):
        name = match.group(1)
        if name.startswith("attr."):
            value = (values.get("attrs") or {}).get(name[5:])
        else:
            value = values.get(name)
        return "" if value is None else _fmt_number(value)

    text = _PLACEHOLDER.sub(sub, template or "")
    text = re.sub(r"\s+", " ", text).strip()
    # Un champ vide laisse des séparateurs orphelins (« A · ») : on les retire.
    return re.sub(r"^(?:[·\-—:]\s*)+|(?:\s*[·\-—:])+$", "", text).strip()


def fill_detail(template: str, values: dict) -> str:
    """Comme fill_template, mais une ligne dont tous les champs sont vides disparaît (« always_run : » seul ne dit rien)."""
    names = _PLACEHOLDER.findall(template or "")
    if names and all(fill_template("{" + n + "}", values) == "" for n in names):
        return ""
    return fill_template(template, values)


def flag_classes(style: dict | None) -> str:
    """Classes d'une option mise en avant, d'après son style (défaut : gras, droit, encre)."""
    style = style or {}
    cls = ["flag-normal" if style.get("weight") == "normal" else "flag-bold"]
    if style.get("italic"):
        cls.append("flag-italic")
    cls.append(f"flag-tone-{style.get('tone', 'ink')}")
    return " ".join(cls)


def attribute_info(attributes: list[dict] | None, key: str) -> tuple[str, str]:
    """Nom affiché et définition (au survol) d'une option. Par défaut le nom technique, tel qu'il est écrit dans le
    système (always_run) ; le libellé lisible seulement si l'étude le demande (« show »: « label »)."""
    decl = next((a for a in attributes or [] if a["key"] == key), None)
    if not decl:
        return key, ""
    tip = f"{decl['label']} ({key})" + (f" : {decl['text']}" if decl.get("text") else "")
    return (decl["label"] if decl.get("show") == "label" else key), tip


def attribute_value(attributes: list[dict] | None, key: str, value) -> str:
    """Valeur d'une option : telle qu'elle est écrite (true / false), sauf sous un libellé lisible, où elle se lit oui / non."""
    decl = next((a for a in attributes or [] if a["key"] == key), None)
    if isinstance(value, bool) and decl and decl.get("show") == "label":
        return "oui" if value else "non"
    return _fmt_number(value)


def entity_flag_items(case: dict, ent_id: str, attributes: list[dict] | None = None) -> list[tuple[str, dict, str]]:
    """Options de l'entité que l'auteur du cas a mises en avant ({"entity", "attr", "style"} dans « highlights ») :
    texte prêt à écrire, style, et définition de l'option (vide si l'étude ne la déclare pas)."""
    attrs = next((e.get("attrs") or {} for e in case.get("entities", []) if e["id"] == ent_id), {})
    out = []
    for h in case.get("highlights") or []:
        if isinstance(h, dict) and h.get("entity") == ent_id and h.get("attr") in attrs:
            label, definition = attribute_info(attributes, h["attr"])
            out.append((f"{label} : {attribute_value(attributes, h['attr'], attrs[h['attr']])}", h.get("style") or {}, definition))
    return out


def entity_flags(case: dict, ent_id: str, attributes: list[dict] | None = None) -> list[str]:
    return [text for text, *_ in entity_flag_items(case, ent_id, attributes)]


def with_flags(label: str, case: dict, ent_id: str, attributes: list[dict] | None = None) -> str:
    flags = entity_flags(case, ent_id, attributes)
    return " · ".join([label, *flags]) if flags else label


def link_flag(case: dict, link: dict) -> dict | None:
    """Style du lien si l'auteur du cas l'a mis en avant ({"link": [de, vers]} dans « highlights »), sinon None."""
    for h in case.get("highlights") or []:
        if isinstance(h, dict) and h.get("link") == [link["from"], link["to"]]:
            return h.get("style") or {}
    return None


def _matches(where: dict | None, item: dict) -> bool:
    if not where:
        return True
    for key, expected in where.items():
        actual = (item.get("attrs") or {}).get(key[5:]) if key.startswith("attr.") else item.get(key)
        options = expected if isinstance(expected, list) else [expected]
        if not any(actual == o or (actual is not None and str(actual) == str(o)) for o in options):
            return False
    return True


@dataclass
class Summary:
    views: list[dict] = field(default_factory=list)

    def view(self, view: dict, layout: str, time: str) -> dict:
        entry = {"id": view["id"], "title": view.get("title", ""), "layout": layout, "time": time,
                 "drawn": {}, "canvas": None, "not_drawn": [], "truncated": [], "warnings": [], "notes": []}
        self.views.append(entry)
        return entry


@dataclass
class Context:
    case: dict
    frames: list[dict]
    statuses: dict[str, dict]
    step: int
    tokens: dict
    siblings: list[dict]
    dimensions: list[dict]
    scale: float = 1.0
    ruleset: dict = field(default_factory=dict)
    lifecycles: list = field(default_factory=list)
    default_status: str = ""
    attributes: list = field(default_factory=list)

    def initial_status(self, ent_id: str) -> str:
        """Statut de l'entité avant la première étape."""
        return (self.case.get("initial") or {}).get(ent_id) or self.default_status

    @property
    def n_steps(self) -> int:
        return len(self.frames)

    def status_at(self, ent_id: str, step: int) -> str:
        if not self.frames:
            return ""
        return self.frames[step]["states"].get(ent_id, {}).get("status") or ""

    def series(self, ent_id: str) -> list[str]:
        return [self.status_at(ent_id, i) for i in range(self.n_steps)]

    def changed(self, ent_id: str) -> str:
        return "".join("1" if ent_id in f["changed"] else "0" for f in self.frames)

    def focused(self, ent_id: str) -> str:
        """Étapes où l'auteur du cas désigne cette entité au relecteur (« focus »), en « 0101 »."""
        return "".join("1" if ent_id in f.get("focus", []) else "0" for f in self.frames)

    def role(self, status: str) -> str:
        return self.statuses.get(status, {}).get("role", "neutral")

    def label(self, status: str, mode: str = "full") -> str:
        info = self.statuses.get(status)
        if not info:
            return status
        return info["short"] if mode == "short" else info["label"]


def _text_width(text: str, size: float, bold: bool = False) -> float:
    return len(text) * size * (0.58 if bold else 0.54)


def _fit(text: str, max_width: float, size: float, bold: bool, summary_view: dict) -> str:
    if _text_width(text, size, bold) <= max_width:
        return text
    chars = max(3, int(max_width / (size * (0.58 if bold else 0.54))) - 1)
    shown = text[:chars].rstrip() + "…"
    summary_view["truncated"].append({"text": text, "shown": shown})
    return shown


def _emphasis_classes(rules: list[dict], status: str, role: str, changed: bool) -> list[str]:
    classes = []
    for rule in rules or []:
        when = rule["when"]
        hit = True
        if "role" in when and role not in when["role"]:
            hit = False
        if "status" in when and status not in when["status"]:
            hit = False
        if when.get("changed") and not changed:
            hit = False
        if hit:
            classes.append(f"fx-{rule['effect']}")
    return classes


def _state_attrs(ctx: Context, ent_id: str, emphasis: list[dict] | None, fixed_step: int | None) -> tuple[str, list[str]]:
    """Attributs data-* d'un élément à état, et classes déjà appliquées pour l'étape rendue."""
    step = ctx.step if fixed_step is None else fixed_step
    status = ctx.status_at(ent_id, step)
    role = ctx.role(status)
    changed = bool(ctx.frames) and ent_id in ctx.frames[step]["changed"]
    classes = _emphasis_classes(emphasis or [], status, role, changed)
    if changed:
        classes.append("is-changed")
    focused = ctx.focused(ent_id)
    if bool(ctx.frames) and focused[step] == "1":
        classes.append("is-focus")
    attrs = f' data-role="{role}" data-status="{escape(status, quote=True)}"'
    if fixed_step is None:
        attrs += f' data-st="{escape("|".join(ctx.series(ent_id)), quote=True)}" data-ch="{ctx.changed(ent_id)}"'
        if "1" in focused:
            attrs += f' data-fo="{focused}"'
        if emphasis:
            attrs += f" data-emph='{escape(json.dumps(emphasis, separators=(',', ':')), quote=True)}'"
    return attrs, classes


def _status_svg(ctx: Context, ent_id: str, x: float, y: float, fixed_step: int | None, mode: str | None = None) -> str:
    step = ctx.step if fixed_step is None else fixed_step
    status = ctx.status_at(ent_id, step)
    role = ctx.role(status)
    mode = mode or ctx.tokens.get("status_label", "full")
    dyn_i = ' data-si=""' if fixed_step is None else ""
    out = f'<use class="st-ic"{dyn_i} href="#ic-{role}" x="{x:.1f}" y="{y - 11.5:.1f}" width="14" height="14"/>'
    if mode != "hidden":
        dyn_l = f' data-sl="{mode}"' if fixed_step is None else ""
        out += f'<text class="st-tx"{dyn_l} x="{x + 19:.1f}" y="{y:.1f}">{escape(ctx.label(status, mode))}</text>'
    return out


def _status_html(ctx: Context, ent_id: str, fixed_step: int | None, mode: str = "full", dynamic: bool = True) -> str:
    step = ctx.step if fixed_step is None else fixed_step
    status = ctx.status_at(ent_id, step)
    role = ctx.role(status)
    full = ctx.label(status, "full")
    if dynamic and fixed_step is None:
        attrs, classes = _state_attrs(ctx, ent_id, None, None)
        dyn_i, dyn_l = ' data-si=""', f' data-sl="{mode}"'
    else:
        attrs, classes = f' data-role="{role}"', []
        dyn_i = dyn_l = ""
    text = "" if mode == "icon" else f'<span class="st-tx"{dyn_l}>{escape(ctx.label(status, mode))}</span>'
    sr_dyn = ' data-sl="full"' if dyn_i else ""
    sr = f'<span class="sr-only"{sr_dyn}>{escape(full)}</span>' if mode == "icon" else ""
    cls = " ".join(["st", *classes])
    return (f'<span class="{cls}"{attrs} title="{escape(full, quote=True)}">'
            f'<svg class="st-ic" width="14" height="14" aria-hidden="true"><use{dyn_i} href="#ic-{role}"/></svg>{text}{sr}</span>')


# ---------------------------------------------------------------------------
# Graphes : couches et couloirs
# ---------------------------------------------------------------------------

def _node_shape_path(shape: str, w: float, h: float, radius: float) -> str:
    if shape == "pill":
        r = h / 2
        return f"M{r} 0H{w - r}A{r} {r} 0 0 1 {w - r} {h}H{r}A{r} {r} 0 0 1 {r} 0Z"
    if shape == "circle":
        return f"M0 {h / 2}A{w / 2} {h / 2} 0 1 1 {w} {h / 2}A{w / 2} {h / 2} 0 1 1 0 {h / 2}Z"
    if shape == "diamond":
        return f"M{w / 2} 0L{w} {h / 2}L{w / 2} {h}L0 {h / 2}Z"
    if shape == "hexagon":
        inset = min(18, w * 0.12)
        return f"M{inset} 0H{w - inset}L{w} {h / 2}L{w - inset} {h}H{inset}L0 {h / 2}Z"
    r = min(radius, h / 2)
    if r <= 0:
        return f"M0 0H{w}V{h}H0Z"
    return f"M{r} 0H{w - r}A{r} {r} 0 0 1 {w} {r}V{h - r}A{r} {r} 0 0 1 {w - r} {h}H{r}A{r} {r} 0 0 1 0 {h - r}V{r}A{r} {r} 0 0 1 {r} 0Z"


def _prepare_nodes(ctx: Context, view: dict, sv: dict) -> tuple[list[dict], list[dict]]:
    node_marks = [with_defaults(m) for m in view["marks"] if m["brick"] == "mark.node"]
    link_marks = [with_defaults(m) for m in view["marks"] if m["brick"] == "mark.link"]
    dens = DENSITY[ctx.tokens.get("density", "comfortable")]
    nodes = []
    for ent in ctx.case.get("entities", []):
        mark = next((m for m in node_marks if _matches(m.get("where"), ent)), None)
        if mark is None:
            sv["not_drawn"].append(ent["id"])
            continue
        shape = mark["shape"]
        w = NODE_WIDTH[mark["size"]] * (0.92 if dens < 1 else 1)
        pad_x = {"rect": 12, "pill": 20, "hexagon": 22, "circle": w * 0.2, "diamond": w * 0.27}[shape]
        lines = []
        label = fill_template(mark["label"], ent) or ent["id"]
        lines.append(("n-label", label, 13 * ctx.scale, True))
        sub = fill_template(mark.get("sublabel", ""), ent)
        if sub:
            lines.append(("n-sub", sub, 11.5 * ctx.scale, False))
        for detail in mark.get("details", []) or []:
            text = fill_detail(detail, ent)
            if text:
                lines.append(("n-detail", text, 11.5 * ctx.scale, False))
        flags = entity_flag_items(ctx.case, ent["id"], ctx.attributes)
        if flags:
            # La boîte s'élargit pour garder l'option sur une ligne, jusqu'à 1,6 fois sa largeur normale ; la largeur est
            # la même à toutes les étapes, le schéma ne bouge pas.
            need = max(_text_width(f, 11.5 * ctx.scale, st.get("weight") != "normal") for f, st, _ in flags) + 2 * pad_x + 4
            w = max(w, min(need, w * 1.6))
        inner_w = w - 2 * pad_x
        for flag, style, _definition in flags:   # l'option dont dépend la règle, sur la boîte elle-même
            # Au-delà, le nom et la valeur passent sur deux lignes plutôt que d'être coupés.
            name, _, value = flag.partition(" : ")
            bold = style.get("weight") != "normal"
            parts_ = [flag] if _text_width(flag, 11.5 * ctx.scale, bold) <= inner_w or not value else [name, f": {value}"]
            lines.extend((f"n-flag {flag_classes(style)}", part, 11.5 * ctx.scale, bold, _definition) for part in parts_)
        pad_y = 9 * dens + {"rect": 0, "pill": 2, "hexagon": 2, "circle": 16, "diamond": 26}[shape]
        h = pad_y * 2 + sum(18 if cls == "n-label" else 15 for cls, *_ in lines) * max(ctx.scale, 1) + (22 if mark["show_status"] else 0)
        if shape in ("circle", "diamond"):
            w += 28
        nodes.append({"id": ent["id"], "ent": ent, "mark": mark, "w": w, "h": h, "pad_x": pad_x, "pad_y": pad_y, "lines": lines})
    drawn = {n["id"] for n in nodes}
    links = []
    for link in ctx.case.get("links", []):
        if link["from"] not in drawn or link["to"] not in drawn:
            continue
        mark = next((m for m in link_marks if _matches(m.get("where"), link)), None)
        if mark is not None:
            links.append({**link, "mark": mark})
    return nodes, links


def _ranks(nodes: list[dict], links: list[dict]) -> dict[str, int]:
    ids = [n["id"] for n in nodes]
    structural = [l for l in links if l["type"] in ACYCLIC_LINK_TYPES] or links
    out: dict[str, list[str]] = {i: [] for i in ids}
    state: dict[str, int] = {}
    kept: list[tuple[str, str]] = []

    def visit(node):
        state[node] = 1
        for nxt in [l["to"] for l in structural if l["from"] == node]:
            if state.get(nxt) == 1:
                continue  # arête de retour : ignorée pour le rang
            kept.append((node, nxt))
            out[node].append(nxt)
            if state.get(nxt) is None:
                visit(nxt)
        state[node] = 2

    for node in ids:
        if state.get(node) is None:
            visit(node)
    rank = {i: 0 for i in ids}
    for _ in range(len(ids)):
        moved = False
        for src, dst in kept:
            if rank[dst] < rank[src] + 1:
                rank[dst] = rank[src] + 1
                moved = True
        if not moved:
            break
    return rank


def _order_ranks(nodes: list[dict], links: list[dict], rank: dict[str, int]) -> list[list[dict]]:
    layers: dict[int, list[dict]] = {}
    for node in nodes:
        layers.setdefault(rank[node["id"]], []).append(node)
    ordered = [layers[r] for r in sorted(layers)]
    position = {}
    for layer in ordered:
        for i, node in enumerate(layer):
            position[node["id"]] = i
    for li in range(1, len(ordered)):
        layer = ordered[li]

        def barycenter(node, _layer=layer):
            parents = [position[l["from"]] for l in links if l["to"] == node["id"] and l["from"] in position and rank[l["from"]] < rank[node["id"]]]
            return (sum(parents) / len(parents)) if parents else _layer.index(node)

        keyed = sorted(layer, key=lambda n: (barycenter(n), layer.index(n)))
        ordered[li] = keyed
        for i, node in enumerate(keyed):
            position[node["id"]] = i
    return ordered


def _route(sx, sy, ex, ey, route: str, axis: str, offset: float = 0) -> tuple[str, float]:
    """Chemin SVG et angle (degrés) de la pointe."""
    if axis == "down":
        forward = ey > sy + 6
        if route == "straight" or not forward:
            if not forward:
                bend = max(40, abs(ex - sx) * 0.5)
                return f"M{sx:.1f} {sy:.1f}C{sx:.1f} {sy + bend:.1f} {ex:.1f} {ey - bend:.1f} {ex:.1f} {ey:.1f}", 90
            return f"M{sx:.1f} {sy:.1f}L{ex:.1f} {ey:.1f}", math.degrees(math.atan2(ey - sy, ex - sx))
        if route == "curve":
            mid = (ey - sy) * 0.5
            return f"M{sx:.1f} {sy:.1f}C{sx:.1f} {sy + mid:.1f} {ex:.1f} {ey - mid:.1f} {ex:.1f} {ey:.1f}", 90
        if abs(ex - sx) < 1:
            return f"M{sx:.1f} {sy:.1f}V{ey:.1f}", 90
        my = sy + (ey - sy) * 0.5 + offset
        r = min(8, abs(ex - sx) / 2, abs(my - sy), abs(ey - my))
        d = 1 if ex > sx else -1
        return (f"M{sx:.1f} {sy:.1f}V{my - r:.1f}Q{sx:.1f} {my:.1f} {sx + d * r:.1f} {my:.1f}"
                f"H{ex - d * r:.1f}Q{ex:.1f} {my:.1f} {ex:.1f} {my + r:.1f}V{ey:.1f}"), 90
    forward = ex > sx + 6
    if route == "straight" or not forward:
        if not forward:
            bend = max(40, abs(ey - sy) * 0.5)
            return f"M{sx:.1f} {sy:.1f}C{sx + bend:.1f} {sy:.1f} {ex - bend:.1f} {ey:.1f} {ex:.1f} {ey:.1f}", 0
        return f"M{sx:.1f} {sy:.1f}L{ex:.1f} {ey:.1f}", math.degrees(math.atan2(ey - sy, ex - sx))
    if route == "curve":
        mid = (ex - sx) * 0.5
        return f"M{sx:.1f} {sy:.1f}C{sx + mid:.1f} {sy:.1f} {ex - mid:.1f} {ey:.1f} {ex:.1f} {ey:.1f}", 0
    if abs(ey - sy) < 1:
        return f"M{sx:.1f} {sy:.1f}H{ex:.1f}", 0
    mx = sx + (ex - sx) * 0.5 + offset
    r = min(8, abs(ey - sy) / 2, abs(mx - sx), abs(ex - mx))
    d = 1 if ey > sy else -1
    return (f"M{sx:.1f} {sy:.1f}H{mx - r:.1f}Q{mx:.1f} {sy:.1f} {mx:.1f} {sy + d * r:.1f}"
            f"V{ey - d * r:.1f}Q{mx:.1f} {ey:.1f} {mx + r:.1f} {ey:.1f}H{ex:.1f}"), 0


def _draw_graph(ctx: Context, view: dict, nodes: list[dict], links: list[dict], pos: dict, size: tuple[float, float],
                axis: str, fixed_step: int | None, extra: str = "") -> str:
    time = with_defaults(view.get("time") or {"brick": "time.stepper"})
    radius = RADIUS[ctx.tokens.get("corners", "soft")]
    parts = [extra]

    # Ports répartis sur le bord pour que les liens ne se superposent pas
    incoming: dict[str, list[dict]] = {}
    outgoing: dict[str, list[dict]] = {}
    for link in links:
        incoming.setdefault(link["to"], []).append(link)
        outgoing.setdefault(link["from"], []).append(link)

    def centre(node_id):
        x, y, w, h = pos[node_id]
        return (x + w / 2, y + h / 2)

    key_axis = 0 if axis == "down" else 1
    for group, other in ((incoming, "from"), (outgoing, "to")):
        for lst in group.values():
            lst.sort(key=lambda l, o=other: centre(l[o])[key_axis])

    def port(node_id, link, side):
        x, y, w, h = pos[node_id]
        lst = (outgoing if side == "out" else incoming)[node_id]
        frac = (lst.index(link) + 1) / (len(lst) + 1)
        if axis == "down":
            return (x + w * frac, y + h if side == "out" else y)
        return (x + w if side == "out" else x, y + h * frac)

    link_svg = []
    for i, link in enumerate(links):
        mark = link["mark"]
        sx, sy = port(link["from"], link, "out")
        ex, ey = port(link["to"], link, "in")
        arrow = mark["arrow"]
        tip = 7 if arrow != "none" else 0
        if axis == "down":
            path, angle = _route(sx, sy, ex, ey - tip, mark["route"], axis, offset=(i % 3 - 1) * 5)
            ax, ay = ex, ey
        else:
            path, angle = _route(sx, sy, ex - tip, ey, mark["route"], axis, offset=(i % 3 - 1) * 5)
            ax, ay = ex, ey
        attrs = ""
        cls = f"lk lk-{mark['line']} lk-w{mark['weight']}"
        if fixed_step is None:
            attrs = f' data-ch="{ctx.changed(link["to"])}"'
            if ctx.frames and link["to"] in ctx.frames[ctx.step]["changed"]:
                cls += " is-changed"
        elif ctx.frames and link["to"] in ctx.frames[fixed_step]["changed"]:
            cls += " is-changed"
        flagged = link_flag(ctx.case, link)
        if flagged is not None:   # la règle tient à ce lien : trait renforcé dans la teinte choisie par l'auteur du cas
            cls += f" is-flagged {flag_classes(flagged)}"
        body = f'<path class="lk-path" d="{path}"/>'
        if arrow in ("end", "both"):
            body += f'<path class="lk-tip" d="M0 0L-8 -4.2L-8 4.2Z" transform="translate({ax:.1f} {ay:.1f}) rotate({angle:.1f})"/>'
        if arrow == "both":
            back = angle + 180
            body += f'<path class="lk-tip" d="M0 0L-8 -4.2L-8 4.2Z" transform="translate({sx:.1f} {sy:.1f}) rotate({back:.1f})"/>'
        text = fill_template(mark.get("label", ""), link)
        if text:
            mx, my = (sx + ex) / 2, (sy + ey) / 2
            body += f'<text class="lk-label" x="{mx:.1f}" y="{my - 4:.1f}" text-anchor="middle">{escape(text)}</text>'
        link_svg.append(f'<g class="{cls}"{attrs}>{body}</g>')
    parts.append(f'<g class="links">{"".join(link_svg)}</g>')

    for node in nodes:
        x, y, w, h = pos[node["id"]]
        mark = node["mark"]
        attrs, classes = _state_attrs(ctx, node["id"], mark.get("emphasis"), fixed_step) if mark["show_status"] or mark.get("emphasis") else ("", [])
        body = f'<title>{escape(node["lines"][0][1])}</title>'
        body += f'<path class="n-halo" d="{_node_shape_path(mark["shape"], w + 8, h + 8, radius + 4)}" transform="translate(-4 -4)"/>'
        body += f'<path class="n-shape" d="{_node_shape_path(mark["shape"], w, h, radius)}"/>'
        cy = node["pad_y"]
        inner = w - 2 * node["pad_x"]
        for cls, text, font_size, bold, *more in node["lines"]:
            cy += 18 if cls == "n-label" else 15
            shown = _fit(text, inner, font_size, bold, node["sv"])
            tip = f"<title>{escape(more[0])}</title>" if more and more[0] else ""   # définition de l'option, au survol
            body += f'<text class="{cls}" x="{node["pad_x"]:.1f}" y="{cy - 4:.1f}">{tip}{escape(shown)}</text>'
        if mark["show_status"]:
            body += f'<g class="n-status">{_status_svg(ctx, node["id"], node["pad_x"], cy + 16, fixed_step)}</g>'
        if mark["show_annotations"]:
            texts = [f["annotations"].get(node["id"], "") for f in ctx.frames]
            if any(texts):
                step = ctx.step if fixed_step is None else fixed_step
                current = texts[step] if texts else ""
                dyn = f" data-tx='{escape(json.dumps(texts, ensure_ascii=False), quote=True)}'" if fixed_step is None else ""
                empty = "" if current else " is-empty"
                ann_w = max(_text_width(t, 11, True) for t in texts) + 14
                ax0 = (w - ann_w) / 2
                body += (f'<g class="n-anno{empty}"{dyn}><rect x="{ax0:.1f}" y="{h + 5:.1f}" width="{ann_w:.1f}" height="18" rx="9"/>'
                         f'<text x="{w / 2:.1f}" y="{h + 18:.1f}" text-anchor="middle" data-tx-target="">{escape(current)}</text></g>')
        cls = " ".join(["n", f"n-{mark['shape']}", *classes])
        parts.append(f'<g class="{cls}"{attrs} transform="translate({x:.1f} {y:.1f})">{body}</g>')

    width, height = size
    hl = " tm-highlight" if time.get("highlight_changes", True) else ""
    dim = " tm-dim" if time.get("dim_unchanged") else ""
    ms = time.get("transition_ms", 160)
    label = escape(view.get("title") or "Schéma du cas", quote=True)
    return (f'<svg class="rep-svg{hl}{dim}" style="--w:{width:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" height="{height:.0f}" '
            f'style="--tm-ms:{ms}ms" role="group" aria-label="{label}">{"".join(parts)}</svg>')


def _layout_layers(ctx: Context, view: dict, sv: dict):
    layout = with_defaults(view["layout"])
    nodes, links = _prepare_nodes(ctx, view, sv)
    for node in nodes:
        node["sv"] = sv
    if not nodes:
        return None
    dens = DENSITY[ctx.tokens.get("density", "comfortable")]
    rank_gap = layout["rank_gap"] * dens
    node_gap = layout["node_gap"] * dens
    rank = _ranks(nodes, links)
    layers = _order_ranks(nodes, links, rank)
    anno = 22 if any(n["mark"]["show_annotations"] and any(f["annotations"].get(n["id"]) for f in ctx.frames) for n in nodes) else 0
    pos = {}
    margin = 16
    if layout["direction"] == "down":
        widths = [sum(n["w"] for n in layer) + node_gap * (len(layer) - 1) for layer in layers]
        total = max(widths)
        y = margin
        for layer, lw in zip(layers, widths):
            x = margin + (total - lw) / 2
            lh = max(n["h"] for n in layer)
            for node in layer:
                pos[node["id"]] = (x, y + (lh - node["h"]) / 2, node["w"], node["h"])
                x += node["w"] + node_gap
            y += lh + rank_gap + anno
        size = (total + margin * 2, y - rank_gap + margin)
        axis = "down"
    else:
        heights = [sum(n["h"] + anno for n in layer) + node_gap * (len(layer) - 1) for layer in layers]
        total = max(heights)
        x = margin
        for layer, lh in zip(layers, heights):
            y = margin + (total - lh) / 2
            lw = max(n["w"] for n in layer)
            for node in layer:
                pos[node["id"]] = (x + (lw - node["w"]) / 2, y, node["w"], node["h"])
                y += node["h"] + anno + node_gap
            x += lw + rank_gap
        size = (x - rank_gap + margin, total + margin * 2)
        axis = "right"
    sv["drawn"] = {"nodes": len(nodes), "links": len(links), "layers": len(layers)}
    sv["canvas"] = {"width": round(size[0]), "height": round(size[1])}
    if len(nodes) > 30:
        sv["warnings"].append(f"{len(nodes)} nœuds : au-delà de 30, un graphe devient difficile à lire ; préférer une table de trace.")
    return nodes, links, pos, size, axis, ""


def _layout_lanes(ctx: Context, view: dict, sv: dict):
    layout = with_defaults(view["layout"])
    nodes, links = _prepare_nodes(ctx, view, sv)
    for node in nodes:
        node["sv"] = sv
    if not nodes:
        return None
    dens = DENSITY[ctx.tokens.get("density", "comfortable")]
    rank_gap = layout["rank_gap"] * dens
    node_gap = layout["node_gap"] * dens
    lane_by = layout["lane_by"]

    def lane_of(ent):
        value = (ent.get("attrs") or {}).get(lane_by[5:]) if lane_by.startswith("attr.") else ent.get(lane_by)
        return _fmt_number(value) if value not in (None, "") else "—"

    lanes = [l for l in layout.get("lane_order") or []]
    for node in nodes:
        name = lane_of(node["ent"])
        node["lane"] = name
        if name not in lanes:
            lanes.append(name)
    lanes = [l for l in lanes if any(n["lane"] == l for n in nodes)]
    rank = _ranks(nodes, links)
    n_ranks = max(rank.values()) + 1
    col_w = [max((n["w"] for n in nodes if rank[n["id"]] == r), default=0) for r in range(n_ranks)]
    label_w = min(170, max(70, max(_text_width(l, 12, True) for l in lanes) + 24))
    anno = 22 if any(n["mark"]["show_annotations"] and any(f["annotations"].get(n["id"]) for f in ctx.frames) for n in nodes) else 0
    pos, bands = {}, []
    y = 8
    pad = 12 * dens
    col_x = []
    x = label_w + 12
    for w in col_w:
        col_x.append(x)
        x += w + rank_gap
    total_w = x - rank_gap + 16
    for lane in lanes:
        stacks: dict[int, list[dict]] = {}
        for node in nodes:
            if node["lane"] == lane:
                stacks.setdefault(rank[node["id"]], []).append(node)
        lane_h = max(sum(n["h"] + anno for n in stack) + node_gap * (len(stack) - 1) for stack in stacks.values()) + pad * 2
        for r, stack in stacks.items():
            sh = sum(n["h"] + anno for n in stack) + node_gap * (len(stack) - 1)
            ny = y + (lane_h - sh) / 2
            for node in stack:
                pos[node["id"]] = (col_x[r] + (col_w[r] - node["w"]) / 2, ny, node["w"], node["h"])
                ny += node["h"] + anno + node_gap
        bands.append((lane, y, lane_h))
        y += lane_h
    extra = ""
    for i, (lane, by, bh) in enumerate(bands):
        shown = _fit(lane, label_w - 16, 12, True, sv)
        extra += (f'<g class="lane lane-{i % 2}"><rect x="0" y="{by:.1f}" width="{total_w:.1f}" height="{bh:.1f}"/>'
                  f'<line x1="{label_w:.1f}" y1="{by:.1f}" x2="{label_w:.1f}" y2="{by + bh:.1f}"/>'
                  f'<text class="lane-label" x="10" y="{by + bh / 2 + 4:.1f}">{escape(shown)}</text></g>')
    size = (total_w, y + 8)
    sv["drawn"] = {"nodes": len(nodes), "links": len(links), "lanes": len(lanes)}
    sv["canvas"] = {"width": round(size[0]), "height": round(size[1])}
    if len(lanes) == 1 and lanes[0] == "—":
        sv["warnings"].append(f"Aucune entité ne renseigne « {lane_by} » : tout est dans un seul couloir.")
    return nodes, links, pos, size, "right", extra


def _render_graph_view(ctx: Context, view: dict, sv: dict, layouter) -> str:
    time = with_defaults(view.get("time") or {"brick": "time.stepper"})
    result = layouter(ctx, view, sv)
    if result is None:
        sv["warnings"].append("Aucune entité du cas ne correspond aux formes de cette vue : rien n'est dessiné.")
        return '<p class="rep-empty">Aucune entité de ce cas ne correspond à cette représentation.</p>'
    nodes, links, pos, size, axis, extra = result
    if time["brick"] == "time.small_multiples":
        figures = []
        for i, frame in enumerate(ctx.frames):
            svg = _draw_graph(ctx, view, nodes, links, pos, size, axis, fixed_step=i, extra=extra)
            current = " is-current" if i == ctx.step else ""
            figures.append(f'<figure class="sm-item{current}" data-step-is="{i}"><div class="rep-canvas">{svg}</div>'
                           f'<figcaption><span class="sm-n">{i + 1}</span> {escape(frame["title"])}</figcaption></figure>')
        if len(ctx.frames) > 8:
            sv["warnings"].append(f"{len(ctx.frames)} vignettes : au-delà de 8 étapes, les vignettes deviennent petites.")
        return f'<div class="sm" style="--sm-cols:{time["columns"]}">{"".join(figures)}</div>'
    fixed = None
    if time["brick"] == "time.static":
        fixed = 0 if time["step"] == "first" else max(0, ctx.n_steps - 1)
    svg = _draw_graph(ctx, view, nodes, links, pos, size, axis, fixed_step=fixed, extra=extra)
    return f'<div class="rep-canvas rep-scroll" tabindex="0" role="region" aria-label="{escape(view.get("title") or "Schéma", quote=True)} — défilement possible">{svg}</div>'


# ---------------------------------------------------------------------------
# Axe du temps
# ---------------------------------------------------------------------------

def _nice_step(span: float, target: int = 9) -> float:
    if span <= 0:
        return 1
    raw = span / target
    for candidate in (0.25, 0.5, 1, 2, 5, 7, 10, 14, 15, 20, 30, 60, 90, 120, 180, 365, 500, 1000):
        if candidate >= raw:
            return candidate
    return 10 ** math.ceil(math.log10(raw))


def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _render_timeline(ctx: Context, view: dict, sv: dict) -> str:
    layout = with_defaults(view["layout"])
    time = with_defaults(view.get("time") or {"brick": "time.cursor"})
    bar_marks = [with_defaults(m) for m in view["marks"] if m["brick"] == "mark.bar"]
    ms_marks = [with_defaults(m) for m in view["marks"] if m["brick"] == "mark.milestone"]
    items = []
    for ent in ctx.case.get("entities", []):
        attrs = ent.get("attrs") or {}
        start, end, at = _num(attrs.get(layout["start_attr"])), _num(attrs.get(layout["end_attr"])), _num(attrs.get(layout["at_attr"]))
        if start is not None and end is not None and end >= start:
            mark = next((m for m in bar_marks if _matches(m.get("where"), ent)), None)
            if mark:
                items.append({"ent": ent, "mark": mark, "kind": "bar", "a": start, "b": end})
                continue
        if at is not None:
            mark = next((m for m in ms_marks if _matches(m.get("where"), ent)), None)
            if mark:
                items.append({"ent": ent, "mark": mark, "kind": "milestone", "a": at, "b": at})
                continue
        sv["not_drawn"].append(ent["id"])
    step_at = []
    last = None
    for frame in ctx.frames:
        if frame.get("at") is not None:
            last = frame["at"]
        step_at.append(last)
    values = [i["a"] for i in items] + [i["b"] for i in items] + [v for v in step_at if v is not None]
    if not items or not values:
        sv["warnings"].append("Ce cas ne porte pas de données de temps (attrs.start/end ou attrs.at sur les entités) : la frise est vide.")
        return '<p class="rep-empty">Ce cas ne porte pas de données de temps : la frise ne peut pas être tracée.</p>'

    lo, hi = min(values), max(values)
    if hi == lo:
        hi = lo + 1
    span = hi - lo
    tick = _nice_step(span)
    lo_axis = math.floor(lo / tick) * tick
    hi_axis = math.ceil(hi / tick) * tick
    row_by = layout["row_by"]
    rows: list[str] = []
    for item in items:
        ent = item["ent"]
        item["row"] = ent["id"] if row_by == "entity" else (ent.get(row_by) or "—")
        if item["row"] not in rows:
            rows.append(item["row"])
    row_h = layout["row_height"] * DENSITY[ctx.tokens.get("density", "comfortable")]
    label_w = 180
    plot_w = 600
    status_w = 140
    top = 34
    width = label_w + plot_w + status_w
    height = top + row_h * len(rows) + 14

    def x_of(value):
        return label_w + (value - lo_axis) / (hi_axis - lo_axis) * plot_w

    fmt = layout["axis_format"]
    parts = []
    grid = []
    value = lo_axis
    guard = 0
    while value <= hi_axis + 1e-9 and guard < 60:
        x = x_of(value)
        number = _fmt_number(int(value) if float(value).is_integer() else round(value, 2))
        # « J+{n} » devient « J-30 » pour une valeur négative, pas « J+-30 ».
        text = fmt.replace("+{n}", number) if value < 0 and "+{n}" in fmt else fmt.replace("{n}", number)
        grid.append(f'<line class="tl-grid" x1="{x:.1f}" y1="{top - 6}" x2="{x:.1f}" y2="{height - 8:.1f}"/>'
                    f'<text class="tl-tick" x="{x:.1f}" y="{top - 12}" text-anchor="middle">{escape(text)}</text>')
        value += tick
        guard += 1
    parts.append(f'<g class="tl-axis">{"".join(grid)}<line class="tl-base" x1="{label_w}" y1="{top - 6}" x2="{label_w + plot_w}" y2="{top - 6}"/></g>')

    for ri, row in enumerate(rows):
        y = top + ri * row_h
        if ri % 2:
            parts.append(f'<rect class="tl-row" x="0" y="{y:.1f}" width="{width}" height="{row_h:.1f}"/>')
        row_items = [i for i in items if i["row"] == row]
        if row_by == "entity":
            first = row_items[0]
            label = with_flags(fill_template(first["mark"]["label"], first["ent"]) or first["ent"]["id"], ctx.case, first["ent"]["id"], ctx.attributes)
        else:
            label = row
        shown = _fit(label, label_w - 18, 12.5, True, sv)
        parts.append(f'<text class="tl-label" x="10" y="{y + row_h / 2 + 4:.1f}"><title>{escape(label)}</title>{escape(shown)}</text>')

    fixed = None
    if time["brick"] == "time.static":
        fixed = 0 if time["step"] == "first" else max(0, ctx.n_steps - 1)

    if time["brick"] != "time.static" and any(v is not None for v in step_at):
        first_at = next(v for v in step_at if v is not None)
        xs = [x_of(v if v is not None else first_at) for v in step_at]
        cur = xs[ctx.step] if xs else label_w
        data_xs = " ".join(f"{x:.1f}" for x in xs)
        if time.get("shade_elapsed", True):
            ws = " ".join(f"{max(0, x - label_w):.1f}" for x in xs)
            parts.insert(0, f'<rect class="tl-elapsed" x="{label_w}" y="{top - 6}" width="{max(0, cur - label_w):.1f}" height="{height - top - 2:.1f}" data-ws="{ws}"/>')
        parts.append(f'<g class="tl-cursor" data-xs="{data_xs}" transform="translate({cur:.1f} 0)">'
                     f'<line x1="0" y1="{top - 4}" x2="0" y2="{height - 6:.1f}"/><path d="M-5 {top - 8}H5L0 {top}Z"/></g>')
    elif time["brick"] != "time.static":
        sv["warnings"].append("Aucune étape ne porte de champ « at » : le curseur temporel n'est pas affiché.")

    for item in items:
        ent, mark = item["ent"], item["mark"]
        ri = rows.index(item["row"])
        y = top + ri * row_h
        attrs, classes = _state_attrs(ctx, ent["id"], mark.get("emphasis"), fixed) if mark["show_status"] or mark.get("emphasis") else ("", [])
        label = fill_template(mark["label"], ent) or ent["id"]
        body = f"<title>{escape(label)}</title>"
        if item["kind"] == "bar":
            x1, x2 = x_of(item["a"]), x_of(item["b"])
            bw = max(4, x2 - x1)
            bh = min(22, row_h - 12)
            by = y + (row_h - bh) / 2
            body += f'<rect class="n-halo" x="{x1 - 3:.1f}" y="{by - 3:.1f}" width="{bw + 6:.1f}" height="{bh + 6:.1f}" rx="7"/>'
            body += f'<rect class="n-shape" x="{x1:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="4"/>'
            end_x = x2
            if row_by != "entity":
                inner = _fit(label, max(0, bw - 10), 11.5, False, sv) if bw > 60 else ""
                if inner:
                    body += f'<text class="tl-in" x="{x1 + 6:.1f}" y="{by + bh / 2 + 4:.1f}">{escape(inner)}</text>'
        else:
            cx = x_of(item["a"])
            cy = y + row_h / 2
            shape = mark["shape"]
            if shape == "circle":
                body += f'<circle class="n-halo" cx="{cx:.1f}" cy="{cy:.1f}" r="12"/><circle class="n-shape" cx="{cx:.1f}" cy="{cy:.1f}" r="8"/>'
            elif shape == "flag":
                body += (f'<path class="n-halo" d="M{cx - 4:.1f} {cy - 14:.1f}h18v16h-18z"/>'
                         f'<path class="n-shape" d="M{cx:.1f} {cy + 10:.1f}V{cy - 10:.1f}H{cx + 12:.1f}L{cx + 8:.1f} {cy - 5:.1f}L{cx + 12:.1f} {cy:.1f}H{cx:.1f}"/>')
            else:
                body += (f'<path class="n-halo" d="M{cx:.1f} {cy - 13:.1f}L{cx + 13:.1f} {cy:.1f}L{cx:.1f} {cy + 13:.1f}L{cx - 13:.1f} {cy:.1f}Z"/>'
                         f'<path class="n-shape" d="M{cx:.1f} {cy - 9:.1f}L{cx + 9:.1f} {cy:.1f}L{cx:.1f} {cy + 9:.1f}L{cx - 9:.1f} {cy:.1f}Z"/>')
            end_x = cx + 10
            if row_by != "entity":
                body += f'<text class="tl-in tl-out" x="{cx + 14:.1f}" y="{cy - 8:.1f}">{escape(_fit(label, 120, 11, False, sv))}</text>'
        if mark["show_status"]:
            sx = max(end_x + 10, 0) if row_by != "entity" else label_w + plot_w + 12
            body += f'<g class="n-status">{_status_svg(ctx, ent["id"], sx, y + row_h / 2 + 4, fixed)}</g>'
        cls = " ".join(["n", f"tl-{item['kind']}", *classes])
        parts.append(f'<g class="{cls}"{attrs}>{body}</g>')

    sv["drawn"] = {"bars": sum(1 for i in items if i["kind"] == "bar"), "milestones": sum(1 for i in items if i["kind"] == "milestone"), "rows": len(rows)}
    sv["canvas"] = {"width": round(width), "height": round(height)}
    sv["axis"] = {"from": lo_axis, "to": hi_axis, "tick": tick}
    hl = " tm-highlight" if time.get("highlight_changes", True) else ""
    label = escape(view.get("title") or "Frise", quote=True)
    svg = (f'<svg class="rep-svg rep-timeline{hl}" viewBox="0 0 {width} {height:.0f}" width="{width}" height="{height:.0f}" '
           f'role="group" aria-label="{label}">{"".join(parts)}</svg>')
    return f'<div class="rep-canvas rep-scroll" tabindex="0" role="region" aria-label="{label} — défilement possible">{svg}</div>'


# ---------------------------------------------------------------------------
# Grille
# ---------------------------------------------------------------------------

def _render_grid(ctx: Context, view: dict, sv: dict) -> str:
    layout = with_defaults(view["layout"])
    time = with_defaults(view.get("time") or {"brick": "time.stepper"})
    marks = [with_defaults(m) for m in view["marks"]]
    rows_kind = layout["rows"]
    fixed = None
    if time["brick"] == "time.static":
        fixed = 0 if time["step"] == "first" else max(0, ctx.n_steps - 1)
    head, body = [], []
    grid_cls = before = ""

    def th(text, extra="", cls=""):
        return f'<th scope="col"{extra} class="{cls}">{escape(text)}</th>'

    def cell_class(mark):
        return f"al-{mark.get('align', 'start')} w-{mark.get('width', 'normal')}" + (" strong" if mark.get("weight") == "strong" else "")

    if rows_kind == "entities":
        entities = [e for e in ctx.case.get("entities", []) if _matches(layout.get("where"), e)]
        sv["not_drawn"] = [e["id"] for e in ctx.case.get("entities", []) if e not in entities]
        for mark in marks:
            if mark["brick"] == "mark.cell":
                head.append(th(mark["header"], cls=cell_class(mark)))
            elif mark["brick"] == "mark.cells_per_step":
                for i, frame in enumerate(ctx.frames):
                    text = fill_template(mark["header"], {"n": i + 1, "title": frame["title"]}) or str(i + 1)
                    current = " is-current" if i == ctx.step and fixed is None else ""
                    dyn = f' data-step-is="{i}"' if fixed is None else ""
                    head.append(f'<th scope="col" class="col-step{current}"{dyn} title="{escape(frame["title"], quote=True)}">{escape(text)}</th>')
        for ent in entities[: layout["max_rows"]]:
            cells = []
            for mark in marks:
                if mark["brick"] == "mark.cell":
                    cls = cell_class(mark)
                    if mark["content"] == "status":
                        pill = _status_html(ctx, ent["id"], fixed, "full")
                        if fixed is None:
                            # Le statut change d'une étape à l'autre : la case réserve la place du libellé le plus long.
                            labels = dict.fromkeys(ctx.label(ctx.status_at(ent["id"], i), "full") for i in range(len(ctx.frames)))
                            sizers = "".join(f'<span class="st tx-size" aria-hidden="true"><svg class="st-ic" width="14" height="14"></svg>'
                                             f'<span class="st-tx">{escape(label)}</span></span>' for label in labels)
                            pill = f'<span class="tx-stack">{pill}{sizers}</span>'
                        cells.append(f'<td class="{cls}">{pill}</td>')
                    elif mark["content"] == "annotation":
                        texts = [f["annotations"].get(ent["id"], "") or (f["states"].get(ent["id"], {}).get("note", "")) for f in ctx.frames]
                        step = ctx.step if fixed is None else fixed
                        current = texts[step] if texts else ""
                        dyn = f" data-tx='{escape(json.dumps(texts, ensure_ascii=False), quote=True)}'" if fixed is None else ""
                        # Les textes des autres étapes sont posés, invisibles, dans la même case : la cellule garde
                        # la taille du plus long, et le tableau ne bouge pas d'une étape à l'autre.
                        sizers = "".join(f'<span class="tx-size" aria-hidden="true">{escape(t)}</span>' for t in dict.fromkeys(texts) if t) if fixed is None else ""
                        cells.append(f'<td class="{cls} cell-anno"><span class="tx-stack"><span{dyn} data-tx-target="">{escape(current)}</span>{sizers}</span></td>')
                    else:
                        text = fill_template(mark["text"], ent)
                        tag = "th" if mark is marks[0] else "td"
                        scope = ' scope="row"' if tag == "th" else ""
                        # L'en-tête de ligne porte aussi les options mises en avant de l'entité.
                        flags = "".join(f'<span class="cell-flag {flag_classes(st)}"{f' title="{escape(d, quote=True)}"' if d else ""}>{escape(f)}</span>'
                                        for f, st, d in entity_flag_items(ctx.case, ent["id"], ctx.attributes)) if tag == "th" else ""
                        cells.append(f'<{tag}{scope} class="{cls}">{escape(text)}{flags}</{tag}>')
                elif mark["brick"] == "mark.cells_per_step":
                    for i, frame in enumerate(ctx.frames):
                        current = " is-current" if i == ctx.step and fixed is None else ""
                        changed = " chg" if ent["id"] in frame["changed"] else ""
                        dyn = f' data-step-is="{i}"' if fixed is None else ""
                        cells.append(f'<td class="col-step{current}{changed}"{dyn}>{_status_html(ctx, ent["id"], i, mark["label"], dynamic=False)}</td>')
            body.append(f'<tr>{"".join(cells)}</tr>')
        if len(entities) > layout["max_rows"]:
            sv["warnings"].append(f"{len(entities) - layout['max_rows']} lignes non affichées (max_rows = {layout['max_rows']}).")
        sv["drawn"] = {"rows": min(len(entities), layout["max_rows"]), "columns": len(head)}

    elif rows_kind == "steps":
        entities = ctx.case.get("entities", [])
        for mark in marks:
            if mark["brick"] == "mark.cell":
                head.append(th(mark["header"], cls=cell_class(mark)))
            elif mark["brick"] == "mark.cells_per_entity":
                for ent in entities:
                    if _matches(mark.get("where"), ent):
                        head.append(th(with_flags(fill_template(mark["header"], ent) or ent["id"], ctx.case, ent["id"], ctx.attributes), cls="col-ent"))
        for i, frame in enumerate(ctx.frames[: layout["max_rows"]]):
            cells = []
            values = {"n": i + 1, "title": frame["title"], "note": frame["note"], "at": frame.get("at"),
                      "global": ctx.label(frame["global"]) if frame.get("global") else ""}
            for mark in marks:
                if mark["brick"] == "mark.cell":
                    cells.append(f'<td class="{cell_class(mark)}">{escape(fill_template(mark["text"], values))}</td>')
                elif mark["brick"] == "mark.cells_per_entity":
                    for ent in entities:
                        if _matches(mark.get("where"), ent):
                            changed = " chg" if ent["id"] in frame["changed"] else ""
                            cells.append(f'<td class="col-ent{changed}">{_status_html(ctx, ent["id"], i, mark["label"], dynamic=False)}</td>')
            current = " is-current" if i == ctx.step and fixed is None else ""
            dyn = f' data-step-is="{i}"' if fixed is None else ""
            body.append(f'<tr class="row-step{current}"{dyn}>{"".join(cells)}</tr>')
        sv["drawn"] = {"rows": min(len(ctx.frames), layout["max_rows"]), "columns": len(head)}

    elif rows_kind == "cases":
        scope = layout["cases_scope"]
        siblings = [s for s in ctx.siblings if scope == "study" or s["family"] == ctx.case.get("family")]
        for mark in marks:
            if mark["brick"] == "mark.cell":
                head.append(th(mark["header"], cls=cell_class(mark)))
            elif mark["brick"] == "mark.cells_per_dimension":
                for dim in ctx.dimensions:
                    head.append(th(dim.get("label") or dim["key"], cls="col-dim"))
        dim_labels = {d["key"]: {v["value"]: v["label"] for v in d["values"]} for d in ctx.dimensions}
        for sib in siblings[: layout["max_rows"]]:
            cells = []
            values = {"number": sib.get("label") or f"{sib['number']:02d}", "title": sib["title"], "family": sib["family"], "outcome": sib.get("outcome") or "", "key": sib["key"]}
            for mark in marks:
                if mark["brick"] == "mark.cell":
                    cells.append(f'<td class="{cell_class(mark)}">{escape(fill_template(mark["text"], values))}</td>')
                elif mark["brick"] == "mark.cells_per_dimension":
                    for dim in ctx.dimensions:
                        raw = sib["dimensions"].get(dim["key"])
                        text = dim_labels[dim["key"]].get(raw, "—") if raw is not None else "—"
                        cells.append(f'<td class="col-dim">{escape(text)}</td>')
            current = sib["key"] == ctx.case.get("key")
            cls = ' class="is-this-case" aria-current="true"' if current else ""
            body.append(f"<tr{cls}>{''.join(cells)}</tr>")
        if len(siblings) > layout["max_rows"]:
            sv["warnings"].append(f"{len(siblings) - layout['max_rows']} cas non affichés (max_rows = {layout['max_rows']}).")
        if not ctx.dimensions and any(m["brick"] == "mark.cells_per_dimension" for m in marks):
            sv["warnings"].append("L'étude ne déclare aucune dimension : la table de décision n'a pas de colonnes de conditions.")
        sv["drawn"] = {"rows": min(len(siblings), layout["max_rows"]), "columns": len(head)}

    else:  # lignes de calcul, champs, règles, états
        from . import render_ext
        extra = render_ext.grid_rows(ctx, view, layout, marks, fixed, sv, th, cell_class)
        head, body, grid_cls, before = extra["head"], extra["body"], extra["cls"], extra["before"]

    if not body:
        sv["warnings"].append("La grille n'a aucune ligne pour ce cas.")
        return '<p class="rep-empty">Rien à afficher dans cette table pour ce cas.</p>'
    zebra = " zebra" if layout.get("zebra") else ""
    hl = " tm-highlight" if time.get("highlight_changes", True) else ""
    caption = escape(view.get("title") or "Table")
    return (f'{before}<div class="rep-scroll" tabindex="0" role="region" aria-label="{escape(view.get("title") or "Table", quote=True)} — défilement possible">'
            f'<table class="rep-grid{grid_cls}{zebra}{hl}"><caption class="sr-only">{caption}</caption>'
            f'<thead><tr>{"".join(head)}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


# ---------------------------------------------------------------------------
# Assemblage
# ---------------------------------------------------------------------------

def status_map(statuses: list[dict]) -> dict[str, dict]:
    out = {}
    for status in statuses:
        label = status.get("label") or status["key"]
        short = status.get("short") or (label if len(label) <= 11 else label[:10].rstrip("_ ") + "…")
        out[status["key"]] = {"label": label, "short": short, "role": status.get("role", "neutral")}
    return out


def render(spec: dict, case: dict, frames: list[dict], statuses: list[dict], *, step: int = 0,
           siblings: list[dict] | None = None, dimensions: list[dict] | None = None,
           ruleset: dict | None = None, lifecycles: list[dict] | None = None, attributes: list[dict] | None = None) -> tuple[str, dict]:
    """Dessine la représentation pour un cas. Renvoie (fragment HTML, résumé structurel)."""
    from . import render_ext
    from .casemodel import default_status
    tokens = {"density": "comfortable", "corners": "soft", "text_scale": 1, "status_label": "full",
              "status_fill": "tint", "canvas": "grid", **(spec.get("tokens") or {})}
    smap = {**status_map(statuses), **render_ext.pseudo_statuses()}
    step = max(0, min(step, len(frames) - 1)) if frames else 0
    ctx = Context(case=case, frames=frames, statuses=smap, step=step, tokens=tokens,
                  siblings=siblings or [], dimensions=dimensions or [], scale=float(tokens["text_scale"]),
                  ruleset=ruleset or {}, lifecycles=lifecycles or [], default_status=default_status(statuses) or "", attributes=attributes or [])
    summary = Summary()
    compose = with_defaults(spec.get("compose") or {"brick": "compose.stack"})
    sections = []
    for view in spec["views"]:
        layout = view["layout"]["brick"]
        time = (view.get("time") or {}).get("brick") or ("time.cursor" if layout == "layout.timeline" else "time.stepper")
        sv = summary.view(view, layout, time)
        if layout == "layout.layers":
            inner = _render_graph_view(ctx, view, sv, _layout_layers)
        elif layout == "layout.lanes":
            inner = _render_graph_view(ctx, view, sv, _layout_lanes)
        elif layout == "layout.timeline":
            inner = _render_timeline(ctx, view, sv)
        elif layout in render_ext.LAYOUTS:
            inner = render_ext.LAYOUTS[layout](ctx, view, sv)
        else:
            inner = _render_grid(ctx, view, sv)
        if sv["canvas"] and sv["canvas"]["width"] > 1400:
            sv["warnings"].append(f"Schéma large ({sv['canvas']['width']} px) : défilement horizontal sur la plupart des écrans.")
        title = view.get("title") or ""
        sections.append({"id": view["id"], "title": title, "html": inner})

    kind = compose["brick"].split(".")[1]
    classes = ["rep", f"rep-{kind}", f"dens-{tokens['density']}", f"corners-{tokens['corners']}",
               f"canvas-{tokens['canvas']}", f"sfill-{tokens['status_fill']}", f"slabel-{tokens['status_label']}"]
    style = f"--rep-ts:{float(tokens['text_scale']):.2f}"
    if kind == "columns":
        ratio = compose.get("ratio") or [1] * len(sections)
        style += ";--rep-cols:" + " ".join(f"minmax(0,{r}fr)" for r in ratio)
    statuses_attr = escape(json.dumps({k: [v["role"], v["label"], v["short"]] for k, v in smap.items()}, ensure_ascii=False, separators=(",", ":")), quote=True)
    out = [f'<div class="{" ".join(classes)}" style="{style}" data-rep="" data-steps="{len(frames)}" data-step="{step}" data-statuses=\'{statuses_attr}\'>']
    if kind == "tabs" and len(sections) > 1:
        tabs = "".join(
            f'<button type="button" role="tab" class="rep-tab" id="reptab-{s["id"]}" aria-controls="repview-{s["id"]}" '
            f'aria-selected="{"true" if i == 0 else "false"}" tabindex="{0 if i == 0 else -1}">{escape(s["title"] or s["id"])}</button>'
            for i, s in enumerate(sections))
        out.append(f'<div class="rep-tabs" role="tablist" aria-label="Vues de la représentation">{tabs}</div>')
    for i, section in enumerate(sections):
        hidden = " hidden" if kind == "tabs" and i > 0 else ""
        role = f' role="tabpanel" aria-labelledby="reptab-{section["id"]}"' if kind == "tabs" and len(sections) > 1 else ""
        heading = f'<h4 class="rep-view-title">{escape(section["title"])}</h4>' if section["title"] and len(sections) > 1 and kind != "tabs" else ""
        out.append(f'<section class="rep-view" id="repview-{section["id"]}" data-view="{section["id"]}"{role}{hidden}>{heading}{section["html"]}</section>')
    out.append("</div>")

    used_statuses = sorted({s for f in frames for s in (e["status"] for e in f["states"].values()) if s})
    result = {
        "steps": len(frames),
        "step_rendered": step + 1 if frames else 0,
        "compose": compose["brick"],
        "tokens": tokens,
        "views": summary.views,
        "statuses_shown": [{"key": s, "label": smap.get(s, {}).get("label", s), "role": smap.get(s, {}).get("role", "neutral"),
                            "role_label": ROLE_LABELS.get(smap.get(s, {}).get("role", "neutral"))} for s in used_statuses],
    }
    result["text"] = summary_text(result, case)
    return "".join(out), result


def summary_text(summary: dict, case: dict) -> str:
    lines = [f"Cas « {case.get('title', '')} » : {len(case.get('entities', []))} entités, {len(case.get('links', []))} liens, {summary['steps']} étapes ; rendu à l'étape {summary['step_rendered']}.",
             f"Composition : {summary['compose']} ; {len(summary['views'])} vue(s) ; densité {summary['tokens']['density']}, libellé de statut {summary['tokens']['status_label']}."]
    for view in summary["views"]:
        drawn = ", ".join(f"{v} {k}" for k, v in view["drawn"].items()) or "rien"
        canvas = f" ; zone de {view['canvas']['width']}×{view['canvas']['height']} px" if view["canvas"] else ""
        lines.append(f"Vue « {view['title'] or view['id']} » ({view['layout']}, {view['time']}) : {drawn}{canvas}.")
        if view["not_drawn"]:
            lines.append(f"  Entités non dessinées (aucune forme ne leur correspond) : {', '.join(view['not_drawn'])}.")
        if view["truncated"]:
            lines.append(f"  {len(view['truncated'])} libellé(s) tronqué(s) : " + " ; ".join(f"« {t['text']} » → « {t['shown']} »" for t in view["truncated"][:6]) + ".")
        for note in view.get("notes", []):
            lines.append(f"  {note}")
        for warning in view["warnings"]:
            lines.append(f"  Attention : {warning}")
    # Ce que l'auteur du cas met sous les yeux du relecteur, pour qu'une IA sans image sache que c'est affiché.
    marked = [f"{h['entity']}.{h['attr']}" if "entity" in h else f"lien {h['link'][0]} → {h['link'][1]}"
              for h in case.get("highlights") or [] if isinstance(h, dict)]
    if marked:
        lines.append("Mis en avant sur le schéma : " + ", ".join(marked) + " (paramètres du cas, et sur l'entité ou le lien quand la vue les dessine).")
    focus = [f"étape {i + 1} : {', '.join(s['focus'])}" for i, s in enumerate(case.get("steps", [])) if s.get("focus")]
    if focus:
        lines.append("Désigné au relecteur (« À regarder ») : " + " ; ".join(focus) + ".")
    if summary["statuses_shown"]:
        lines.append("Statuts rencontrés : " + ", ".join(f"{s['label']} ({s['role_label']})" for s in summary["statuses_shown"]) + ". Chaque statut est rendu par une couleur de rôle, une icône et un libellé.")
    return "\n".join(lines)
