# Représentations : briques, création, ajustement, aperçu

Version {{version}}.

## Principe

Une représentation est un **document JSON** qui assemble des **briques fournies par le site**. Le site valide le document puis dessine lui-même en SVG/HTML. Il n'exécute **aucun code** : pas de HTML, de CSS ni de script dans une représentation.

Cinq familles de briques, détaillées avec leurs paramètres par `GET /api/v1/bricks` (public) :

| Famille | Briques | Rôle |
|---|---|---|
| Dispositions | `layout.layers`, `layout.lanes`, `layout.timeline`, `layout.grid`, `layout.matrix`, `layout.scale`, `layout.tree`, `layout.states`, `layout.lifelines` | Où les éléments se placent. |
| Formes | `mark.node`, `mark.link`, `mark.bar`, `mark.milestone`, `mark.cell`, `mark.cells_per_step`, `mark.cells_per_entity`, `mark.cells_per_dimension`, et pour les règles et processus : `mark.tally`, `mark.value`, `mark.field`, `mark.cells_per_condition`, `mark.rule_result`, `mark.cells_per_event`, `mark.band`, `mark.point`, `mark.decision`, `mark.conclusion`, `mark.state`, `mark.transition`, `mark.lifeline`, `mark.message` | Ce qui est dessiné pour chaque élément. |
| Liaisons donnée → visuel | gabarits `{label}`, `where`, `show_status`, `emphasis`, `lane_by`, `start_attr`… ; `bind.all_cases`, `bind.scale`, `bind.match`, `bind.diff` | Quelle donnée du cas pilote quoi. |
| Évolution dans le temps | `time.stepper`, `time.small_multiples`, `time.cursor`, `time.static` | Comment les étapes sont montrées. |
| Composition | `compose.stack`, `compose.columns`, `compose.tabs` | Comment plusieurs vues s'assemblent. |

Le schéma JSON complet est servi par `GET /api/v1/bricks/schema`.

## Le document

```json
{
  "schema": "demetra.representation/1",
  "compose": {"brick": "compose.columns", "ratio": [3, 2]},
  "tokens": {"density": "compact", "corners": "soft", "status_label": "full", "status_fill": "tint", "canvas": "grid"},
  "views": [
    {
      "id": "graphe", "title": "Graphe",
      "layout": {"brick": "layout.layers", "direction": "down"},
      "marks": [
        {"brick": "mark.node", "shape": "rect", "label": "{id} · {label}",
         "emphasis": [{"when": {"role": ["error", "blocked"]}, "effect": "halo"}]},
        {"brick": "mark.link", "where": {"type": "prerequisite"}, "route": "elbow"},
        {"brick": "mark.link", "line": "dashed", "label": "{type}"}
      ],
      "time": {"brick": "time.stepper", "highlight_changes": true}
    },
    {
      "id": "trace", "title": "Trace",
      "layout": {"brick": "layout.grid", "rows": "entities"},
      "marks": [
        {"brick": "mark.cell", "header": "Entité", "text": "{id}", "weight": "strong"},
        {"brick": "mark.cells_per_step", "header": "{n}", "label": "icon"}
      ],
      "time": {"brick": "time.stepper"}
    }
  ]
}
```

Règles d'assemblage :

- 1 à 4 vues ; chaque vue a un `id` unique, une disposition, 1 à 12 formes, et éventuellement une brique de temps.
- Chaque disposition accepte certaines formes et certaines briques de temps (`accepts_marks`, `accepts_time` dans le catalogue).
- Une entité est dessinée par la **première** forme dont le filtre `where` lui correspond ; un lien de même.
- Les gabarits de texte n'acceptent que des champs connus : `{id}`, `{label}`, `{type}`, `{group}`, `{attr.<nom>}` pour une entité ; `{label}`, `{type}`, `{from}`, `{to}` pour un lien ; `{n}`, `{title}`, `{note}`, `{global}`, `{at}` pour une étape ; `{number}`, `{title}`, `{family}`, `{outcome}`, `{key}` pour un cas.

## Seize représentations fournies

`GET /api/v1/representations` les liste avec leur identifiant ; `representation` accepte aussi leur `slug`.

### Enchaînements de tâches, groupes et temps : sept représentations

Elles lisent la structure commune à tous les cas : `entities`, `links`, `steps[].changes`, et pour la frise les attributs de temps.

