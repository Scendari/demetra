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

Un **cas paramétré** (chapitre `cases`) compte pour toutes les combinaisons de dimensions que ses paramètres permettent, et pour un seul cas dans `cases_counted` et `by_dimension`. Dans l'interface, la case qu'il couvre est marquée « paramétré ».

## Limite à dire à l'utilisateur

La couverture ne vaut que ce que vaut la liste des dimensions. Une situation que les dimensions ne décrivent pas n'apparaît pas comme manquante. Si vous découvrez un facteur qui change le comportement, ajoutez-le comme dimension.

## Contrôles de structure

`GET /api/v1/studies/{id}/checks` signale, à l'échelle de l'étude :

- `duplicate_content` : plusieurs cas ont exactement le même déroulé ;
- `rule_without_case` : une règle qu'aucun cas n'illustre ;
- `case_without_rule` : des cas rattachés à aucune règle ;
- `unused_status` : un statut déclaré mais jamais atteint ;
- `single_step` : un cas d'une seule étape ;
- `compare_missing_case` : un `compare_with` qui vise un cas absent ou retiré ;
- `model_mismatch` : des cas annoncent un sort des lignes que le jeu de règles de l'étude ne donne pas (avertissement) ;
- `workshop_mismatch` : des cas, rejoués dans l'atelier de l'étude, ne donnent pas ce qu'ils annoncent (avertissement ; voir le chapitre `cases`) ;
- `workshop_untranslatable` : des cas que l'atelier de l'étude ne sait pas rejouer, faute des briques, options ou liens qu'ils utilisent (information).

## Niveau de preuve

Chaque cas affiche ce qui le fonde :

- **affirmé** (`proof: "asserted"`) : déposé par son auteur, sans autre preuve ;
- **structure vérifiée** : accordé par le site à tout cas enregistré (références valides, étapes rejouables) ;
- **observé** (`proof: "observed"`) : vous déclarez l'avoir constaté sur le système réel ; citez le test ou l'exécution dans `references` ;
- **validé** : un relecteur humain l'a validé.
