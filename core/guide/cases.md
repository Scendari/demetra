# Cas : format, dépôt en lot, validation à blanc

Version {{version}}.

## Format d'un cas

```json
{
  "key": "chaine-simple",
  "number": 2,
  "family": "Bases",
  "title": "B attend la réussite de A",
  "summary": "B dépend de A : B ne démarre qu'après la réussite de A.",
  "kind": "workflow",
  "rules": ["R1"],
  "dimensions": {"issue_de_a": "réussite"},
  "tags": ["parcours"],
  "config": {"capacity": 3},
  "highlights": ["issue_de_a", {"entity": "A", "attr": "always_run"}],
  "entities": [
    {"id": "A", "label": "source", "type": "task", "group": "", "attrs": {"always_run": false}},
    {"id": "B", "label": "suite", "type": "task"}
  ],
  "links": [{"from": "A", "to": "B", "type": "prerequisite", "label": ""}],
  "initial": {"A": "WAITING"},
  "steps": [
    {"title": "A démarre", "note": "B attend.", "changes": {"A": "RUNNING"}, "annotations": {"B": "attend A"}, "focus": ["B"]},
    {"title": "A réussit, B démarre", "changes": {"A": "FINISHED_OK", "B": {"status": "RUNNING", "note": "une place est libre"}}},
    {"title": "Fin", "changes": {"B": "FINISHED_OK"}, "global": "FINISHED_OK"}
  ],
  "outcome": {"label": "Tout réussit", "status": "FINISHED_OK"},
  "references": [{"kind": "test", "label": "test_workflow.py::test_chain"}],
  "caution": "",
  "question": "B doit-elle vraiment attendre la réussite de A, et pas seulement sa fin ?",
  "compare_with": ["a-echoue"],
  "proof": "asserted"
}
```

| Champ | Obligatoire | Sens |
|---|---|---|
| `key` | oui | Identifiant **stable**, en minuscules : lettres, chiffres, `_ . -`. Ne le changez jamais pour un même cas. |
| `title` | oui | Titre court. |
| `steps` | oui (≥ 1) | Le déroulé. Chaque étape a un `title` et des `changes`. |
| `number` | non | Numéro d'ordre (entier) ; attribué par le site s'il est absent. |
| `label` | non | Libellé affiché à la place du numéro, 12 caractères au plus (par exemple « 16-A »). |
| `family` | non | Regroupement dans la liste (« Général » par défaut). |
| `kind` | non | `workflow`, `decision`, `temporal`. |
| `rules` | non | Clés des règles de l'étude que ce cas illustre. |
| `dimensions` | non | Valeur du cas pour chaque dimension déclarée. Sans elles, le cas ne compte pas dans la couverture. |
| `config` | non | Réglages du cas, en valeurs simples (`{"capacity": 3}`). 24 au plus. |
| `highlights` | non | Les caractéristiques à **garder sous les yeux du relecteur**, 4 au plus. Deux formes : une clé de `dimensions` ou de `config` de ce cas (`"stop_on_error"`), une **option portée par une entité**, `{"entity": "C", "attr": "always_run"}` (l'entité doit exister et déclarer cet attribut dans ses `attrs`), ou un **lien**, `{"link": ["A", "C"]}` (un lien de ce cas doit aller de A à C), avec au besoin un `style` (graisse, italique, teinte ; chapitre `representations`). Elles s'affichent avec leur valeur à côté du résultat attendu, quelle que soit la représentation ; une option d'entité s'écrit en plus **sur l'entité elle-même** dans le schéma (voir le chapitre `representations`). Les autres caractéristiques sont repliées. Mettez-y ce dont dépend le cas — l'option qui fait la règle —, pas tout. Si la même dimension compte pour toute l'étude, marquez-la plutôt une fois (`"highlight": true` dans l'étude). |
| `entities` | non | `id` (obligatoire), `label`, `type`, `group`, `attrs` (valeurs simples). 60 au plus. |
| `links` | non | `from`, `to`, `type`, `label`. Les types `prerequisite`, `dependency`, `depends_on` doivent être **sans cycle** ; pour un cycle voulu (machine à états), utilisez un autre type, par exemple `transition`. |
| `initial` | non | Statut de départ de certaines entités ; les autres prennent le statut par défaut de l'étude. |
| `steps[].changes` | — | `{entité: statut}` ou `{entité: {status, note}}`. **Seulement ce qui change** : le reste est hérité de l'étape précédente. |
| `steps[].global` | non | Statut d'ensemble à cette étape (par exemple celui du workflow). |
| `steps[].at` | non | Position sur l'axe du temps (nombre), croissante. Nécessaire à la frise. |
| `steps[].annotations` | non | `{entité: texte court}` affiché à cette étape (par exemple la décision prise). |
| `outcome` | non | Résultat du cas : `{label, status}`. Sert aux tables de décision. |
| `steps[].focus` | non | Les entités que le relecteur doit **regarder** à cette étape, 3 au plus — surtout quand la règle porte sur ce qui **ne change pas** (« C reste en attente »). Elles reçoivent un anneau accent sur le schéma, et la ligne « À regarder » de l'étape les nomme, avec leur annotation. Ne change pas les avis. |
| `references` | non | Sources et tests : `{kind, label}`. |
| `caution` | non | Un **point d'attention** sur le cas (une incertitude, une limite, un comportement contesté), affiché en encadré sous le schéma. Texte libre. |
| `question` | non | **Ce que vous demandez au relecteur de vérifier**, en une phrase (300 caractères au plus). Affichée juste au-dessus des boutons Valider / Refuser : l'avis répond à cette question. Ne change pas les avis. |
| `compare_with` | non | Les clés de 1 à 3 cas à **comparer** à celui-ci, typiquement le même cas avec l'option inverse. Le panneau les liste sous le schéma, avec un tableau de ce qui diffère (dimensions, réglages, options des entités, résultat) et un lien qui ouvre le cas. Un cas ne se compare pas à lui-même (`self_reference`) ; une clé absente ou retirée est signalée par les contrôles (`compare_missing_case`). Ne change pas les avis. |
| `proof` | non | `asserted` (affirmé, par défaut) ou `observed` (constaté sur le système réel, par un test ou une exécution). |
| `time_axis` | non | `{"unit": "day" ou "month", "origin": "2026-01-01"}` : les temps du cas (`attrs.start`, `end`, `at`, et `at` des étapes) sont des rangs comptés en jours ou en mois depuis `origin`. La frise écrit alors des dates (« janv. 2026 ») au lieu des nombres. Les cas produits par un atelier en dates le portent d'eux-mêmes. Ne change pas les avis. |
| `covers` | non | Les clés des **points de l'inventaire** de l'étude que ce cas couvre (chapitre `studies`, champ `inventory`). Un point inconnu est refusé (`unknown_inventory_point`). Ne change pas les avis. |