| Représentation (`slug`) | Disposition et formes | Donnée lue | Quand la choisir |
|---|---|---|---|
| Graphe en couches à statuts (`graphe-couches`) | `layout.layers` + `mark.node`, `mark.link` | `entities`, `links`, `steps[].changes` | Des tâches qui dépendent les unes des autres : chaque boîte après ses prérequis, ce qui vient de changer est entouré. |
| Graphe et trace côte à côte (`graphe-et-trace`) | `layout.layers` + `layout.grid` | idem | La structure et tout le déroulé ensemble, sur un écran large. |
| Couloirs par groupe (`couloirs`) | `layout.lanes` + `mark.node`, `mark.link` | `entities[].group` | Les entités appartiennent à des acteurs, services ou niveaux distincts. |
| Vignettes par étape (`vignettes`) | `layout.layers` + `time.small_multiples` | idem graphe | Peu d'étapes et peu d'entités : comparer les états sans faire défiler. |
| Table de trace (`table-trace`) | `layout.grid` `rows: "entities"` + `mark.cells_per_step` | `steps[].changes` | Beaucoup d'entités ou d'étapes : une ligne par entité, une colonne par étape. |
| Table de décision (`table-decision`) | deux `layout.grid` | `dimensions`, `outcome`, cas de la même famille | Des conditions combinées : la ligne appliquée, parmi les cas voisins. |
| Frise temporelle (`frise-temporelle`) | `layout.timeline` + `mark.bar`, `mark.milestone` | `entities[].attrs.start`/`end`/`at`, `steps[].at` | Des délais et des échéances sur un axe du temps. |

### Règles et processus : neuf représentations

Chacune lit une donnée précise du cas ou de l'étude (chapitres `cases` et `studies`). Sans cette donnée, elle affiche un message et le résumé textuel le dit : ne la proposez pas.

| Représentation (`slug`) | Disposition et formes | Donnée lue | Quand la choisir |
|---|---|---|---|
| Matrice croisée (`matrice-croisee`) | `layout.matrix` + `mark.tally` | deux dimensions de l'étude, `outcome` des cas | L'étude croise exactement deux facteurs : on voit toutes les combinaisons, et celles qui manquent. |
| Calcul pas à pas (`calcul-pas-a-pas`) | `layout.grid` `rows: "values"` + `mark.value` | `steps[].values` | Un montant se construit ligne après ligne. |
| Axe à bandes (`axe-a-bandes`) | `layout.scale` + `mark.band`, `mark.point` | `bands` de la dimension, `measures` des cas | Des seuils : où tombe ce cas, et les cas voisins de chaque borne. |
| Avant / après (`avant-apres`) | `layout.grid` `rows: "fields"` + `mark.field` | `entities[].fields`, `steps[].fields` | Un objet métier dont des champs changent. |
| Table de règles (`table-regles`) | `layout.grid` `rows: "rules"` + `mark.cells_per_condition`, `mark.rule_result` | `ruleset`, `steps[].rows` | Plusieurs règles en concurrence : la ligne retenue, les lignes écartées, celles qui ne correspondent pas et pourquoi. |
| Arbre de décision (`arbre-decision`) | `layout.tree` + `mark.decision`, `mark.conclusion` | `ruleset`, `dimensions` du cas | Jeu de règles court (8 lignes et 3 conditions au plus) : le chemin du cas, question après question. |
| Table d'états (`table-etats`) | `layout.grid` `rows: "states"` + `mark.cells_per_event` | `lifecycles`, `steps[].changes` | Beaucoup de transitions : la table montre aussi ce qui n'est pas permis. |
| Diagramme d'états (`diagramme-etats`) | `layout.states` + `mark.state`, `mark.transition` | `lifecycles`, `steps[].changes` | Peu de transitions : le cycle se lit d'un regard, boucles et retours compris. À chaque étape, le parcours déjà fait reste tracé et les états pas encore atteints sont en tirets (`show_visited`, actif par défaut). |
| Diagramme de séquence (`diagramme-sequence`) | `layout.lifelines` + `mark.lifeline`, `mark.message` | `steps[].messages` | Des acteurs qui s'échangent des messages dans un ordre précis ; un message perdu se voit. |

Ces dispositions exigent leurs formes (`needs_marks` dans le catalogue) : un document sans elles est refusé (`missing_mark`). Elles se composent comme les autres — par exemple une table de règles et un calcul côte à côte avec `compose.columns`.

## Options et liens mis en avant

Quand la règle dépend d'une option portée par une entité (par exemple `always_run` sur une tâche), déclarez-la dans `attrs` **et** mettez-la en avant dans le cas : `"highlights": [{"entity": "C", "attr": "always_run"}]` (chapitre `cases`). L'application l'affiche alors :

