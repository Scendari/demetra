# Atelier : déclarer les règles d'une étude, dérouler une situation construite

Version {{version}}.

## Ce que c'est

Dans l'onglet « Atelier » d'une étude, un humain part d'une **page vide**. Il pose des briques du vocabulaire de l'étude, les relie, règle leurs options, provoque un évènement, et le site lui montre ce qui se passe, pas après pas. **Aucun cas déposé n'y figure** : ce que l'atelier montre vient des règles que l'étude déclare, appliquées par le site à la situation construite.

Votre rôle est de **déclarer ces règles** : les types de briques, leurs options, les évènements qu'on peut y provoquer, les liens permis, et une table de règles « quand telle condition, alors tel état ». Le site les exécute lui-même. **Il n'exécute aucun code** : les conditions sont un vocabulaire fermé, décrit ci-dessous. Ce qui ne s'y dit pas ne se déclare pas ; dites-le à l'utilisateur plutôt que d'approcher la règle par une autre.

Une étude qui ne déclare pas de règles n'a pas d'atelier : l'onglet le dit et renvoie vers ses cas.

Il existe **deux familles** d'atelier, choisies par le champ `family` de la déclaration. `"linked"` (par défaut) : des éléments reliés qui changent d'état, décrits dans la première partie de ce chapitre. `"periods"` : des périodes datées que le site combine en un historique, décrites dans la section « Famille périodes ». Une étude n'en déclare qu'une.

Ce que l'atelier montre est **ce que disent les règles déclarées**. Rien ne prouve que le système réel se comporte ainsi : l'écran le rappelle, faites de même.

## Ce qui s'y dit, et ce qui ne s'y dit pas

Une règle d'atelier dit l'état que prend **un élément**, d'après son état, ses options, ce qu'on y provoque, l'état de ses voisins (directs ou de proche en proche), l'état des autres éléments et les réglages de la situation. Cela couvre un enchaînement de tâches, un circuit de validation, des prérequis entre modules.

Une combinaison de périodes datées (historisation, versions successives, rattachements) se déclare avec la famille `periods`, plus bas.

Ne s'y disent pas, pour l'instant : un calcul de montants, un délai, une relance automatique, une limite au nombre d'éléments actifs en même temps, une action d'un élément sur un autre. Pour ces règles, déposez des cas.

## Déclarer : le champ `workshop` de l'étude

À la création (`POST /api/v1/studies`) ou par `PATCH /api/v1/studies/{id}` avec `{"workshop": { … }}`. Portée : `studies:write`. Envoyer `{"workshop": {}}` retire la déclaration.

```json
"workshop": {
  "title": "Composer un enchaînement",
  "bricks": [
    {"type": "tache", "label": "Tâche",
     "options": [{"key": "obligatoire", "label": "Obligatoire", "values": [true, false]},
                 {"key": "niveau", "label": "Niveau", "values": ["simple", "double"], "default": "simple"}],
     "events": [{"key": "echec", "label": "Échoue"}]},
    {"type": "jalon", "label": "Jalon", "initial": "A_FAIRE"}
  ],
  "links": [{"type": "avant", "label": "précède", "reverse": "dépend de",
             "from": ["tache"], "to": ["tache", "jalon"]}],
  "settings": [{"key": "arret", "label": "Arrêt à la première erreur", "values": [false, true]}],
  "rules": [
    {"key": "R1", "title": "Une tâche est bloquée dès qu'une tâche en amont a échoué",
     "on": "tache",
     "when": {"status": "A_FAIRE", "upstream": {"link": "avant", "any": {"status": "ECHEC"}}},
     "then": "BLOQUEE"},
    {"key": "R2", "title": "Un élément démarre quand tout ce qui le précède a réussi",
     "when": {"status": "A_FAIRE", "incoming": {"all": {"status": "FAIT"}}}, "then": "EN_COURS"},
    {"key": "R3", "title": "Une tâche qui échoue termine en échec",
     "when": {"status": "EN_COURS", "event": "echec"}, "then": "ECHEC"},
    {"key": "R4", "title": "Un élément en cours aboutit", "when": {"status": "EN_COURS"}, "then": "FAIT"}
  ],
  "outcome": [
    {"when": {"elements": {"any": {"status": "ECHEC"}}}, "label": "Enchaînement en échec", "status": "ECHEC"},
    {"label": "Enchaînement réussi", "status": "FAIT"}
  ],
  "max_steps": 24
}
```

