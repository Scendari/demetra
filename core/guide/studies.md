# Études : statuts, dimensions, règles de gestion

Version {{version}}.

Une étude porte les définitions que tous ses cas partagent. Déclarez-les **avant** de déposer des cas : un cas qui emploie un statut, une valeur de dimension ou une règle non déclarés est refusé.

## Créer

`POST /api/v1/studies`

```json
{
  "title": "Remboursement d'une commande",
  "description": "Règles d'éligibilité au remboursement.",
  "kind": "decision",
  "statuses": [
    {"key": "A_EVALUER", "label": "À évaluer", "role": "waiting", "default": true},
    {"key": "SATISFAITE", "label": "Satisfaite", "role": "success"},
    {"key": "NON_SATISFAITE", "label": "Non satisfaite", "role": "error"}
  ],
  "dimensions": [
    {"key": "delai", "label": "Délai depuis la livraison", "values": ["≤ 14 j", "15–30 j", "> 30 j"]},
    {"key": "etat", "label": "État du produit", "values": ["intact", "ouvert", "endommagé"]}
  ],
  "rules": [
    {"key": "R1", "title": "Rétractation sous 14 jours", "text": "Un produit intact est remboursé intégralement sous 14 jours."}
  ],
  "exclusions": [
    {"when": {"delai": "> 30 j", "etat": "ouvert"}, "reason": "Hors délai : l'état du produit n'est pas examiné."}
  ]
}
```