- toujours, dans les paramètres du cas, à côté du résultat attendu : « always_run (C · cleanup) : true » ;
- sur l'entité elle-même (en gras par défaut, voir « Choisir le style »), dans les représentations qui dessinent les entités : graphe en couches, graphe et trace, couloirs, vignettes, table de trace (en-tête de ligne), frise (libellé de ligne) et diagramme de séquence (en-tête d'acteur).

### Choisir le style

Par défaut, l'option s'écrit en gras, à l'encre du texte. Vous pouvez choisir un autre style avec `style` :

```json
"highlights": [{"entity": "C", "attr": "always_run", "style": {"weight": "bold", "italic": false, "tone": "warning"}}]
```

| Clé | Valeurs | Défaut |
|---|---|---|
| `weight` | `bold`, `normal` | `bold` |
| `italic` | `true`, `false` | `false` |
| `tone` | `ink` (encre du texte), `muted` (texte secondaire), `accent` (bleu du site), ou un rôle de statut : `neutral`, `waiting`, `active`, `success`, `warning`, `error`, `blocked`, `disabled`, `info` | `ink` |

- **Pas de couleur libre** (`#ff0000`, `red`…) : seules ces teintes, qui gardent un contraste lisible en thème clair comme sombre, sont acceptées (`enum` sinon). Une couleur de rôle reprend celle des statuts de l'étude : choisissez-la pour son sens (`warning` pour une option qui change la règle, `error` pour une option dangereuse), pas pour décorer.
- Le texte « always_run : true » est toujours écrit : la teinte ne porte jamais seule l'information.
- Le style s'applique sur l'entité et dans les paramètres du cas. Avec des boîtes en aplat (`status_fill: "solid"`), le texte reste dans la couleur lisible sur l'aplat. Dans la frise, le libellé de ligne reste en texte simple.

### Un lien mis en avant

Quand la règle tient à une dépendance (un prérequis, une action), mettez le lien en avant : `"highlights": [{"link": ["A", "C"]}]`. Il est tracé en trait renforcé, dans la teinte du `style` (encre par défaut), dans les graphes, couloirs et vignettes ; les paramètres du cas l'affichent (« Lien A → C : prerequisite », ou son libellé).

### Libellé et définition de l'option

L'option s'écrit sous son nom technique et sa valeur telle qu'elle est écrite (« always_run : true »). Si l'étude la déclare dans `attributes` (chapitre `studies`), son libellé et sa définition s'affichent au survol ; avec `"show": "label"`, le libellé remplace le nom et la valeur se lit oui / non. La boîte s'élargit pour garder l'option sur une ligne (jusqu'à 1,6 fois sa largeur) ; au-delà, la valeur passe sur une seconde ligne.

C'est le cas qui porte cette mise en avant, pas la représentation : elle suit le relecteur s'il change de représentation. Pour afficher en permanence un attribut sur toutes les entités, ajoutez plutôt une ligne de détail à la forme : `"details": ["always_run : {attr.always_run}"]` dans `mark.node`. Une ligne dont tous les champs sont vides n'est pas écrite.

## L'entité à regarder à une étape

`steps[].focus` (chapitre `cases`) désigne au relecteur les entités à regarder à cette étape. L'application les entoure d'un **anneau accent plein**, distinct du pointillé « vient de changer », et souligne leur nom, dans les graphes, couloirs, vignettes et le diagramme de séquence (contour de l'en-tête d'acteur). La ligne « À regarder » de l'étape les nomme en toutes lettres, quelle que soit la représentation : l'information ne dépend jamais du seul dessin. Le résumé textuel de l'aperçu les cite aussi (« Désigné au relecteur »).

## Ce que la représentation ne contrôle pas

La zone d'avis, le curseur d'étapes, le libellé et la note d'étape, la légende des statuts et le **rôle visuel** de chaque statut sont affichés par l'application. Un statut est toujours rendu par une couleur de rôle, une icône et, sauf réglage `status_label: "hidden"`, un libellé : jamais par la couleur seule.

## Une étude = une représentation

Une étude a **une** représentation : celle qui convient à la nature de ses règles. C'est vous, qui avez analysé les règles, qui la fixez en déposant l'étude. Le relecteur peut ensuite en changer pour lui, pour un seul cas, ou pour toute l'étude : c'est son choix.

`GET /api/v1/studies/{id}/representations/recommended` renvoie la **forme** de l'étude (taille des cas, liens, temps, dimensions, groupes, champs étendus employés), les représentations recommandées avec leurs raisons, les autres avec leurs réserves, et la représentation actuellement affichée. Prenez la première sauf raison contraire, et vérifiez-la par un aperçu.