Le site **rejoue** les changements pour reconstruire l'état complet à chaque étape ; `GET …/cases/{key}` renvoie ces états dans `frames`.

## Champs étendus : calculs, seuils, champs, messages, lignes de règles

Tous facultatifs. Un cas qui ne les emploie pas reste valide et inchangé. Chacun alimente une représentation précise : n'ajoutez que ce que le cas a réellement à montrer.

```json
{
  "key": "fidele-mensuel", "title": "18 mois d'ancienneté, formule mensuelle",
  "dimensions": {"anciennete": "fidele", "formule": "Mensuelle"},
  "measures": {"anciennete": 18},
  "entities": [
    {"id": "abo", "label": "Abonnement", "type": "abonnement", "fields": {"Prix du mois": "20 €", "Remise": "aucune"}},
    {"id": "service", "label": "Service d'abonnement", "type": "acteur"},
    {"id": "banque", "label": "Banque", "type": "acteur"}
  ],
  "steps": [
    {"title": "Les règles de prix sont examinées",
     "rows": {"P1": {"result": "failed", "on": "formule"}, "P2": "selected"},
     "values": [{"label": "Prix catalogue", "op": "=", "value": 20, "unit": "€", "result": 20},
                {"label": "Remise de 10 %", "op": "-", "value": 2, "unit": "€", "result": 18}]},
    {"title": "Le renouvellement est prélevé", "changes": {"abo": "ACTIF"},
     "fields": {"abo": {"Prix du mois": "18 €", "Remise": "10 %"}},
     "messages": [{"from": "service", "to": "banque", "label": "Prélever 18 €"},
                  {"from": "banque", "to": "service", "label": "Accepté", "status": "received"}]}
  ]
}
```