- `kind` : `workflow`, `decision`, `temporal` ou `mixed`. Sert de nature par défaut des cas.
- `statuses[].role` fixe l'apparence du statut : `neutral`, `waiting`, `active`, `success`, `warning`, `error`, `blocked`, `disabled`, `info`. Chaque rôle a une couleur **et** une icône ; une représentation ne peut pas changer le rôle d'un statut. `default: true` désigne le statut de départ des entités ; `short` (14 caractères au plus) donne un libellé abrégé.
- `dimensions` : les facteurs qui varient d'un cas à l'autre, chacun avec au moins deux valeurs. C'est sur elles que la couverture est mesurée : choisissez-les avec soin. Ajoutez `"highlight": true` à une dimension pour que sa valeur reste **visible sur tous les cas** de l'étude, à côté du résultat attendu (par exemple l'option dont dépend presque chaque cas) ; les autres caractéristiques sont repliées. Pour une mise en avant propre à un seul cas, utilisez le champ `highlights` du cas.
- `rules` : les règles de gestion en langage clair. Un cas cite les règles qu'il illustre.
- `exclusions` : combinaisons de valeurs déclarées impossibles, avec leur raison ; elles ne sont pas comptées comme manquantes.
- `attributes` : les **options portées par les entités** (leurs `attrs`), déclarées une fois pour l'étude. Voir ci-dessous.

## Nommer et définir les options des entités (`attributes`)

Les entités portent souvent des options techniques (`always_run`, `ignore_on_error`, `active`…) dont dépend le déroulé. Le relecteur ne connaît pas forcément ces noms : déclarez-les avec un libellé lisible et une définition.

```json
"attributes": [
  {"key": "always_run", "label": "Toujours exécutée", "text": "La tâche s'exécute même si un de ses prérequis a échoué."},
  {"key": "ignore_on_error", "label": "Erreur ignorée", "text": "Un échec de la tâche n'arrête pas ses successeurs."}
]
```

- `key` : le nom de l'option, **exactement** comme dans les `attrs` des entités ; `label` : libellé lisible, 60 caractères au plus ; `text` : la définition, 300 caractères au plus, facultative ; `show` : voir ci-dessous. 40 options au plus.
- Effet à l'affichage : par défaut, une option s'écrit sous son **nom technique**, avec sa valeur **telle qu'elle est écrite** (« always_run : true ») — c'est le nom que les équipes lisent dans la configuration et le code. Le libellé et la définition s'affichent au survol, et l'onglet **Règles et définitions** les liste.
- `show` : `key` (par défaut) ou `label`. Avec `"show": "label"`, l'option s'écrit sous son libellé lisible, et une valeur vraie/fausse en oui / non (« Toujours exécutée : oui »). Choisissez-le quand le nom technique ne dit rien (`flg_x2`) ou quand les relecteurs sont des gens du métier, pas des techniciens ; gardez le nom technique quand le titre et le résumé des cas l'emploient.
- Dès qu'une option est déclarée, toute option d'entité **non déclarée** donne un avertissement `undeclared_attr` au dépôt : c'est souvent une faute de frappe (`alway_run`). Le cas est quand même écrit.
- `PATCH /api/v1/studies/{id}` avec `attributes` remplace la liste. Changer un libellé ou une définition ne touche pas aux avis.

## Pour les règles chiffrées, les jeux de règles et les cycles de vie

Trois déclarations facultatives. Une étude qui ne les emploie pas n'a rien à changer.

### Tranches d'une dimension numérique (`bands`)

Quand une dimension découpe un nombre en tranches (montant, âge, délai), déclarez les bornes : la représentation « axe à bandes » montre alors les seuils, et chaque cas peut porter sa valeur exacte (`measures`, chapitre `cases`).

```json
{"key": "montant", "label": "Montant de la note", "unit": "€", "inclusive": "from",
 "values": [{"value": "petit", "label": "Moins de 50 €"}, {"value": "moyen", "label": "De 50 à 500 €"}, {"value": "grand", "label": "500 € et plus"}],
 "bands": [{"value": "petit", "to": 50, "result": "Validation automatique"},
           {"value": "moyen", "from": 50, "to": 500, "result": "Responsable"},
           {"value": "grand", "from": 500, "result": "Direction"}]}
```

- Une tranche par valeur de la dimension (`missing_band` sinon), dans l'ordre croissant, sans trou ni recouvrement : chacune commence où la précédente finit (`gap`). Seule la première peut ne pas avoir de `from`, seule la dernière de `to`.
- `inclusive` dit à quelle tranche appartient une borne : `from` (par défaut) — 50 est dans la tranche qui **commence** à 50 ; `to` — 50 est dans celle qui **finit** à 50. C'est là que se cachent les erreurs de seuil : déposez un cas pile sur chaque borne et un de chaque côté.
- `unit` (12 caractères au plus) et `result` (ce que la tranche entraîne, 80 caractères au plus) sont facultatifs.

### Jeu de règles partagé (`ruleset`)

Une table de règles commune à tous les cas : chaque ligne teste des conditions et donne une conclusion.

```json
"ruleset": {
  "title": "Priorité d'un ticket", "policy": "priority",
  "conditions": [{"key": "client", "label": "Client"}, {"key": "gravite", "label": "Gravité"}],
  "rows": [
    {"key": "T1", "when": {"client": "Premium", "gravite": "Bloquant"}, "then": "Astreinte immédiate", "status": "P1"},
    {"key": "T2", "when": {"gravite": "Bloquant"}, "then": "Prise en charge sous 1 h"},
    {"key": "T3", "when": {}, "then": "File d'attente normale"}
  ]}
```

- `policy` dit quelle ligne l'emporte quand plusieurs correspondent : `unique` (une seule ligne peut correspondre), `first` (la première dans l'ordre), `priority` (la plus prioritaire, l'ordre des lignes donnant la priorité), `any` (toutes celles qui correspondent donnent la même conclusion), `collect` (toutes s'appliquent).
- `conditions` : 1 à 8, chacune avec `key` et `label`. Si la clé est aussi celle d'une dimension de l'étude, la représentation affiche la valeur du cas en tête de colonne.
- `rows[].when` : valeur attendue par condition ; une condition absente est **indifférente**. `then` est obligatoire ; `status` (facultatif) est un statut de l'étude qui colore la conclusion.
- Chaque cas dit ensuite le sort des lignes (`steps[].rows`, chapitre `cases`). Représentations : « table de règles » (toutes les lignes, la retenue et les écartées) et « arbre de décision » (jeu court, lu comme une suite de questions).

### Cycles de vie (`lifecycles`)

Les états possibles d'un type d'entité et les **seules transitions permises**.

