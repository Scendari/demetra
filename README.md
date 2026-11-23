# Demetra

Demetra rassemble les cas qui découlent d'un ensemble de règles de gestion ou d'un processus métier, montre
chaque cas comme un schéma qui évolue étape par étape, signale les combinaisons qu'aucun cas n'illustre encore,
et recueille l'avis d'un humain sur chacun : validé, refusé, à analyser.

Une IA externe (Claude Code, Cursor…) dépose les règles et les cas par une API REST, avec un jeton personnel.
Le site vérifie la structure, mesure la couverture et dessine. Il n'embarque aucun modèle de langage et
n'exécute aucun code fourni par l'IA.

Ce dépôt est un **POC fonctionnel**, conforme à `reports/Cadrage du projet Demetra.md` sauf pour les écarts
listés [plus bas](#écarts-avec-le-cadrage).

## Lancer le site

Prérequis : [uv](https://docs.astral.sh/uv/) (il installe Python 3.14 si besoin).

```bash
uv sync                                  # installe les dépendances
uv run python manage.py migrate          # crée la base SQLite et les 16 représentations système
uv run python manage.py seed_demo        # crée les comptes et les 12 études de démonstration
uv run python manage.py runserver        # http://127.0.0.1:8000
```

Comptes de démonstration (mot de passe `demetra-demo`) :

| Compte | Rôle sur les études de démonstration |
|---|---|
| `demo` | propriétaire |
| `lea` | commentatrice |
| `marc` | aucun accès (sert à essayer le partage) |

`seed_demo --token` crée en plus un jeton d'API pour `demo` et l'affiche une seule fois.
`seed_demo --no-verdicts` n'ajoute aucun avis de démonstration.

Facultatif — l'aperçu **image** d'une représentation (API `…/preview`) et le test de bout en bout ont besoin de
Chromium : `uv run playwright install chromium`. Sans lui, l'aperçu renvoie le résumé textuel seul.

## Connexion d'entreprise et HTTPS

Tout se règle par variables d'environnement ; sans elles, le site garde la connexion locale par mot de passe.
Les trois modes se combinent : bouton SSO, formulaire LDAP et comptes locaux sur la même page.

### SSO (OpenID Connect)

Entra ID (Azure AD), Okta, Keycloak, Google Workspace, ADFS, Authentik… : tout fournisseur qui publie
`/.well-known/openid-configuration`. Déclarez Demetra chez le fournisseur avec l'adresse de retour
`https://<votre-domaine>/comptes/sso/retour/`.

| Variable | Rôle |
|---|---|
| `DEMETRA_OIDC_ISSUER` | émetteur, par exemple `https://login.microsoftonline.com/<tenant>/v2.0` (obligatoire) |
| `DEMETRA_OIDC_CLIENT_ID`, `DEMETRA_OIDC_CLIENT_SECRET` | identifiants de l'application (le secret est facultatif : PKCE est toujours utilisé) |
| `DEMETRA_OIDC_NAME` | texte du bouton : « Continuer avec … » |
| `DEMETRA_OIDC_SCOPES` | défaut `openid email profile` |
| `DEMETRA_OIDC_USERNAME_CLAIM` | défaut `preferred_username` |
| `DEMETRA_OIDC_CREATE_USERS` | `1` par défaut : le compte est créé à la première connexion ; `0` : seuls les comptes déjà liés entrent |
| `DEMETRA_OIDC_LINK_BY_EMAIL` | `0` par défaut. À `1`, une première connexion SSO reprend le compte local de même e-mail. À n'activer que si le fournisseur garantit les adresses |
| `DEMETRA_OIDC_ALLOWED_DOMAINS` | domaines d'e-mail admis, séparés par des virgules |
| `DEMETRA_OIDC_ADMIN_GROUPS`, `DEMETRA_OIDC_GROUPS_CLAIM` | groupes qui donnent l'accès à `/admin/` ; claim `groups` par défaut. Le droit est recalculé à chaque connexion |
| `DEMETRA_OIDC_CA_BUNDLE` | autorité de certification interne, si le fournisseur en utilise une |

Le compte est lié à l'identité du fournisseur (émetteur et `sub`), jamais à l'e-mail seul. Le jeton
d'identité est vérifié : signature, émetteur, audience, expiration, nonce.

### Annuaire LDAP ou Active Directory

```bash
uv sync --extra ldap      # installe django-auth-ldap et python-ldap (bibliothèque OpenLDAP du système)
```

| Variable | Rôle |
|---|---|
| `DEMETRA_LDAP_URI` | `ldaps://annuaire.exemple.fr` (active le mode LDAP) |
| `DEMETRA_LDAP_BIND_DN`, `DEMETRA_LDAP_BIND_PASSWORD` | compte de service pour la recherche |
| `DEMETRA_LDAP_USER_BASE`, `DEMETRA_LDAP_USER_FILTER` | base et filtre de recherche ; filtre `(uid=%(user)s)` par défaut, `(sAMAccountName=%(user)s)` pour Active Directory |
| `DEMETRA_LDAP_USER_DN_TEMPLATE` | à la place de la recherche : `uid=%(user)s,ou=people,dc=exemple,dc=fr` |
| `DEMETRA_LDAP_START_TLS`, `DEMETRA_LDAP_CA_FILE` | StartTLS sur `ldap://` ; autorité de certification interne |
| `DEMETRA_LDAP_GROUP_BASE`, `DEMETRA_LDAP_GROUP_TYPE` | groupes : `groupOfNames` (défaut), `activedirectory` (groupes imbriqués) ou `posix` |
| `DEMETRA_LDAP_REQUIRE_GROUP` | DN du groupe obligatoire pour entrer |
| `DEMETRA_LDAP_ADMIN_GROUP` | DN du groupe qui donne l'accès à `/admin/` |
| `DEMETRA_LDAP_ATTR_FIRST_NAME`, `…_LAST_NAME`, `…_EMAIL` | défauts `givenName`, `sn`, `mail` |

Le formulaire de connexion interroge l'annuaire, puis les comptes locaux.

### Comptes locaux, inscription, e-mails

- `DEMETRA_SIGNUP_OPEN=0` ferme l'inscription. La page d'inscription refuse alors les envois, en plus de ne plus
  être proposée.
- `DEMETRA_PASSWORD_LOGIN=0` retire le formulaire de mot de passe : tout passe par le SSO. Le compte créé par
  `createsuperuser` entre toujours par `/admin/`, en secours.
- `DEMETRA_SMTP_HOST`, `DEMETRA_SMTP_PORT` (587), `DEMETRA_SMTP_USER`, `DEMETRA_SMTP_PASSWORD`,
  `DEMETRA_SMTP_STARTTLS` (1) et `DEMETRA_MAIL_FROM` règlent l'envoi des e-mails « mot de passe oublié ».
  Sans serveur SMTP, ces e-mails sont écrits dans la console.

### HTTPS

Le site ne gère pas TLS lui-même. Il tourne derrière un frontal HTTPS (Caddy, nginx, Apache, répartiteur de
charge), qui lui transmet les requêtes. Dès que `DEMETRA_DEBUG=0`, il impose HTTPS :

- cookies de session et CSRF marqués `Secure` ;
- redirection de HTTP vers HTTPS ;
- HSTS d'un an.

Il refuse aussi de démarrer sans `DEMETRA_SECRET_KEY`.

| Variable | Rôle |
|---|---|
| `DEMETRA_BEHIND_PROXY=1` | fait confiance à l'en-tête `X-Forwarded-Proto` du frontal (obligatoire derrière un frontal, sinon la redirection boucle) |
| `DEMETRA_HTTPS` | force (`1`) ou coupe (`0`) ces protections ; défaut : actives quand le débogage est coupé |
| `DEMETRA_HSTS_SECONDS`, `DEMETRA_HSTS_SUBDOMAINS`, `DEMETRA_HSTS_PRELOAD` | durée HSTS (31536000), sous-domaines (0), préchargement (0) |
| `DEMETRA_ALLOWED_HOSTS`, `DEMETRA_CSRF_TRUSTED_ORIGINS` | `demetra.exemple.fr` et `https://demetra.exemple.fr` |

`uv run python manage.py check --deploy` ne signale plus rien quand les variables HTTPS, SMTP et HSTS sont
renseignées.

### Administration

`/admin/` sert à exploiter le site, pas à relire. Y entrent les comptes « équipe » :
- ceux créés par `uv run python manage.py createsuperuser` ;
- les membres du groupe d'administration SSO ou LDAP.

Un lien « Administration » apparaît dans le menu pour eux seuls.

- **Tableau de bord** : comptes actifs, connexions de la semaine, études en cours, jetons actifs, signalements à
  traiter, événements des 7 derniers jours. Chaque chiffre ouvre la liste filtrée.
- **Comptes** : recherche, filtres (actif, équipe, SSO), nombre d'études et de jetons actifs, identités SSO liées.
  L'action « Désactiver » coupe aussi les jetons. La suppression en masse est retirée, parce qu'elle
  effacerait les études des comptes supprimés.
- **Études** :
  - transfert de propriété : l'ancien propriétaire reste éditeur ;
  - ajout, changement de rôle et retrait d'accès ;
  - archivage et désarchivage.

  Chaque geste est inscrit dans l'historique de l'étude, avec la mention « par l'administration du site ».
- **Jetons** : état (actif, révoqué, expiré), dernier usage. L'action « Révoquer » est journalisée. L'empreinte
  secrète n'est jamais affichée.
- **Signalements de brique** : état à traiter, prévu, fait ou écarté.
- **Consultation seule** : journal, cas, avis, représentations, propositions, demandes de partage. Le contenu
  des études passe par l'interface ou l'API, qui le vérifient et l'historisent.

## Ce que contient la démonstration

| Étude | Nature | Contenu |
|---|---|---|
| Catalogue des runs Lancelot | workflows et états | les 136 cas, 15 familles et 392 étapes de `sources/catalogue` |
| Remboursement d'une commande | règles de décision | 12 cas, 3 dimensions, 2 combinaisons manquantes, 1 combinaison déclarée impossible |
| Relances d'une facture impayée | règles temporelles | 12 cas datés (périodes, échéances, étapes positionnées dans le temps) |

Neuf autres études, à données fictives et marquées « Exemple », illustrent chacune une représentation du
catalogue élargi (règles logicielles et processus métier). Chacune porte la représentation qu'elle illustre.

| Étude d'exemple | Représentation | Ce qu'elle porte |
|---|---|---|
| Droits d'accès aux documents | Matrice croisée | 2 dimensions, 11 cas, 1 combinaison sans cas |
| Prix à payer d'une commande | Calcul pas à pas | 5 cas, lignes de calcul par étape |
| Validation d'une note de frais | Axe à bandes | 8 cas, dont un sur chaque seuil et un centime de part et d'autre |
| Changement d'adresse d'un assuré | Avant / après | 3 cas, champs de deux objets métier |
| Priorité d'un ticket de support | Table de règles | 9 lignes, 4 conditions, politique de priorité, 7 cas |
| Mode de livraison proposé | Arbre de décision | 6 lignes, 3 conditions, 6 cas |
| Validation d'un document | Table d'états | 6 états, 15 transitions, 4 cas |
| Cycle de vie d'une commande en ligne | Diagramme d'états | 8 états, 9 transitions dont une boucle sur soi et un retour, 5 cas |
| Paiement par carte d'une commande | Diagramme de séquence | 4 acteurs, 3 cas dont un message perdu |

`uv run python manage.py seed_demo` crée ou met à jour ces douze études ; la rejouer ne crée ni doublon ni
révision de cas.

Le catalogue est importé depuis `core/demo/catalogue_lancelot.json`, copie fidèle des données de
`sources/catalogue` produite par `scripts/dump_catalogue.mjs` (Node n'est nécessaire que pour régénérer cette
copie). `sources/` n'est jamais modifié.

## Faire travailler une IA

1. Dans l'interface : **Jetons d'accès › Créer un jeton**. Le secret est affiché une fois, avec un texte prêt à
   coller dans la conversation avec l'IA.
2. L'IA lit le mode d'emploi : `/llms.txt`, puis `GET /api/v1/guide` (public, par chapitre). La même
   documentation est lisible par un humain sur `/guide/` ; le contrat OpenAPI est sur `/api/v1/openapi.json`
   et `/api/v1/docs`.
3. Elle crée une étude, valide ses cas à blanc, les dépose, lit la couverture, fixe la représentation de
   l'étude, puis relit les avis et commentaires des relecteurs pour corriger.

`scripts/ia_externe.py` joue ce parcours complet avec la seule bibliothèque standard, puis dépose une seconde
étude au format étendu (tranches, jeu de règles, cycle de vie, montants, champs, messages) et choisit sa
représentation aux trois niveaux :

```bash
uv run python scripts/ia_externe.py --base http://127.0.0.1:8000 --token dmt_…
```

Ce qu'un jeton ne peut pas faire : rendre un avis (403 `human_only`), partager directement (la demande attend
une confirmation dans **Étude › Partage**), remplacer la représentation qu'un humain a choisie pour l'étude
(409 `human_choice`), dépasser le rôle de son titulaire, sortir des études auxquelles il est limité. Tout ce
qu'il fait est inscrit au journal de l'étude sous son nom.

## Représentations par briques

Une représentation est un document JSON validé par schéma, qui assemble des briques fournies par le site :
dispositions (`layout.*`), formes (`mark.*`), liaisons donnée → visuel (gabarits, filtres, mises en évidence),
évolution dans le temps (`time.*`) et composition (`compose.*`). Le site dessine lui-même en SVG et en HTML.
Le catalogue est sur `/briques/` et `GET /api/v1/bricks`.

Sept représentations système sont assemblées avec ces briques : graphe en couches à statuts, table de
décision, frise temporelle, table de trace, graphe et trace côte à côte, couloirs par groupe, vignettes par
étape. Par l'API, l'IA liste les briques, obtient les représentations recommandées pour une étude, en crée,
ajuste ou duplique une (ajustement personnel ou nouveau thème), demande un aperçu (image et résumé textuel)
et signale une brique manquante.

### Règles et processus : neuf représentations de plus

D'après `reports/Représentations des règles et processus.md`, le catalogue couvre aussi les règles chiffrées,
les jeux de règles, les cycles de vie et les échanges entre acteurs. Les neuf représentations sont fournies par
le site et assemblées avec des briques documentées sur `/briques/` (48 briques au catalogue), où chacune est
montrée sur un exemple :

| Représentation | Briques | Donnée lue |
|---|---|---|
| Matrice croisée | `layout.matrix`, `mark.tally` | deux dimensions, résultat des cas |
| Calcul pas à pas | `layout.grid` (`rows: values`), `mark.value` | `steps[].values` : libellé, opération, valeur, unité, cumul |
| Axe à bandes | `layout.scale`, `mark.band`, `mark.point` | `bands` d'une dimension, `measures` des cas |
| Avant / après | `layout.grid` (`rows: fields`), `mark.field` | `entities[].fields`, `steps[].fields` |
| Table de règles | `layout.grid` (`rows: rules`), `mark.cells_per_condition`, `mark.rule_result` | `ruleset` de l'étude, `steps[].rows` |
| Arbre de décision | `layout.tree`, `mark.decision`, `mark.conclusion` | `ruleset` de l'étude, dimensions du cas |
| Table d'états | `layout.grid` (`rows: states`), `mark.cells_per_event` | `lifecycles` de l'étude, changements d'état |
| Diagramme d'états | `layout.states`, `mark.state`, `mark.transition` | `lifecycles` de l'étude, changements d'état |
| Diagramme de séquence | `layout.lifelines`, `mark.lifeline`, `mark.message` | `steps[].messages` (reçu ou perdu) |

Le format de cas est étendu sans rien casser : tous les champs nouveaux sont facultatifs, un cas déjà déposé se
redépose à l'identique (`unchanged`) et garde ses avis. Chaque ajout est validé avec le chemin exact de
l'erreur, et le site contrôle la cohérence : ligne de règle citée existante, message entre entités déclarées,
transition présente dans le cycle de vie, mesure située dans la tranche déclarée. Modifier les tranches, le jeu
de règles ou un cycle de vie d'une étude est refusé si des cas déposés n'y sont plus conformes.

Tous les dessins sont calculés par le site en Python (arbre, diagramme d'états avec boucles et retours,
séquence) : aucune bibliothèque de mise en page, ni ELK ni Graphviz.

### Une étude = une représentation

Une étude a une représentation : celle que l'IA en charge de l'étude fixe en la déposant
(`PUT /api/v1/studies/{id}/representation`), ou à défaut la première conseillée. Le relecteur peut en changer
à trois niveaux, dans **Étude › Représentation** comme par l'API (`level`) :

| Niveau | Interface | API | Effet |
|---|---|---|---|
| pour lui | « Utiliser pour moi » | `"level": "me"` | lui seul, sur toute l'étude |
| pour un cas | « Pour le cas n° … seulement » ; « Suivre l'étude » pour revenir | `"level": "case", "case": "<clé>"` | lui seul, sur ce cas |
| pour toute l'étude | « Utiliser pour toute l'étude » (éditeur) | `"level": "study"` | tous les membres |

À l'affichage, le choix pour le cas l'emporte sur le choix personnel, qui l'emporte sur la représentation de
l'étude. Le conseil (`GET …/representations/recommended`) tient compte des données que portent les cas : pour
chacune des douze études de démonstration, la première représentation conseillée est celle qui convient, et un
test le vérifie.

La zone d'avis, le déroulé du cas (liste des étapes et, pour l'étape affichée, ce qui change d'état) et la
légende des statuts sont affichés par l'application, hors de la représentation. Un statut porte toujours une couleur de rôle, une icône et un libellé.

Le panneau d'un cas ne montre d'emblée que ce qui sert à juger : titre, résumé, résultat attendu, déroulé,
schéma et avis. Sous le résumé, deux rubriques nommées : « Paramètres », puis « Résultat attendu ». Les
paramètres non mis en avant et la légende des statuts se déplient à la demande (le choix est
mémorisé), comme les règles illustrées, les sources et les révisions. Le schéma ne change ni de place ni de
hauteur d'une étape à l'autre : le test dans le navigateur le vérifie sur un cas aux étapes volontairement
inégales, et, pour les neuf représentations du catalogue élargi, sur chaque cas de leur étude d'exemple, à
chaque étape et à deux largeurs.

L'IA peut désigner, par l'API, les caractéristiques à garder sous les yeux du relecteur, à deux niveaux :
pour toute l'étude, en ajoutant `"highlight": true` à une dimension ; pour un seul cas, avec le champ
`highlights` du cas, qui liste jusqu'à quatre clés de ses `dimensions` ou de sa `config`. Elles s'affichent
avec leur valeur à côté du résultat attendu ; les changer ne remet pas les avis en cause. Dans la
démonstration, l'option `stop_on_error` est marquée pour toute l'étude du catalogue.

Un cas peut aussi mettre en avant une option portée par une entité, `{"entity": "C", "attr": "always_run"}` :
elle s'affiche dans les paramètres du cas et sur l'entité elle-même, dans les représentations qui dessinent les
entités (graphes, couloirs, vignettes, table de trace, frise, séquence). L'IA en choisit le style dans une liste
fermée : gras ou normal, italique, teinte du site (encre, secondaire, accent ou rôle de statut), jamais une couleur
libre. Dans le catalogue Lancelot, les options qui s'écartent du défaut (`always_run`, `ignore_on_error` à vrai,
`active` à faux) sont mises en avant sur leur tâche, dans 43 cas.

