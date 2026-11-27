# Étude complète : relever tous les cas, pas une sélection

Version {{version}}.

## Pourquoi une IA s'arrête à mi-chemin

Une IA qui analyse un code ou un processus existant a tendance à déposer quelques cas représentatifs, à tirer les dimensions de ces mêmes cas, puis à conclure. La couverture affiche alors 100 % sans rien mesurer : rien ne lui disait où était la fin.

Demetra donne cette fin, en quatre phases :

1. **Inventaire** : relever chaque point de décision des sources, avec sa source, **avant** d'écrire un cas (champ `inventory`, chapitre `studies`).
2. **Construction** : tirer les dimensions de l'inventaire, puis couvrir chaque point par des cas (`covers`), l'exclure avec sa raison, ou le marquer à confirmer.
3. **Reprise** : quand le sujet dépasse une conversation, repartir des points encore ouverts, pas de sa mémoire.
4. **Contre-vérification** : une autre session relit les sources sans regarder d'abord l'étude, et cherche les trous.

Le site rend le travail inachevé visible : `GET …/coverage` compte les points ouverts (`inventory.open`), `GET …/checks` signale `inventory_open` et une dimension qui recopie les cas (`dimension_echoes_cases`). Le travail est fini quand `inventory.open` vaut 0. Même alors, « couvert » veut dire « un cas le cite », pas « vérifié », et 100 % de couverture ne prouve pas que les sources ont toutes été relevées : seule la relecture humaine juge.

## Les prompts à copier

Chaque prompt se donne à l'IA tel quel, après avoir rempli les crochets. Aucun ne contient de secret : le jeton reste dans la variable `DEMETRA_TOKEN` (chapitre `agents`). Pour la cible, écrivez soit `nouvelle étude « titre »`, soit `étude existante <identifiant>` : l'IA vérifie l'étude avant d'y écrire.

Les prompts conviennent à un code comme à un processus décrit dans des documents ; seule la façon d'énumérer change. Adaptez-les : ce sont des aides, pas une garantie.

### 1. Inventaire

```prompt
Mission : relever TOUS les points de décision de [code, fonction, workflow ou processus], à partir de [sources accessibles : dépôt, fichiers, documents, règles métier], dans le périmètre [à préciser], pour [nouvelle étude « titre » | étude existante <identifiant>] sur Demetra. Mode d'emploi : {{origin}}/llms.txt — lis « Brancher une IA en sécurité », puis les chapitres « studies » et « complete ».

1. Liste les sources que tu peux réellement lire, avec leur version ou leur date, et ce qui est hors périmètre. S'il manque une source essentielle, demande-la avant de continuer.
2. Énumère source par source, sans choisir d'exemples. Pour du code : chaque condition, branche, exception, état et transition, paramètre et valeur limite. Pour un document : chaque phrase qui pose une condition, une exception, une obligation, un délai ou un seuil.
3. Pour chaque point : une clé stable (P1, P2…), un libellé court, la source exacte (fichier et ligne, ou paragraphe) et un court extrait. N'écris aucun cas à ce stade.
4. Déclare l'inventaire dans l'étude (champ inventory). Hors périmètre : state excluded avec la raison. Ambigu ou contradictoire : state to_confirm avec la question à poser.
5. Rends compte : nombre de points par source, sources non lues, points exclus et questions ouvertes.
```

### 2. Construction

```prompt
Construis les cas de l'étude Demetra <identifiant> à partir de son inventaire. Mode d'emploi : {{origin}}/llms.txt (chapitres « cases », « coverage » et « complete »).

1. Lis l'étude et GET …/coverage (champ inventory). Tire les dimensions des facteurs qui font varier le comportement (un réglage, un type d'élément, une erreur, une limite), jamais des cas eux-mêmes.
2. Pour chaque point ouvert : un ou plusieurs cas qui le citent dans covers, avec ses frontières (juste en dessous, juste au-dessus) et ses erreurs ; ou une exclusion motivée ; ou to_confirm avec la question.
3. proof: observed seulement si un test ou une exécution le montre, cité dans references ; sinon asserted. N'invente ni source ni résultat.
4. Valide à blanc, dépose, puis lis GET …/coverage et GET …/checks : traite inventory_open, les combinaisons manquantes, dimension_echoes_cases et les écarts signalés.
5. Critère d'arrêt : inventory.open vaut 0. Sinon, dis ce qui reste et pourquoi. Ne présente jamais une sélection d'exemples comme une étude complète. Tu ne rends aucun avis : la relecture est humaine.
```

### 3. Reprise

```prompt
Reprends l'étude Demetra <identifiant> là où elle s'est arrêtée. Mode d'emploi : {{origin}}/llms.txt (chapitre « complete »).

1. Ne repars pas de ta mémoire : lis GET …/coverage (inventory.open_points) et GET …/checks.
2. Traite les points ouverts par lots de [20], comme pour la construction : cas qui les citent dans covers, exclusion motivée ou question à confirmer.
3. Si tu trouves un point de décision absent de l'inventaire, ajoute-le (PATCH de l'étude avec la liste entière de l'inventaire) avant d'écrire son cas.
4. Termine par l'état des compteurs de l'inventaire et la liste de ce qui reste.
```

### 4. Contre-vérification

```prompt
Tu vérifies une étude Demetra que tu n'as pas construite : <identifiant>. Mode d'emploi : {{origin}}/llms.txt (chapitres « coverage » et « complete »). Un jeton en lecture seule (portée studies:read) suffit.

1. Lis d'abord les sources [à préciser], seules, et dresse ta propre liste de points de décision.
2. Ensuite seulement, lis l'inventaire et les cas de l'étude.
3. Rends la liste de ce qui manque ou cloche : points absents de l'inventaire, points couverts par un cas qui ne les illustre pas vraiment, exclusions mal motivées, frontières et erreurs non testées.
4. N'écris rien dans l'étude sans l'accord de la personne. Tu ne rends aucun avis.
```