```json
"lifecycles": [{"type": "commande", "title": "Cycle de vie d'une commande", "initial": "PANIER",
  "transitions": [
    {"from": "PANIER", "to": "PAIEMENT", "label": "valider le panier"},
    {"from": "PAIEMENT", "to": "PAIEMENT", "label": "paiement refusé"},
    {"from": "PAIEMENT", "to": "PAYEE", "label": "paiement accepté", "guard": "solde suffisant"},
    {"from": "PAIEMENT", "to": "PANIER", "label": "abandonner"}
  ]}]
```

- `type` désigne le champ `type` des entités des cas ; un cycle par type, 8 au plus.
- `from` et `to` sont des statuts de l'étude ; `label` nomme l'évènement (obligatoire) ; `guard` est une condition facultative. Depuis un même état, un même évènement ne mène qu'à un état (`ambiguous`). Une boucle sur soi (`from` = `to`) et un retour en arrière sont permis.
- Dès qu'un cycle est déclaré, chaque changement d'état d'une entité de ce type est contrôlé : une transition absente est refusée (`forbidden_transition`, avec les états permis dans `expected`), de même qu'un état de départ hors du cycle (`outside_lifecycle`).
- Représentations : « diagramme d'états » (peu de transitions) et « table d'états » (beaucoup de transitions : elle montre aussi ce qui n'est pas permis).

### Règles d'atelier (`workshop`)

Ce que le site **exécute** quand un humain construit une situation dans l'onglet « Atelier » : des briques, des liens et une table de règles (famille `linked`), ou des sources de périodes et la façon de les combiner (famille `periods`). Chapitre `atelier`. Une étude qui ne les déclare pas n'a pas d'atelier.

### Modifier ces déclarations

`PATCH /api/v1/studies/{id}` avec `dimensions`, `ruleset` ou `lifecycles`. Le site revalide les cas déjà déposés contre la nouvelle déclaration : si un cas cite une ligne retirée, porte une mesure hors de sa tranche ou emprunte une transition supprimée, la modification est refusée (`in_use`, avec les cas concernés) et rien ne change.

## Lire et modifier

- `GET /api/v1/studies` — mes études (vue sommaire).
- `GET /api/v1/studies/{id}` — définitions complètes et état de la revue.
- `PATCH /api/v1/studies/{id}` — envoyer seulement les champs à changer. Chaque liste envoyée **remplace** la liste existante : pour ajouter un statut, renvoyez la liste complète avec le nouveau. Retirer un statut, une valeur de dimension ou une règle encore utilisés par des cas est refusé (`in_use`).

## Supprimer et restaurer

Seul le **propriétaire** supprime une étude, et une suppression passe d'abord par la corbeille.

- `DELETE /api/v1/studies/{id}` met l'étude à la corbeille (portée `studies:write`, jeton du propriétaire). Elle
  disparaît aussitôt pour tous ses membres ; la réponse donne `purge_at`, la date à laquelle elle sera effacée.
- `GET /api/v1/trash` liste vos études à la corbeille ; `POST /api/v1/trash/{id}/restore` en rétablit une, avec ses
  cas, ses avis et son historique intacts.
- **L'effacement définitif n'est pas dans l'API.** Il se fait dans l'interface (*Études › Corbeille*), par une
  personne, ou d'office à la fin du délai (30 jours par défaut). Ne supprimez une étude que si la personne vous
  l'a demandé, et dites-lui qu'elle peut la restaurer.
- Dans l'interface, le message « mise à la corbeille » porte un bouton **Annuler**, qui la restaure aussitôt.

## Trois familles, un seul format

- **Workflows et états** : entités = tâches ; liens = prérequis ; étapes = changements de statut.
- **Règles de décision** : entités = conditions et résultat (`type: "condition"`, `type: "result"`, valeur dans `attrs.value`) ; dimensions = les conditions ; `outcome` = le résultat du cas.
- **Règles temporelles** : entités = périodes (`attrs.start`, `attrs.end`) et échéances (`attrs.at`) ; chaque étape porte `at`, sa position sur l'axe du temps.
- **Calculs, seuils, objets métier, processus entre acteurs** : mêmes cas, avec des champs en plus — `values`, `measures`, `fields`, `messages`, `rows` (chapitre `cases`).
