# Demetra — consignes pour tout agent (IA ou humain)

Ce fichier est la référence pour maintenir et faire évoluer Demetra, quel que soit l'outil (Copilot, Codex,
Claude Code, Cursor, Mistral, autre). Il ne dépend d'aucune conversation passée : tout ce qu'il faut savoir est
ici ou dans les fichiers qu'il cite. Lisez-le en entier avant de modifier quoi que ce soit.

## Ce qu'est Demetra

Site web Django (Python 3.14, `uv`) qui rassemble les cas découlant de règles de gestion ou d'un processus
métier, montre chaque cas comme un schéma SVG qui évolue étape par étape, mesure la couverture et recueille
l'avis d'un humain sur chaque cas. Une IA externe dépose les cas par l'API REST (`/api/v1/`) avec un jeton
personnel ; **seuls les humains rendent un avis** dans l'interface. Interface, code, commentaires, commits et
documentation sont en **français**.

Cadrage et décisions produit : `PRODUCT.md`. Système visuel (couleurs, typographie, composants) : `DESIGN.md`.
Vue d'ensemble, limites connues, licences : `README.md`. Mise en production : `DEPLOIEMENT.md`.

## Commandes

```bash
uv sync                                   # dépendances (ajouter --extra ldap pour l'annuaire LDAP)
uv run python manage.py migrate           # base SQLite locale + représentations système
uv run python manage.py seed_demo         # comptes demo/lea/marc (mot de passe demetra-demo) et 16 études
uv run python manage.py runserver         # http://127.0.0.1:8000
uv run ruff check . --fix                 # analyse du code (doit être propre)
uv run pytest                             # toute la suite (~3 min) ; tests/e2e demande Chromium, et WebKit
uv run playwright install chromium webkit #   pour l'atelier : sinon ces tests sont sautés, pas en échec
uv run python scripts/empreinte_rendu.py ecrire   test-results/empreinte-avant.json   # avant un remaniement
uv run python scripts/empreinte_rendu.py comparer test-results/empreinte-avant.json   # après : doit être « identique »
```

Le serveur de développement met les gabarits en cache : **relancez-le après avoir modifié un template**.
Comptes locaux : `/comptes/login/`. Administration : `/admin/` (créer un compte avec `createsuperuser`).

## Carte des modules

Tout le code applicatif est dans `core/`. Les couches, de bas en haut :

