# Pile Python et architecture applicative (état au 21 novembre 2026)

*Méthode : numéros de version et dates relevés le 21/11/2026 directement dans les registres PyPI, npm, GitHub Releases, postgresql.org et sqlite.org ; documentation officielle lue pour FastAPI, Django, htmx, django-allauth, SDK MCP, FastMCP ; manifestes de dépendances (pyproject / requirements / package.json) lus sur GitHub pour les applications comparables ; prototype local lu en lecture seule. « Versions sur 12 mois » = nombre de publications PyPI depuis le 21/11/2025.*

## 1. Framework backend : FastAPI, Django (+ Django Ninja / DRF), Litestar

### Takeaway
Pour un développeur seul qui doit livrer comptes, partage, permissions, historique, admin et API, **Django 6.1 + Django Ninja** est le choix le plus économe : tout ce qui n'est pas le coeur du produit est fourni et stable, alors que FastAPI (toujours en 0.x, 128 versions et 14 versions « Breaking Changes » en cinq mois) oblige à assembler soi-même auth, sessions, permissions, admin et migrations. FastAPI garde un avantage net sur un seul point : monter un serveur MCP dans le même processus y est documenté et trivial, alors que côté Django cela demande une composition ASGI ou un petit processus séparé.

### Cited Findings

