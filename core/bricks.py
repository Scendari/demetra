"""Catalogue de briques et validation des représentations.

Une représentation est un document JSON qui assemble des briques fournies par le site :
formes, dispositions, liaisons donnée→visuel, évolution dans le temps, composition.
Le site valide le document puis le dessine lui-même. Aucun code, aucun HTML et aucun
CSS fournis par l'auteur de la représentation ne sont exécutés ni injectés.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from jsonschema import Draft202012Validator

from .casemodel import ROLES, Report

SCHEMA_ID = "demetra.representation/1"
MAX_SPEC_BYTES = 24_000
MAX_VIEWS = 4
MAX_MARKS = 12

_TEMPLATE = {"type": "string", "maxLength": 120}
_SCALAR = {"type": ["string", "number", "boolean"]}
_WHERE = {
    "type": "object",
    "description": "Filtre : ne garder que les éléments dont les champs ont ces valeurs. Clés : type, group, id, attr.<nom>. Une valeur peut être une liste (au moins une doit correspondre).",
    "maxProperties": 4,
    "propertyNames": {"pattern": r"^(type|group|id|attr\.[A-Za-z0-9_.\-]{1,40})$"},
    "additionalProperties": {"oneOf": [_SCALAR, {"type": "array", "items": _SCALAR, "minItems": 1, "maxItems": 12}]},
}
_EMPHASIS = {
    "type": "array",
    "maxItems": 4,
    "description": "Mise en évidence conditionnelle, réévaluée à chaque étape.",
    "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["when", "effect"],
        "properties": {
            "when": {
                "type": "object",
                "additionalProperties": False,
                "minProperties": 1,
                "properties": {
                    "role": {"type": "array", "items": {"enum": ROLES}, "minItems": 1, "uniqueItems": True},
                    "status": {"type": "array", "items": {"type": "string", "maxLength": 40}, "minItems": 1, "maxItems": 12},
                    "changed": {"const": True},
                },
            },
            "effect": {"enum": ["halo", "bold", "fade"]},
        },
    },
}

ENTITY_FIELDS = ["id", "label", "type", "group"]
LINK_FIELDS = ["label", "type", "from", "to"]
STEP_FIELDS = ["n", "title", "note", "global", "at"]
CASE_FIELDS = ["number", "title", "family", "outcome", "key"]
VALUE_FIELDS = ["label", "op", "operation", "note", "unit", "step"]
FIELD_FIELDS = ["entity", "entity_label", "field"]
RULE_FIELDS = ["key", "then", "n"]
STATE_FIELDS = ["state", "key"]
MESSAGE_FIELDS = ["label", "from", "to", "n"]
ROW_FIELDS = {
    "entities": [*ENTITY_FIELDS, "attr.*"], "steps": STEP_FIELDS, "cases": CASE_FIELDS,
    "values": VALUE_FIELDS, "fields": FIELD_FIELDS, "rules": RULE_FIELDS, "states": STATE_FIELDS,
}
# Formes qui n'ont de sens que pour une nature de ligne de grille
ROW_MARKS = {
    "mark.cells_per_step": "entities", "mark.cells_per_entity": "steps", "mark.cells_per_dimension": "cases",
    "mark.value": "values", "mark.field": "fields", "mark.cells_per_condition": "rules", "mark.rule_result": "rules",
    "mark.cells_per_event": "states",
}
_DIM_KEY = {"type": "string", "pattern": r"^(auto|[A-Za-z0-9][A-Za-z0-9_.\-]{0,39})$", "default": "auto"}

FAMILIES = {
    "disposition": "Dispositions — où les éléments se placent",
    "forme": "Formes — ce qui est dessiné pour chaque élément",
    "liaison": "Liaisons donnée → visuel — quelle donnée du cas pilote quoi",
    "temps": "Évolution dans le temps — comment les étapes sont montrées",
    "composition": "Composition — comment plusieurs vues s'assemblent",
}

# Chaque brique : famille, titre, description, schéma de ses paramètres, exemple.
CATALOG: list[dict] = [
    # ------------------------------------------------------------------ dispositions
    {
        "brick": "layout.layers", "family": "disposition", "title": "Couches",
        "description": "Graphe en couches : chaque entité est placée après celles dont elle dépend. Lisible jusqu'à environ 30 nœuds.",
        "slot": "view.layout", "accepts_marks": ["mark.node", "mark.link"], "accepts_time": ["time.stepper", "time.small_multiples", "time.static"],
        "properties": {
            "direction": {"enum": ["down", "right"], "default": "down", "description": "Sens de lecture des dépendances."},
            "rank_gap": {"type": "integer", "minimum": 24, "maximum": 200, "default": 56, "description": "Espace entre deux couches."},
            "node_gap": {"type": "integer", "minimum": 12, "maximum": 160, "default": 28, "description": "Espace entre deux nœuds d'une même couche."},
        },
        "example": {"brick": "layout.layers", "direction": "down"},
    },
    {
        "brick": "layout.lanes", "family": "disposition", "title": "Couloirs",
        "description": "Couloirs parallèles : les entités sont rangées par acteur, type ou groupe, et avancent dans le sens des liens.",
        "slot": "view.layout", "accepts_marks": ["mark.node", "mark.link"], "accepts_time": ["time.stepper", "time.small_multiples", "time.static"],
        "properties": {
            "lane_by": {"type": "string", "pattern": r"^(type|group|attr\.[A-Za-z0-9_.\-]{1,40})$", "default": "group", "description": "Donnée qui décide du couloir : type, group ou attr.<nom>."},
            "lane_order": {"type": "array", "items": {"type": "string", "maxLength": 80}, "maxItems": 20, "description": "Ordre des couloirs (facultatif)."},
            "rank_gap": {"type": "integer", "minimum": 24, "maximum": 200, "default": 48},
            "node_gap": {"type": "integer", "minimum": 8, "maximum": 120, "default": 16},
        },
        "example": {"brick": "layout.lanes", "lane_by": "group"},
    },
    {
        "brick": "layout.timeline", "family": "disposition", "title": "Axe du temps",
        "description": "Frise : un axe horizontal gradué, une ligne par entité (ou par groupe). Les barres vont de attrs.start à attrs.end, les jalons se posent sur attrs.at ; le curseur suit le champ « at » des étapes.",
        "slot": "view.layout", "accepts_marks": ["mark.bar", "mark.milestone"], "accepts_time": ["time.cursor", "time.stepper", "time.static"],
        "properties": {
            "start_attr": {"type": "string", "pattern": r"^[A-Za-z0-9_.\-]{1,40}$", "default": "start"},
            "end_attr": {"type": "string", "pattern": r"^[A-Za-z0-9_.\-]{1,40}$", "default": "end"},
            "at_attr": {"type": "string", "pattern": r"^[A-Za-z0-9_.\-]{1,40}$", "default": "at"},
            "row_by": {"enum": ["entity", "group", "type"], "default": "entity", "description": "Une ligne par entité, par groupe ou par type."},
            "axis_format": {"type": "string", "maxLength": 24, "default": "J+{n}", "description": "Libellé des graduations ; {n} est la valeur."},
            "row_height": {"type": "integer", "minimum": 28, "maximum": 72, "default": 40},
        },
        "example": {"brick": "layout.timeline", "axis_format": "J+{n}"},
    },
    {
        "brick": "layout.grid", "family": "disposition", "title": "Grille",
        "description": "Tableau : une ligne par entité, par étape, par cas voisin, par ligne de calcul, par champ, par règle ou par état ; les colonnes sont des cellules (mark.cell et ses variantes). Sert aux tables de décision, de trace, de calcul, de règles et d'états.",
        "slot": "view.layout",
        "accepts_marks": ["mark.cell", "mark.cells_per_step", "mark.cells_per_entity", "mark.cells_per_dimension", "mark.value", "mark.field",
                          "mark.cells_per_condition", "mark.rule_result", "mark.cells_per_event"],
        "accepts_time": ["time.stepper", "time.static"],
        "properties": {
            "rows": {"enum": ["entities", "steps", "cases", "values", "fields", "rules", "states"], "default": "entities",
                     "description": "entities : une ligne par entité ; steps : par étape ; cases : par cas de la même famille (table de décision) ; values : par ligne de calcul (steps[].values) ; fields : par champ d'entité (avant/après) ; rules : par ligne du jeu de règles de l'étude ; states : par état du cycle de vie."},
            "where": {**_WHERE, "description": "Filtre des entités quand rows = entities ou fields."},
            "entity": {"type": "string", "maxLength": 40, "default": "auto", "description": "Quand rows = states : entité dont on suit le cycle de vie (auto : la première dont le type en déclare un)."},
            "cases_scope": {"enum": ["family", "study"], "default": "family", "description": "Quand rows = cases : cas de la même famille ou de toute l'étude."},
            "max_rows": {"type": "integer", "minimum": 5, "maximum": 200, "default": 60},
            "zebra": {"type": "boolean", "default": False},
        },
        "example": {"brick": "layout.grid", "rows": "entities"},
    },
    {
        "brick": "layout.matrix", "family": "disposition", "title": "Matrice croisée",
        "description": "Deux dimensions de l'étude croisées : une ligne par valeur de l'une, une colonne par valeur de l'autre. Chaque case rassemble les cas qui portent cette combinaison ; la case du cas affiché est mise en avant, les combinaisons sans cas restent visibles.",
        "slot": "view.layout", "accepts_marks": ["mark.tally"], "needs_marks": ["mark.tally"], "accepts_time": ["time.static"],
        "properties": {
            "rows": {**_DIM_KEY, "description": "Clé de la dimension en lignes (auto : la première dimension de l'étude)."},
            "columns": {**_DIM_KEY, "description": "Clé de la dimension en colonnes (auto : la deuxième)."},
            "cases_scope": {"enum": ["study", "family"], "default": "study", "description": "Cas pris en compte : toute l'étude ou la famille du cas affiché."},
        },
        "example": {"brick": "layout.matrix", "rows": "auto", "columns": "auto"},
    },
    {
        "brick": "layout.scale", "family": "disposition", "title": "Axe à bandes",
        "description": "Une échelle de nombres découpée en tranches (dimension qui déclare « bands »). Chaque borne est écrite avec le côté auquel elle appartient ; la mesure du cas (« measures ») y est placée.",
        "slot": "view.layout", "accepts_marks": ["mark.band", "mark.point"], "needs_marks": ["mark.band"], "accepts_time": ["time.static"],
        "properties": {
            "dimension": {**_DIM_KEY, "description": "Clé de la dimension à tranches (auto : la première qui en déclare)."},
        },
        "example": {"brick": "layout.scale", "dimension": "auto"},
    },
    {
        "brick": "layout.tree", "family": "disposition", "title": "Arbre de décision",
        "description": "Arbre tiré du jeu de règles de l'étude : chaque niveau teste une condition, chaque feuille est une conclusion. Le chemin suivi par le cas est tracé. L'arbre lit les lignes dans l'ordre (la première qui correspond l'emporte) ; pour une politique « collect », préférer la table de règles.",
        "slot": "view.layout", "accepts_marks": ["mark.decision", "mark.conclusion"], "needs_marks": ["mark.conclusion"], "accepts_time": ["time.static"],
        "properties": {
            "direction": {"enum": ["right", "down"], "default": "right", "description": "Sens de lecture, de la première condition vers les conclusions."},
            "max_leaves": {"type": "integer", "minimum": 4, "maximum": 40, "default": 24, "description": "Au-delà, l'arbre n'est pas dessiné : la table de règles reste lisible."},
        },
        "example": {"brick": "layout.tree", "direction": "right"},
    },
    {
        "brick": "layout.states", "family": "disposition", "title": "Diagramme d'états",
        "description": "Le cycle de vie déclaré par l'étude : un nœud par état, une flèche par transition permise, boucles et retours compris. L'état courant de l'entité suit les étapes ; la transition qui vient d'être empruntée est marquée.",
        "slot": "view.layout", "accepts_marks": ["mark.state", "mark.transition"], "needs_marks": ["mark.state"], "accepts_time": ["time.stepper", "time.static"],
        "properties": {
            "entity": {"type": "string", "maxLength": 40, "default": "auto", "description": "Entité suivie (auto : la première dont le type déclare un cycle de vie)."},
            "direction": {"enum": ["right", "down"], "default": "down", "description": "down : les états se suivent de haut en bas, le schéma reste étroit ; right : de gauche à droite, pour un cycle court."},
            "rank_gap": {"type": "integer", "minimum": 30, "maximum": 200, "default": 46, "description": "Espace entre deux rangs d'états ; de gauche à droite, il s'élargit seul pour loger le nom des évènements."},
            "node_gap": {"type": "integer", "minimum": 16, "maximum": 120, "default": 34},
        },
        "example": {"brick": "layout.states", "entity": "auto"},
    },
    {
        "brick": "layout.lifelines", "family": "disposition", "title": "Lignes de vie",
        "description": "Diagramme de séquence : une colonne par entité, le temps descend. Chaque message (steps[].messages) est une flèche entre deux colonnes, dans l'ordre des étapes ; un message perdu s'arrête en chemin.",
        "slot": "view.layout", "accepts_marks": ["mark.lifeline", "mark.message"], "needs_marks": ["mark.lifeline"], "accepts_time": ["time.stepper", "time.static"],
        "properties": {
            "where": {**_WHERE, "description": "Filtre des entités qui ont une ligne de vie."},
            "column_width": {"type": "integer", "minimum": 110, "maximum": 260, "default": 190},
            "row_height": {"type": "integer", "minimum": 30, "maximum": 64, "default": 44},
        },
        "example": {"brick": "layout.lifelines"},
    },
    # ------------------------------------------------------------------ formes
    {
        "brick": "mark.node", "family": "forme", "title": "Nœud",
        "description": "Une boîte par entité, avec libellé, lignes de détail et statut (icône + libellé).",
        "slot": "view.marks", "context": "entity",
        "properties": {
            "where": _WHERE,
            "shape": {"enum": ["rect", "pill", "circle", "diamond", "hexagon"], "default": "rect"},
            "size": {"enum": ["s", "m", "l"], "default": "m"},
            "label": {**_TEMPLATE, "default": "{id} · {label}", "description": "Gabarit de texte : {id}, {label}, {type}, {group}, {attr.<nom>}."},
            "sublabel": {**_TEMPLATE, "default": ""},
            "details": {"type": "array", "items": _TEMPLATE, "maxItems": 4, "description": "Lignes supplémentaires (gabarits). Une ligne dont tous les champs sont vides n'est pas écrite. Les options que le cas met en avant ({entity, attr, style} dans highlights) s'ajoutent d'elles-mêmes, dans le style choisi (gras par défaut)."},
            "show_status": {"type": "boolean", "default": True, "description": "Liaison statut → couleur de rôle + icône + libellé."},
            "show_annotations": {"type": "boolean", "default": True, "description": "Affiche l'annotation de l'étape pour cette entité."},
            "emphasis": _EMPHASIS,
        },
        "example": {"brick": "mark.node", "shape": "rect", "label": "{id} · {label}", "emphasis": [{"when": {"role": ["error"]}, "effect": "halo"}]},
    },
    {
        "brick": "mark.link", "family": "forme", "title": "Lien",
        "description": "Un trait par lien du cas. Un lien est dessiné par la première brique mark.link dont le filtre lui correspond.",
        "slot": "view.marks", "context": "link",
        "properties": {
            "where": {**_WHERE, "propertyNames": {"pattern": r"^(type)$"}, "description": "Filtre sur le type du lien."},
            "line": {"enum": ["solid", "dashed", "dotted"], "default": "solid"},
            "arrow": {"enum": ["end", "both", "none"], "default": "end"},
            "route": {"enum": ["elbow", "curve", "straight"], "default": "elbow", "description": "elbow : segments droits à angles arrondis ; curve : courbe ; straight : ligne droite."},
            "weight": {"enum": [1, 2, 3], "default": 1},
            "label": {**_TEMPLATE, "default": "", "description": "Gabarit : {label}, {type}, {from}, {to}."},
        },
        "example": {"brick": "mark.link", "where": {"type": "action"}, "line": "dashed", "label": "{type}"},
    },
    {
        "brick": "mark.bar", "family": "forme", "title": "Barre",
        "description": "Sur un axe du temps : une barre de attrs.start à attrs.end pour chaque entité qui porte ces deux attributs.",
        "slot": "view.marks", "context": "entity",
        "properties": {
            "where": _WHERE,
            "label": {**_TEMPLATE, "default": "{label}"},
            "show_status": {"type": "boolean", "default": True},
            "emphasis": _EMPHASIS,
        },
        "example": {"brick": "mark.bar", "label": "{label}"},
    },
    {
        "brick": "mark.milestone", "family": "forme", "title": "Jalon",
        "description": "Sur un axe du temps : un repère ponctuel posé sur attrs.at pour chaque entité qui porte cet attribut.",
        "slot": "view.marks", "context": "entity",
        "properties": {
            "where": _WHERE,
            "shape": {"enum": ["diamond", "circle", "flag"], "default": "diamond"},
            "label": {**_TEMPLATE, "default": "{label}"},
            "show_status": {"type": "boolean", "default": True},
            "emphasis": _EMPHASIS,
        },
        "example": {"brick": "mark.milestone", "shape": "diamond"},
    },
    {
        "brick": "mark.cell", "family": "forme", "title": "Cellule",
        "description": "Une colonne de grille. content = text : gabarit de texte ; status : statut à l'étape courante (lignes entities) ou état de la ligne (lignes states) ; annotation : annotation de l'étape.",
        "slot": "view.marks", "context": "row",
        "required": ["header"],
        "properties": {
            "header": {"type": "string", "maxLength": 60, "description": "En-tête de la colonne."},
            "content": {"enum": ["text", "status", "annotation"], "default": "text"},
            "text": {**_TEMPLATE, "default": "{label}", "description": "Gabarit selon les lignes : entités {id} {label} {type} {group} {attr.<nom>} ; étapes {n} {title} {note} {global} {at} ; cas {number} {title} {family} {outcome} {key} ; calcul {label} {op} {operation} {note} {unit} {step} ; champs {entity} {entity_label} {field} ; règles {key} {then} {n} ; états {state} {key}."},
            "align": {"enum": ["start", "center", "end"], "default": "start"},
            "width": {"enum": ["narrow", "normal", "wide"], "default": "normal"},
            "weight": {"enum": ["normal", "strong"], "default": "normal"},
        },
        "example": {"brick": "mark.cell", "header": "État", "content": "status"},
    },
    {
        "brick": "mark.cells_per_step", "family": "forme", "title": "Une colonne par étape",
        "description": "Grille par entités uniquement : ajoute une colonne par étape montrant le statut de l'entité à cette étape (table de trace). La colonne de l'étape courante est mise en avant.",
        "slot": "view.marks", "context": "row",
        "properties": {
            "header": {**_TEMPLATE, "default": "{n}", "description": "Gabarit de l'en-tête : {n}, {title}."},
            "label": {"enum": ["full", "short", "icon"], "default": "short", "description": "Niveau de détail du statut dans chaque cellule."},
        },
        "example": {"brick": "mark.cells_per_step", "header": "{n}"},
    },
    {
        "brick": "mark.cells_per_entity", "family": "forme", "title": "Une colonne par entité",
        "description": "Grille par étapes uniquement : ajoute une colonne par entité montrant son statut à chaque étape.",
        "slot": "view.marks", "context": "row",
        "properties": {
            "header": {**_TEMPLATE, "default": "{id}", "description": "Gabarit de l'en-tête : {id}, {label}."},
            "label": {"enum": ["full", "short", "icon"], "default": "short"},
            "where": _WHERE,
        },
        "example": {"brick": "mark.cells_per_entity", "header": "{id}"},
    },
    {
        "brick": "mark.cells_per_dimension", "family": "forme", "title": "Une colonne par dimension",
        "description": "Grille par cas uniquement : ajoute une colonne par dimension déclarée dans l'étude (table de décision). La ligne du cas affiché est mise en avant.",
        "slot": "view.marks", "context": "row",
        "properties": {},
        "example": {"brick": "mark.cells_per_dimension"},
    },
    {
        "brick": "mark.tally", "family": "forme", "title": "Case de matrice",
        "description": "Contenu de chaque case d'une matrice croisée : le résultat des cas de la combinaison (avec son statut), leur nombre, ou leurs numéros.",
        "slot": "view.marks",
        "properties": {
            "show": {"enum": ["outcome", "count"], "default": "outcome", "description": "outcome : résultat attendu des cas de la case ; count : nombre de cas."},
            "list_cases": {"type": "boolean", "default": True, "description": "Écrit les numéros des cas de la case."},
        },
        "example": {"brick": "mark.tally", "show": "outcome"},
    },
    {
        "brick": "mark.value", "family": "forme", "title": "Valeur chiffrée",
        "description": "Grille par lignes de calcul uniquement : une colonne de nombres alignés à droite, avec le signe de l'opération et l'unité. show = value : le nombre de la ligne ; result : le cumul après la ligne.",
        "slot": "view.marks", "context": "row",
        "required": ["header"],
        "properties": {
            "header": {"type": "string", "maxLength": 60, "description": "En-tête de la colonne."},
            "show": {"enum": ["value", "result"], "default": "value"},
            "signed": {"type": "boolean", "default": True, "description": "Fait précéder le nombre du signe de l'opération (+, −, ×, ÷)."},
        },
        "example": {"brick": "mark.value", "header": "Montant", "show": "value"},
    },
    {
        "brick": "mark.field", "family": "forme", "title": "Valeur d'un champ",
        "description": "Grille par champs uniquement : la valeur du champ à un moment donné. at = initial : avant la première étape ; current : à l'étape courante ; final : à la dernière. Un champ modifié porte la mention « modifié ».",
        "slot": "view.marks", "context": "row",
        "required": ["header"],
        "properties": {
            "header": {"type": "string", "maxLength": 60, "description": "En-tête de la colonne."},
            "at": {"enum": ["initial", "current", "final"], "default": "current"},
            "mark_changes": {"type": "boolean", "default": True, "description": "Signale par une mention écrite les valeurs qui diffèrent de la valeur de départ."},
        },
        "example": {"brick": "mark.field", "header": "Après", "at": "current"},
    },
    {
        "brick": "mark.cells_per_condition", "family": "forme", "title": "Une colonne par condition",
        "description": "Grille par règles uniquement : ajoute une colonne par condition du jeu de règles, avec la valeur attendue par chaque ligne (un tiret quand la condition est indifférente). La condition qui fait échouer une ligne est marquée.",
        "slot": "view.marks", "context": "row",
        "properties": {
            "case_values": {"type": "boolean", "default": True, "description": "Rappelle sous chaque en-tête la valeur du cas pour cette condition (prise dans ses dimensions ou sa configuration)."},
        },
        "example": {"brick": "mark.cells_per_condition"},
    },
    {
        "brick": "mark.rule_result", "family": "forme", "title": "Sort de la règle",
        "description": "Grille par règles uniquement : pour chaque ligne, ce qu'elle devient pour ce cas — retenue, écartée (elle correspond mais une autre l'emporte), ne correspond pas, ou pas encore examinée. Toujours une icône et un libellé.",
        "slot": "view.marks", "context": "row",
        "properties": {
            "header": {"type": "string", "maxLength": 60, "default": "Pour ce cas"},
        },
        "example": {"brick": "mark.rule_result", "header": "Pour ce cas"},
    },
    {
        "brick": "mark.cells_per_event", "family": "forme", "title": "Une colonne par évènement",
        "description": "Grille par états uniquement : ajoute une colonne par évènement du cycle de vie. Chaque case donne l'état d'arrivée, ou reste vide quand l'évènement n'est pas permis depuis cet état.",
        "slot": "view.marks", "context": "row",
        "properties": {
            "empty": {"type": "string", "maxLength": 12, "default": "—", "description": "Texte des cases sans transition."},
        },
        "example": {"brick": "mark.cells_per_event"},
    },
    {
        "brick": "mark.band", "family": "forme", "title": "Bande",
        "description": "Une tranche de l'axe à bandes : son libellé, ses bornes écrites en clair (borne incluse ou exclue) et le résultat qu'elle donne.",
        "slot": "view.marks",
        "properties": {
            "show_result": {"type": "boolean", "default": True, "description": "Écrit le résultat déclaré pour la tranche."},
            "show_range": {"type": "boolean", "default": True, "description": "Écrit les bornes de la tranche en toutes lettres."},
        },
        "example": {"brick": "mark.band"},
    },
    {
        "brick": "mark.point", "family": "forme", "title": "Point de mesure",
        "description": "La mesure du cas posée sur l'axe à bandes, avec sa valeur. others = true ajoute les mesures des autres cas de l'étude : on voit si chaque borne est encadrée.",
        "slot": "view.marks",
        "properties": {
            "others": {"type": "boolean", "default": True, "description": "Montre aussi les mesures des autres cas."},
        },
        "example": {"brick": "mark.point", "others": True},
    },
    {
        "brick": "mark.decision", "family": "forme", "title": "Test d'une condition",
        "description": "Nœud intérieur d'un arbre de décision : la condition testée. Les valeurs possibles sont écrites sur les branches.",
        "slot": "view.marks",
        "properties": {
            "shape": {"enum": ["rect", "pill", "hexagon"], "default": "hexagon"},
        },
        "example": {"brick": "mark.decision", "shape": "hexagon"},
    },
    {
        "brick": "mark.conclusion", "family": "forme", "title": "Conclusion",
        "description": "Feuille d'un arbre de décision : la conclusion de la ligne de règle atteinte, avec son statut si la ligne en déclare un.",
        "slot": "view.marks",
        "properties": {
            "show_key": {"type": "boolean", "default": True, "description": "Écrit la clé de la ligne de règle sous la conclusion."},
        },
        "example": {"brick": "mark.conclusion"},
    },
    {
        "brick": "mark.state", "family": "forme", "title": "État",
        "description": "Un nœud par état du cycle de vie, avec la couleur de rôle, l'icône et le libellé du statut. L'état courant porte la mention « état actuel » ; un état final a un double contour.",
        "slot": "view.marks",
        "properties": {
            "shape": {"enum": ["pill", "rect"], "default": "pill"},
            "show_visited": {"type": "boolean", "default": True, "description": "Garde la trace du parcours : états et transitions déjà traversés, états pas encore atteints en tirets."},
        },
        "example": {"brick": "mark.state", "shape": "pill"},
    },
    {
        "brick": "mark.transition", "family": "forme", "title": "Transition",
        "description": "Une flèche par transition permise, avec le nom de l'évènement. Les retours en arrière passent sous le schéma, les boucles sur soi au-dessus du nœud.",
        "slot": "view.marks",
        "properties": {
            "show_guard": {"type": "boolean", "default": False, "description": "Ajoute la garde entre crochets après le nom de l'évènement."},
        },
        "example": {"brick": "mark.transition"},
    },
    {
        "brick": "mark.lifeline", "family": "forme", "title": "Ligne de vie",
        "description": "Une colonne par entité dans un diagramme de séquence : un en-tête (libellé et statut à l'étape courante) et une ligne verticale.",
        "slot": "view.marks",
        "properties": {
            "label": {**_TEMPLATE, "default": "{label}"},
            "show_status": {"type": "boolean", "default": True},
        },
        "example": {"brick": "mark.lifeline", "label": "{label}"},
    },
    {
        "brick": "mark.message", "family": "forme", "title": "Message",
        "description": "Une flèche horizontale par message, de l'émetteur au destinataire. Un message perdu s'arrête avant d'arriver et porte la mention « perdu ».",
        "slot": "view.marks",
        "properties": {
            "label": {**_TEMPLATE, "default": "{label}", "description": "Gabarit : {label}, {from}, {to}, {n} (rang du message)."},
            "numbered": {"type": "boolean", "default": True, "description": "Numérote les messages dans l'ordre."},
        },
        "example": {"brick": "mark.message", "label": "{label}"},
    },
    # ------------------------------------------------------------------ liaisons
    {
        "brick": "bind.text", "family": "liaison", "title": "Texte ← données",
        "description": "Tout paramètre « gabarit » relie un texte aux données : écrire {label}, {id}, {type}, {group} ou {attr.<nom>} entre accolades. Les textes sont toujours échappés ; un champ absent donne une chaîne vide.",
        "slot": "paramètres label, sublabel, details, text, header", "properties": {},
        "example": {"label": "{id} · {label}", "sublabel": "{attr.owner}"},
    },
    {
        "brick": "bind.status", "family": "liaison", "title": "Statut → rôle visuel",
        "description": "show_status relie le statut courant d'une entité à son rôle visuel (défini par l'étude) : couleur, icône et libellé. L'icône est toujours présente : un statut n'est jamais indiqué par la couleur seule. Une représentation ne peut pas changer le rôle d'un statut.",
        "slot": "paramètre show_status ; cellules content = status", "properties": {},
        "example": {"show_status": True},
    },
    {
        "brick": "bind.filter", "family": "liaison", "title": "Filtre ← données",
        "description": "where choisit les éléments auxquels une forme s'applique, d'après type, group, id ou attr.<nom>. Une entité est dessinée par la première forme qui lui correspond.",
        "slot": "paramètre where", "properties": {},
        "example": {"where": {"type": ["condition", "result"]}},
    },
    {
        "brick": "bind.emphasis", "family": "liaison", "title": "Mise en évidence ← état",
        "description": "emphasis applique un effet (halo, bold, fade) quand le rôle ou le statut courant correspond, ou quand l'élément vient de changer. Réévalué à chaque étape.",
        "slot": "paramètre emphasis", "properties": {},
        "example": {"emphasis": [{"when": {"role": ["error", "blocked"]}, "effect": "halo"}, {"when": {"role": ["disabled"]}, "effect": "fade"}]},
    },
    {
        "brick": "bind.group", "family": "liaison", "title": "Couloir ← donnée",
        "description": "lane_by (couloirs) et row_by (axe du temps) rangent les entités d'après leur type, leur groupe ou un attribut.",
        "slot": "paramètres lane_by, row_by", "properties": {},
        "example": {"lane_by": "attr.acteur"},
    },
    {
        "brick": "bind.time", "family": "liaison", "title": "Position ← temps",
        "description": "Sur un axe du temps, start_attr, end_attr et at_attr désignent les attributs numériques qui placent barres et jalons ; le champ « at » de chaque étape place le curseur.",
        "slot": "paramètres start_attr, end_attr, at_attr", "properties": {},
        "example": {"start_attr": "debut", "end_attr": "fin"},
    },
    {
        "brick": "bind.all_cases", "family": "liaison", "title": "Ensemble des cas → vue",
        "description": "Certaines vues se calculent sur tous les cas de l'étude, pas sur le seul cas affiché : la matrice croisée, la table de décision, les mesures des autres cas sur l'axe à bandes. cases_scope choisit l'étude entière ou la famille du cas.",
        "slot": "paramètres cases_scope, others", "properties": {},
        "example": {"cases_scope": "study"},
    },
    {
        "brick": "bind.scale", "family": "liaison", "title": "Position ← nombre",
        "description": "Sur un axe à bandes, la position d'un point vient de « measures » du cas, et les bandes de « bands » de la dimension. Le site vérifie au dépôt que la mesure tombe dans la tranche que le cas déclare.",
        "slot": "paramètre dimension", "properties": {},
        "example": {"dimension": "montant"},
    },
    {
        "brick": "bind.match", "family": "liaison", "title": "Règle ↔ cas",
        "description": "Le sort de chaque ligne de règle vient de steps[].rows du cas : selected, discarded, failed (avec « on » : la condition en échec). Les lignes non citées restent « non examinées ».",
        "slot": "formes mark.rule_result, mark.cells_per_condition, mark.conclusion", "properties": {},
        "example": {"rows": {"L1": {"result": "failed", "on": "client"}, "L2": "selected"}},
    },
    {
        "brick": "bind.diff", "family": "liaison", "title": "Écart avant ↔ après",
        "description": "La valeur d'un champ vient de entities[].fields (départ) puis de steps[].fields (modifications). Une valeur qui diffère du départ est signalée par une mention écrite, jamais par la couleur seule.",
        "slot": "forme mark.field", "properties": {},
        "example": {"at": "current", "mark_changes": True},
    },
    # ------------------------------------------------------------------ temps
    {
        "brick": "time.stepper", "family": "temps", "title": "Pas à pas",
        "description": "Une étape à la fois, pilotée par le curseur d'étapes de l'application. Les positions ne bougent pas ; seuls les états changent.",
        "slot": "view.time",
        "properties": {
            "highlight_changes": {"type": "boolean", "default": True, "description": "Entoure ce qui vient de changer."},
            "dim_unchanged": {"type": "boolean", "default": False, "description": "Estompe ce qui n'a pas changé à cette étape."},
            "transition_ms": {"type": "integer", "minimum": 0, "maximum": 400, "default": 160, "description": "Durée de la transition (ignorée si l'utilisateur réduit les animations)."},
        },
        "example": {"brick": "time.stepper", "highlight_changes": True},
    },
    {
        "brick": "time.small_multiples", "family": "temps", "title": "Vignettes par étape",
        "description": "Toutes les étapes côte à côte, une vignette par étape : on compare sans mémoriser. La vignette de l'étape courante est mise en avant.",
        "slot": "view.time",
        "properties": {
            "columns": {"type": "integer", "minimum": 2, "maximum": 6, "default": 3},
            "highlight_changes": {"type": "boolean", "default": True},
        },
        "example": {"brick": "time.small_multiples", "columns": 3},
    },
    {
        "brick": "time.cursor", "family": "temps", "title": "Curseur temporel",
        "description": "Sur un axe du temps : un trait vertical se pose sur la date de l'étape courante et le temps écoulé est teinté.",
        "slot": "view.time",
        "properties": {
            "shade_elapsed": {"type": "boolean", "default": True},
            "highlight_changes": {"type": "boolean", "default": True},
        },
        "example": {"brick": "time.cursor"},
    },
    {
        "brick": "time.static", "family": "temps", "title": "État figé",
        "description": "Montre un seul état, sans suivre le curseur d'étapes : le premier ou le dernier.",
        "slot": "view.time",
        "properties": {"step": {"enum": ["first", "last"], "default": "last"}},
        "example": {"brick": "time.static", "step": "last"},
    },
    # ------------------------------------------------------------------ composition
    {
        "brick": "compose.stack", "family": "composition", "title": "Empilées",
        "description": "Les vues se suivent de haut en bas.",
        "slot": "compose", "properties": {},
        "example": {"brick": "compose.stack"},
    },
    {
        "brick": "compose.columns", "family": "composition", "title": "Côte à côte",
        "description": "Les vues sont placées en colonnes ; ratio donne leurs largeurs relatives. Repasse en pile sur écran étroit.",
        "slot": "compose",
        "properties": {"ratio": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 4}, "minItems": 2, "maxItems": 3, "default": [1, 1]}},
        "example": {"brick": "compose.columns", "ratio": [3, 2]},
    },
    {
        "brick": "compose.tabs", "family": "composition", "title": "Onglets",
        "description": "Une vue à la fois, choisie par onglet.",
        "slot": "compose", "properties": {},
        "example": {"brick": "compose.tabs"},
    },
]

BRICKS = {b["brick"]: b for b in CATALOG}

TOKENS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "description": "Réglages d'apparence communs à toutes les vues.",
    "properties": {
        "density": {"enum": ["compact", "comfortable", "spacious"], "default": "comfortable"},
        "corners": {"enum": ["sharp", "soft", "round"], "default": "soft"},
        "text_scale": {"type": "number", "minimum": 0.85, "maximum": 1.25, "default": 1},
        "status_label": {"enum": ["full", "short", "hidden"], "default": "full", "description": "Libellé du statut : complet, abrégé ou masqué (l'icône reste toujours affichée)."},
        "status_fill": {"enum": ["tint", "solid", "outline"], "default": "tint", "description": "Façon de colorer une forme selon le rôle de son statut."},
        "canvas": {"enum": ["plain", "grid", "dots"], "default": "grid", "description": "Fond de la zone de dessin."},
    },
}


def _brick_schema(brick: dict) -> dict:
    props = {"brick": {"const": brick["brick"]}}
    props.update(brick.get("properties", {}))
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["brick", *brick.get("required", [])],
        "properties": props,
    }


def json_schema() -> dict:
    """Schéma JSON complet d'une représentation, publié par l'API."""
    defs = {name.replace(".", "_"): _brick_schema(b) for name, b in BRICKS.items() if b["family"] != "liaison"}

    def refs(prefix: str) -> list[dict]:
        return [{"$ref": f"#/$defs/{n.replace('.', '_')}"} for n in BRICKS if n.startswith(prefix)]

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "title": "Représentation Demetra",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema", "views"],
        "properties": {
            "schema": {"const": SCHEMA_ID},
            "compose": {"oneOf": refs("compose.")},
            "tokens": TOKENS_SCHEMA,
            "views": {
                "type": "array", "minItems": 1, "maxItems": MAX_VIEWS,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "layout", "marks"],
                    "properties": {
                        "id": {"type": "string", "pattern": "^[a-z][a-z0-9_-]{0,30}$"},
                        "title": {"type": "string", "maxLength": 80},
                        "layout": {"oneOf": refs("layout.")},
                        "marks": {"type": "array", "minItems": 1, "maxItems": MAX_MARKS, "items": {"oneOf": refs("mark.")}},
                        "time": {"oneOf": refs("time.")},
                    },
                },
            },
        },
        "$defs": defs,
    }


_TOP_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema", "views"],
    "properties": {
        "schema": {"const": SCHEMA_ID},
        "compose": {"type": "object"},
        "tokens": TOKENS_SCHEMA,
        "views": {"type": "array", "minItems": 1, "maxItems": MAX_VIEWS, "items": {"type": "object"}},
    },
}
_VIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "layout", "marks"],
    "properties": {
        "id": {"type": "string", "pattern": "^[a-z][a-z0-9_-]{0,30}$"},
        "title": {"type": "string", "maxLength": 80},
        "layout": {"type": "object"},
        "marks": {"type": "array", "minItems": 1, "maxItems": MAX_MARKS, "items": {"type": "object"}},
        "time": {"type": "object"},
    },
}

EXAMPLE_SPEC = {
    "schema": SCHEMA_ID,
    "compose": {"brick": "compose.stack"},
    "tokens": {"density": "comfortable"},
    "views": [
        {
            "id": "graphe",
            "title": "Graphe",
            "layout": {"brick": "layout.layers", "direction": "down"},
            "marks": [
                {"brick": "mark.node", "label": "{id} · {label}"},
                {"brick": "mark.link"},
            ],
            "time": {"brick": "time.stepper"},
        }
    ],
}

_PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
_ATTR = re.compile(r"^attr\.[A-Za-z0-9_.\-]{1,40}$")


def _json_path(base: str, path) -> str:
    out = base
    for part in path:
        out += f"[{part}]" if isinstance(part, int) else f".{part}"
    return out


def _schema_errors(instance, schema, base: str, report: Report):
    validator = Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
        path = _json_path(base, err.absolute_path)
        expected = None
        if err.validator == "enum":
            expected = err.validator_value
        elif err.validator == "additionalProperties":
            expected = sorted(schema.get("properties", {}).keys()) if not err.absolute_path else None
            extra = sorted(set(err.instance) - set(err.schema.get("properties", {})))
            report.error(path, "unknown_param", "Paramètre inconnu : " + ", ".join(extra) + ".", received=extra, expected=sorted(err.schema.get("properties", {})))
            continue
        elif err.validator in ("minimum", "maximum", "maxLength", "minItems", "maxItems", "pattern", "const", "type"):
            expected = {err.validator: err.validator_value}
        received = err.instance if isinstance(err.instance, (str, int, float, bool)) or err.instance is None else None
        report.error(path, f"schema.{err.validator}", err.message[:300], received=received, expected=expected)


def _check_template(text: str, allowed: list[str], path: str, report: Report):
    for name in _PLACEHOLDER.findall(text):
        if name in allowed or ("attr.*" in allowed and _ATTR.match(name)):
            continue
        report.error(path, "unknown_placeholder", f"Champ « {{{name}}} » inconnu dans ce gabarit.", received=name, expected=[a if a != "attr.*" else "attr.<nom>" for a in allowed])


def _check_brick(obj: Any, slot_prefix: str, path: str, report: Report) -> dict | None:
    if not isinstance(obj, dict) or not isinstance(obj.get("brick"), str):
        names = [n for n in BRICKS if n.startswith(slot_prefix)]
        report.error(path, "brick_required", "Chaque élément nomme sa brique dans le champ « brick ».", received=obj if not isinstance(obj, dict) else obj.get("brick"), expected=names, example=BRICKS[names[0]]["example"])
        return None
    name = obj["brick"]
    brick = BRICKS.get(name)
    if brick is None or not name.startswith(slot_prefix) or brick["family"] == "liaison":
        names = [n for n in BRICKS if n.startswith(slot_prefix)]
        report.error(f"{path}.brick", "unknown_brick", f"Brique « {name} » inconnue à cet emplacement. Si elle vous manque, signalez-la (POST /bricks/requests).", received=name, expected=names)
        return None
    before = len(report.errors)
    _schema_errors(obj, _brick_schema(brick), path, report)
    return brick if len(report.errors) == before else None


def with_defaults(obj: dict) -> dict:
    """Complète une brique avec les valeurs par défaut de son schéma."""
    brick = BRICKS.get(obj.get("brick"))
    out = dict(obj)
    if brick:
        for key, schema in brick.get("properties", {}).items():
            if key not in out and "default" in schema:
                out[key] = copy.deepcopy(schema["default"])
    return out


def validate_spec(spec: Any) -> Report:
    """Valide une représentation : structure, briques connues, paramètres, compatibilités."""
    report = Report()
    if not isinstance(spec, dict):
        report.error("spec", "type", "Une représentation est un objet JSON.", example=EXAMPLE_SPEC)
        return report
    size = len(json.dumps(spec, ensure_ascii=False))
    if size > MAX_SPEC_BYTES:
        report.error("spec", "too_large", f"Document trop volumineux ({size} octets).", expected={"max_bytes": MAX_SPEC_BYTES})
        return report
    _schema_errors(spec, _TOP_SCHEMA, "spec", report)
    if report.errors:
        if "schema" not in spec:
            report.issues[0].example = EXAMPLE_SPEC
        return report

    if "compose" in spec:
        _check_brick(spec["compose"], "compose.", "spec.compose", report)
        if spec["compose"].get("brick") == "compose.columns" and "ratio" in spec["compose"] and len(spec["compose"]["ratio"]) != len(spec["views"]):
            report.error("spec.compose.ratio", "ratio_mismatch", "« ratio » doit avoir une valeur par vue.", received=spec["compose"]["ratio"], expected={"length": len(spec["views"])})

    seen_ids = set()
    for vi, view in enumerate(spec["views"]):
        vp = f"spec.views[{vi}]"
        before = len(report.errors)
        _schema_errors(view, _VIEW_SCHEMA, vp, report)
        if len(report.errors) > before:
            continue
        if view["id"] in seen_ids:
            report.error(f"{vp}.id", "duplicate", f"Identifiant de vue « {view['id']} » en double.", received=view["id"])
        seen_ids.add(view["id"])

        layout = _check_brick(view["layout"], "layout.", f"{vp}.layout", report)
        rows = with_defaults(view["layout"]).get("rows") if layout and layout["brick"] == "layout.grid" else None
        if layout and layout["brick"] == "layout.matrix":
            full_layout = with_defaults(view["layout"])
            if full_layout["rows"] != "auto" and full_layout["rows"] == full_layout["columns"]:
                report.error(f"{vp}.layout.columns", "same_dimension", "Une matrice croise deux dimensions différentes.", received=full_layout["columns"])

        kinds = []
        for mi, mark in enumerate(view["marks"]):
            mp = f"{vp}.marks[{mi}]"
            brick = _check_brick(mark, "mark.", mp, report)
            if not brick:
                continue
            name = brick["brick"]
            kinds.append(name)
            if layout and name not in layout["accepts_marks"]:
                report.error(f"{mp}.brick", "incompatible_mark", f"La forme « {name} » ne se pose pas dans la disposition « {layout['brick']} ».", received=name, expected=layout["accepts_marks"])
                continue
            full = with_defaults(mark)
            if name in ("mark.node", "mark.bar", "mark.milestone"):
                for key in ("label", "sublabel"):
                    if isinstance(full.get(key), str):
                        _check_template(full[key], [*ENTITY_FIELDS, "attr.*"], f"{mp}.{key}", report)
                for di, detail in enumerate(full.get("details", []) or []):
                    _check_template(detail, [*ENTITY_FIELDS, "attr.*"], f"{mp}.details[{di}]", report)
            elif name == "mark.link":
                _check_template(full.get("label", ""), LINK_FIELDS, f"{mp}.label", report)
            elif name == "mark.cell":
                allowed = ROW_FIELDS.get(rows or "entities")
                if full["content"] == "text":
                    _check_template(full["text"], allowed, f"{mp}.text", report)
                elif rows != "entities" and not (rows == "states" and full["content"] == "status"):
                    report.error(f"{mp}.content", "incompatible_content", f"content = {full['content']} n'a de sens que pour une grille par entités (rows = entities)"
                                 + (" ou par états (rows = states)." if full["content"] == "status" else "."), received=full["content"], expected=["text"])
            elif name == "mark.lifeline":
                _check_template(full["label"], [*ENTITY_FIELDS, "attr.*"], f"{mp}.label", report)
            elif name == "mark.message":
                _check_template(full["label"], MESSAGE_FIELDS, f"{mp}.label", report)
            elif name in ROW_MARKS and name not in ("mark.cells_per_step", "mark.cells_per_entity", "mark.cells_per_dimension") and rows != ROW_MARKS[name]:
                report.error(f"{mp}.brick", "incompatible_rows", f"{name} demande une grille dont les lignes sont « {ROW_MARKS[name]} » (layout.rows = {ROW_MARKS[name]}).",
                             received=rows, expected=ROW_MARKS[name])
            elif name == "mark.cells_per_step":
                _check_template(full["header"], ["n", "title"], f"{mp}.header", report)
                if rows != "entities":
                    report.error(f"{mp}.brick", "incompatible_rows", "mark.cells_per_step demande une grille par entités (layout.rows = entities).", received=rows, expected="entities")
            elif name == "mark.cells_per_entity":
                _check_template(full["header"], ["id", "label"], f"{mp}.header", report)
                if rows != "steps":
                    report.error(f"{mp}.brick", "incompatible_rows", "mark.cells_per_entity demande une grille par étapes (layout.rows = steps).", received=rows, expected="steps")
            elif name == "mark.cells_per_dimension" and rows != "cases":
                report.error(f"{mp}.brick", "incompatible_rows", "mark.cells_per_dimension demande une grille par cas (layout.rows = cases).", received=rows, expected="cases")

        if layout:
            name = layout["brick"]
            if name in ("layout.layers", "layout.lanes") and "mark.node" not in kinds and not any(i.path.startswith(f"{vp}.marks") for i in report.errors):
                report.error(f"{vp}.marks", "missing_mark", f"La disposition « {name} » a besoin d'au moins une forme mark.node.", example=BRICKS["mark.node"]["example"])
            if name == "layout.timeline" and not ({"mark.bar", "mark.milestone"} & set(kinds)) and not any(i.path.startswith(f"{vp}.marks") for i in report.errors):
                report.error(f"{vp}.marks", "missing_mark", "Un axe du temps a besoin d'au moins une forme mark.bar ou mark.milestone.", example=BRICKS["mark.bar"]["example"])
            for needed in layout.get("needs_marks", []):
                if needed not in kinds and not any(i.path.startswith(f"{vp}.marks") for i in report.errors):
                    report.error(f"{vp}.marks", "missing_mark", f"La disposition « {name} » a besoin de la forme {needed}.", example=BRICKS[needed]["example"])

        if "time" in view:
            time = _check_brick(view["time"], "time.", f"{vp}.time", report)
            if time and layout and time["brick"] not in layout["accepts_time"]:
                report.error(f"{vp}.time.brick", "incompatible_time", f"« {time['brick']} » ne s'applique pas à la disposition « {layout['brick']} ».", received=time["brick"], expected=layout["accepts_time"])
    return report


def merge_spec(base: dict, patch: dict) -> dict:
    """Applique un ajustement à une représentation parente.

    Les objets sont fusionnés en profondeur ; les tableaux sont remplacés en bloc, sauf
    `views` : une vue de l'ajustement fusionne avec la vue de même `id`, une vue d'id
    nouveau est ajoutée, et {"id": …, "$remove": true} retire une vue.
    """
    result = copy.deepcopy(base)
    for key, value in (patch or {}).items():
        if key == "views" and isinstance(value, list) and isinstance(result.get("views"), list):
            views = result["views"]
            index = {v.get("id"): i for i, v in enumerate(views) if isinstance(v, dict)}
            for item in value:
                if not isinstance(item, dict):
                    views.append(item)
                    continue
                vid = item.get("id")
                if item.get("$remove") is True:
                    views[:] = [v for v in views if not (isinstance(v, dict) and v.get("id") == vid)]
                    index = {v.get("id"): i for i, v in enumerate(views) if isinstance(v, dict)}
                elif vid in index:
                    views[index[vid]] = _deep_merge(views[index[vid]], item)
                else:
                    views.append(copy.deepcopy(item))
                    index[vid] = len(views) - 1
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        elif value is None:
            result.pop(key, None)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _deep_merge(base: dict, patch: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in patch.items():
        if value is None:
            out.pop(key, None)
        elif isinstance(value, dict) and isinstance(out.get(key), dict) and not (key in ("layout", "time", "compose") and value.get("brick") and value.get("brick") != out[key].get("brick")):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def bricks_used(spec: dict) -> list[str]:
    used = []

    def add(name):
        if name and name not in used:
            used.append(name)

    add((spec.get("compose") or {}).get("brick") or "compose.stack")
    for view in spec.get("views", []):
        add(view.get("layout", {}).get("brick"))
        for mark in view.get("marks", []):
            add(mark.get("brick"))
        add((view.get("time") or {}).get("brick") or "time.stepper")
    return used


def catalog_payload() -> dict:
    families = []
    for key, title in FAMILIES.items():
        bricks = []
        for brick in CATALOG:
            if brick["family"] != key:
                continue
            entry = {"brick": brick["brick"], "title": brick["title"], "description": brick["description"], "slot": brick["slot"],
                     "params": brick.get("properties", {}), "example": brick["example"]}
            for extra in ("accepts_marks", "needs_marks", "accepts_time", "required"):
                if extra in brick:
                    entry[extra] = brick[extra]
            bricks.append(entry)
        families.append({"family": key, "title": title, "bricks": bricks})
    return {
        "schema": SCHEMA_ID,
        "principle": "Une représentation assemble ces briques dans un document JSON. Le site valide puis dessine ; il n'exécute aucun code fourni. Si une brique manque, signalez-la : POST /api/v1/bricks/requests.",
        "document": {"fields": {"schema": SCHEMA_ID, "compose": "une brique de composition (facultatif)", "tokens": TOKENS_SCHEMA["properties"], "views": f"1 à {MAX_VIEWS} vues {{id, title, layout, marks, time}}"}, "example": EXAMPLE_SPEC},
        "fixed_by_site": ["zone d'avis", "libellé et note d'étape", "curseur d'étapes", "légende des statuts", "rôle visuel de chaque statut (défini par l'étude)"],
        "roles": ROLES,
        "families": families,
    }


# ---------------------------------------------------------------------------
# Représentations système
# ---------------------------------------------------------------------------

_DEP = ["prerequisite", "dependency", "depends_on"]

SYSTEM_REPRESENTATIONS: list[dict] = [
    {
        "slug": "graphe-couches",
        "name": "Graphe en couches à statuts",
        "description": "Chaque entité est une boîte placée après ses prérequis ; les statuts changent étape par étape, ce qui vient de changer est entouré.",
        "manifest": {
            "families": ["workflow"],
            "shows_time": "pas à pas, positions fixes",
            "strengths": "Montre qui attend qui et comment une erreur ou une désactivation se propage.",
            "limits": "Au-delà d'une trentaine de nœuds, préférer la table de trace.",
            "max_entities": 30,
        },
        "spec": {
            "schema": SCHEMA_ID,
            "compose": {"brick": "compose.stack"},
            "tokens": {"density": "comfortable", "canvas": "grid"},
            "views": [{
                "id": "graphe", "title": "Graphe des dépendances",
                "layout": {"brick": "layout.layers", "direction": "down"},
                "marks": [
                    {"brick": "mark.node", "shape": "rect", "label": "{id} · {label}", "sublabel": "{type}",
                     "emphasis": [{"when": {"role": ["error", "blocked"]}, "effect": "bold"}, {"when": {"role": ["disabled"]}, "effect": "fade"}]},
                    {"brick": "mark.link", "where": {"type": _DEP}, "line": "solid", "route": "elbow"},
                    {"brick": "mark.link", "line": "dashed", "route": "curve", "label": "{label}"},
                ],
                "time": {"brick": "time.stepper", "highlight_changes": True},
            }],
        },
    },
    {
        "slug": "table-decision",
        "name": "Table de décision",
        "description": "En haut, les conditions du cas et leur évaluation étape par étape ; en bas, la table des cas de la même famille avec la ligne appliquée mise en avant.",
        "manifest": {
            "families": ["decision"],
            "shows_time": "ligne par ligne : chaque condition passe de « à évaluer » à son résultat",
            "strengths": "Compare d'un coup d'œil les combinaisons de conditions et leur résultat ; fait apparaître les lignes voisines.",
            "limits": "Ne montre ni ordre d'exécution ni dépendances.",
            "needs_dimensions": True,
        },
        "spec": {
            "schema": SCHEMA_ID,
            "compose": {"brick": "compose.stack"},
            "tokens": {"density": "comfortable", "canvas": "plain"},
            "views": [
                {
                    "id": "evaluation", "title": "Évaluation du cas",
                    "layout": {"brick": "layout.grid", "rows": "entities"},
                    "marks": [
                        {"brick": "mark.cell", "header": "Élément", "text": "{label}", "weight": "strong", "width": "wide"},
                        {"brick": "mark.cell", "header": "Valeur", "text": "{attr.value}"},
                        {"brick": "mark.cell", "header": "État", "content": "status"},
                        {"brick": "mark.cell", "header": "Motif", "content": "annotation", "width": "wide"},
                    ],
                    "time": {"brick": "time.stepper", "highlight_changes": True},
                },
                {
                    "id": "table", "title": "Table de décision de la famille",
                    "layout": {"brick": "layout.grid", "rows": "cases", "cases_scope": "family", "zebra": True},
                    "marks": [
                        {"brick": "mark.cell", "header": "N°", "text": "{number}", "width": "narrow", "align": "end"},
                        {"brick": "mark.cells_per_dimension"},
                        {"brick": "mark.cell", "header": "Résultat", "text": "{outcome}", "weight": "strong"},
                    ],
                    "time": {"brick": "time.static"},
                },
            ],
        },
    },
    {
        "slug": "frise-temporelle",
        "name": "Frise temporelle",
        "description": "Un axe du temps gradué : les périodes sont des barres, les échéances des jalons ; un curseur avance d'étape en étape.",
        "manifest": {
            "families": ["temporal"],
            "shows_time": "curseur sur l'axe, temps écoulé teinté",
            "strengths": "Montre les délais, les chevauchements et ce qui se passe avant ou après une échéance.",
            "limits": "Demande des attributs numériques start/end ou at sur les entités et un champ at sur les étapes.",
            "needs_time": True,
        },
        "spec": {
            "schema": SCHEMA_ID,
            "compose": {"brick": "compose.stack"},
            "tokens": {"density": "comfortable", "canvas": "plain"},
            "views": [{
                "id": "frise", "title": "Frise",
                "layout": {"brick": "layout.timeline", "axis_format": "J+{n}", "row_by": "entity"},
                "marks": [
                    {"brick": "mark.bar", "label": "{label}", "emphasis": [{"when": {"role": ["error"]}, "effect": "halo"}]},
                    {"brick": "mark.milestone", "shape": "diamond", "label": "{label}", "emphasis": [{"when": {"role": ["error"]}, "effect": "halo"}]},
                ],
                "time": {"brick": "time.cursor", "shade_elapsed": True},
            }],
        },
    },
    {
        "slug": "table-trace",
        "name": "Table de trace",
        "description": "Une ligne par entité, une colonne par étape : tout le déroulé d'un seul regard, sans mémoriser l'étape précédente.",
        "manifest": {
            "families": ["workflow", "decision", "temporal"],
            "shows_time": "une colonne par étape, étape courante mise en avant",
            "strengths": "Fonctionne pour toutes les familles et pour les cas nombreux en entités ; lisible au lecteur d'écran.",
            "limits": "Ne montre pas les liens entre entités.",
        },
        "spec": {
            "schema": SCHEMA_ID,
            "compose": {"brick": "compose.stack"},
            "tokens": {"density": "compact", "canvas": "plain"},
            "views": [{
                "id": "trace", "title": "Trace",
                "layout": {"brick": "layout.grid", "rows": "entities"},
                "marks": [
                    {"brick": "mark.cell", "header": "Entité", "text": "{id} · {label}", "weight": "strong", "width": "wide"},
                    {"brick": "mark.cells_per_step", "header": "{n}", "label": "short"},
                ],
                "time": {"brick": "time.stepper", "highlight_changes": True},
            }],
        },
    },
    {
        "slug": "graphe-et-trace",
        "name": "Graphe et trace côte à côte",
        "description": "Le graphe en couches à gauche, la table de trace à droite : la structure et le déroulé ensemble.",
        "manifest": {
            "families": ["workflow"],
            "shows_time": "pas à pas dans le graphe, colonnes dans la trace",
            "strengths": "Utile quand la question est « à quel moment » autant que « qui dépend de qui ».",
            "limits": "Demande un écran large.",
            "max_entities": 12,
        },
        "spec": {
            "schema": SCHEMA_ID,
            "compose": {"brick": "compose.columns", "ratio": [3, 2]},
            "tokens": {"density": "compact", "canvas": "grid"},
            "views": [
                {
                    "id": "graphe", "title": "Graphe",
                    "layout": {"brick": "layout.layers", "direction": "down"},
                    "marks": [
                        {"brick": "mark.node", "shape": "rect", "size": "s", "label": "{id} · {label}",
                         "emphasis": [{"when": {"role": ["error", "blocked"]}, "effect": "bold"}]},
                        {"brick": "mark.link", "where": {"type": _DEP}, "route": "elbow"},
                        {"brick": "mark.link", "line": "dashed", "route": "curve"},
                    ],
                    "time": {"brick": "time.stepper"},
                },
                {
                    "id": "trace", "title": "Trace",
                    "layout": {"brick": "layout.grid", "rows": "entities"},
                    "marks": [
                        {"brick": "mark.cell", "header": "Entité", "text": "{id}", "weight": "strong", "width": "narrow"},
                        {"brick": "mark.cells_per_step", "header": "{n}", "label": "icon"},
                    ],
                    "time": {"brick": "time.stepper"},
                },
            ],
        },
    },
    {
        "slug": "couloirs",
        "name": "Couloirs par groupe",
        "description": "Les entités sont rangées dans un couloir par groupe (acteur, service, niveau) et avancent de gauche à droite.",
        "manifest": {
            "families": ["workflow"],
            "shows_time": "pas à pas, positions fixes",
            "strengths": "Fait apparaître qui porte chaque élément quand plusieurs acteurs ou niveaux interviennent.",
            "limits": "Demande que les entités aient un groupe (champ group).",
            "needs_groups": True,
            "max_entities": 30,
        },
        "spec": {
            "schema": SCHEMA_ID,
            "compose": {"brick": "compose.stack"},
            "tokens": {"density": "comfortable", "canvas": "plain"},
            "views": [{
                "id": "couloirs", "title": "Couloirs",
                "layout": {"brick": "layout.lanes", "lane_by": "group"},
                "marks": [
                    {"brick": "mark.node", "shape": "pill", "size": "s", "label": "{label}",
                     "emphasis": [{"when": {"role": ["error", "blocked"]}, "effect": "bold"}]},
                    {"brick": "mark.link", "route": "curve"},
                ],
                "time": {"brick": "time.stepper", "highlight_changes": True},
            }],
        },
    },
    {
        "slug": "vignettes",
        "name": "Vignettes par étape",
        "description": "Le graphe répété une fois par étape, côte à côte : on compare les états sans faire défiler.",
        "manifest": {
            "families": ["workflow"],
            "shows_time": "une vignette par étape",
            "strengths": "Pour comparer précisément deux moments ; aucune animation.",
            "limits": "Prend de la place : à réserver aux cas de quelques nœuds et quelques étapes.",
            "max_entities": 8,
            "max_steps": 8,
        },
        "spec": {
            "schema": SCHEMA_ID,
            "compose": {"brick": "compose.stack"},
            "tokens": {"density": "compact", "canvas": "plain", "status_label": "short"},
            "views": [{
                "id": "vignettes", "title": "Étapes côte à côte",
                "layout": {"brick": "layout.layers", "direction": "down", "rank_gap": 36, "node_gap": 16},
                "marks": [
                    {"brick": "mark.node", "shape": "rect", "size": "s", "label": "{id}", "show_annotations": False},
                    {"brick": "mark.link", "route": "straight"},
                ],
                "time": {"brick": "time.small_multiples", "columns": 3},
            }],
        },
    },
    {
        "slug": "matrice-croisee",
        "name": "Matrice croisée",
        "description": "Deux dimensions croisées : chaque case donne le résultat des cas de la combinaison ; la case du cas affiché ressort, les combinaisons sans cas se voient.",
        "manifest": {
            "families": ["decision"],
            "shows_time": "vue d'ensemble figée ; le déroulé du cas reste dans le bloc d'étapes",
            "strengths": "Montre d'un regard toutes les combinaisons de deux facteurs, les trous et les résultats voisins.",
            "limits": "Deux dimensions seulement : au-delà, les cases mélangent plusieurs cas.",
            "needs": "two_dimensions",
        },
        "spec": {
            "schema": SCHEMA_ID,
            "compose": {"brick": "compose.stack"},
            "tokens": {"density": "comfortable", "canvas": "plain"},
            "views": [{
                "id": "matrice", "title": "Matrice des combinaisons",
                "layout": {"brick": "layout.matrix", "rows": "auto", "columns": "auto", "cases_scope": "study"},
                "marks": [{"brick": "mark.tally", "show": "outcome", "list_cases": True}],
                "time": {"brick": "time.static"},
            }],
        },
    },
    {
        "slug": "calcul-pas-a-pas",
        "name": "Calcul pas à pas",
        "description": "Une ligne par opération, dans l'ordre du calcul : libellé, montant signé, cumul. Les lignes à venir restent en place, estompées.",
        "manifest": {
            "families": ["decision"],
            "shows_time": "les lignes de l'étape courante ressortent, les suivantes sont estompées",
            "strengths": "Fait suivre un montant ligne à ligne : d'où vient chaque chiffre, dans quel ordre, avec quel cumul.",
            "limits": "Demande des lignes de calcul dans les étapes (steps[].values).",
            "needs": "values",
        },
        "spec": {
            "schema": SCHEMA_ID,
            "compose": {"brick": "compose.stack"},
            "tokens": {"density": "comfortable", "canvas": "plain"},
            "views": [{
                "id": "calcul", "title": "Calcul",
                "layout": {"brick": "layout.grid", "rows": "values"},
                "marks": [
                    {"brick": "mark.cell", "header": "Étape", "text": "{step}", "width": "narrow", "align": "end"},
                    {"brick": "mark.cell", "header": "Ligne", "text": "{label}", "weight": "strong", "width": "wide"},
                    {"brick": "mark.value", "header": "Montant", "show": "value"},
                    {"brick": "mark.value", "header": "Cumul", "show": "result", "signed": False},
                    {"brick": "mark.cell", "header": "Précision", "text": "{note}", "width": "wide"},
                ],
                "time": {"brick": "time.stepper", "highlight_changes": True},
            }],
        },
    },
    {
        "slug": "axe-a-bandes",
        "name": "Axe à bandes",
        "description": "Une échelle découpée en tranches : chaque borne dit de quel côté elle tombe, la mesure du cas est posée dessus, celles des autres cas autour.",
        "manifest": {
            "families": ["decision"],
            "shows_time": "vue figée ; le déroulé du cas reste dans le bloc d'étapes",
            "strengths": "Rend visibles les seuils et les valeurs limites : juste en dessous, pile dessus, juste au-dessus.",
            "limits": "Demande une dimension à tranches (bands) et une mesure par cas (measures).",
            "needs": "bands",
        },
        "spec": {
            "schema": SCHEMA_ID,
            "compose": {"brick": "compose.stack"},
            "tokens": {"density": "comfortable", "canvas": "plain"},
            "views": [{
                "id": "axe", "title": "Seuils",
                "layout": {"brick": "layout.scale", "dimension": "auto"},
                "marks": [{"brick": "mark.band"}, {"brick": "mark.point", "others": True}],
                "time": {"brick": "time.static"},
            }],
        },
    },
    {
        "slug": "avant-apres",
        "name": "Avant / après",
        "description": "Une ligne par champ : la valeur de départ, la valeur à l'étape courante, et la mention « modifié » sur ce qui a changé.",
        "manifest": {
            "families": ["workflow", "decision"],
            "shows_time": "la colonne « après » suit les étapes ; le champ qui vient de changer est entouré",
            "strengths": "Montre précisément ce qu'une règle modifie dans un dossier, champ par champ, et ce qu'elle laisse intact.",
            "limits": "Demande des champs sur les entités (entities[].fields, steps[].fields).",
            "needs": "fields",
        },
        "spec": {
            "schema": SCHEMA_ID,
            "compose": {"brick": "compose.stack"},
            "tokens": {"density": "comfortable", "canvas": "plain"},
            "views": [{
                "id": "champs", "title": "Champs",
                "layout": {"brick": "layout.grid", "rows": "fields"},
                "marks": [
                    {"brick": "mark.cell", "header": "Objet", "text": "{entity_label}", "width": "narrow"},
                    {"brick": "mark.cell", "header": "Champ", "text": "{field}", "weight": "strong"},
                    {"brick": "mark.field", "header": "Avant", "at": "initial", "mark_changes": False},
                    {"brick": "mark.field", "header": "Après", "at": "current"},
                ],
                "time": {"brick": "time.stepper", "highlight_changes": True},
            }],
        },
    },
    {
        "slug": "table-regles",
        "name": "Table de règles",
        "description": "Toutes les lignes du jeu de règles, condition par condition. Pour ce cas : la ligne retenue, celles qui correspondaient mais ont été écartées, celles qui ne correspondent pas et pourquoi.",
        "manifest": {
            "families": ["decision"],
            "shows_time": "les lignes sont examinées d'étape en étape ; leur sort s'affiche au fur et à mesure",
            "strengths": "Montre la règle appliquée parmi toutes les autres, et les lignes écartées : c'est là que se cachent les conflits de priorité.",
            "limits": "Demande un jeu de règles sur l'étude (ruleset) et le sort des lignes dans les cas (steps[].rows).",
            "needs": "ruleset",
        },
        "spec": {
            "schema": SCHEMA_ID,
            "compose": {"brick": "compose.stack"},
            "tokens": {"density": "comfortable", "canvas": "plain"},
            "views": [{
                "id": "regles", "title": "Jeu de règles",
                "layout": {"brick": "layout.grid", "rows": "rules"},
                "marks": [
                    {"brick": "mark.cell", "header": "Ligne", "text": "{key}", "weight": "strong", "width": "narrow"},
                    {"brick": "mark.rule_result", "header": "Pour ce cas"},
                    {"brick": "mark.cells_per_condition", "case_values": True},
                    {"brick": "mark.cell", "header": "Conclusion", "text": "{then}", "weight": "strong", "width": "wide"},
                ],
                "time": {"brick": "time.stepper", "highlight_changes": True},
            }],
        },
    },
    {
        "slug": "arbre-decision",
        "name": "Arbre de décision",
        "description": "Le jeu de règles déplié en arbre : une condition par niveau, une conclusion par feuille, le chemin du cas tracé d'un trait fort.",
        "manifest": {
            "families": ["decision"],
            "shows_time": "vue figée : le chemin complet du cas",
            "strengths": "Fait lire la décision comme une suite de questions ; convient à un jeu de règles court.",
            "limits": "Au-delà d'une dizaine de lignes ou de trois conditions, la table de règles se lit mieux.",
            "needs": "ruleset",
            "prefers": "small_ruleset",
        },
        "spec": {
            "schema": SCHEMA_ID,
            "compose": {"brick": "compose.stack"},
            "tokens": {"density": "comfortable", "canvas": "plain"},
            "views": [{
                "id": "arbre", "title": "Arbre de décision",
                "layout": {"brick": "layout.tree", "direction": "right"},
                "marks": [{"brick": "mark.decision", "shape": "hexagon"}, {"brick": "mark.conclusion", "show_key": True}],
                "time": {"brick": "time.static"},
            }],
        },
    },
    {
        "slug": "table-etats",
        "name": "Table d'états",
        "description": "Une ligne par état, une colonne par évènement : chaque case dit où l'on arrive, les cases vides sont les évènements refusés. La ligne de l'état courant suit les étapes.",
        "manifest": {
            "families": ["workflow"],
            "shows_time": "la ligne de l'état courant et la case de la transition empruntée suivent les étapes",
            "strengths": "Fait apparaître les trous : tout ce qui n'est pas permis depuis un état. Reste lisible quand les transitions sont nombreuses.",
            "limits": "Demande un cycle de vie sur l'étude (lifecycles).",
            "needs": "lifecycle",
            "prefers": "dense_lifecycle",
        },
        "spec": {
            "schema": SCHEMA_ID,
            "compose": {"brick": "compose.stack"},
            "tokens": {"density": "comfortable", "canvas": "plain"},
            "views": [{
                "id": "etats", "title": "États et évènements",
                "layout": {"brick": "layout.grid", "rows": "states", "entity": "auto"},
                "marks": [
                    {"brick": "mark.cell", "header": "État", "content": "status"},
                    {"brick": "mark.cells_per_event"},
                ],
                "time": {"brick": "time.stepper", "highlight_changes": True},
            }],
        },
    },
    {
        "slug": "diagramme-etats",
        "name": "Diagramme d'états",
        "description": "Le cycle de vie dessiné : un nœud par état, une flèche par transition, retours et boucles compris. L'état courant suit les étapes.",
        "manifest": {
            "families": ["workflow"],
            "shows_time": "l'état courant se déplace d'étape en étape, positions fixes",
            "strengths": "Fait voir le parcours d'un objet dans son cycle de vie, y compris les retours en arrière et les boucles.",
            "limits": "Au-delà d'une dizaine d'états ou de transitions très nombreuses, préférer la table d'états.",
            "needs": "lifecycle",
            "prefers": "sparse_lifecycle",
        },
        "spec": {
            "schema": SCHEMA_ID,
            "compose": {"brick": "compose.stack"},
            "tokens": {"density": "comfortable", "canvas": "plain"},
            "views": [{
                "id": "etats", "title": "Cycle de vie",
                "layout": {"brick": "layout.states", "entity": "auto", "direction": "down", "rank_gap": 44},
                "marks": [{"brick": "mark.state", "shape": "pill"}, {"brick": "mark.transition"}],
                "time": {"brick": "time.stepper", "highlight_changes": True},
            }],
        },
    },
    {
        "slug": "diagramme-sequence",
        "name": "Diagramme de séquence",
        "description": "Une colonne par acteur, le temps descend : chaque message est une flèche, dans l'ordre. Un message perdu s'arrête en chemin.",
        "manifest": {
            "families": ["workflow"],
            "shows_time": "les messages de l'étape courante ressortent, les suivants sont estompés",
            "strengths": "Montre qui parle à qui et dans quel ordre : appels entre services, relances, messages perdus.",
            "limits": "Demande des messages dans les étapes (steps[].messages) ; au-delà de huit acteurs, le schéma défile.",
            "needs": "messages",
        },
        "spec": {
            "schema": SCHEMA_ID,
            "compose": {"brick": "compose.stack"},
            "tokens": {"density": "comfortable", "canvas": "plain"},
            "views": [{
                "id": "sequence", "title": "Échanges",
                "layout": {"brick": "layout.lifelines"},
                "marks": [{"brick": "mark.lifeline", "label": "{label}", "show_status": True}, {"brick": "mark.message", "label": "{label}", "numbered": True}],
                "time": {"brick": "time.stepper", "highlight_changes": True},
            }],
        },
    },
]