`PUT /api/v1/studies/{id}/representation`

```json
{"representation": "table-regles", "level": "study"}
```

| `level` | Effet | Rôle requis |
|---|---|---|
| `study` (par défaut) | Fixe la représentation de toute l'étude, pour tous ses membres. | éditeur |
| `me` | Change la représentation pour le titulaire du jeton seulement, sur toute l'étude. | lecteur |
| `case` | Change la représentation d'un seul cas (champ `case` : sa clé), pour le titulaire du jeton seulement. | lecteur |

- `"representation": null` annule le choix de ce niveau : le cas suit de nouveau l'étude, ou l'étude revient à la représentation conseillée.
- `representation` accepte l'identifiant ou le `slug` d'une représentation système.
- Ordre appliqué à l'affichage : choix pour le cas, sinon choix personnel, sinon représentation de l'étude, sinon la première conseillée.
- `GET /api/v1/studies/{id}/representation` renvoie les choix en place : `study`, `study_chosen_by` (`ai` ou `human`), `me`, `cases`, `effective`.
- Si un **humain** a déjà choisi la représentation de l'étude dans l'interface, un jeton ne la remplace pas : `409 human_choice`. Proposez alors la vôtre.

## Proposer plutôt que choisir

Quand l'étude a déjà une représentation choisie par un humain, ou pour suggérer une seconde lecture, différente par nature et non par couleur :

`POST /api/v1/studies/{id}/representations/proposals` avec `{"representation": "<id>", "reason": "Pourquoi elle convient à ces cas."}`

L'utilisateur voit la proposition dans **Étude › Représentation** et décide.

## Créer ou ajuster

`POST /api/v1/representations`

- **Nouveau thème** à partir d'un document complet : `{"name": "…", "description": "…", "spec": { … }}`
- **Nouveau thème** à partir d'une représentation existante : `{"name": "…", "parent": "<id>", "overrides": { … }}`
- **Ajustement personnel** (visible de son seul auteur, suit les évolutions du parent) : `{"mode": "adjustment", "parent": "<id>", "overrides": { … }}`

`overrides` ne contient que ce qui change. Les objets sont fusionnés en profondeur ; les tableaux sont remplacés en bloc, sauf `views` : une vue fusionne avec la vue de même `id`, une vue d'`id` nouveau est ajoutée, `{"id": "trace", "$remove": true}` retire une vue. Pour changer une forme, renvoyez la liste `marks` complète de la vue.

Exemple — « mets les erreurs plus en évidence et resserre » :

```json
{"mode": "adjustment", "parent": "graphe-couches",
 "overrides": {"tokens": {"density": "compact"},
               "views": [{"id": "graphe", "time": {"brick": "time.stepper", "dim_unchanged": true}}]}}
```

- `PATCH /api/v1/representations/{id}` — modifier une représentation **qui vous appartient** (`spec` ou `overrides`) ; chaque modification crée une version. Une représentation système n'est pas modifiable : ajustez-la ou dupliquez-la.
- `POST /api/v1/representations/{id}/duplicate` — copie en nouveau thème.
- `POST /api/v1/representations/validate` avec `{"spec": { … }}` — valider sans enregistrer.
- `GET /api/v1/representations` et `GET /api/v1/representations/{id}` — lister, lire le document résolu.

## Vérifier le rendu

`POST /api/v1/studies/{id}/cases/{key}/preview`

```json
{"representation": "<id>", "step": 2, "image": true, "theme": "light"}
```

ou `{"spec": { … }}` pour essayer un document sans l'enregistrer. La réponse contient :

- `summary.text` : ce qui est dessiné, vue par vue — nombre de formes, taille de la zone, **libellés tronqués**, **entités non dessinées**, avertissements. Lisez-le toujours : il vaut même si vous ne voyez pas l'image.
- `image` : un PNG en base64, si le serveur dispose de Chromium ; sinon `image_unavailable` en donne la raison.

Regardez le résultat avant de proposer une représentation : essayez-la sur le cas le plus gros de l'étude et sur un cas typique.

## Quand une brique manque

Vous ne pouvez assembler que ce que les briques permettent. S'il vous manque une disposition, une forme ou un comportement :

`POST /api/v1/bricks/requests` avec `{"title": "Disposition radiale", "need": "Montrer un cycle de vie qui revient à son point de départ.", "family": "disposition", "study": "<id>"}`

Le signalement alimente la liste des évolutions du site. En attendant, composez au mieux avec les briques existantes et dites à l'utilisateur ce que vous n'avez pas pu montrer.