L'IA dispose aussi de quoi guider le relecteur, sans toucher aux avis déjà rendus :

- `steps[].focus` : l'entité à regarder à une étape (anneau accent sur le schéma, ligne « À regarder » dans l'étape) ;
- `question` : ce que l'avis doit trancher, affiché au-dessus des boutons d'avis ;
- `compare_with` : le cas « contraire », avec le tableau de ce qui diffère et un lien qui l'ouvre ;
- `{"link": [de, vers]}` dans `highlights` : un lien tracé en trait renforcé ;
- `attributes` dans l'étude : le libellé lisible et la définition de chaque option des entités, au survol ; le schéma
  garde le nom technique et la valeur telle qu'elle est écrite (`always_run : true`), sauf si l'étude demande le libellé
  (`"show": "label"`, la valeur se lit alors oui / non). Une option non déclarée donne un avertissement au dépôt.

Dans la démonstration, l'étude Lancelot définit ses cinq options d'après le catalogue d'origine et désigne, à chaque
étape, la Task sur laquelle le moteur prend une décision ; l'étude fictive des remboursements pose une question et
propose le cas jumeau quand le type de client change la décision.

## Tests et preuves

```bash
uv run pytest                 # 135 tests : services, API, interface, représentations, format étendu, démonstration, contrastes, navigateur
uv run pytest tests/e2e       # le parcours dans Chromium seul
DEMETRA_CAPTURES=docs/captures uv run pytest tests/e2e   # régénère les captures d'écran
uv run ruff check .
```