| Champ | Contenu | Limites |
|---|---|---|
| `title` | Titre de l'atelier, affiché sur la page vide | 80 caractères |
| `bricks` | Types de briques : `type` (nom court sans espace), `label`, `options`, `events`, `initial` | 1 à 8 |
| `bricks[].options` | `key`, `label`, `values` (textes courts, nombres ou booléens), `default` (sinon la première valeur) | 8 options, 2 à 8 valeurs |
| `bricks[].events` | Ce qu'on peut provoquer sur un élément de ce type : `key`, `label` | 6 |
| `bricks[].initial` | Statut de départ des éléments de ce type ; sinon le statut par défaut de l'étude | — |
| `links` | Types de liens : `type`, `label` (lu de l'origine vers la cible), `reverse` (lu dans l'autre sens, facultatif), `from` et `to` (types de briques reliés ; tous si absent) | 8 |
| `settings` | Réglages de toute la situation : même forme qu'une option | 8 |
| `rules` | La table de règles, **de la plus prioritaire à la moins prioritaire** | 1 à 60 |
| `outcome` | Le résultat d'ensemble : `when` (facultatif), `label`, `status` (facultatif) ; le premier dont la condition est vraie est retenu | 12 |
| `max_steps` | Nombre de pas au-delà duquel le déroulé s'arrête | 1 à 40, 24 par défaut |

Une option à deux valeurs `true` et `false` se coche dans l'interface ; les autres se choisissent dans une liste. `then` et `status` sont des statuts de l'étude : un statut cité par une règle ne se retire plus de l'étude.

Une règle : `key`, `title` (une phrase qui dit ce que fait la règle ; c'est elle que le relecteur lit à chaque pas), `on` (types de briques concernés ; tous si absent), `when`, `then`.

## Conditions : un vocabulaire fermé

Une condition est un objet ; **toutes** ses entrées doivent être vraies.

| Entrée | Vraie quand |
|---|---|
| `"status": "FAIT"` ou `["FAIT", "IGNORE"]` | l'élément est dans cet état, ou dans l'un d'eux |
| `"type": "tache"` | l'élément est une brique de ce type |
| `"option": {"obligatoire": true}` | chaque option citée a cette valeur |
| `"event": "echec"` | cet évènement a été provoqué sur l'élément |
| `"setting": {"arret": true}` | chaque réglage cité a cette valeur |
| `"incoming": {"link": "avant", "all": { … }}` | les éléments **d'où part** un lien vers celui-ci satisfont la condition |
| `"outgoing": { … }` | les éléments **vers lesquels** part un lien depuis celui-ci |
| `"upstream": { … }`, `"downstream": { … }` | les mêmes, de proche en proche : toute la chaîne en amont, ou en aval |
| `"elements": {"type": "tache", "any": { … }}` | les éléments de toute la situation (y compris celui-ci) |
| `"all": [ … ]`, `"any": [ … ]`, `"not": { … }` | et, ou, non |

- `incoming`, `outgoing`, `upstream`, `downstream` et `elements` prennent **un seul** quantificateur : `all` (tous ; vrai s'il n'y en a aucun), `any` (au moins un), `none` (aucun). `link` restreint à un type de lien ; `type`, dans `elements`, à un type de brique.
- L'égalité est stricte : `true` ne vaut pas `1`, `"1"` ne vaut pas `1`.
- Les conditions s'emboîtent sur 5 niveaux au plus (`too_deep`).
- Dans `outcome[].when`, la condition porte sur la situation, pas sur un élément : seuls `setting`, `elements`, `all`, `any`, `not` y ont un sens (`no_element` sinon).

Erreurs de déclaration : `unknown_test`, `unknown_status`, `unknown_brick`, `unknown_option`, `unknown_setting`, `unknown_event`, `unknown_link`, `unknown_value`, `unknown_field`, `duplicate`, `too_deep`, `no_element`, `type`, `required`. Chaque erreur donne le chemin exact (`workshop.rules[3].when.incoming.all.status`).

## Comment le site déroule une situation

1. Au départ, chaque élément est dans l'état `initial` de sa brique, sinon dans le statut par défaut de l'étude.
2. À chaque pas, chaque élément suit **la première règle de la table qui lui correspond**. Toutes les règles lisent l'état du pas précédent : les changements d'un même pas sont simultanés.
3. Le déroulé s'arrête quand plus rien ne bouge (`end: "stable"`), quand la situation revient à un état déjà vu (`loop`) ou quand `max_steps` est atteint (`limit`).

L'ordre des règles fait donc la priorité : placez les règles d'arrêt (blocage, désactivation) avant les règles de démarrage. Une règle dont l'état d'arrivée est l'état actuel ne change rien, mais elle empêche les suivantes de s'appliquer à cet élément.

## Lire ce que l'étude déclare

`GET /api/v1/studies/{id}/workshop` — portée `studies:read`.

```json
{"declared": true, "family": "linked", "workshop": { … la déclaration normalisée … },
 "default_status": "A_FAIRE",
 "limits": {"elements": 24, "links": 60, "steps": 24},
 "web_url": "/etudes/ab12cd34ef/atelier/", "hint": ""}
```

Sans déclaration : `declared: false`, `family: null`, `workshop: null`, et `hint` dit comment en déclarer une. Le champ `workshop` figure aussi dans `GET /api/v1/studies/{id}`.

## Valider une déclaration sans rien écrire

`POST /api/v1/studies/{id}/workshop/validate` — portée `studies:read`. **Lecture seule : rien n'est écrit**, l'étude garde sa déclaration et sa révision, rien n'est journalisé. Corps : `{"workshop": { … }}`, la déclaration telle que vous la passeriez à `PATCH /studies/{id}` ; facultatif, `statuses` (les statuts à supposer si vous comptez les changer du même coup — par défaut, ceux de l'étude). Faites-le **avant** le `PATCH` : vous corrigez sans toucher à l'étude, et vous lisez les règles que le relecteur lirait avant de les lui proposer.