| Champ | Sens | Contrôles |
|---|---|---|
| `measures` | `{dimension: nombre}` — la valeur exacte du cas sur une dimension à tranches (`bands`, chapitre `studies`). | La dimension doit déclarer des tranches (`unknown_measure`) ; le nombre doit tomber dans une tranche (`out_of_scale`), et dans **celle que le cas déclare** dans `dimensions` (`out_of_band`). |
| `entities[].fields` | `{nom: valeur}` — les champs d'un objet métier avant le cas. Valeurs simples : texte court, nombre, booléen ; 16 champs au plus. | `type`, `format`, `max_items`. |
| `steps[].fields` | `{entité: {nom: valeur}}` — les champs que l'étape **modifie**. Le reste est hérité. | L'entité doit exister (`unknown_entity`). |
| `steps[].values` | Les lignes de calcul de l'étape : `label`, `op`, `value`, et au besoin `unit`, `result` (cumul après la ligne), `note`. `op` vaut `=` `+` `-` `×` `÷` `%` `min` `max` `arrondi`. 12 lignes au plus par étape. | `op` inconnu (`enum`), `value` non numérique (`type`). Un `result` qui ne correspond pas à l'opération donne un **avertissement** `inconsistent_total` : le cas est écrit, vérifiez votre calcul. |
| `steps[].messages` | Les messages échangés à l'étape, dans l'ordre : `from`, `to`, `label`, et `status` — `received` (par défaut) ou `lost` (émis, jamais reçu). Un message de soi à soi est permis. 8 au plus par étape. | Émetteur et destinataire sont des entités du cas (`unknown_entity`) ; `status` inconnu (`enum`). |
| `steps[].rows` | `{ligne: résultat}` — le sort des lignes du jeu de règles de l'étude pour ce cas : `selected` (retenue), `discarded` (elle correspondait, mais la politique en a retenu une autre), `failed` (elle ne correspond pas). Forme longue : `{"result": "failed", "on": "formule"}` nomme la condition en échec. | L'étude doit déclarer un `ruleset` (`no_ruleset`) ; la ligne doit y exister (`unknown_rule`) ; `on` désigne une condition déclarée (`unknown_condition`) et ne vaut que pour `failed`. |

Avec un cycle de vie déclaré sur l'étude (`lifecycles`), les `changes` d'une entité de ce type ne peuvent suivre que les transitions permises (`forbidden_transition`). Pour rester dans le même état par une transition déclarée (une boucle : « paiement refusé »), écrivez le changement vers le même statut : `"changes": {"commande": "PAIEMENT"}`.

Ces champs font partie de l'empreinte du déroulé : les modifier repasse les avis « à analyser », comme tout changement de fond.

Quelle donnée pour quelle représentation :

| Vous avez… | Champs | Représentation |
|---|---|---|
| deux dimensions et un résultat par cas | `dimensions`, `outcome` | matrice croisée |
| un montant qui se calcule | `steps[].values` | calcul pas à pas |
| des seuils | `bands` (étude), `measures` | axe à bandes |
| un objet dont des champs changent | `entities[].fields`, `steps[].fields` | avant / après |
| plusieurs règles en concurrence | `ruleset` (étude), `steps[].rows` | table de règles, arbre de décision |
| un objet qui change d'état | `lifecycles` (étude), `steps[].changes` | diagramme d'états, table d'états |
| des acteurs qui se parlent | `steps[].messages` | diagramme de séquence |

## Un cas pour plusieurs situations

Un cas peut décrire plusieurs situations qui ne diffèrent que par quelques paramètres. Déclarez les paramètres, posez une condition sur les étapes qui en dépendent.

```json
{
  "key": "abonne-recent", "title": "Échéance d'un abonné récent",
  "dimensions": {"anciennete": "recent"},
  "params": [
    {"key": "paiement", "label": "Premier prélèvement", "values": ["accepte", "refuse"]},
    {"key": "relance", "label": "Relance automatique", "values": ["active", "inactive"], "default": "active"}
  ],
  "entities": [{"id": "abonnement", "label": "Abonnement", "type": "abonnement"},
               {"id": "prelevement", "label": "Prélèvement", "type": "paiement"}],
  "steps": [
    {"title": "Le prélèvement est tenté", "changes": {"prelevement": "EN_COURS"}},
    {"when": {"paiement": "accepte"}, "title": "Le prélèvement est accepté",
     "changes": {"prelevement": "ACCEPTE", "abonnement": "RENOUVELE"}},
    {"when": {"all": [{"paiement": "refuse"}, {"relance": "inactive"}]}, "title": "L'abonnement est suspendu",
     "changes": {"prelevement": "REFUSE", "abonnement": "SUSPENDU"}},
    {"when": {"all": [{"paiement": "refuse"}, {"relance": "active"}]}, "title": "Une relance part",
     "changes": {"prelevement": "REFUSE"}}
  ],
  "outcome": [
    {"when": {"paiement": "accepte"}, "label": "Abonnement renouvelé", "status": "RENOUVELE"},
    {"when": {"relance": "active"}, "label": "Relance envoyée"},
    {"label": "Abonnement suspendu", "status": "SUSPENDU"}
  ]
}
```