- `tests/test_api.py` — jetons (hachés, portées, révocation, expiration, limitation à une étude), dépôt en lot
  rejouable, validation à blanc, clé d'idempotence, erreurs précises, couverture et combinaisons manquantes,
  avis réservés aux humains, cas modifié qui repasse « à analyser », partage en attente de confirmation,
  rôles, journal humain/jeton.
- `tests/test_representations.py` — catalogue de briques, documents refusés, création, ajustement,
  duplication, versions, aperçu, statut jamais porté par la couleur seule, import complet du catalogue
  (136 / 15 / 392), rendu de chaque cas dans chaque représentation système (2 240 rendus).
- `tests/test_elargi.py` — format étendu (chemin exact de chaque erreur, contrôles de cohérence, cas anciens
  inchangés et avis conservés, modification d'étude refusée si des cas en dépendent), les neuf représentations
  (documents valides, briques documentées, rien d'autre qu'une brique n'est accepté, texte hostile dessiné comme
  du texte, statut jamais porté par la couleur seule, résumé textuel et aperçu image par l'API), choix à trois niveaux par l'API et dans
  l'interface, première représentation conseillée de chaque étude de démonstration, démonstration rejouable.
- `tests/test_contrast.py` — contrastes des jetons de couleur dans les deux thèmes, y compris les textes et
  traits des nouvelles représentations ; aucun texte n'y est estompé par transparence.
- `tests/test_web.py` — inscription, connexion, pages, revue, partage, choix de représentation, jetons,
  flux d'événements.
- `tests/e2e/test_parcours.py` — dans un vrai navigateur : connexion, revue d'un cas au clavier (avec
  annulation), filtres et recherche, mode focus, passage d'un cas à l'autre avec Tab, panneaux repliables,
  changement de représentation, partage vérifié depuis le
  compte invité, jeton créé dans l'interface, **mise à jour en direct** quand l'API modifie l'étude ouverte,
  thème sombre, petit écran. Un second test parcourt les neuf représentations du catalogue élargi : schéma
  immobile d'une étape à l'autre, thème sombre, largeur mobile sans défilement de la page, choix « pour ce cas
  seulement » puis retour à l'étude, exemples de la page Briques.
- `tests/test_licences.py` — toute dépendance installée doit avoir une licence de la liste admise ; aucune
  licence EPL, MPL, LGPL, GPL ou AGPL, même au choix ; aucune bibliothèque de mise en page (ELK, Graphviz…)
  ni script tiers dans l'interface.
- `docs/captures/` — captures des écrans principaux, produites par les tests de bout en bout ; `19` à `27` :
  une capture par représentation du catalogue élargi ; `28` : le choix à trois niveaux ; `29` : les exemples de
  la page Briques ; `30` : diagramme de séquence sur petit écran.

## Architecture en bref

```
core/services.py     toutes les règles métier ; l'interface et l'API passent par cette seule couche
core/api.py          API REST (Django Ninja), jetons Bearer, erreurs structurées
core/views.py        interface (gabarits Django + JavaScript natif, sans cadre côté navigateur)
core/casemodel.py    format de cas, validation, rejeu des étapes, empreinte du déroulé
core/extensions.py   format étendu : tranches, jeu de règles, cycles de vie, montants, champs, messages
core/coverage.py     couverture par combinaisons de dimensions, contrôles de structure
core/bricks.py       catalogue de briques, schéma JSON, validation et fusion des documents
core/render.py       dessin SVG/HTML des représentations (aucun code tiers exécuté)
core/render_ext.py   dessin des neuf représentations du catalogue élargi
core/samples.py      exemples de la page Briques, tirés des études de démonstration
core/recommend.py    présélection des représentations d'après la forme des cas
core/preview.py      aperçu image (Chromium, facultatif)
core/guide/          mode d'emploi destiné aux IA (Markdown)
core/demo/           études de démonstration
```

Un cas décrit des entités, des liens et des étapes qui ne déclarent que **ce qui change** ; le site rejoue ces
changements. L'avis d'un relecteur est attaché à l'empreinte du déroulé : corriger un titre conserve l'avis,
changer le déroulé le remet « à analyser » et garde l'ancien dans l'historique.

Conception de l'interface : `PRODUCT.md` (contexte produit) et `DESIGN.md` (système de design), établis avec le
skill impeccable.

## Licences : tout est utilisable en entreprise

Aucune dépendance sous licence à copyleft, fort ou faible (GPL, AGPL, LGPL, MPL, EPL), ni à usage non
commercial. Le test `tests/test_licences.py` échoue si une dépendance installée sort de la liste admise.
La connexion d'entreprise a ajouté PyJWT et cryptography (SSO) et, en option, django-auth-ldap et python-ldap.
Le module social de django-allauth a été **écarté** : il tire `requests`, donc `certifi`, sous licence MPL-2.0.
Le client OpenID Connect est écrit avec la bibliothèque standard.

| Composant | Version | Licence | Usage |
|---|---|---|---|
| Python | 3.14 | PSF-2.0 | langage |
| Django | 6.1.3 | BSD-3-Clause | socle web, ORM, comptes |
| django-allauth | 65.22.1 | MIT | inscription et connexion |
| django-ninja | 1.8.0 | MIT | API REST et OpenAPI |
| pydantic, pydantic-core | 2.14.4, 2.50.5 | MIT | schémas de l'API |
| annotated-types, typing-inspection | 0.8.0, 0.4.5 | MIT | dépendances de pydantic |
| typing-extensions | 4.16.0 | PSF-2.0 | dépendance de pydantic |
| jsonschema, jsonschema-specifications, referencing, rpds-py, attrs | 4.26.0… | MIT | validation des représentations |
| Markdown | 3.11.3 | BSD-3-Clause | rendu du mode d'emploi |
| PyJWT | 2.15.1 | MIT | vérification du jeton d'identité (SSO) |
| cryptography, cffi, pycparser | 50.0.2, 2.1.1, 3.12 | Apache-2.0 ou BSD-3-Clause, MIT-0, BSD-3-Clause | signatures RSA et EC du SSO |
| django-auth-ldap | 5.4.0 | BSD-3-Clause | connexion par l'annuaire (option `ldap`) |
| python-ldap, pyasn1, pyasn1-modules | 3.4.8, 0.6.5, 0.4.2 | PSF (python-ldap), BSD-2-Clause | client LDAP (option `ldap`) ; s'appuie sur la bibliothèque OpenLDAP du système (licence OpenLDAP, permissive) |
| asgiref, sqlparse | 3.13.0, 0.6.1 | BSD-3-Clause | dépendances de Django |
| playwright | 1.65.2 | Apache-2.0 | aperçu image, test de bout en bout |
| greenlet | 3.5.6 | MIT et PSF-2.0 | dépendance de playwright |
| pytest, pluggy, iniconfig | 9.2.0… | MIT | tests (développement) |
| pytest-django | 4.14.0 | BSD-3-Clause | tests (développement) |
| packaging | 26.3 | Apache-2.0 ou BSD-2-Clause | tests (développement) |
| Pygments | 2.21.0 | BSD-2-Clause | tests (développement) |
| ruff | 0.17.6 | MIT | analyse du code (développement) |
| uv | 0.13 | MIT ou Apache-2.0 | gestion du projet (outil) |
| SQLite | — | domaine public | base de données |
| Police Archivo | variable | SIL OFL 1.1 | interface ; fichier et licence dans `core/static/core/fonts/` |
| Chromium | — | BSD-3-Clause et autres licences permissives | téléchargé par Playwright sur le poste, **non redistribué** |

Les icônes, les dessins et tout le JavaScript de l'interface sont écrits pour ce projet : aucune bibliothèque
côté navigateur. Le personnage de Demetra (accueil, logo du menu, icône d'onglet et du site) est une image générée et fournie
par le porteur du projet (`icon_small.png`) ; les fichiers de `core/static/core/` en sont tirés par recadrage et mise
à l'échelle (Pillow, lancé à part avec `uv run --with pillow`, pas une dépendance du projet). `pytest-playwright` a été écarté parce qu'il tire `text-unidecode` (Artistic/GPL) ; le test
de bout en bout pilote Playwright directement.

Cette liste a été établie à partir des métadonnées des paquets installés ; elle ne vaut pas avis juridique.

## Écarts avec le cadrage

Voulus par la demande :

- **Pas de MCP** : API REST seule.
- **Représentations par briques** assemblées par l'IA, au lieu des thèmes à surcharge de paramètres du cadrage.
- **Une étude = une représentation**, fixée par l'IA qui dépose l'étude ; le cadrage réservait ce choix à
  l'humain. Le relecteur garde la main : il en change pour lui, pour un cas ou pour toute l'étude, et un jeton
  ne remplace pas un choix humain fait pour l'étude.
- **Ni ELK ni Graphviz** : les licences EPL, MPL, LGPL, GPL et AGPL sont exclues ; les dessins sont calculés
  par le site.

Choix du POC :

- **SQLite** au lieu de PostgreSQL.
- **Jetons personnels uniquement** pour l'API : pas d'OAuth. Le SSO ne sert qu'à la connexion au site.
- **Un avis par relecteur et par cas** ; pas de règle de consensus entre relecteurs.
- Vérification de niveau « A renforcé » seulement : structure, rejeu, couverture sur dimensions déclarées,
  doublons. Pas de vérification formelle des tables de décision ni de modèle à états simulé.
- Disposition des graphes calculée par le site en Python ; ni dagre ni ELK.
- Le niveau de preuve d'un cas se limite à « affirmé » ou « constaté ».
- Non réalisés : avis en lot, commentaires ancrés à une étape ou à un nœud, comparaison avant/après d'un cas
  modifié (l'historique des révisions est listé, sans différence visuelle), galerie de cartes, indicateur
  d'étapes vues, progression par famille, export de fichier (les données sortent par l'API).
- Catalogue élargi, limites connues : l'axe à bandes est schématique (chaque tranche a la même largeur, l'ordre
  des valeurs est respecté, pas les distances) ; l'arbre de décision est déduit du jeu de règles, condition
  après condition dans l'ordre déclaré, sans optimisation ; le diagramme d'états range les états par rangs et
  trace les retours en arc, sans minimiser les croisements — quand les transitions sont nombreuses (plus de
  deux par état), c'est la table d'états qui est conseillée ; le diagramme de séquence ne dessine ni fragments (alternative, boucle) ni durées
  d'activation ; la matrice croise deux dimensions, pas davantage. Calcul pas à pas, axe à bandes et
  avant / après ne montrent aucun statut coloré, seulement des nombres et des textes.
- Le site contrôle la cohérence des champs étendus, pas leur vérité : il ne recalcule pas la ligne de règle
  retenue d'après la politique, et un cumul de calcul incohérent n'est qu'un avertissement.
- Les signalements de brique manquante se suivent dans l'administration (`/admin/`), sans écran dédié dans
  l'application.
- impeccable : `PRODUCT.md` a été rédigé à partir du cadrage, sans l'entretien interactif du skill.

## Ce qui n'a pas été vérifié

- **Déploiement** : seul `runserver` a été utilisé. Aucun essai derrière un serveur de production, en HTTPS,
  ni avec plusieurs processus. Les réglages HTTPS sont posés et `check --deploy` ne signale plus rien, mais
  aucun frontal réel n'a été essayé. Avec `DEMETRA_DEBUG=0`, les fichiers statiques ne sont plus servis par
  Django : `collectstatic` puis le frontal doit servir `staticfiles/`.
- **SSO et LDAP** : vérifiés par tests avec un fournisseur simulé (vraie signature RSA, découverte, échange du
  code avec PKCE) et un annuaire simulé. Aucun essai contre un vrai Entra ID, Keycloak ou Active Directory.
- **Charge** : le flux d'événements en direct occupe un fil par étude ouverte, à dimensionner avant tout usage
  réel.
- **Navigateurs** : Chromium uniquement. Firefox et Safari n'ont pas été essayés.
- **Catalogue élargi** : la stabilité de l'affichage est vérifiée sur les cas des études de démonstration, pas
  sur des jeux de règles ou des cycles de vie de grande taille (le plus gros essayé : 9 lignes de règles,
  8 états, 15 transitions, 4 acteurs). Sur petit écran, les schémas larges (séquence, arbre) défilent dans leur
  cadre et leur texte est réduit ; la lisibilité n'a été jugée que sur captures.
- **Détecteur impeccable** : il a été passé à la main, hors de la suite de tests (il dépend du skill installé
  sur le poste), sur les feuilles de style puis sur les pages rendues dans Chromium, à 1440 et 390 px, en thème
  clair et en thème sombre. Écrans passés : accueil, connexion, inscription, déconnexion, page introuvable, les
  huit pages du mode d'emploi, liste des études, jetons, page Briques, une étude sans cas ; la revue d'un cas
  de chacune des douze études de démonstration, puis légende et aide clavier ouvertes ; le choix de la
  représentation ; couverture, partage, historique, règles et définitions (une étude d'origine, deux
  nouvelles). La revue des neuf représentations nouvelles ne lève aucun constat, et aucun type de constat
  n'apparaît sur une étude nouvelle sans apparaître sur une étude d'origine. La carte de démonstration de
  l'accueil, qui encadrait un schéma lui-même encadré, a été remplacée par un simple filet. L'accueil montre
  désormais un cas fictif qui se déroule seul dans le diagramme d'états (arrêt à la première flèche ou au bouton
  pause, rien de lancé si le système demande moins d'animation) ; un test navigateur vérifie la lecture,
  l'arrêt et l'immobilité du schéma ; le cas « moins d'animation » a été vérifié à la main dans Chromium.
- **Constats acceptés** : restent cinq constats, tous antérieurs au catalogue élargi, acceptés le 22/11/2026 :
  le fond quadrillé du schéma (choix de design) ; l'échelle de titres serrée des onglets d'étude (20, 17 et
  15 px) ; les hachures des combinaisons exclues en couverture (elles portent du sens) ; dans l'étude
  « Relances d'une facture impayée », le nombre de tirets longs des textes et les étapes repliées sur petit
  écran. `scripts/controle_impeccable.py` passe tous les écrans au détecteur, dans les deux thèmes et aux deux
  largeurs, et échoue sur tout constat hors de cette liste :
  `uv run python scripts/controle_impeccable.py --detecteur <lanceur du skill impeccable>` (serveur de
  démonstration lancé). Il ne fait pas partie de `pytest`, car il dépend du skill installé sur le poste.
  Dernier passage (22/11/2026), contre une copie de la base servie sans mode débogage pour inclure la vraie
  page 404 : 348 écrans, aucun constat hors de la liste.
- **Gabarits pris comme fichiers** : lancé sur `core/templates` et `templates`, le détecteur signale un avis
  `design-system-color` par gabarit, y compris sur les 16 gabarits que ce travail n'a pas touchés. Il lit le
  gabarit sans sa feuille de style et voit le noir par défaut du navigateur ; l'avis disparaît dès que les
  styles du site sont attachés, et n'apparaît sur aucune page rendue. Faute d'historique git, les six
  gabarits modifiés ont été reconstruits dans leur état d'avant en défaisant chaque retouche (la
  reconstruction échoue si un texte ne se retrouve pas exactement une fois) : le détecteur donne 22 avis
  avant et 22 après, le même, sur le même élément de chaque gabarit.
- **Accessibilité** : dans la liste des cas, Tab passe au cas suivant au lieu de suivre l'ordre habituel du
  focus ; Entrée entre dans le cas, où Tab retrouve son rôle (c'est indiqué dans l'aide, touche `?`). Ce choix
  n'a pas été essayé avec des personnes qui naviguent uniquement au clavier. Navigation au clavier et libellés
  ont été conçus et relus sur captures ; les contrastes des
  jetons de couleur sont calculés par un test dans les deux thèmes (texte ≥ 4,5:1, contours de contrôle et
  focus ≥ 3:1), pas mesurés sur les pixels rendus. Aucun essai avec un lecteur d'écran, aucun audit automatisé
  de type axe.
- **IA réelle** : le parcours d'API est joué par un script déterministe. Aucune session pilotée par un vrai
  assistant n'a été menée.
- **Charge** : l'étude la plus grosse essayée compte 136 cas. Pas de limitation de débit sur l'API.
- **Courriels** : l'adresse n'est pas vérifiée à l'inscription et aucun envoi réel n'est configuré.

## État du dépôt

Le dépôt git est initialisé ; **rien n'a été committé**. `sources/` n'a pas été modifié.