Une déclaration avec deux fautes :

```json
{"workshop": {"family": "periods", "title": "Tarif à vérifier",
  "axis": {"label": "Mois", "min": 1, "max": 13, "grain": 1},
  "bricks": [{"type": "contrat", "label": "Contrat",
              "options": [{"key": "offre", "label": "Offre", "values": ["A", "B"]}]}],
  "image": {"sources": [{"brick": "contrat", "several": "newest"}],
            "fields": [{"key": "offre", "label": "Offre", "from": "contrat.offre"}],
            "status": [{"then": "REMISE"}]},
  "states": {"active": "EN_COURS", "past": "FINIE", "ignored": "IGNOREE", "invalid": "KO", "blocked": "KO"},
  "outcome": [{"label": "Tarif"}],
  "rules": []}}
```

La réponse, toujours `200` :

```json
{"valid": false, "declared": false, "written": false, "family": null,
 "errors": [
  {"path": "workshop", "code": "unknown_field", "message": "Champ inconnu dans « workshop ».",
   "severity": "error", "received": ["rules"]},
  {"path": "workshop.image.sources[0].several", "code": "enum", "message": "Valeur inconnue.",
   "severity": "error", "received": "newest", "expected": ["latest_start", "earliest_start", "block"]}],
 "warnings": [], "rules": [], "workshop": null, "study_revision": 0,
 "hint": "Corrigez les erreurs puis revalidez ; PATCH /studies/{id} refuserait cette déclaration."}
```