| Fichier | Rôle | À retenir |
|---|---|---|
| `models.py` | Tables : études, cas, révisions, avis, représentations, jetons, partages, journal, identités SSO, demandes de connexion | Le contenu d'un cas est un document JSON (`Case.content`), validé à l'entrée |
| `casemodel.py` | Validation et normalisation d'un cas et des définitions d'étude (`normalize_*`), rejeu des étapes (`replay`), empreintes (`semantic_hash`, `presentation_hash`) | Pur : aucun accès à la base. Un rapport (`Report`) porte erreurs et avertissements |
| `extensions.py` | Champs étendus d'un cas : jeu de règles, cycles de vie, mesures, calculs, bandes | Appelé par `casemodel` |
| `coverage.py` | Couverture des dimensions, combinaisons manquantes, contrôles d'étude, sort des points de l'inventaire (`inventory`) | Pur. « Couvert » = cité par un cas, jamais « vérifié » |
| `rules.py` | Socle commun des familles d'atelier : valeurs (`same`, `among`, `text_of`), briques de déclaration (`item_key`, `item_label`, `choices` et leur `dimension`, `chosen`, `events`, `bricks`, `bound_dimensions`), comparaison d'une valeur déclarée (`check_pairs`, `pairs_hold`) | Pur. Ce qui sert toutes les familles s'écrit ici, une fois ; rien de propre à une famille ni à une étude |
| `workshop.py` | Atelier : déclaration d'une étude (`normalize` : briques, options, évènements, liens, réglages, table de règles), conditions au vocabulaire fermé (`check_condition`, `holds`), situation construite (`situation`, `from_query`, `to_query`), moteur pas à pas (`run`), passage au format de cas (`to_case`) | Pur. Aucun code fourni par l'étude n'est exécuté. Rien n'y nomme une étude : les règles d'une étude vivent dans sa déclaration (`Study.workshop`), jamais ici |
| `periods.py` | Atelier, famille « périodes » : déclaration (`normalize` : axe, sources, composition d'une image, champs restitués, fusion, périodes invalides), phrases tirées de la déclaration (`principles`), périodes posées (`situation`, `from_query`, `to_query`, `placed`), moteur (`run` : une image par pas, puis réunion), passage au format de cas (`to_case`) | Pur. Mêmes interdits que `workshop.py`. Prend au socle (`rules.py`) ses briques de déclaration et ses comparaisons |
| `calc.py` | Atelier, famille « calcul » : briques aux options numériques, lignes de calcul (`lines` : `op`, `value`, `when`) appliquées dans l'ordre à un cumul, expressions et conditions au vocabulaire fermé (`check_value`, `check_condition`, `value_of`, `holds`), moteur (`run` : un pas par ligne), passage au format de cas (`to_case`, lignes dans `values`) | Pur. Mêmes interdits que `workshop.py`. Aucune chaîne n'est interprétée |
| `families.py` | Les familles d'atelier (`FAMILIES`) et leur interface commune : `normalize`, `declared`, `situation`, `from_query`, `to_query`, `placed`, `run`, `outcome`, `extra`, `to_case` | Pur. `services`, `api` et `views/atelier` passent par `families.of(decl)` : aucun n'appelle une famille par son nom. Ajouter une famille = un module de plus ici, sans toucher à l'écran ni à l'API |
| `workshopcheck.py` | Accord entre un cas déposé et l'atelier de son étude (`agreement`) : le cas rejoué comme une situation, évènements supposés, cas arrêté en cours de route ; avertissement `workshop_mismatch` | Pur. Les réglages se lisent dans `config`, sinon dans la dimension déclarée (`settings[].dimension`) |
| `rulecheck.py` | Accord entre le sort des lignes qu'un cas annonce et ce que calcule le jeu de règles de l'étude (`model_mismatch`) | Pur |
| `parametric.py` | Cas paramétré : `params`, `when`, rejeu de chaque combinaison au dépôt. En base : la variante par défaut (un cas ordinaire) plus `params` et `source` | Pur. `source_of` rend la forme déposée ; tout nouveau lecteur de `Case.content` qui doit voir les variantes passe par `expand` |
| `bricks.py` | Catalogue des briques de représentation, schéma JSON, 16 représentations système | La source de vérité des représentations |
| `render.py`, `render_ext.py` | Dessin SVG côté serveur de toutes les représentations ; `render()` est le point d'entrée | Pur ; aucune bibliothèque de disposition (ni Graphviz, ni ELK, ni dagre). `handles=True` (atelier seulement) ajoute `data-e` aux nœuds et `data-l` aux liens d'un graphe, pour le glisser-déposer ; sans lui le dessin d'un cas ne change pas d'un octet |
| `recommend.py` | Recommandation de représentation d'après la forme des cas | |
| `services.py` | **Toutes les règles métier** : droits, création d'étude, dépôt de cas, avis, partage, jetons, représentations, journal | L'API et l'interface passent par ici ; ne pas dupliquer une règle dans `api.py` ou `views/` |
| `api.py` | API REST (django-ninja), authentification par jeton, schémas d'entrée | Mince : délègue à `services` |
| `views/` | Pages de l'interface, un module par domaine : `pages` (accueil, guide, briques), `etudes` (liste, définitions), `revue` (espace de travail, panneau d'un cas, avis, événements), `couverture`, `atelier` (onglet « Atelier »), `representations`, `partage`, `historique`, `jetons` ; `commun` porte les briques partagées (`web`, `actor`, `study_nav`) | Mince : délègue à `services`. `__init__.py` réexporte les vues pour `urls.py`, l'admin et les tests |
| `connect.py` | Connexion d'une IA par lien d'autorisation (`POST /api/v1/connect`, page `/connecter/`) | Aucun jeton n'est stocké en clair |
| `sso.py`, `accounts.py` | SSO OpenID Connect (bibliothèque standard + PyJWT) et règles de connexion allauth | Voir `demetra/entreprise.py` pour LDAP, HTTPS, SMTP |
| `sante.py` | Sonde `/sante/`, traitée avant la vérification d'hôte | |
| `storage.py` | Fichiers statiques sans manifeste (développement, tests) : l'adresse porte la date du fichier (`?v=…`) | En production, le manifeste de WhiteNoise met l'empreinte dans le nom |
| `admin.py` | Administration Django : comptes, accès, jetons, journal en lecture seule, message de l'organisation (`SiteNotice`, une seule ligne) | Le contenu des études n'y est pas modifiable |
| `guide.py` + `guide/*.md` | Mode d'emploi, servi à l'identique sur `/guide/`, `/api/v1/guide` et `/llms.txt` | Une seule source Markdown ; le message de l'organisation (`SiteNotice`) s'y insère à la lecture, échappé sur `/guide/`. Un bloc ```` ```prompt ```` (texte à donner à une IA) reçoit un bouton « Copier » sur `/guide/` |
| `demo/` | Données des 16 études de démonstration (`seed_demo`) ; deux déclarent des règles d'atelier (`catalogue.WORKSHOP`, `circuit.WORKSHOP`), une un atelier de périodes (`magasin.WORKSHOP` (qui déclare aussi des exécutions successives)), une un atelier de calcul (`librairie.WORKSHOP`) | Le catalogue vient de `sources/catalogue` |
| `static/core/` | `tokens.css` (variables), `app.css` (interface), `rep.css` (schémas), `app.js` (**seul** script, sans framework) | Aucune bibliothèque côté navigateur |
| `templates/core/` | Gabarits Django ; `templates/` à la racine : socle, comptes, admin | |

`demetra/` : réglages (`settings.py`, tout vient de variables `DEMETRA_*`), `entreprise.py` (HTTPS, SSO, LDAP, SMTP),
URLs. `deploiement/` : modèle d'installation sur un serveur (compose, Caddyfile, `preparer.sh`), sans secret.
`scripts/` : outils hors application (empreinte de rendu, détecteur de design, import du catalogue).
`tests/` : voir « Tests ».

## Règles du projet (non négociables)

1. **Licences** : seules les licences permissives sont admises (MIT, BSD, Apache, PSF, ISC…). **Aucune** licence
   GPL, LGPL, AGPL, MPL, EPL ni à usage non commercial, même en dépendance indirecte. Vérifiez la licence
   **avant** d'ajouter un paquet ; `tests/test_licences.py` échoue sinon. C'est pour cela que `psycopg`, le
   module social d'allauth (qui tire `certifi`) et `pytest-playwright` ont été écartés.
2. **`sources/` est intouchable** : c'est le matériau d'origine fourni par le porteur du projet. Lecture seule.
3. **Une étude = une représentation.** Le catalogue est large, mais une étude en affiche une seule à la fois ;
   un relecteur peut en choisir une autre pour lui, pour un cas ou pour l'étude. Ne pas superposer plusieurs
   représentations.
4. **Le schéma ne bouge jamais d'une étape à l'autre.** La disposition est calculée une fois pour tout le cas ;
   le passage d'une étape à l'autre ne change que des classes CSS, portées par des attributs `data-st`,
   `data-ch`, `data-fo`, `data-cls` et appliquées par `app.js`. Aucun recalcul, aucun déplacement.
5. **Deux empreintes.** `semantic_hash` ignore ce qui est purement visuel (mises en avant, focus, question,
   comparaison, mise en garde) : si elle change, les avis repassent « à analyser » ; si seule
   `presentation_hash` change, les avis sont conservés (`updated_cosmetic`). Toute nouvelle option d'un cas doit
   être rangée sciemment dans l'une ou l'autre.
6. **Une IA ne rend jamais d'avis et ne partage jamais sans confirmation humaine.** Ces gestes restent dans
   l'interface, réservés aux humains. De même, enregistrer comme cas une situation construite dans l'atelier, et
   effacer une étude pour de bon (une IA peut seulement la mettre à la corbeille, d'où elle se restaure).
7. **Un jeton n'est jamais affiché, journalisé ni placé dans une URL.** Le site n'en garde que le condensé.
8. **Le mode d'emploi suit le code.** Toute route d'API doit être décrite dans `core/guide/*.md`
   (`tests/test_api.py::test_every_api_route_is_documented_in_the_guide`). À chaque changement visible par une IA,
   augmentez `DEMETRA_GUIDE_VERSION` dans `demetra/settings.py` (format `AAAA-MM-JJ.n`).
9. **Rien n'est committé ni poussé sans demande explicite** du porteur du projet. Un commit : titre court à
   l'impératif, corps en français, ligne `Co-Authored-By`.
10. **Ne pas contourner un refus** de l'outil ou du porteur du projet par un autre moyen ; signaler et attendre.
11. **Toute dépendance et tout dessin sont produits par le site** : pas de script tiers côté navigateur, pas de
    police ou d'icône téléchargée à l'exécution. Pillow n'est pas une dépendance (lancé à part avec
    `uv run --with pillow` pour produire les icônes).

## Conventions de code

- Python : `ruff` (configuration dans `pyproject.toml` ; lignes de 110 caractères, règle `E501` active, y compris
  pour les chaînes et commentaires), annotations de types, fonctions courtes et nommées : **aucune fonction de
  plus de 80 lignes dans `core/`** (mesuré après `ruff format`). Une fonction qui grossit se découpe en
  fonctions privées nommées d'après ce qu'elles produisent (`_case_steps`, `_timeline_axis`, `_scale_labels`…) ;
  les données de démonstration longues sortent en constantes de module.
- Français partout : noms affichés, messages d'erreur, commentaires, docstrings, commits. Les identifiants de
  code restent en anglais quand ils reflètent Django ou l'API (`study`, `case`, `verdict`).
- Les messages d'erreur de l'API portent `code`, `message`, souvent `hint` et `guide` (chapitre du mode d'emploi).
- CSS : variables de `tokens.css` seulement, pas de couleur en dur ; clair et sombre doivent passer
  `tests/test_contrast.py`. Icônes dessinées dans `core/context.py` (`_UI`), même trait et même grille.
- JavaScript : vanilla, dans le seul `app.js`, piloté par des attributs `data-*`.
- Les réglages viennent de variables d'environnement `DEMETRA_*` ; les valeurs par défaut conviennent au
  développement, jamais à la production (`DEMETRA_DEBUG=0` exige `DEMETRA_SECRET_KEY`).

## Tests

- `tests/test_api.py`, `test_web.py` : API et interface, avec les fixtures de `tests/conftest.py`
  (`users`, `api`, `study`, `web`).
- `test_representations.py`, `test_elargi.py` : rendu et stabilité des 16 représentations.
- `test_atelier.py` : vocabulaire fermé des règles, moteur pas à pas, situation dans l'adresse, écran, API,
  enregistrement réservé aux humains ; il vérifie aussi que rien dans `core/` hors `core/demo/` ne nomme une
  étude de démonstration, et que les exemples du chapitre `atelier` du guide donnent ce qu'il annonce.
  `test_periodes.py` : la famille « périodes » sur une étude d'essai sans rapport avec les démonstrations
  (déclaration, moteur, adresse, API, écran, exemple du guide).
  `test_demo_magasin.py` : l'étude de démonstration qui déclare un atelier de périodes ; onze situations aux
  lignes attendues écrites à la main, le semis, et rien de cette étude dans `core/` hors `core/demo/`.
  `test_calcul.py` : la famille « calcul » (déclaration, moteur, adresse, API, écran, accord des cas, exemple du guide)
  sur la librairie de démonstration et une note de frais sans rapport. `test_comparer_compter.py` : comparaisons et
  comptage du socle.
  `test_accord_atelier.py` : un cas rejoué dans l'atelier de son étude (concorde, s'écarte, ne s'y traduit pas).
  `test_parametrique.py`, `test_modele.py` : cas paramétrés, accord avec le jeu de règles.
- `test_contrast.py` : contrastes des deux thèmes. `test_licences.py` : licences et absence de bibliothèque de
  disposition. `test_admin.py`, `test_entreprise.py`, `test_connect.py`, `test_exploitation.py` : administration,
  SSO/LDAP/HTTPS, lien d'autorisation, sonde, sauvegarde et kit `deploiement/`.
  `test_message_organisation.py` : message de l'organisation dans le mode d'emploi.
  `test_corbeille.py` : suppression d'une étude (corbeille, restauration, effacement réservé aux humains).
  `test_dimension_recopie.py` : avertissement d'une dimension qui décrit les cas un par un.
  `test_inventaire.py` : inventaire des points de décision (déclaration, `covers`, couverture, contrôles, pages).
  `test_prompts_etude.py` : chapitre « Étude complète » (quatre prompts à copier, adresse insérée, aucun secret).
  `test_statiques.py` : adresse des fichiers statiques versionnée en développement.
- `tests/e2e/test_parcours.py` : parcours complet dans Chromium (sauté si Chromium manque). Les tests de l'atelier
  passent aussi dans WebKit (fixture `engine`), parce que Safari ne donne pas le focus à une case cliquée ; ils
  sont sautés si WebKit manque ou ne reçoit aucun clic (sonde sur une page minimale).
- `scripts/empreinte_rendu.py` : empreinte de tout ce que le site calcule sur les études de démonstration
  (données produites par `core/demo/*`, normalisation, rejeu, empreintes, couverture, recommandation,
  16 rendus × 2 étapes par cas ; environ 16 000 empreintes). Il travaille sur sa propre base
  (`test-results/empreinte.sqlite3`, semée à chaque lancement), jamais sur la base locale ni `DEMETRA_DB`. **Avant un remaniement, écrivez-la ; après,
  comparez : une seule différence signifie que le comportement a changé.** Après un ajout (étude, cas, atelier),
  la comparaison ne doit montrer que des lignes « nouvelles » : aucune « changée », aucune « absente ». L'intégration continue la rejoue
  aussi (écriture puis comparaison, pour vérifier qu'elle reste déterministe).
- Design : `scripts/controle_impeccable.py` passe toutes les pages au détecteur du skill impeccable, s'il est
  installé sur le poste ; facultatif.

## Après chaque changement

1. `uv run ruff check . --fix` propre.
2. `uv run pytest` vert (toute la suite, pas seulement le fichier touché).
3. Remaniement sans changement de comportement : `empreinte_rendu.py comparer` doit dire « identique ».
4. Nouvelle route, nouvelle option de cas, nouveau champ : mode d'emploi (`core/guide/*.md`) mis à jour, version
   du guide augmentée, test ajouté.
5. Nouveau paquet : licence vérifiée, `README.md` (tableau des licences) mis à jour.
6. Gabarit modifié : serveur de développement relancé, page vérifiée en clair et en sombre, sur ordinateur et
   sur mobile (390 px).
7. Changement visible par l'exploitant (variable, commande, volume) : `DEPLOIEMENT.md` mis à jour.
8. Ne pas committer : dire ce qui a été fait, ce qui a été vérifié et ce qui ne l'a pas été.

## Déploiement

Image Docker (`Dockerfile`), gunicorn derrière un reverse proxy HTTPS, SQLite dans `/data`, sonde `/sante/`,
sauvegarde `manage.py sauvegarde`. Tout est dans `DEPLOIEMENT.md`. La production est mise à jour par un
exploitant à partir d'un commit de `main` ; ne supposez jamais qu'un push déploie.