- `params` : 6 paramètres au plus, 8 valeurs au plus chacun (texte, nombre ou booléen), **64 combinaisons au plus** (`too_many_combinations`). `default` est la valeur montrée d'abord ; sans lui, c'est la première.
- Un paramètre qui porte la clé d'une **dimension de l'étude** prend ses valeurs parmi celles de la dimension : le cas compte alors, dans la couverture, pour toutes les combinaisons que ses paramètres permettent. Il y est marqué « paramétré ». Ne répétez pas cette clé dans `dimensions`.
- Un paramètre qui n'est pas une dimension devient un réglage du cas (`config`) pour chaque variante.
- `steps[].when` : l'étape n'existe que si la condition est vraie. `outcome` peut être une liste : le premier résultat dont la condition est vraie est retenu ; une entrée sans `when` sert de repli.
- Une option d'entité peut suivre un paramètre : `"attrs": {"always_run": {"param": "always_run"}}`.

Conditions — un vocabulaire fermé, aucun code n'est exécuté :

| Forme | Sens |
|---|---|
| `{"paiement": "refuse"}` | le paramètre vaut cette valeur |
| `{"essais": {"gte": 2}}` | comparaison : `eq`, `ne`, `in`, `gt`, `gte`, `lt`, `lte` |
| `{"paiement": "refuse", "relance": "active"}` | toutes les égalités à la fois |
| `{"all": [ … ]}`, `{"any": [ … ]}`, `{"not": { … }}` | et, ou, non (4 niveaux au plus) |

L'égalité est stricte : `true` ne vaut pas `1`, `"1"` ne vaut pas `1`.

**Le site rejoue le cas pour chaque combinaison au moment du dépôt.** Si une seule combinaison donne un cas invalide (transition interdite, aucune étape, statut inconnu…), le cas entier est refusé ; l'erreur dit pour quelles valeurs : « (avec paiement = refuse, relance = active) ». Codes propres aux cas paramétrés : `too_many_combinations`, `unknown_param`, `never_true` (une étape qu'aucune combinaison ne garde), `unknown_value`, `duplicate`.

**L'avis porte sur le cas entier**, conditions comprises : dès qu'un paramètre change, ou que ce que montre une seule combinaison change, les avis repassent « à analyser ». Réécrire une condition sans rien changer à ce que montrent les combinaisons garde les avis. `GET …/cases/{key}` rend le cas tel que déposé (avec `params` et `when`) ; `frames` rejoue la première combinaison et `parametric.combinations` liste les autres.

Préférez un cas paramétré quand les variantes partagent l'essentiel du déroulé. Si elles divergent dès la deuxième étape, déposez des cas distincts : le relecteur les lira mieux.

## Écart entre un cas et le jeu de règles

Quand un cas annonce, dans `steps[].rows`, un sort des lignes que le jeu de règles de l'étude ne donne pas pour ses dimensions et réglages, le dépôt renvoie l'avertissement `model_mismatch`. **C'est un avertissement, jamais un refus** : le cas est écrit. Soit le cas se trompe, soit le jeu de règles est incomplet ; dites-le à l'utilisateur au lieu de corriger l'un pour faire taire l'autre. `GET /api/v1/studies/{id}/checks` liste les cas concernés sous le même code.

## Écart entre un cas et les règles de l'atelier

Quand l'étude déclare des règles d'atelier (chapitre `atelier`), chaque cas déposé est **rejoué dans l'atelier** : mêmes briques (le `type` des entités), mêmes options (les `attrs` qui portent le nom d'une option), mêmes liens, mêmes réglages, même état de départ (`initial`). Un réglage se lit dans `config`, sinon dans la dimension que la déclaration de l'atelier lui associe (`settings[].dimension`). Si les règles ne mènent pas là où le cas finit, ou à un autre résultat d'ensemble (`outcome.status`), le dépôt renvoie l'avertissement `workshop_mismatch`, qui dit quelle entité s'écarte et comment. **C'est un avertissement, jamais un refus** : le cas est écrit. Soit le cas se trompe, soit les règles de l'atelier sont incomplètes ; dites-le à l'utilisateur au lieu de corriger l'un pour faire taire l'autre.

- Un cas ne dit pas quels évènements (« tombe en panne »…) ont eu lieu : le site cherche lui-même, parmi ceux que les règles savent traiter, jusqu'à trois évènements qui expliquent le cas.
- Un cas peut s'arrêter en cours de route : il concorde s'il décrit un moment que les règles traversent.
- Pour un atelier de périodes, ce sont les lignes de l'historique (entités qui ne sont pas des briques, avec `attrs.start` et `attrs.end`) qui sont comparées à celles que les règles donnent.
- Un cas sans aucune entité d'une brique de l'atelier n'est pas rejoué. Un cas qui mêle des briques de l'atelier et d'autres types, ou des liens que l'atelier ne déclare pas, n'est pas signalé au dépôt : `GET …/checks` le liste sous `workshop_untranslatable` (information).