**FastAPI**
- Dernière version 0.165.0 (18/11/2026), toujours en 0.x ; 128 versions publiées en 12 mois ; Python >= 3.11 — [PyPI fastapi](https://pypi.org/project/fastapi/)
- Entre 0.137.0 (14/06/2026) et 0.162.6 (13/11/2026), quatorze versions comportent une section « Breaking Changes », dont une grappe du 18 au 20/10/2026 (traitement des formulaires, `null` JSON distingué de l'absence de valeur en 0.151.0, suppression des `**extra` en 0.155.0, changement de 0.147.0 annulé en 0.162.0, Python 3.10 abandonné en 0.162.6) — [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/)
- Ajouts récents utiles ici : `app.frontend("/", directory="dist")` pour servir un frontend compilé (0.138.0), dépendances d'auth par cookie sur ce frontend (0.139.0), module `fastapi.sse` documenté et corrigé (0.140.12-13), OpenTelemetry natif (0.142.0), sécurité sur WebSocket (0.144.0), limites de taille de corps de requête (0.164.0), Python 3.15 (0.162.3) — [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/)
- Les notes lues (jusqu'à 0.136.2) ne mentionnent aucune échéance pour une version 1.0 — [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/)
- Starlette (socle de FastAPI) est en 1.10.0 (24/10/2026) — [PyPI starlette](https://pypi.org/project/starlette/)
- Enquête Python Developers Survey (résultats publiés en août 2025) : FastAPI 38 % (contre 29 % l'année précédente), Django 35 %, Flask 34 % — [The Register](https://www.theregister.com/software/2025/08/19/python-usage-growing-while-foundation-struggles-for-funds/937983) (chiffres repris d'un extrait de recherche, page primaire JetBrains/PSF non consultée)

**Django**
- Django 6.1 est sorti le 5 août 2026 ; version courante 6.1.3 (03/11/2026) ; Python 3.12 à 3.15 ; support standard jusqu'en avril 2027, étendu jusqu'en décembre 2027 — [Django 6.1 release notes](https://docs.djangoproject.com/en/6.1/releases/6.1/), [PyPI django](https://pypi.org/project/django/)
- Django 6.0 (3 décembre 2025) a intégré les *template partials* (`{% partialdef %}`, syntaxe `template#partial`, très utile avec htmx) et un framework de tâches de fond (`@task`), sans worker fourni — [Django 6.0 release notes](https://docs.djangoproject.com/en/6.0/releases/6.0/)
- Django 6.1 ajoute les *fetch modes* (`FETCH_PEERS` contre les N+1), les `on_delete` côté base (`DB_CASCADE`), les nonces CSP dans les templates (`csp_nonce_attr`), `JSONNull`, les fonctions `UUID7` ; SQLite minimum 3.37 ; PostgreSQL 14 abandonné — [Django 6.1 release notes](https://docs.djangoproject.com/en/6.1/releases/6.1/)
- Django Ninja 1.8.0 (08/11/2026), 19 versions en 12 mois ; DRF 3.18.3 (06/10/2026), 7 versions en 12 mois — [PyPI django-ninja](https://pypi.org/project/django-ninja/), [PyPI djangorestframework](https://pypi.org/project/djangorestframework/)
- Enquête Django (environ 4 600 répondants) : 51 % utilisent Django pour une API REST avec DRF ; paquets favoris : djangorestframework 49 %, django-debug-toolbar 27 %, django-allauth 18 % ; Django Ninja « continue de gagner en popularité comme alternative à DRF » (sans chiffre) — [Django Developers Survey, JetBrains](https://lp.jetbrains.com/django-developer-survey-2025/)
- Streaming/SSE : « When serving under ASGI [...] a StreamingHttpResponse need not stop other requests from being served whilst waiting for I/O. This opens up the possibility of long-lived requests for streaming content and implementing patterns such as long-polling, and server-sent events » ; sous WSGI en revanche un flux « will tie a worker process for the entire duration of the response » — [Django request/response](https://docs.djangoproject.com/en/6.1/ref/request-response/)

**Litestar**
- Litestar 2.25.0 (18/10/2026), 8 versions en 12 mois ; aucune version 3 stable publiée sur PyPI à la date de collecte ; plugin `litestar-htmx` 0.5.0 sans publication depuis juin 2025 — [PyPI litestar](https://pypi.org/project/litestar/), [PyPI litestar-htmx](https://pypi.org/project/litestar-htmx/)

**MCP dans le même processus**
- SDK officiel `mcp` 2.3.0 (02/10/2026), 27 versions en 12 mois ; FastMCP 4.2.4 (21/11/2026), 80 versions en 12 mois — [PyPI mcp](https://pypi.org/project/mcp/), [PyPI fastmcp](https://pypi.org/project/fastmcp/)
- Le SDK (v2, classe `MCPServer`) expose `streamable_http_app()`, une application Starlette ASGI montable dans FastAPI/Starlette via `Mount` ; le lifespan de l'application hôte doit entrer `mcp.session_manager.run()` (sinon « Task group is not initialized ») ; derrière un vrai nom d'hôte, toute requête reçoit `421 Misdirected Request` tant que `TransportSecuritySettings(allowed_hosts, allowed_origins)` n'est pas renseigné ; la page ne cite que Starlette, FastAPI, uvicorn, Hypercorn (Django non mentionné) — [MCP Python SDK, Add to an existing app](https://py.sdk.modelcontextprotocol.io/run/asgi/)
- FastMCP : `mcp.http_app(path=...)` se monte par `app.mount()` avec `combine_lifespans` ; `FastMCP.from_fastapi(app)` convertit les routes en outils mais la doc le réserve au prototypage : les LLM « perform significantly better with well-designed, curated MCP servers than with auto-converted OpenAPI servers » — [FastMCP, FastAPI integration](https://gofastmcp.com/integrations/fastapi)
- Côté Django, les paquets tiers sont jeunes ou peu actifs : `django-mcp-server` 0.5.7 (dernière publication 10/10/2025, aucune en 12 mois), `django-rest-mcp` (fine couche au-dessus du SDK officiel, Python 3.12+, Django 5.1+), `djangorestframework-mcp-server` 0.13.0 — [PyPI django-mcp-server](https://pypi.org/project/django-mcp-server/), [PyPI django-rest-mcp](https://pypi.org/project/django-rest-mcp/), [PyPI djangorestframework-mcp-server](https://pypi.org/project/djangorestframework-mcp-server/0.13.0/)
- Authentification des connecteurs distants côté Claude : trois modes documentés, OAuth 2.0, identifiant statique envoyé dans un en-tête (bêta, saisi par un Owner de l'organisation) ou aucune authentification — [Claude connectors, authentication](https://claude.com/docs/connectors/building/authentication) (lu via extrait de recherche)

**Admin**
- Admins tiers pour FastAPI/SQLAlchemy : `sqladmin` 0.32.0, `starlette-admin` 1.0.3 ; côté Django, l'admin est intégré et `django-unfold` 0.110.1 le modernise — [PyPI sqladmin](https://pypi.org/project/sqladmin/), [PyPI starlette-admin](https://pypi.org/project/starlette-admin/), [PyPI django-unfold](https://pypi.org/project/django-unfold/)

### Inferences
- **Comparatif synthétique** (jugement) :

| Critère | Django 6.1 + Ninja | FastAPI 0.165 | Litestar 2.25 |
|---|---|---|---|
| Auth, sessions, CSRF, admin | intégrés + allauth | à assembler | à assembler (plugins) |
| OpenAPI / Pydantic | oui via Ninja | natif | natif (msgspec/Pydantic) |
| Async, SSE | oui sous ASGI, ORM surtout synchrone | natif, `fastapi.sse` | natif |
| MCP même processus | composition ASGI à écrire | documenté | faisable (ASGI), non documenté par le SDK |
| Stabilité d'API | calendrier de dépréciation, LTS | 0.x, ruptures fréquentes | stable mais petite communauté |
| Migrations | intégrées | Alembic | Alembic |

- **Agents de code IA** : la cadence de ruptures de FastAPI fin 2026 signifie que les connaissances d'un agent (figées à sa date d'entraînement) divergent vite du comportement réel ; Django, très conventionné et à dépréciations lentes, réduit le volume de code spécifique que l'agent doit inventer et que le développeur seul doit relire. C'est un argument de maintenabilité, pas de performance.
- **MCP avec Django, trois voies** : (a) une application Starlette externe qui monte `/mcp` (SDK officiel, mode HTTP streamable) et délègue tout le reste à `get_asgi_application()`, le lifespan Starlette pilotant le gestionnaire de sessions MCP ; (b) un petit processus FastMCP séparé qui appelle l'API REST avec le jeton de l'utilisateur ; (c) un paquet tiers Django-MCP (maturité insuffisante). La voie (a) garde un seul conteneur ; la voie (b) est la plus découplée. Dans tous les cas, écrire les outils MCP à la main au-dessus des mêmes fonctions de service que l'API REST, plutôt que de convertir l'OpenAPI.
- Litestar est techniquement solide mais sa petite communauté et son rythme plus lent en font un pari inutile pour un projet mené seul.
- **Pile recommandée (synthèse)** : Python 3.14, Django 6.1, Django Ninja (API REST + OpenAPI), django-allauth (comptes, passkeys, OIDC), PostgreSQL 18 (SQLite WAL en variante mono-conteneur), templates Django + htmx + Alpine pour l'habillage, composants web en JavaScript natif pour le visualiseur de cas, SSE pour le temps réel, SDK `mcp` monté en ASGI, uv/ruff/pytest/Playwright, Docker Compose + Caddy. Alternative crédible si l'on préfère une SPA : FastAPI + SQLAlchemy 2.1 + Alembic + Authlib + SvelteKit (modèle Open WebUI / Mealie), au prix de l'auth, des permissions et de l'admin à écrire.

### Gaps
- Les notes de Django 6.1 évoquent un passage au versionnage calendaire (« Django 2028 », avertissements `RemovedInDjango2028Warning`) ; le résumé obtenu est ambigu sur le calendrier exact et sur la prochaine LTS. À vérifier avant de choisir entre 6.1 et 5.2 LTS (authentik, Paperless-ngx et Tandoor épinglent encore Django 5.2.x).
- Je n'ai pas pu lire la doc d'authentification de Django Ninja (404) : la combinaison session + `HttpBearer` sur une même route est à confirmer dans la doc 1.8.
- Aucune source primaire trouvée sur un calendrier FastAPI 1.0, ni sur l'état de Litestar 3.
- Les résultats 2026 de l'enquête PSF/JetBrains n'ont pas été trouvés ; les parts de marché datent de l'édition publiée en 2025.
- Aucune mesure indépendante de la qualité du code produit par des agents IA selon le framework.

## 2. Approche frontend pour une application « très UX »

### Takeaway
L'approche la mieux adaptée est **hybride** : pages rendues par le serveur (Django templates + htmx + un peu d'Alpine) pour tout ce qui est navigation, formulaires, partage et réglages, et un **îlot client** en JavaScript natif (composants web, éventuellement Lit) pour le visualiseur de cas, alimenté par la même API JSON que l'IA. Le prototype est déjà exactement cet îlot : du JavaScript sans dépendance qui construit le SVG et l'anime côté client ; il se réutilise presque tel quel, alors qu'une SPA React/Svelte imposerait de le réécrire et que les frameworks « tout Python » le rendraient inutilisable.

### Cited Findings

**htmx, Alpine, Datastar**
- htmx 4.0.0 est sorti le 28 août 2026 : passage de XMLHttpRequest à `fetch()`, *morphing* intégré au coeur, balise `<hx-partial>` pour mettre à jour plusieurs cibles, héritage d'attributs explicite (`:inherited`), SSE fourni par l'extension `hx-sse`, WebSocket par `hx-ws` — [htmx 4.0.0 is released](https://four.htmx.org/announcements/2026-08-28-htmx-4.0.0-is-released)
- Sur npm, `latest` reste 2.0.11 (22/09/2026) et la 4.0.2 (18/11/2026) est sous l'étiquette `next` jusqu'à « early 2027 » ; « htmx 2 will continue to be supported indefinitely » ; un vérificateur de migration existe (`npx htmx.org@4.0.0 upgrade-check`) ainsi que des fichiers de *skills* pour agents IA — [htmx 4.0.0 is released](https://four.htmx.org/announcements/2026-08-28-htmx-4.0.0-is-released), [npm htmx.org](https://www.npmjs.com/package/htmx.org)
- Alpine.js 3.17.5 (20/10/2026) — [npm alpinejs](https://www.npmjs.com/package/alpinejs)
- `django-htmx` 1.29.0 date du 5 août 2026, donc d'avant la sortie stable de htmx 4 — [PyPI django-htmx](https://pypi.org/project/django-htmx/)
- Datastar a publié sa 1.0 (v1.0.5 le 09/11/2026 sur GitHub) ; SDK Python `datastar-py` 1.0.3 (27/09/2026) ; les versions candidates avaient renommé les événements SSE et changé la syntaxe des attributs (RC.6, RC.9) — [Datastar releases](https://github.com/starfederation/datastar/releases), [PyPI datastar-py](https://pypi.org/project/datastar-py/)
- Chez les développeurs Django, htmx est passé de 5 % (2021) à 24 % (2025) et Alpine.js de 3 % à 14 % — [heise, State of Django 2025](https://heise.de/-10961541) ; React 29 %, Vue 18 %, jQuery 18 % — [Django Developers Survey, JetBrains](https://lp.jetbrains.com/django-developer-survey-2025/)

**Retours d'expérience htmx contre SPA**
- Portage React vers htmx chez Contexte (environ 2 mois) : code réduit de 67 % (21 500 à 7 200 lignes), Python +140 % (500 à 1 200 lignes), dépendances JS de 255 à 9, build de 40 s à 5 s, temps avant interactivité de 2-6 s à 1-2 s, mémoire de 75 à 45 Mo. Réserve explicite des auteurs : application orientée contenu, ils « would not expect every web application to see these sorts of numbers » — [A Real World React -> htmx Port](https://htmx.org/essays/a-real-world-react-to-htmx-port/)
- Talk Python n° 484 (passage de React à Django + htmx) : développement plus simple, mais risque de prolifération de templates partiels, à cadrer avec les *template partials* — [Talk Python #484](https://talkpython.fm/484) (extrait de recherche)

**SPA et adaptateurs**
- Svelte 5.59.1, SvelteKit 3.4.0, React 19.3.1, Vue 3.5.46, Vite 8.3.8, Lit 3.3.3 (toutes vérifiées le 21/11/2026) — [npm svelte](https://www.npmjs.com/package/svelte), [npm @sveltejs/kit](https://www.npmjs.com/package/@sveltejs/kit), [npm react](https://www.npmjs.com/package/react), [npm vue](https://www.npmjs.com/package/vue), [npm vite](https://www.npmjs.com/package/vite), [npm lit](https://www.npmjs.com/package/lit)
- Inertia : `@inertiajs/core` 3.11.0 côté client ; adaptateur `inertia-django` 2.0.0 (16/08/2026), une seule publication en 12 mois — [npm @inertiajs/core](https://www.npmjs.com/package/@inertiajs/core), [PyPI inertia-django](https://pypi.org/project/inertia-django/)
- Bibliothèques de mise en page de graphes utilisables dans un îlot : elkjs 0.12.1, @dagrejs/dagre 3.1.3, d3 7.9.2 — [npm elkjs](https://www.npmjs.com/package/elkjs), [npm @dagrejs/dagre](https://www.npmjs.com/package/@dagrejs/dagre), [npm d3](https://www.npmjs.com/package/d3)

**Frameworks UI « tout Python »**
- NiceGUI 4.0.0 (04/11/2026), Reflex 0.11.0 (12/11/2026, 84 versions en 12 mois, toujours 0.x), Streamlit 1.67.0 — [PyPI nicegui](https://pypi.org/project/nicegui/), [PyPI reflex](https://pypi.org/project/reflex/), [PyPI streamlit](https://pypi.org/project/streamlit/)

**Prototype existant (lecture locale)**
- `catalogue-runs.js` (531 lignes) est une seule fonction auto-exécutée, sans dépendance ni étape de build : fabriques `element()` / `svg()`, mise en page en couches (`graphLayout`, rang = plus long chemin depuis les parents, colonnes de 204 px, rangées de 150 px, disposition explicite exigée pour les cycles), tracé SVG avec flèches et courbes de Bézier (`buildGraph`), puis `renderFrame()` qui ne modifie que classes et textes des noeuds quand le curseur bouge — fichier local `sources/catalogue/catalogue-runs.js`
- Filtres, recherche (normalisation sans accents) et tri agissent côté client sur toutes les cartes déjà construites, en basculant l'attribut `hidden` ; raccourcis clavier `v` / `r` / `x` et flèches ; attributs ARIA (`aria-live`, `aria-valuetext`, `aria-keyshortcuts`) — fichier local `sources/catalogue/catalogue-runs.js`
- Les données sont un objet global `runCatalog` : `version`, `compatibleReviewVersions`, `retiredScenarioIds`, `scopes`, `sources`, `cases[]` ; chaque cas porte `nodes`, `edges`, `actions`, des `frames` dont les états complets sont dérivés de `steps` exprimés en deltas (`changes`) — fichier local `sources/catalogue/catalogue-runs-data.js`
- Les avis sont dans `localStorage` (clé versionnée), avec import/export JSON et contrôle de compatibilité de version — fichier local `sources/catalogue/catalogue-runs.js`
- Le métier est codé en dur : liste fermée de onze statuts, libellés (`always_run`, `ignore_on_error`, « Workflow », « TNR »), probabilités ; la CSS (127 lignes) n'a que trois variables globales (`--teal`, `--muted`, `--line`) plus une paire `--status-bg` / `--status-color` par classe de statut, le reste des couleurs étant en dur — fichiers locaux `catalogue-runs.js`, `catalogue-runs.css`

### Inferences
- **Réutilisation du prototype** : `graphLayout`, `buildGraph`, `renderFrame`, la logique de filtres et les raccourcis clavier se transposent directement dans un élément personnalisé (par exemple `<case-diagram>` et `<case-catalogue>`) qui reçoit ses données par `fetch()` au lieu d'un fichier global. À remplacer : `localStorage` par des appels API (avec mise à jour optimiste), l'objet `runCatalog` par des réponses JSON, et les éléments métier codés en dur par un schéma fourni par l'étude (liste de statuts, libellés, champs de noeud).
- **Thèmes** : la paire `--status-bg` / `--status-color` montre la voie. Un thème devient un document JSON de jetons (couleurs, typographie, formes de noeud, correspondance statut vers style, paramètres de mise en page) converti en propriétés CSS personnalisées posées sur le conteneur du visualiseur. L'IA modifie des jetons validés par schéma, jamais du CSS ou du JavaScript libre, ce qui évite l'injection et reste compatible avec une CSP stricte (nonces Django 6.1).
- **Échelle** : construire toutes les cartes d'un coup fonctionne pour une centaine de cas ; pour plusieurs centaines, garder le filtrage instantané côté client mais ne construire le SVG qu'à l'entrée dans la fenêtre (IntersectionObserver ou `content-visibility: auto`).
- **Pourquoi pas une SPA complète** : elle donne le meilleur plafond d'interactivité mais double la surface (routage, état, validation, build, tests) pour un développeur seul, alors que l'interactivité riche est concentrée dans un seul écran. Le choix hybride garde la possibilité d'introduire Svelte ou Lit dans l'îlot plus tard sans toucher au reste.
- **Pourquoi pas NiceGUI / Reflex / Streamlit** : l'état d'interface y vit côté serveur ou dans un runtime généré, ce qui rend l'intégration d'un rendu SVG sur mesure et de thèmes libres laborieuse, et empêche de reprendre le JavaScript existant ; Streamlit n'est pas conçu pour une application multi-utilisateur avec permissions par objet. Jugement fondé sur leur architecture connue, non revérifié dans leur documentation pendant cette collecte.
- **htmx 2 ou 4** : un projet neuf fin 2026 peut partir sur htmx 4 (morphing natif, `<hx-partial>`), mais 2.0.x reste l'étiquette `latest` et NetBox l'épingle encore ; la compatibilité de `django-htmx` 1.29 avec htmx 4 est à tester. Datastar est séduisant pour le temps réel (SSE natif) mais sa communauté est petite et son API a beaucoup bougé avant la 1.0.

### Gaps
- Pas de mesure publique comparant htmx et SPA sur une application à dominante visualisation interactive (les retours trouvés concernent des applications de contenu).
- Nombre exact de cas du prototype non compté ; comportement du prototype au-delà de quelques centaines de cartes non mesuré.
- Compatibilité `django-htmx` / htmx 4 et position de Datastar sur d'éventuelles fonctions payantes non vérifiées.
- Je n'ai pas lu `catalogue-runs.html` en détail (structure des filtres et de l'en-tête).

## 3. Base de données, modèle de données, ORM et migrations

### Takeaway
À cette échelle les deux moteurs tiennent la charge ; **PostgreSQL 18** est recommandé pour le déploiement d'équipe (écritures concurrentes de l'IA et des relecteurs, JSONB, `LISTEN/NOTIFY`, verrous de ligne), **SQLite en mode WAL** restant une variante légitime si l'on veut un seul conteneur. Le modèle gagnant est **hybride** : tables relationnelles pour tout ce qui porte identité, droits et avis ; document JSON pour le contenu d'un cas (noeuds, liens, étapes), avec l'ORM et les migrations de Django.

### Cited Findings
- PostgreSQL : 19.0 vient d'être listée comme version courante (date 19/11/2026) ; 18.7 et 17.12 datent du 12/11/2026 — [postgresql.org versions.json](https://www.postgresql.org/versions.json)
- SQLite 3.54.1 (16/10/2026) — [sqlite.org](https://sqlite.org/index.html)
- Django sur SQLite : « SQLite is meant to be a lightweight database, and thus can't support a high level of concurrency » ; option `transaction_mode` (`DEFERRED` par défaut, `IMMEDIATE` recommandé pour que les transactions attendent le `timeout` au lieu d'échouer) ; `init_command` pour poser des PRAGMA ; `ATOMIC_REQUESTS` déconseillé avec `IMMEDIATE` ; `select_for_update()` sans effet ; `JSONField` pris en charge via JSON1 (activé par défaut depuis SQLite 3.38) ; correspondances insensibles à la casse défaillantes hors ASCII — [Django databases, SQLite notes](https://docs.djangoproject.com/en/6.1/ref/databases/)
- Parts d'usage chez les développeurs Django (choix multiples) : PostgreSQL 76 %, SQLite 42 %, MySQL 27 % — [Django Developers Survey, JetBrains](https://lp.jetbrains.com/django-developer-survey-2025/)
- Litestream v0.5.18 (03/11/2026). La 0.5.0 (octobre 2025) a refondu le format (compaction propre, restauration à un instant donné) mais est sortie avec des bogues corrigés en 0.5.1-0.5.2 ; un utilisateur conseillait d'attendre avant la production — [Litestream releases](https://github.com/benbjohnson/litestream/releases), [Litestream v0.5.0 is Here](https://fly.io/blog/litestream-v050-is-here/), [Hold Off on Litestream 0.5.0](https://mtlynch.io/notes/hold-off-on-litestream-0.5.0/)
- Simon Willison rapporte utiliser Litestream en production « for a couple of years now without incident » (avant la 0.5) — [simonwillison.net](https://simonwillison.net/2025/Oct/3/litestream)
- ORM et migrations hors Django : SQLAlchemy 2.1.9 (16/11/2026), Alembic 1.20.1 (22/10/2026), SQLModel 0.0.50 (13/11/2026, toujours en 0.0.x) ; pilotes psycopg 3.3.9, asyncpg 0.32.0, aiosqlite 0.22.1 — [PyPI sqlalchemy](https://pypi.org/project/sqlalchemy/), [PyPI alembic](https://pypi.org/project/alembic/), [PyPI sqlmodel](https://pypi.org/project/sqlmodel/), [PyPI psycopg](https://pypi.org/project/psycopg/)
- Django 6.1 : `JSONNull`, `UUID7`, colonnes générées virtuelles sur PostgreSQL 18+ — [Django 6.1 release notes](https://docs.djangoproject.com/en/6.1/releases/6.1/)
- Applications auto-hébergées comparables : linkding choisit SQLite par défaut (`LD_DB_ENGINE` par défaut `sqlite`, PostgreSQL en option) ; Healthchecks démarre sur SQLite par défaut et prend en charge PostgreSQL/MySQL ; NetBox, authentik et Kiwi TCMS dépendent de psycopg (PostgreSQL) — [linkding](https://github.com/sissbruecker/linkding), [healthchecks](https://github.com/healthchecks/healthchecks), [NetBox](https://github.com/netbox-community/netbox), [authentik](https://github.com/goauthentik/authentik), [Kiwi TCMS](https://github.com/kiwitcms/Kiwi)

### Inferences
- **Modèle de données proposé** (clés UUID v7, tout rattaché à une étude) :
  - `User` (modèle utilisateur personnalisé dès le premier commit, identifiant = e-mail)
  - `Study` (propriétaire, titre, thème par défaut, compteur `revision`, archivage)
  - `Membership` (étude, utilisateur, rôle), `Invitation` (e-mail, rôle, jeton haché, expiration), `ShareLink` (jeton haché, rôle, expiration, révocation)
  - `Rule` (étude, clé stable, énoncé, références de source, retrait logique)
  - `Case` (étude, clé stable, famille, étiquettes, règles liées, `retired_at`, pointeur vers la révision courante)
  - `CaseRevision` (cas, numéro, `content` JSON avec noeuds / liens / étapes, empreinte du contenu, auteur humain ou jeton)
  - `CatalogueVersion` (étude, numéro, auteur, note, manifeste `{clé de cas: empreinte}`)
  - `Verdict` (cas, relecteur, décision, commentaire, révision de cas relue, compteur de version), `Comment` (fil par cas)
  - `Theme` (portée système / utilisateur / étude, `parent` pour les dérivations, jetons JSON, version de schéma)
  - `ApiToken` (utilisateur, nom, préfixe, empreinte, portées, étude éventuelle, expiration, dernière utilisation, révocation)
  - `AuditEvent` (horodatage, acteur humain ou jeton, étude, action, cible, différence JSON)
- **JSON ou tables** : les étapes (*frames*) ne sont jamais interrogées isolément et arrivent en bloc depuis l'IA, donc un document JSON validé à l'entrée (schémas Pydantic de Django Ninja) est plus simple et versionnable. Stocker les deltas (`steps` / `changes`, comme dans le prototype) plutôt que les états développés, et développer côté client. À l'inverse, avis, appartenance et identité des cas doivent rester relationnels (contraintes d'unicité, jointures, filtres, droits).
- **SQLite ou PostgreSQL, critères de bascule** : SQLite suffit si un seul processus applicatif, des transactions courtes et pas de besoin de notification inter-processus ; PostgreSQL s'impose si plusieurs workers, imports volumineux pendant que d'autres relisent, recherche plein texte en français, ou historique par déclencheurs. Ne tester et ne prendre en charge qu'un seul moteur en production : les écarts de comportement (verrous, casse, JSON) doublent sinon la matrice de tests. PostgreSQL 19.0 n'ayant que quelques jours, partir sur la 18.
- Le mode WAL s'active par `PRAGMA journal_mode=WAL` (via `init_command`) ; la doc Django ne le mentionne pas, c'est une pratique SQLite courante à valider par un test de charge simple.
- SQLModel reste en 0.0.x après plusieurs années : à éviter comme fondation ; si l'on choisit FastAPI, utiliser SQLAlchemy 2.1 directement.

### Gaps
- Aucun banc d'essai trouvé pour ce profil précis (imports JSON de quelques centaines de cas + relecture concurrente) sur SQLite contre PostgreSQL.
- Le moteur par défaut de Paperless-ngx, Mealie et Open WebUI n'a pas été vérifié dans leurs sources (seule la présence de psycopg l'a été).
- Stabilité réelle de PostgreSQL 19.0 inconnue (trop récente).

## 4. Authentification pour une petite équipe auto-hébergée

### Takeaway
**django-allauth** couvre à lui seul tout le périmètre demandé (mot de passe, code de connexion par e-mail, passkeys/WebAuthn, TOTP, connexion OIDC, et même fournisseur OAuth/OIDC pour les connecteurs MCP) et il est très activement maintenu ; côté FastAPI, **fastapi-users est en mode maintenance** et il faudrait assembler pwdlib, Authlib et py_webauthn soi-même. Pour le navigateur : cookie de session ; pour l'API : jeton personnel haché en base, à portées limitées.

### Cited Findings
- django-allauth 65.22.1 (13/11/2026), 24 versions en 12 mois, Python >= 3.11 ; Django 6.1 officiellement pris en charge depuis 65.19.0, Python 3.15 depuis 65.22.1 — [PyPI django-allauth](https://pypi.org/project/django-allauth/), [allauth release notes](https://docs.allauth.org/en/latest/release-notes/recent.html)
- Fonctions présentes dans les notes 2026 : connexion par code (formats à tirets, renvoi optionnel), réauthentification par code (65.22.0), passkeys avec vérification utilisateur toujours exigée (65.21.1, `MFA_WEBAUTHN_USER_VERIFICATION`), TOTP et codes de secours, mode *headless* avec intégration DRF/Ninja et description OpenAPI, suivi des sessions utilisateur, réglage `ACCOUNT_SIGNUP_ENABLED` pour fermer l'inscription — [allauth release notes](https://docs.allauth.org/en/latest/release-notes/recent.html)
- `allauth.idp` (fournisseur OIDC intégré) : enregistrement dynamique de clients et indicateurs de ressource RFC 8707 (65.18.0), *Client ID Metadata Documents*, introspection RFC 7662, rotation de clés (65.19.0), PKCE limité à `S256` (65.22.0) — [allauth release notes](https://docs.allauth.org/en/latest/release-notes/recent.html)
- Flux soutenu de correctifs de sécurité en 2026 (limitation de débit, contournement de la vérification utilisateur WebAuthn sans mot de passe, réutilisation de TOTP, redirection ouverte, analyse stricte des *claims* de vérification d'e-mail en 65.22.1) ; `X-Forwarded-For` n'est plus approuvé par défaut depuis 65.14.2 (`ALLAUTH_TRUSTED_PROXY_COUNT` à régler derrière un proxy) — [allauth release notes](https://docs.allauth.org/en/latest/release-notes/recent.html)
- fastapi-users : « This project is now in maintenance mode » ; correctifs de sécurité et dépendances seulement, aucune nouvelle fonction, un successeur est en préparation ; dernière version 15.0.5 (27/03/2026) — [fastapi-users GitHub](https://github.com/fastapi-users/fastapi-users), [PyPI fastapi-users](https://pypi.org/project/fastapi-users/)
- Briques pour un assemblage manuel : pwdlib 0.4.2 (15/11/2026), Authlib 1.9.10 (20/11/2026, 23 versions en 12 mois), `webauthn` (py_webauthn) 3.0.1 (25/09/2026), argon2-cffi 25.1.0 (juin 2025, aucune publication depuis), PyJWT 2.15.1 — [PyPI pwdlib](https://pypi.org/project/pwdlib/), [PyPI authlib](https://pypi.org/project/authlib/), [PyPI webauthn](https://pypi.org/project/webauthn/), [PyPI argon2-cffi](https://pypi.org/project/argon2-cffi/)
- Django 6.1 porte PBKDF2 à 1 500 000 itérations par défaut — [Django 6.1 release notes](https://docs.djangoproject.com/en/6.1/releases/6.1/)
- Autres options Django : django-oauth-toolkit 3.4.1 (serveur OAuth2), django-otp 1.7.5, django-rest-knox 6.0.0 (jetons hachés pour DRF) — [PyPI django-oauth-toolkit](https://pypi.org/project/django-oauth-toolkit/), [PyPI django-otp](https://pypi.org/project/django-otp/), [PyPI django-rest-knox](https://pypi.org/project/django-rest-knox/)
- Pratiques observées : Paperless-ngx et Tandoor utilisent django-allauth ; linkding utilise mozilla-django-oidc ; authentik et Weblate utilisent `webauthn` 3.0.1 ; Mealie et Open WebUI (FastAPI) utilisent Authlib — [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx), [Tandoor](https://github.com/TandoorRecipes/recipes), [linkding](https://github.com/sissbruecker/linkding), [Weblate](https://github.com/WeblateOrg/weblate), [Mealie](https://github.com/mealie-recipes/mealie), [Open WebUI](https://github.com/open-webui/open-webui)
- Fournisseur d'identité auto-hébergeable si l'équipe veut un SSO central : authentik 2026.8.6 (20/11/2026) — [authentik releases](https://github.com/goauthentik/authentik/releases)

### Inferences
- **Parcours recommandé** : comptes locaux e-mail + mot de passe (Argon2 ou PBKDF2 par défaut), passkeys proposés en complément, connexion par code e-mail comme secours, OIDC générique optionnel (Google, Microsoft, authentik, Keycloak) activé par configuration, inscription fermée par défaut avec invitation.
- **Deux mécanismes étanches** : navigateur = cookie de session `HttpOnly`, `Secure`, `SameSite=Lax` + jeton CSRF ; API et MCP = `Authorization: Bearer`, sans cookie, exempt de CSRF. Les routes de l'îlot client appellent l'API avec la session ; les agents avec leur jeton.
- **Jetons personnels** : 32 octets aléatoires, préfixe lisible pour l'identification et la détection de fuite, seule l'empreinte SHA-256 est stockée, affichage unique à la création, portées (lecture / écriture, étude précise), expiration, date de dernière utilisation, révocation. Chaque jeton est un acteur distinct dans le journal d'audit, ce qui répond à « qui, humain ou IA, a changé quoi ».
- **OAuth pour MCP** : si l'on veut que des connecteurs distants (Claude Desktop/web, ChatGPT) s'authentifient par OAuth plutôt que par en-tête statique, `allauth.idp` fournit les briques attendues (enregistrement dynamique, métadonnées de client, RFC 8707, PKCE) sans service supplémentaire. C'est un avantage concret de la voie Django.
- La fréquence des correctifs de sécurité d'allauth est un signe de réactivité, mais impose de suivre les mises à jour (Dependabot ou Renovate) et de régler correctement la confiance envers le proxy.

### Gaps
- Je n'ai pas vérifié dans la doc d'allauth la configuration exacte d'un fournisseur OIDC générique ni l'interopérabilité réelle d'`allauth.idp` avec les clients MCP.
- La prise en charge d'un jeton en en-tête par Claude Code, Claude Desktop et ChatGPT n'a été vue qu'à travers un extrait de recherche ; des tickets d'utilisateurs signalent des échecs OAuth côté connecteurs web/Desktop (non confirmés officiellement). À traiter par le chercheur chargé de l'API agent.
- Le « successeur » annoncé de fastapi-users n'a pas été identifié ni évalué.

## 5. Partage et permissions par étude

### Takeaway
Quatre rôles sur un seul type d'objet se modélisent par une simple table `Membership(étude, utilisateur, rôle)` et un point de passage unique qui filtre toutes les requêtes ; django-guardian ou `rules` sont possibles mais pas nécessaires, et Oso (déprécié), OpenFGA ou Cerbos sont disproportionnés.

### Cited Findings
- Django n'implémente pas les permissions par objet : « Django's permission framework has a foundation for object permissions, though there is no implementation for it in the core. That means that checking for object permissions will always return False or an empty list » — [Django, customizing authentication](https://docs.djangoproject.com/en/6.1/topics/auth/customizing/)
- django-guardian 3.5.2 (20/10/2026), 10 versions en 12 mois : permissions par objet stockées en base — [PyPI django-guardian](https://pypi.org/project/django-guardian/)
- `rules` 3.5 (02/09/2024) : aucune publication depuis plus de deux ans ; à ne pas confondre avec le paquet PyPI `django-rules` 0.2, abandonné depuis 2011 — [PyPI rules](https://pypi.org/project/rules/), [PyPI django-rules](https://pypi.org/project/django-rules/)
- La bibliothèque open source Oso est dépréciée depuis le 18/12/2023 ; dernière version 0.27.3 (janvier 2024) ; l'éditeur pousse son offre hébergée Oso Cloud — [Oso GitHub](https://github.com/osohq/oso), [PyPI oso](https://pypi.org/project/oso/)
- Usages observés : Paperless-ngx et Kiwi TCMS dépendent de django-guardian 3.5.2 ; Label Studio dépend de `rules` — [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx), [Kiwi TCMS](https://github.com/kiwitcms/Kiwi), [Label Studio](https://github.com/HumanSignal/label-studio)

### Inferences
- Avec FastAPI, il n'existe pas d'équivalent intégré : le contrôle d'accès par objet s'écrit dans une dépendance (`Depends`) qui charge l'étude et vérifie le rôle, ce qui revient au même modèle `Membership` mais sans le socle utilisateurs/groupes de Django.
- **Modèle** : rôles ordonnés `viewer < commenter < editor < owner`. Le lecteur voit ; le commentateur donne avis et commentaires ; l'éditeur modifie règles, cas et thème de l'étude ; le propriétaire gère membres, liens et suppression. Un jeton d'API hérite au plus du rôle de son utilisateur, restreint par ses portées.
- **Application** : une seule fonction d'accès (par exemple `Study.objects.for_user(user, min_role)`) utilisée par les vues HTML, les routes Ninja et les outils MCP ; aucune requête sur `Case`, `Verdict` ou `Theme` qui ne parte de cette étude filtrée. Répondre 404 plutôt que 403 pour ne pas révéler l'existence d'une étude. Tests paramétrés rôle x action pour chaque route.
- **Invitations et liens** : invitation par e-mail avec jeton haché et expiration, transformée en `Membership` à l'acceptation ; lien de partage optionnel en lecture seule, jeton haché, révocable, à expiration.
- django-guardian devient utile si des droits fins apparaissent sur plusieurs types d'objets ; ici il ajouterait des tables génériques sans bénéfice. OpenFGA et Cerbos sont des services à part entière à déployer et opérer : hors de proportion pour quelques dizaines d'utilisateurs.

### Gaps
- OpenFGA et Cerbos n'ont pas été recherchés en détail (versions, coût d'exploitation) : le jugement « disproportionné » repose sur leur nature de service séparé.
- Le statut de maintenance réel de `rules` (stable ou délaissé) n'est pas établi au-delà de l'absence de publication.

## 6. Mise à jour en direct et relecture concurrente

### Takeaway
Les **Server-Sent Events** suffisent : le serveur signale « l'étude X est passée à la révision N » et le navigateur recharge ce qui a changé ; pas besoin de WebSocket ni de collaboration temps réel type CRDT. La relecture à plusieurs se règle en donnant à chaque relecteur son propre avis et en protégeant les champs partagés par un numéro de version.

### Cited Findings
- Django sous ASGI permet les flux longs (interrogation longue, SSE) via `StreamingHttpResponse` avec itérateur asynchrone ; à la déconnexion du client, Django annule la coroutine (`asyncio.CancelledError` à intercepter pour libérer les ressources) ; les middlewares qui lisent le contenu (ETag, Content-Length) ne s'appliquent pas à un flux — [Django request/response](https://docs.djangoproject.com/en/6.1/ref/request-response/)
- FastAPI fournit un module `fastapi.sse` (référence d'API ajoutée en 0.140.13) et des flux JSON Lines — [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/)
- htmx 4 : SSE par l'extension `hx-sse` (flux `text/event-stream`), WebSocket par `hx-ws` ; pour htmx 2, extension `htmx-ext-sse` 2.2.4 (18/10/2025) — [htmx 4.0.0 is released](https://four.htmx.org/announcements/2026-08-28-htmx-4.0.0-is-released), [npm htmx-ext-sse](https://www.npmjs.com/package/htmx-ext-sse)
- Paquets temps réel Django : `channels` 4.3.2 (20/11/2025, aucune publication dans les 12 derniers mois), `django-eventstream` 5.3.4 (une publication en 12 mois), `sse-starlette` 3.7.0 côté Starlette/FastAPI — [PyPI channels](https://pypi.org/project/channels/), [PyPI django-eventstream](https://pypi.org/project/django-eventstream/), [PyPI sse-starlette](https://pypi.org/project/sse-starlette/)
- Pratiques observées : authentik utilise `channels` avec une couche `django-channels-postgres` (pas de Redis) ; Paperless-ngx utilise `channels` + Redis + Celery — [authentik](https://github.com/goauthentik/authentik), [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx)
- Sur SQLite, `select_for_update()` est sans effet : le verrouillage pessimiste de ligne n'existe que sur PostgreSQL — [Django databases, SQLite notes](https://docs.djangoproject.com/en/6.1/ref/databases/)

### Inferences
- **Mécanisme proposé** : chaque écriture (API, MCP ou interface) incrémente `Study.revision` et ajoute un `AuditEvent`. Une route SSE par étude émet des événements minimalistes (`cases_changed`, `theme_changed`, `verdict_changed` avec identifiants et révision). L'îlot client écoute avec `EventSource` (reconnexion automatique, `Last-Event-ID`) puis redemande les éléments concernés. Solution de repli : interrogation périodique de `GET /studies/{id}/changes?since=N`.
- **Diffusion** : avec un seul processus ASGI, une file `asyncio` en mémoire suffit ; avec plusieurs workers, utiliser `LISTEN/NOTIFY` de PostgreSQL (psycopg 3 asynchrone) ou, plus simple, une boucle qui relit le compteur de révision toutes les une à deux secondes. Redis et Channels sont inutiles ici.
- **Expérience** : ne jamais remplacer l'écran sous les yeux du relecteur. Afficher un bandeau « 12 cas ajoutés, 3 modifiés par [jeton X] » avec un bouton d'actualisation, et marquer les cartes modifiées ; appliquer en direct uniquement les changements sans risque (compteurs, avis des autres).
- **Concurrence** : un avis par couple (cas, relecteur) supprime presque tous les conflits et garde la trace de qui a validé quoi ; un statut consolidé peut être dérivé. Pour les champs partagés (titre d'un cas, thème), verrouillage optimiste : numéro de version envoyé avec la modification, réponse 409 en cas d'écart, l'interface propose de recharger. Les commentaires sont en ajout seul. La question n'est donc un souci que si l'on impose un avis unique par cas.
- Si une IA modifie un cas déjà relu, l'avis reste attaché à l'ancienne révision et est signalé « à revoir, contenu modifié » plutôt qu'effacé.

### Gaps
- Aucun retour d'expérience chiffré trouvé sur SSE avec Django ASGI en production à petite échelle (nombre de connexions tenues par worker, comportement derrière Caddy).
- La prise en charge du streaming par Django Ninja 1.8 n'a pas été vérifiée ; une vue Django asynchrone simple suffit de toute façon.
- La décision produit « un avis par relecteur » ou « un avis unique par cas » n'est pas tranchée dans le cadrage.

## 7. Historique, versions, audit, import/export

### Takeaway
Le prototype contient déjà les bons concepts (version de catalogue, versions d'avis compatibles, identifiants de scénarios retirés) ; il faut les porter côté serveur avec des **révisions de cas immuables**, des **versions de catalogue** sous forme de manifeste d'empreintes, et un **journal d'audit en ajout seul** dont l'acteur est soit un humain, soit un jeton d'IA.

### Cited Findings
- Le prototype expose `version: "2026-11-19.1"`, une liste `compatibleReviewVersions` de onze versions antérieures et `retiredScenarioIds` (quatre identifiants) ; `validateReviews` accepte les avis portant sur des scénarios retirés et refuse une version incompatible — fichiers locaux `sources/catalogue/catalogue-runs-data.js`, `sources/catalogue/catalogue-runs.js`
- L'export JSON du prototype contient `version`, `exportedAt` et un avis par scénario ; l'import fusionne après confirmation — fichier local `sources/catalogue/catalogue-runs.js`
- Bibliothèques d'historique Django : django-simple-history 3.13.0 (22/07/2026), django-reversion 6.5.2 (12/11/2026), django-pghistory 3.9.2 (17/02/2026, déclencheurs PostgreSQL) — [PyPI django-simple-history](https://pypi.org/project/django-simple-history/), [PyPI django-reversion](https://pypi.org/project/django-reversion/), [PyPI django-pghistory](https://pypi.org/project/django-pghistory/)
- Kiwi TCMS (gestion de cas de test, domaine le plus proche) dépend de django-simple-history 3.13.0 et de django-guardian — [Kiwi TCMS](https://github.com/kiwitcms/Kiwi)
- allauth émet des signaux d'audit (codes rejetés, échecs MFA) depuis 65.16.0, exploitables dans le même journal — [allauth release notes](https://docs.allauth.org/en/latest/release-notes/recent.html)

### Inferences
- **Identité stable** : chaque cas a une clé stable dans l'étude (comme `base-chaine` dans le prototype). L'IA pousse un cas par sa clé ; si l'empreinte du contenu change, une nouvelle `CaseRevision` est créée, sinon rien (idempotence des appels répétés).
- **Version de catalogue** : instantané nommé = manifeste `{clé: empreinte}` + auteur + note. Comparer deux versions revient à comparer deux manifestes (ajoutés, retirés, modifiés), puis à afficher la différence JSON des cas modifiés. Aucun outil de diff générique n'est nécessaire.
- **Retrait logique** : `retired_at` au lieu d'une suppression ; les avis et commentaires restent consultables et exportables, le cas sort des compteurs. Restauration possible.
- **Avis et révisions** : l'avis mémorise la révision relue ; un filtre « validé sur une version antérieure » devient possible, ce qui remplace proprement la liste `compatibleReviewVersions` maintenue à la main.
- **Audit** : une table d'événements explicite (`acteur_utilisateur`, `acteur_jeton`, action, cible, différence) est préférable à django-simple-history seul, dont le champ d'auteur vise un utilisateur humain ; les deux peuvent coexister (historique automatique des modèles + événements métier lisibles).
- **Import/export** : format JSON versionné (`schema_version`) couvrant étude, règles, cas, thème et avis, validé par les mêmes schémas que l'API ; garder la compatibilité de lecture avec l'export d'avis du prototype pour migrer les relectures existantes.

### Gaps
- Aucune source externe ne décrit ce modèle précis ; il s'agit d'une conception déduite du prototype et des pratiques courantes.
- Les bibliothèques de diff JSON (jsonpatch, DeepDiff) n'ont pas été vérifiées (versions, maintenance).
- Politique de rétention de l'historique et du journal d'audit non définie.

## 8. Déploiement, exploitation et outillage

### Takeaway
Un `docker compose` à trois services (Caddy pour le HTTPS automatique, l'application Django servie en ASGI, PostgreSQL) plus une sauvegarde planifiée couvre le besoin ; la variante SQLite tient en un conteneur applicatif avec Litestream. L'outillage 2026 est stabilisé autour de uv, ruff, pytest et Playwright.

### Cited Findings
- Caddy v2.11.9 (05/11/2026) ; Traefik v3.7.19 (13/11/2026) — [Caddy releases](https://github.com/caddyserver/caddy/releases), [Traefik releases](https://github.com/traefik/traefik/releases)
- Serveurs d'application : uvicorn 0.54.0 (25/09/2026), granian 2.8.9 (20/11/2026), gunicorn 27.0.1 (12/11/2026), daphne 4.2.3 (21/07/2026) ; hypercorn 0.18.0 sans publication depuis novembre 2025 — [PyPI uvicorn](https://pypi.org/project/uvicorn/), [PyPI granian](https://pypi.org/project/granian/), [PyPI gunicorn](https://pypi.org/project/gunicorn/), [PyPI hypercorn](https://pypi.org/project/hypercorn/)
- Adoption observée : Paperless-ngx et Weblate ont granian en dépendance ; NetBox, authentik et Tandoor gunicorn ; Mealie et Open WebUI uvicorn — [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx), [Weblate](https://github.com/WeblateOrg/weblate), [NetBox](https://github.com/netbox-community/netbox), [Mealie](https://github.com/mealie-recipes/mealie)
- Outillage : uv 0.13.9 (17/11/2026, 101 versions en 12 mois), ruff 0.17.6 (19/11/2026), pytest 9.2.0 (27/10/2026), pytest-django 4.14.0, Playwright Python 1.65.2 (14/11/2026), pytest-playwright 0.10.0 ; le vérificateur de types `ty` d'Astral est encore en 0.0.107 — [PyPI uv](https://pypi.org/project/uv/), [PyPI ruff](https://pypi.org/project/ruff/), [PyPI pytest](https://pypi.org/project/pytest/), [PyPI pytest-django](https://pypi.org/project/pytest-django/), [PyPI playwright](https://pypi.org/project/playwright/), [PyPI ty](https://pypi.org/project/ty/)
- Fichiers statiques : whitenoise 6.12.0 ; intégration Vite optionnelle : django-vite 3.2.0 — [PyPI whitenoise](https://pypi.org/project/whitenoise/), [PyPI django-vite](https://pypi.org/project/django-vite/)
- Sauvegarde SQLite : Litestream v0.5.18 (03/11/2026), binaire sans CGO depuis la 0.5 — [Litestream releases](https://github.com/benbjohnson/litestream/releases), [Litestream v0.5.0 is Here](https://fly.io/blog/litestream-v050-is-here/)
- Derrière un proxy, allauth ne fait plus confiance à `X-Forwarded-For` par défaut (réglage explicite requis) et le transport MCP exige une liste d'hôtes autorisés, sous peine de réponses 421 — [allauth release notes](https://docs.allauth.org/en/latest/release-notes/recent.html), [MCP Python SDK, Add to an existing app](https://py.sdk.modelcontextprotocol.io/run/asgi/)
- Tâches de fond : Django 6.0 intègre le framework de tâches mais sans worker ; les deux backends fournis sont destinés au développement et aux tests — [Django 6.0 release notes](https://docs.djangoproject.com/en/6.0/releases/6.0/)
- FastAPI 0.164-0.165 ajoute des limites configurables de taille de corps et de formulaire, utiles si l'on retient FastAPI pour recevoir de gros imports — [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/)

### Inferences
- **Composition type** : `caddy` (TLS automatique, compression, désactivation du tampon sur la route SSE), `app` (image construite avec `uv sync --frozen`, exécution non-root, `migrate` + `collectstatic` au démarrage, un à deux workers ASGI), `db` (PostgreSQL 18, volume nommé), plus une tâche planifiée `pg_dump` vers un stockage externe. Variante mono-conteneur : SQLite WAL sur volume + Litestream vers un stockage S3 compatible.
- **Configuration** : variables d'environnement (clé secrète, URL de base, hôtes autorisés, SMTP, OIDC optionnel), un fichier `.env.example`, une route de santé, journaux structurés sur la sortie standard.
- **Mises à jour** : images étiquetées par version, migrations Django rejouables au démarrage, sauvegarde automatique avant migration, notes de version ; tester la restauration, pas seulement la sauvegarde.
- **Tests** : pytest + pytest-django pour le modèle, les permissions (matrice rôle x action) et l'API ; tests de contrat sur le schéma OpenAPI et sur les outils MCP ; quelques parcours Playwright sur l'îlot (curseur, raccourcis clavier, avis, réception d'un événement SSE). Les fonctions pures du visualiseur (`graphLayout`) se testent sans navigateur.
- **Sans chaîne de build au départ** : modules ES natifs servis par whitenoise ; n'introduire Vite que si TypeScript ou une bibliothèque de composants devient nécessaire.
- Aucune tâche de fond n'est indispensable au lancement (pas de LLM embarqué) ; l'envoi d'e-mails d'invitation peut rester synchrone, ce qui évite Celery et Redis.

### Gaps
- Réglages précis de Caddy pour SSE et pour le transport MCP en streaming non vérifiés dans sa documentation.
- Pas de comparaison chiffrée granian / uvicorn pour Django ASGI à cette échelle.
- Stratégie de montée de version majeure de PostgreSQL en auto-hébergement non documentée ici.

## 9. Choix des applications open source auto-hébergées comparables

### Takeaway
Deux familles coexistent : **Django rendu serveur + JavaScript léger** (NetBox avec htmx, linkding avec Turbo et Lit, Healthchecks, Kiwi TCMS, Weblate) et **API Python + SPA** (Paperless-ngx/Angular, Tandoor/Vue, Label Studio/React, Mealie/Nuxt, Open WebUI/SvelteKit). Les projets à faible part de JavaScript (linkding, Healthchecks, NetBox à 96 % Python) sont tous dans la première famille ; les projets FastAPI sont tous couplés à une SPA et assemblent eux-mêmes auth et migrations.

### Cited Findings
Relevé des manifestes de dépendances au 21/11/2026 :

| Application | Backend | Frontend | Base | Notes |
|---|---|---|---|---|
| [NetBox](https://github.com/netbox-community/netbox) (21,9 k étoiles) | Django 6.1.3, DRF, django-htmx 1.29, GraphQL | htmx 2.0.11, Bootstrap, 409 templates HTML, 96 % Python | PostgreSQL + Redis | gunicorn |
| [linkding](https://github.com/sissbruecker/linkding) (11,4 k) | Django >= 6.0.7, DRF | Turbo 8 + Lit 3, 83 % Python | SQLite par défaut, PostgreSQL en option | OIDC via mozilla-django-oidc |
| [Healthchecks](https://github.com/healthchecks/healthchecks) | Django 6.1.3, pydantic, fido2 | aucun `package.json` | SQLite par défaut, PostgreSQL/MySQL | WebAuthn via fido2 |
| [Kiwi TCMS](https://github.com/kiwitcms/Kiwi) | Django 6.1.3, guardian, simple-history | pages serveur + webpack | PostgreSQL | gestion de cas de test |
| [Weblate](https://github.com/WeblateOrg/weblate) | Django 6.0.10, DRF, Celery, django-otp, webauthn | pages serveur + Bootstrap | PostgreSQL + Redis | granian |
| [authentik](https://github.com/goauthentik/authentik) | Django 5.2.19, DRF, channels (couche PostgreSQL) | Lit 3 + PatternFly | PostgreSQL | webauthn 3.0.1 |
| [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) (48,4 k) | Django 5.2, DRF, channels, Celery, allauth, guardian | Angular 22 (28 % TypeScript) | psycopg présent | granian |
| [Tandoor](https://github.com/TandoorRecipes/recipes) | Django 5.2.18, DRF, allauth | Vue 3 + Vite | Redis présent | gunicorn |
| [Label Studio](https://github.com/HumanSignal/label-studio) (28,7 k) | Django, DRF, `rules` | React 18 (64 % TS/JS) | psycopg présent | outil d'annotation avec relecture |
| [Mealie](https://github.com/mealie-recipes/mealie) (14,0 k) | FastAPI 0.163.1, SQLAlchemy 2.1.8, Alembic, Authlib | Nuxt 4 / Vue 3 | psycopg présent | uvicorn |
| [Open WebUI](https://github.com/open-webui/open-webui) (159 k) | FastAPI 0.136.3, SQLAlchemy 2.0.50, Alembic, Authlib | SvelteKit 2 / Svelte 5 | psycopg, Redis présents | uvicorn |
| [Datasette](https://github.com/simonw/datasette) | ASGI maison, Jinja2, uvicorn | aucun framework | SQLite | architecture à plugins |

- Mealie épingle FastAPI 0.163.1 et Open WebUI 0.136.3 : les deux fixent une version exacte, Open WebUI ayant près de trente versions mineures de retard — [Mealie](https://github.com/mealie-recipes/mealie), [Open WebUI](https://github.com/open-webui/open-webui)
- Retour de Contexte : équipe redevenue entièrement « full-stack » après le passage à htmx, sans perte d'expérience utilisateur selon eux — [A Real World React -> htmx Port](https://htmx.org/essays/a-real-world-react-to-htmx-port/)

### Inferences
- linkding est le modèle le plus proche de l'architecture recommandée : Django rendu serveur, navigation accélérée, composants web Lit pour les parties interactives, SQLite par défaut, petite équipe de maintenance (taille exacte non vérifiée). NetBox montre que htmx tient sur une très grande application Django.
- Label Studio et Kiwi TCMS sont les plus proches par le métier (cas à relire, statuts, commentaires) : tous deux sur Django, avec permissions par objet par bibliothèque et, pour Kiwi, historique par django-simple-history.
- L'épinglage strict de FastAPI par Mealie et Open WebUI corrobore le coût de suivi de ses versions : un projet FastAPI doit prévoir du temps de mise à niveau régulier.
- Aucune de ces applications n'utilise un framework d'interface « tout Python » ; aucune n'embarque de serveur MCP dans les manifestes relevés, ce point reste à défricher soi-même.
- Plusieurs applications Django matures restent sur la 5.2 (authentik, Paperless-ngx, Tandoor) : signe qu'une LTS est souvent préférée en auto-hébergement ; les projets plus légers (NetBox, Healthchecks, Kiwi) suivent la 6.1.

### Gaps
- Je n'ai pas trouvé de billet d'architecture de NetBox ou de linkding expliquant leurs choix ; les « leçons » ci-dessus sont déduites des dépendances, pas de leurs déclarations.
- Plane (Django + React) n'a pu être relevé que partiellement (chemins de fichiers non trouvés, quota d'API GitHub atteint).
- Les moteurs de base par défaut de Paperless-ngx, Tandoor, Mealie, Label Studio et Open WebUI ne sont pas confirmés.
- Aucun exemple trouvé d'application auto-hébergée combinant visualisations SVG animées et relecture collaborative, qui servirait de référence directe.