- `valid` : `PATCH /studies/{id}` accepterait cette déclaration. `errors` et `warnings` ont la forme des erreurs de validation de l'API (`path`, `code`, `message`, et selon le cas `received`, `expected`, `example`).
- `declared` : l'étude aurait bien un atelier. Une déclaration vide (`{}`) est valide et retire l'atelier : `valid: true`, `declared: false`.
- `written` : toujours `false`. `study_revision` : la révision de l'étude, inchangée.
- `workshop` : la déclaration normalisée, celle que `GET …/workshop` rendrait après le `PATCH` ; `family` : sa famille.
- `rules` : **les règles que le site en tirerait**, celles que le relecteur lit dans l'onglet « Atelier ». Pour la famille périodes, les phrases écrites par le site (`key` `P1`…, `role`, `title`) ; pour les éléments reliés, votre table de règles normalisée. Une fois les deux fautes corrigées (retirer `rules`, écrire `"several": "latest_start"`), la même requête rend `valid: true` et cinq règles : `P1` (une image par pas), `P2` (début inclus, fin exclue), `P3` (les périodes invalides), `P4` (la source « Contrat »), `P5` (les champs restitués et la fusion).

Une requête sans `workshop` est une requête mal formée (`422`), comme partout ailleurs.

## Dérouler une situation

`POST /api/v1/studies/{id}/workshop/run` — portée `studies:read`. **Lecture seule : rien n'est écrit**, la révision de l'étude ne bouge pas.

```json
{"situation": {
  "elements": [{"id": "A", "type": "tache", "events": ["echec"]},
               {"id": "B", "type": "tache", "label": "Contrôle", "options": {"niveau": "double"}},
               {"id": "C", "type": "jalon"}],
  "links": [{"from": "A", "to": "B", "type": "avant"}, {"from": "B", "to": "C"}],
  "settings": {"arret": false}
}}
```

- `elements` : 1 à 24, chacun avec `id` (nom court unique) et `type` ; `label`, `options` (les options absentes prennent leur valeur par défaut) et `events` sont facultatifs.
- `links` : 60 au plus ; `type` peut être omis quand l'étude ne déclare qu'un type de lien. Un lien relie deux éléments distincts, dans le sens et entre les types que l'étude permet.
- `settings` : les réglages absents prennent leur valeur par défaut.

Réponse :

```json
{"family": "linked",
 "situation": { … la situation complétée de ses valeurs par défaut … },
 "steps": [{"step": 0, "states": {"A": "A_FAIRE", "B": "A_FAIRE", "C": "A_FAIRE"}, "changes": []},
           {"step": 1, "states": {"A": "EN_COURS", "B": "A_FAIRE", "C": "A_FAIRE"},
            "changes": [{"id": "A", "from": "A_FAIRE", "to": "EN_COURS", "rule": "R2"}]}],
 "end": "stable",
 "final": {"A": "ECHEC", "B": "BLOQUEE", "C": "A_FAIRE"},
 "outcome": {"label": "Enchaînement en échec", "status": "ECHEC"},
 "rules_applied": [{"key": "R2", "title": "…"}, {"key": "R3", "title": "…"}, {"key": "R1", "title": "…"}],
 "case": { … le même déroulé, au format d'un cas … },
 "web_url": "/etudes/ab12cd34ef/atelier/?e=A%3Atache&e=B%3Atache&…"}
```