`GET /api/v1/studies/{id}/checks` liste les cas qui s'écartent sous `workshop_mismatch`.

## Valider à blanc

`POST /api/v1/studies/{id}/cases/validate` avec `{"cases": [...]}` — rien n'est écrit. La réponse a la même forme qu'un dépôt, avec `dry_run: true`, et donne la couverture **comme si** le lot était déposé.

## Déposer

`POST /api/v1/studies/{id}/cases/batch`

```json
{"cases": [ … ], "atomic": false}
```

- 200 cas au plus par lot.
- Chaque cas reçoit son résultat : `created`, `updated` (le déroulé a changé), `updated_cosmetic` (seuls des textes ont changé), `unchanged`, `restored` (un cas retiré est rétabli), `error`.
- Par défaut les cas valides sont écrits même si d'autres sont en erreur. Avec `"atomic": true`, rien n'est écrit si un seul cas est invalide.
- **Rejouable** : renvoyer exactement le même lot donne `unchanged` partout. Vous pouvez aussi envoyer l'en-tête `Idempotency-Key: <chaîne>` : la même clé avec le même contenu renvoie la réponse enregistrée (`"replayed": true`) ; la même clé avec un autre contenu répond 409.
- La réponse contient `coverage` (total, couvertes, manquantes) pour que vous sachiez tout de suite ce qui manque.

## Ce qui se passe quand un cas change

L'avis d'un relecteur est attaché à l'**empreinte du déroulé** : structure, configuration, dimensions, changements d'état, résultat.

- Vous corrigez un titre, un résumé, une note, un libellé, ou vous changez `highlights`, `focus`, `question`, `compare_with`, `covers`, `caution` : `updated_cosmetic`, les avis sont conservés.
- Vous changez le déroulé : `updated`, les avis rendus repassent **à analyser** (`verdicts_reset` dans la réponse) et l'ancien avis reste dans l'historique.

## Erreurs de cas

Chaque erreur donne le chemin exact :

```json
{"path": "cases[0].steps[1].changes.B", "code": "unknown_status",
 "message": "Statut « RUNING » non déclaré dans l'étude.",
 "received": "RUNING", "expected": ["FINISHED_OK", "RUNNING", "WAITING"],
 "example": {"key": "RUNNING", "label": "En cours", "role": "active"}}
```

Codes fréquents : `required`, `format`, `duplicate`, `unknown_entity`, `unknown_status`, `unknown_dimension`, `unknown_value`, `unknown_rule`, `cycle`, `order`, `min_items`, `max_items`. Pour `highlights` : `unknown_highlight`, `unknown_entity`, `unknown_attr`, `unknown_link`, et pour son `style` : `enum`, `type`, `unknown_field`. Pour les champs étendus : `unknown_measure`, `out_of_scale`, `out_of_band`, `no_ruleset`, `unknown_condition`, `forbidden_transition`, `outside_lifecycle`, `enum`, `type`. Pour `compare_with` : `self_reference`. Pour `covers` : `unknown_inventory_point`. Pour un cas paramétré : `too_many_combinations`, `unknown_param`, `never_true`. Les `warnings` n'empêchent pas l'écriture (`missing_dimension`, `never_changes`, `unknown_field`, `inconsistent_total`, `undeclared_attr`, `model_mismatch` : le cas annonce un sort des lignes que le jeu de règles de l'étude ne donne pas ; `workshop_mismatch` : rejoué dans l'atelier de l'étude, le cas ne donne pas ce qu'il annonce).

## Lire, retirer, rétablir

- `GET /api/v1/studies/{id}/cases?limit=50&offset=0` — vue sommaire paginée. Filtres : `family`, `verdict`, `q`, `changed_since`, `include_retired`.
- `GET /api/v1/studies/{id}/cases/{key}` — le cas complet, ses états rejoués, ses avis. Le champ `case` contient le cas **tel que déposé** : modifiez-le et redéposez-le tel quel pour corriger un cas. Pour un cas paramétré, il porte `params` et les `when` ; `parametric.combinations` liste ses combinaisons.
- `GET /api/v1/studies/{id}/cases/{key}/revisions` — historique.
- `DELETE /api/v1/studies/{id}/cases/{key}` — **retire** le cas : il sort de la revue mais reste dans l'historique avec ses avis.
- `POST /api/v1/studies/{id}/cases/{key}/restore` — le rétablit.
