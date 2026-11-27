# Couverture : dimensions, combinaisons manquantes, contrôles

Version {{version}}.

## Ce que le site mesure

Un relecteur qui valide les cas un par un ne voit pas celui qui manque. Le site ne sait pas si « tous les cas » existent ; il sait compter les **combinaisons de valeurs de dimensions** qu'aucun cas n'illustre.

`GET /api/v1/studies/{id}/coverage?strength=2`

- `strength=1` : chaque valeur de chaque dimension est-elle illustrée ?
- `strength=2` (par défaut) : chaque **paire** de valeurs de deux dimensions différentes.
- `strength=3` : chaque triplet.

```json
{
  "strength": 2, "total": 27, "covered": 21, "excluded": 2, "missing_count": 6, "ratio": 0.7778,
  "missing": [{"delai": "15–30 j", "etat": "endommagé"}, …],
  "by_dimension": [{"key": "etat", "values": [{"value": "intact", "cases": 6}, …], "unused": []}],
  "cases_without_dimensions": ["cas-sans-dimension"]
}
```

Pour chaque combinaison de `missing`, vous avez trois issues honnêtes :

1. **Ajouter un cas** qui l'illustre.
2. **Déclarer une exclusion** dans l'étude si la combinaison est impossible, avec sa raison (`PATCH /studies/{id}`, champ `exclusions`).
3. **La laisser** et le dire à l'utilisateur.

Quand l'étude déclare un atelier dont des réglages se lisent dans des dimensions (`settings[].dimension`, chapitre `atelier`), la réponse porte aussi `workshop` : une entrée par combinaison de `missing`, dans le même ordre (60 au plus). Elle vaut `null` quand l'atelier n'a aucun réglage pour ces dimensions ; sinon `{"settings": {…}, "from_case": "<clé ou null>", "web_url": "/etudes/…/atelier/?…"}` : l'atelier ouvert sur cette combinaison, à partir d'un cas existant qui a déjà les autres valeurs (`from_case`), ou vide. **Rien n'est déposé** : c'est une piste pour voir ce que les règles donnent avant d'écrire le cas. Si le résultat vous convient, déposez le cas vous-même (`POST …/cases/batch`) ; il sera rejoué et comparé à l'atelier comme les autres.

Un **cas paramétré** (chapitre `cases`) compte pour toutes les combinaisons de dimensions que ses paramètres permettent, et pour un seul cas dans `cases_counted` et `by_dimension`. Dans l'interface, la case qu'il couvre est marquée « paramétré ».

## Inventaire des points de décision

Quand l'étude déclare un `inventory` (chapitre `studies`), la réponse de `GET …/coverage` porte aussi :

```json
"inventory": {
  "total": 42, "covered": 30, "excluded": 6, "to_confirm": 2, "open": 4,
  "open_points": [{"key": "P17", "label": "Remise cumulée plafonnée", "ref": "remises.py:212"}, …],
  "to_confirm_points": [{"key": "P4", "label": "…", "ref": "…", "reason": "…"}],
  "note": "Un point couvert est cité par au moins un cas : ce n'est pas une vérification. …"
}
```

Un point est couvert dès qu'un cas actif le cite (`covers`). Les listes donnent 60 points au plus. Votre travail est fini quand `open` vaut 0 : chaque point est couvert, exclu avec sa raison, ou à confirmer avec la question posée. Ne dites pas l'étude complète tant qu'il reste des points ouverts, ni si des sources n'ont pas été relevées.

## Limite à dire à l'utilisateur

La couverture ne vaut que ce que vaut la liste des dimensions. Une situation que les dimensions ne décrivent pas n'apparaît pas comme manquante. Si vous découvrez un facteur qui change le comportement, ajoutez-le comme dimension.

Ne tirez pas les dimensions des cas déjà écrits. Une dimension dont chaque valeur nomme un cas (13 cas, 13 valeurs, une par cas) donne 100 % par construction : elle ne mesure rien. Une dimension décrit un **facteur** qui fait varier le comportement (un réglage, un type d'élément, une erreur, une limite), et plusieurs cas partagent chacune de ses valeurs. Le site signale ce piège (`dimension_echoes_cases`, ci-dessous).

## Contrôles de structure

`GET /api/v1/studies/{id}/checks` signale, à l'échelle de l'étude :

- `duplicate_content` : plusieurs cas ont exactement le même déroulé ;
- `rule_without_case` : une règle qu'aucun cas n'illustre ;
- `case_without_rule` : des cas rattachés à aucune règle ;
- `unused_status` : un statut déclaré mais jamais atteint ;
- `single_step` : un cas d'une seule étape ;
- `dimension_echoes_cases` : une dimension d'au moins 5 valeurs dont chaque valeur n'est portée que par un cas, avec autant de valeurs que de cas : elle décrit les cas un par un, et sa couverture de 100 % ne prouve rien (avertissement ; le champ `dimension` la nomme) ;
- `compare_missing_case` : un `compare_with` qui vise un cas absent ou retiré ;
- `inventory_open` : des points de l'inventaire qu'aucun cas ne couvre, ni exclus ni à confirmer (avertissement ; le champ `points` les nomme) ;
- `inventory_to_confirm` : des points de l'inventaire en attente d'une confirmation (information) ;
- `model_mismatch` : des cas annoncent un sort des lignes que le jeu de règles de l'étude ne donne pas (avertissement) ;
- `workshop_mismatch` : des cas, rejoués dans l'atelier de l'étude, ne donnent pas ce qu'ils annoncent (avertissement ; voir le chapitre `cases`) ;
- `workshop_untranslatable` : des cas que l'atelier de l'étude ne sait pas rejouer, faute des briques, options ou liens qu'ils utilisent (information).

## Niveau de preuve

Chaque cas affiche ce qui le fonde :

- **affirmé** (`proof: "asserted"`) : déposé par son auteur, sans autre preuve ;
- **structure vérifiée** : accordé par le site à tout cas enregistré (références valides, étapes rejouables) ;
- **observé** (`proof: "observed"`) : vous déclarez l'avoir constaté sur le système réel ; citez le test ou l'exécution dans `references` ;
- **validé** : un relecteur humain l'a validé.