- `steps[0]` est la situation de départ ; chaque pas suivant donne les états et, pour chaque changement, la règle appliquée.
- `outcome` vaut `null` si l'étude ne déclare pas de résultat d'ensemble, ou si aucun ne correspond.
- `web_url` ouvre l'atelier sur cette situation : donnez ce lien à l'utilisateur pour qu'il la voie et la modifie. Tout l'état tient dans l'adresse.
- `case` vaut `null` si la situation ne donne pas un cas que le site sait valider (par exemple un changement d'état qu'un cycle de vie de l'étude interdit).

Erreurs : 409 `no_workshop` (l'étude ne déclare pas de règles) ; 422 `validation_failed` avec, dans `details`, `unknown_brick`, `unknown_option`, `unknown_value`, `unknown_event`, `unknown_link`, `unknown_element`, `forbidden_link`, `duplicate`, `max_items`, `required`.

Servez-vous-en pour **vérifier vos règles avant de les annoncer** : déroulez les situations que les cas de l'étude décrivent et comparez. Un écart entre une règle déclarée et un cas se signale à l'utilisateur ; ne corrigez pas l'un pour faire taire l'autre.

## Famille périodes : combiner des périodes datées en un historique

Pour une étude où des **versions datées** de plusieurs sources se combinent : une historisation, un tarif qui dépend d'un contrat et d'une remise, un rattachement qui change dans le temps. L'humain pose des périodes, leur donne un début, une fin et des valeurs ; le site calcule l'historique obtenu et le montre sur la représentation de l'étude.

Vous ne déclarez **pas de table de règles** : vous déclarez comment une image se compose, et le site en tire lui-même les phrases que le relecteur lit (`rules`, numérotées `P1`, `P2`…, rendues par `GET …/workshop`). Un champ `rules`, `links` ou `max_steps` est refusé (`unknown_field`).

```json
"workshop": {
  "family": "periods",
  "title": "Composer un tarif",
  "axis": {"label": "Mois", "min": 1, "max": 13, "grain": 1, "step": 0.5},
  "bricks": [
    {"type": "contrat", "label": "Contrat",
     "options": [{"key": "offre", "label": "Offre", "values": ["A", "B"]}]},
    {"type": "remise", "label": "Remise",
     "options": [{"key": "taux", "label": "Taux", "values": [10, 20]}]}
  ],
  "settings": [{"key": "sans_remise", "label": "Mois sans remise", "values": ["gardés", "retirés"]}],
  "image": {
    "sources": [
      {"brick": "contrat"},
      {"brick": "remise", "mode": {"setting": "sans_remise", "inner": ["retirés"]},
       "several": "latest_start", "tie": "block"}
    ],
    "fields": [{"key": "offre", "label": "Offre", "from": "contrat.offre"},
               {"key": "taux", "label": "Taux", "from": "remise.taux"}],
    "status": [{"when": {"missing": "remise"}, "then": "SANS_REMISE"}, {"then": "REMISE"}]
  },
  "merge": true,
  "invalid": {"zero": "ignore", "missing": "block", "inverted": "block"},
  "states": {"active": "EN_COURS", "past": "FINIE", "ignored": "IGNOREE", "invalid": "KO", "blocked": "KO"},
  "outcome": [
    {"when": {"blocked": true}, "label": "Tarif non publié", "status": "KO"},
    {"when": {"empty": true}, "label": "Aucun tarif"},
    {"when": {"status": "REMISE"}, "label": "Tarif avec remise", "status": "REMISE"},
    {"label": "Plein tarif", "status": "SANS_REMISE"}
  ]
}
```

| Champ | Contenu | Limites |
|---|---|---|
| `family` | `"periods"` | — |
| `title` | Titre de l'atelier | 80 caractères |
| `axis` | L'axe du temps : `label`, `min`, `max`, `grain` (le pas : une image par pas), `step` (la finesse des bornes qu'on saisit ; `grain` par défaut). Des nombres : jours d'un mois, heures, rangs | 400 pas au plus |
| `bricks` | Les sources de périodes : `type`, `label`, `options` (les champs d'une période, même forme que dans l'autre famille). Ni `events` ni `initial` ; `start` et `end` sont réservés aux bornes | 1 à 8 |
| `settings` | Réglages de toute la situation | 8 |
| `image.sources` | La **base** d'abord, puis les sources rattachées, dans l'ordre où elles se résolvent | une par brique au plus |
| `image.fields` | Les champs restitués : `key`, `label`, `from` (`"brique.champ"`). **Seuls ces champs distinguent deux images** | 1 à 8 |
| `image.status` | Le statut d'une image : la première entrée `{when, then}` dont la condition est vraie | 1 à 12 |
| `merge` | `true` (par défaut) : deux images identiques sur les champs restitués, sans trou entre elles, forment une seule période. `false` : tout changement de période source ouvre une image | — |
| `invalid` | Le sort d'une période de durée nulle (`zero`), sans l'une de ses bornes (`missing`) ou qui finit avant de commencer (`inverted`) : `"ignore"` ou `"block"` | — |
| `states` | Le statut de l'étude qui dit chaque état d'une période posée : `active` (en vigueur), `past` (finie), `ignored` (devancée par une autre, ou ignorée), `invalid` (invalide et bloquante), `blocked` (statut des images quand le traitement est bloqué) | les cinq sont requis |
| `outcome` | Le résultat d'ensemble : `when` (facultatif), `label`, `status` | 12 |
| `runs` | Facultatif : des exécutions successives (`label`, `max`, `write`), voir plus bas | 2 à 6 exécutions |

Une source rattachée (toute source après la première) :

| Entrée | Sens |
|---|---|
| `"mode": "left"` (par défaut) | faute de période en vigueur, l'image est gardée et les champs de cette source restent vides |
| `"mode": "inner"` | faute de période en vigueur, aucune image |
| `"mode": {"setting": "sans_remise", "inner": ["retirés"]}` | `inner` quand le réglage a l'une de ces valeurs, `left` sinon |
| `"match": {"code": "remise.code"}` | on ne retient que les périodes dont le champ `code` vaut le champ `code` de la période retenue pour `remise` (une source déjà nommée) |
| `"several"` | quand plusieurs périodes sont en vigueur : `"latest_start"` (par défaut : celle qui a commencé le plus tard), `"earliest_start"`, ou `"block"` (le traitement est bloqué) |
| `"tie"` | quand elles ont le même début : `"block"` (par défaut) ou `"first"` (la première posée) |

La base accepte `several` et `tie`, pas `mode` ni `match` : sans période de base en vigueur, il n'y a pas d'image.

Conditions de `image.status[].when` : `"missing": "remise"` ou `["a", "b"]` (aucune période retenue pour l'une de ces sources), `"present": […]` (une période retenue pour chacune), `"setting": {…}`. Conditions de `outcome[].when` : `"blocked": true|false`, `"empty": true|false` (aucune image), `"status": "REMISE"` ou une liste (au moins une image a ce statut).

### Comment le site combine

1. Les périodes invalides sont ignorées ou bloquent, selon `invalid`.
2. Pour chaque pas de l'axe, l'image montre les périodes **en vigueur à la fin du pas** ; une période vaut de son début inclus à sa fin exclue. Un changement à l'intérieur d'un pas, défait avant sa fin, ne laisse aucune trace.
3. Chaque source est résolue dans l'ordre déclaré (`match`, puis `several` et `tie`).
4. Les pas qui se suivent et donnent la même image sont réunis (`merge`).
5. Si quelque chose bloque (période invalide bloquante, égalité sans départage), **toutes** les images prennent le statut `states.blocked` et `blocking` dit pourquoi.

### Dérouler une situation de périodes

Même route : `POST /api/v1/studies/{id}/workshop/run`, lecture seule.

```json
{"situation": {
  "elements": [{"id": "A", "type": "contrat", "start": 1, "end": 6, "options": {"offre": "A"}},
               {"id": "B", "type": "remise", "start": 3, "end": 5}],
  "settings": {"sans_remise": "gardés"}
}}
```

- `elements` : 1 à 24 périodes, chacune avec `id`, `type`, `start` et `end` (nombres sur l'axe ; une borne omise ou `null` est une **borne absente**, que `invalid.missing` traite) ; `label` et `options` sont facultatifs.
- Pas de `links` ni d'`events` (`unknown_field`). Une borne hors de l'axe est refusée (`out_of_range`).

La réponse a la forme de l'autre famille (`steps`, `final`, `outcome`, `rules_applied`, `case`, `web_url`), avec `"family": "periods"` et deux champs de plus :

```json
{"images": [{"id": "I1", "start": 1, "end": 3, "fields": {"offre": "A", "taux": null},
             "status": "SANS_REMISE", "from": {"contrat": "A", "remise": null},
             "sources": ["A"], "rules": ["P1", "P5", "P6"],
             "why": "Contrat : Contrat A ; Remise : aucune en vigueur, la ligne est gardée. 2 pas de l'axe aux mêmes valeurs, réunis en une période."},
            {"id": "I2", "start": 3, "end": 5, "fields": {"offre": "A", "taux": 10},
             "status": "REMISE", "from": {"contrat": "A", "remise": "B"},
             "sources": ["A", "B"], "rules": ["P1", "P6"],
             "why": "Contrat : Contrat A ; Remise : Remise B. 2 pas de l'axe aux mêmes valeurs, réunis en une période."},
            {"id": "I3", "start": 5, "end": 6, "fields": {"offre": "A", "taux": null},
             "status": "SANS_REMISE", "from": {"contrat": "A", "remise": null},
             "sources": ["A"], "rules": ["P1", "P5"],
             "why": "Contrat : Contrat A ; Remise : aucune en vigueur, la ligne est gardée."}],
 "blocking": []}
```

- `images` : l'historique obtenu, période par période ; `from` nomme la période retenue pour chaque source au premier pas de l'image.
- `images[].sources`, `rules`, `why` : **d'où vient la ligne**. `sources` liste toutes les périodes posées qui l'ont nourrie (plusieurs par source quand des périodes de mêmes valeurs se suivent) ; `rules` les règles de l'étude en cause (clés `P1`…, celles de `workshop.rules`) ; `why` le dit en une phrase : la période retenue pour chaque source, celle qu'elle a devancée, une source absente, une égalité, des pas réunis. Citez `why` à l'humain plutôt que de le reformuler : c'est ce que l'écran de l'atelier affiche quand il choisit une ligne.
- `blocking` : ce qui bloque le traitement, en phrases ; vide quand rien ne bloque.
- `steps` : un pas chaque fois qu'une image commence, qu'un trou s'ouvre ou qu'une période posée change d'état ; `at` y donne la position sur l'axe. Le déroulé va jusqu'au bout de l'axe : `final` est l'état des périodes posées à ce moment (`{"A": "FINIE", "B": "FINIE"}` ici, les deux périodes finissant avant la fin de l'axe ; une période qui court jusqu'au bout de l'axe reste `states.active`). Un pas sans image dit quelle source manque.
- `case` : les périodes posées (groupe « Périodes posées ») et les images (groupe « Historique obtenu »), avec `attrs.start` et `attrs.end` : la représentation de l'étude les dessine telles quelles. Une frise convient le mieux.

### Exécutions successives : ce qu'un traitement publie, passage après passage

Pour une étude où le traitement **repasse** sur des sources qui ont bougé : un premier lancement, une relance sans changement, une période arrivée plus tard, une correction rétroactive. L'étude le déclare d'un champ de plus :

```json
"runs": {"label": "Exécution", "max": 3, "write": "differences"}
```

| Champ | Contenu |
|---|---|
| `label` | Le nom d'une exécution à l'écran (« Exécution », « Passage », « Lot »…) ; 40 caractères |
| `max` | Le nombre d'exécutions qu'une situation peut compter : de 2 à 6 (3 par défaut) |
| `write` | Ce qu'une exécution écrit par rapport à ce qui était publié : `"differences"` (par défaut : seules les lignes qui diffèrent ; sans différence, rien n'est écrit) ou `"all"` (tout l'historique est réécrit à chaque exécution) |

Le site en tire une règle de plus (rôle `runs`, la dernière de `rules`). Dans une situation, trois champs s'ajoutent alors ; une étude qui ne déclare pas `runs` les refuse (`unknown_field`) :

- `runs` (à côté de `elements`) : le nombre d'exécutions, de 1 à `max` ; 1 par défaut.
- `known_from` sur une période : la première exécution qui la connaît (1 par défaut).
- `known_until` sur une période : la dernière exécution qui la connaît, comprise (par défaut : toutes). Une **correction** se dit ainsi : l'ancienne période avec `known_until: 2`, la nouvelle avec `known_from: 3`.

Avec la déclaration donnée plus haut et ce champ `runs`, une remise qui n'arrive qu'à la troisième exécution :

```json
{"situation": {"runs": 3, "elements": [
  {"id": "A", "type": "contrat", "start": 1, "end": 6, "options": {"offre": "A"}},
  {"id": "B", "type": "remise", "start": 3, "end": 5, "options": {"taux": 10}, "known_from": 3}]}}
```

La réponse porte un champ `runs` de plus, une entrée par exécution :

```json
{"runs": [
 {"run": 1, "known": ["A"], "new": ["A"], "withdrawn": [], "published": true, "blocking": [],
  "lines": [{"start": 1, "end": 6, "fields": {"offre": "A", "taux": null}, "status": "SANS_REMISE", "change": "added"}],
  "removed": [], "written": {"deleted": 0, "appended": 1},
  "text": "Exécution 1 : 1 ligne ajoutée ; à l'écriture : 1 ligne écrite."},
 {"run": 2, "known": ["A"], "new": [], "withdrawn": [], "published": true, "blocking": [],
  "lines": [{"start": 1, "end": 6, "fields": {"offre": "A", "taux": null}, "status": "SANS_REMISE", "change": "same"}],
  "removed": [], "written": {"deleted": 0, "appended": 0},
  "text": "Exécution 2 : 1 ligne inchangée ; rien n'est écrit."},
 {"run": 3, "known": ["A", "B"], "new": ["B"], "withdrawn": [], "published": true, "blocking": [],
  "lines": [{"start": 1, "end": 3, "fields": {"offre": "A", "taux": null}, "status": "SANS_REMISE", "change": "closed",
             "was": {"start": 1, "end": 6, "fields": {"offre": "A", "taux": null}, "status": "SANS_REMISE"}},
            {"start": 3, "end": 5, "fields": {"offre": "A", "taux": 10}, "status": "REMISE", "change": "added"},
            {"start": 5, "end": 6, "fields": {"offre": "A", "taux": null}, "status": "SANS_REMISE", "change": "added"}],
  "removed": [], "written": {"deleted": 1, "appended": 3},
  "text": "Exécution 3 : 2 lignes ajoutées et 1 ligne fermée ; à l'écriture : 1 ligne supprimée et 3 lignes écrites."}]}
```

- Chaque exécution **recalcule tout l'historique** avec les périodes qu'elle connaît (`known` ; `new` : celles qu'elle découvre ; `withdrawn` : celles qu'elle ne connaît plus), puis le compare à ce qui était publié. Une ligne se reconnaît à son **début**.
- `lines[].change` : `"added"` (ajoutée : aucun début pareil n'était publié), `"closed"` (fermée : mêmes valeurs, fin avancée), `"changed"` (modifiée : valeurs ou statut différents, ou fin reculée), `"same"` (inchangée). `was` donne la ligne d'avant pour `closed` et `changed`. `removed` : les lignes publiées dont le début n'existe plus (`"change": "removed"`, retirées).
- `written` : ce que l'exécution écrit selon `write` — avec `"differences"`, elle supprime les lignes fermées, modifiées et retirées, et écrit les lignes ajoutées, fermées et modifiées ; avec `"all"`, elle supprime et réécrit tout.
- Une exécution **bloquée** (`published: false`, `blocking` dit pourquoi) ne publie rien : `lines` rend ce qui était publié, inchangé, et l'exécution suivante repart de là.
- `text` : la même chose en une phrase, celle que l'écran affiche. Citez-la.
- `images`, `final`, `outcome`, `steps` et `case` décrivent la **dernière** exécution ; une période qu'elle ne connaît pas (ou plus) y prend le statut `states.ignored`.
- `web_url` garde tout : `x=3` (le nombre d'exécutions), `c.B=3` (`known_from`), `j.A=2` (`known_until`).

Ne s'y disent pas : une publication en plusieurs temps qui échoue en chemin (suppression faite, écriture non), le périmètre d'un recalcul (quelles clés, quelles colonnes), plusieurs entités à la fois (un lien qui passe d'un parent à un autre), un calcul sur les valeurs. Pour ces règles, déposez des cas.

## Ce qui reste réservé aux humains

- **Enregistrer une situation comme cas.** Dans l'atelier, un humain peut garder ce qu'il a construit comme un cas à relire (clé `atelier-1`, `atelier-2`…, famille « Atelier »). L'API n'a pas de route pour cela, et un jeton ne peut pas le faire à sa place. Vous pouvez toujours déposer vos propres cas par `POST …/cases/batch`, sous votre nom.
- **Rendre un avis**, comme partout : une situation de l'atelier ne reçoit jamais d'avis ; un cas enregistré depuis l'atelier attend le sien comme tout autre cas.
