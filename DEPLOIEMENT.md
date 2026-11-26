# Déploiement de Demetra

Image Docker construite depuis ce dépôt. Elle n'écrit que dans `/data` et se place derrière un reverse proxy
HTTPS (Caddy). Le dossier `deploiement/` fournit un modèle sans secret : `docker-compose.yml`, `Caddyfile` et
`preparer.sh`. Ce dernier écrit sur le serveur la clé secrète et les réglages, qui ne sont jamais versionnés.

## Installer sur un nouveau serveur

Mode opératoire pour une personne ou une IA qui dispose d'un shell sur le serveur. Chaque étape se termine par
une vérification ; ne passez à la suivante que si elle est conforme. Aucune étape n'affiche la clé secrète ni
un mot de passe : ne les affichez pas non plus (pas de `cat demetra.env`, pas de `env`).

Prérequis : un serveur Linux 64 bits (Debian 12+ ou Ubuntu 22.04+ ; 1 CPU et 1 Go de mémoire suffisent), un nom
DNS qui pointe déjà sur lui, les ports 80 et 443 ouverts depuis Internet, un accès root ou sudo.

1. **Docker et le module compose.** Sur Debian ou Ubuntu :

   ```bash
   sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
   ```

   Si `docker-compose-v2` n'existe pas dans la distribution, suivez l'installation officielle (dépôt
   `download.docker.com`). Vérification : `docker compose version` affiche une version 2.

2. **Le code.** Le dépôt est privé : il faut un accès en lecture, soit une clé de déploiement GitHub ajoutée au
   dépôt, soit une archive fournie par le porteur du projet (`git archive --format=tar.gz -o demetra.tar.gz
   main`). Ne demandez pas de jeton GitHub dans une conversation.

   ```bash
   sudo git clone git@github.com:Scendari/demetra.git /opt/demetra   # ou : décompresser l'archive dans /opt/demetra
   cd /opt/demetra/deploiement
   ```

   Vérification : `ls` montre `docker-compose.yml`, `Caddyfile` et `preparer.sh`.

3. **Réglages et dossiers.** Remplacez le domaine :

   ```bash
   sudo sh preparer.sh demetra.exemple.fr
   ```

   Vérification : `.env` et `demetra.env` existent, ce dernier en `-rw-------` ; `data/` et `backup/` appartiennent
   à l'UID 1000 (`ls -la`). `grep -c DEMETRA_SECRET_KEY demetra.env` répond 1, sans afficher la clé.

4. **Construire et démarrer.**

   ```bash
   sudo docker compose up -d --build
   ```

   La construction prend quelques minutes. Vérification : `sudo docker compose ps` montre `demetra` en
   `healthy` (jusqu'à une minute) et `caddy` en `running`. En cas d'échec : `sudo docker compose logs demetra`.

5. **Compte d'administration.** Choisissez un identifiant et une adresse ; le mot de passe est généré, rangé
   dans un fichier en 0600 hors du dépôt et jamais affiché. Transmettez-le à la personne par le canal convenu
   avec elle (elle peut aussi lire elle-même le fichier).

   ```bash
   sudo sh -c 'umask 077; tr -dc A-Za-z0-9 < /dev/urandom | head -c 24 > /root/demetra-admin.txt'
   sudo sh -c 'cd /opt/demetra/deploiement && DJANGO_SUPERUSER_PASSWORD="$(cat /root/demetra-admin.txt)" \
     docker compose exec -T -e DJANGO_SUPERUSER_PASSWORD -e DJANGO_SUPERUSER_USERNAME=admin \
     -e DJANGO_SUPERUSER_EMAIL=admin@exemple.fr demetra python manage.py createsuperuser --noinput'
   ```

   Vérification : la commande répond `Superuser created successfully.`

6. **Recette.** Depuis le serveur :

   ```bash
   curl -s https://demetra.exemple.fr/sante/                       # ok
   curl -s -o /dev/null -w '%{http_code}\n' https://demetra.exemple.fr/llms.txt   # 200
   curl -s -o /dev/null -w '%{http_code}\n' http://demetra.exemple.fr/            # 308 (vers https)
   ```

   Puis le tableau de la section « Recette » plus bas. La personne se connecte à `/admin/` avec le compte de
   l'étape 5, y crée les comptes et, si elle le souhaite, écrit le message de l'organisation (voir plus bas).

7. **Facultatif.** Études de démonstration (`seed_demo`, voir « Première mise en route ») ; sauvegarde
   quotidienne par cron (voir « Sauvegarde ») ; e-mails, SSO ou LDAP : ajouter les variables dans
   `demetra.env`, puis `sudo docker compose up -d`.

Mettre à jour : `cd /opt/demetra && sudo git pull && cd deploiement && sudo docker compose up -d --build`. Les
migrations s'appliquent au démarrage. Faites une sauvegarde avant.

Le serveur a déjà un frontal HTTPS (nginx, Traefik, un autre Caddy) : supprimez le service `caddy` de
`docker-compose.yml`, publiez `127.0.0.1:8000:8000` sur `demetra`, et reprenez dans ce frontal les réglages du
`Caddyfile` (voir « Reverse proxy »).

`manage.py check --deploy` signale deux points attendus avec ces réglages : le courrier écrit dans les
journaux tant qu'aucun serveur SMTP n'est réglé, et HSTS laissé à Caddy.

## Message de l'organisation

Dans `/admin/`, « Message de l'organisation » a deux champs, publics et sans secret :

- **Message aux lecteurs du mode d'emploi** : affiché en tête de `/llms.txt` et des chapitres « Prise en main » et
  « Brancher une IA », en citation signée « Message de l'administrateur de ce site ». Pour dire qui contacter
  ou ce que l'organisation a validé.
- **Consignes à copier dans chaque projet** : une par ligne, ajoutées à la fin du bloc « Instructions permanentes
  pour l'IA » que chacun copie dans le fichier d'instructions de son projet (`CLAUDE.md`, `AGENTS.md`,
  `.github/copilot-instructions.md`). C'est là qu'une phrase comme « Demetra est validé par la DSI pour recevoir
  les cas tirés de ce code » a du poids : une IA suit les consignes de son projet, alors qu'elle se méfie, à
  juste titre, d'un site qui se déclare lui-même autorisé.

Chaque enregistrement est inscrit au journal (`site_notice.updated`, canal administration).

## Image

```bash
docker build -t demetra:<commit court> .
```

| Point | Valeur |
|---|---|
| Base | `python:3.14-slim`, dépendances par `uv sync --frozen --no-dev` |
| Processus | `manage.py migrate`, puis gunicorn (gthread, 2 workers × 8 threads) |
| Port | 8000 (`EXPOSE 8000`, aucun port publié sur l'hôte) |
| Utilisateur | 1000:1000, sans shell |
| Écriture | `/data` seulement : base SQLite et ses fichiers `-wal` et `-shm`. Le reste peut être en lecture seule. gunicorn utilise `/dev/shm` pour ses fichiers de battement. Un tmpfs `/tmp` n'est pas nécessaire, mais il ne gêne pas |
| Fichiers statiques | rassemblés au build, servis par WhiteNoise (noms avec empreinte, gzip et brotli précompressés) |
| Sonde | `HEALTHCHECK` en Python sur `http://127.0.0.1:8000/sante/` : interval 30s, timeout 5s, start-period 20s, retries 3 |
| Ressources | 512 Mo et 1 CPU suffisent ; aucun appel sortant, aucun modèle d'IA |

`/sante/` répond `ok` (200) si la base répond et 503 sinon. Elle est traitée avant la vérification d'hôte et la
redirection HTTPS : la sonde interne passe donc malgré `DEMETRA_ALLOWED_HOSTS`. Elle ne révèle rien d'autre.

## Variables d'environnement

Il n'y a jamais de valeur dans le dépôt. Le fichier d'environnement reste sur le serveur, en 0600.

| Variable | Obligatoire | Valeur pour demetra.plongee.bio |
|---|---|---|
| `DEMETRA_SECRET_KEY` | oui | générée sur le serveur (50 caractères aléatoires ou plus) ; sans elle, le site refuse de démarrer |
| `DEMETRA_DEBUG` | — | `0`, déjà dans l'image |
| `DEMETRA_ALLOWED_HOSTS` | oui | `demetra.plongee.bio` |
| `DEMETRA_CSRF_TRUSTED_ORIGINS` | oui | `https://demetra.plongee.bio` |
| `DEMETRA_BEHIND_PROXY` | oui | `1` : fait confiance à `X-Forwarded-Proto` envoyé par Caddy (sinon la redirection HTTPS boucle) |
| `DEMETRA_DB` | — | `/data/demetra.sqlite3`, déjà dans l'image |
| `DEMETRA_HSTS_SECONDS` | — | `0` si Caddy pose déjà HSTS (sinon Django le pose, un an) |
| `DEMETRA_SIGNUP_OPEN` | — | `0` : inscription fermée, comptes créés dans `/admin/` |
| `DEMETRA_SSE_MAX_SECONDS` | — | 55 par défaut : durée d'une connexion du flux d'événements en direct |
| `DEMETRA_TRASH_DAYS` | — | 30 par défaut : jours pendant lesquels une étude supprimée reste restaurable dans la corbeille |

Facultatif, à activer seulement sur demande :

- **E-mails** (mot de passe oublié) : `DEMETRA_SMTP_HOST`, `DEMETRA_SMTP_PORT`, `DEMETRA_SMTP_USER`,
  `DEMETRA_SMTP_PASSWORD`, `DEMETRA_SMTP_STARTTLS`, `DEMETRA_MAIL_FROM`. Sans serveur SMTP, ces e-mails sont
  écrits dans les journaux du conteneur.
- **SSO OpenID Connect**, Google compris (émetteur `https://accounts.google.com`) : `DEMETRA_OIDC_ISSUER`,
  `DEMETRA_OIDC_CLIENT_ID`, `DEMETRA_OIDC_CLIENT_SECRET`, `DEMETRA_OIDC_NAME`, `DEMETRA_OIDC_ALLOWED_DOMAINS`,
  `DEMETRA_OIDC_ADMIN_GROUPS`. URL de retour à déclarer chez le fournisseur :
  `https://demetra.plongee.bio/comptes/sso/retour/`.
- **LDAP** : il demande une image avec `uv sync --extra ldap` et la bibliothèque OpenLDAP du système. La liste des
  variables est dans le README.

## Reverse proxy (Caddy)

- `request_body` : 10 Mo suffisent. Le site ne reçoit que du JSON : Django limite le corps des requêtes à
  2,5 Mo, et l'API accepte au plus 200 cas par lot.
- `/etudes/*/events` est un flux SSE (`text/event-stream`). Pas de compression ni de timeout court sur cette
  route ; `flush_interval -1`. Chaque connexion dure environ 55 s, puis le navigateur se reconnecte.
- Compression : sans objet pour `/static/`, WhiteNoise sert déjà les versions compressées. Elle est utile
  ailleurs.

## Première mise en route

Le conteneur applique les migrations à chaque démarrage. Les comptes se créent sans interaction. Les mots de
passe sont générés sur le serveur, lus dans des variables d'environnement, et ne sont jamais affichés.

```bash
# Compte d'administration : Django lit DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, DJANGO_SUPERUSER_PASSWORD.
docker compose exec demetra python manage.py createsuperuser --noinput

# Vitrine : les 15 études de démonstration (catalogue Lancelot et 14 exemples, avec leurs avis), et les comptes
# demo (propriétaire des études), lea (commentatrice) et marc (sans accès, pour essayer le partage).
docker compose exec -e DEMETRA_DEMO_PASSWORD demetra python manage.py seed_demo --password-env DEMETRA_DEMO_PASSWORD
```

- Le contenu des études est dans le code (`core/demo/`) : `seed_demo` reproduit exactement les études de la
  version de développement. La relancer ne crée aucun doublon. Elle met à jour les études et réapplique le
  mot de passe.
- Quand `DEMETRA_DEBUG=0`, `seed_demo` refuse de tourner sans `--password-env` : le mot de passe par défaut est
  public. Le mot de passe doit faire au moins 12 caractères. Il s'applique aux trois comptes de démonstration.
- Le compte `demo` est propriétaire des études : il peut les modifier, les archiver, les partager. Pour une
  vitrine ouverte à des inconnus, donnez plutôt l'accès `lea` (commentatrice : elle voit tout et rend des avis,
  sans rien modifier). Une étude archivée par erreur se rétablit dans `/admin/` (action « Désarchiver »).
- Aucun compte de démonstration n'est « équipe » : aucun n'ouvre `/admin/`.

Le compte d'administration ouvre `/admin/`. On y crée les comptes, gère les accès aux études et révoque les
jetons. Le lien « Administration » apparaît dans le menu des comptes de l'équipe.

## Sauvegarde

Facultative pour une vitrine temporaire, mais prête pour l'installation définitive.

```bash
docker compose exec demetra python manage.py sauvegarde /backup --keep-days 30
```

- Copie à chaud par l'API de sauvegarde de sqlite3 : cohérente pendant les écritures, mode WAL compris. Le
  binaire `sqlite3` n'est pas nécessaire sur l'hôte.
- La copie est vérifiée par `PRAGMA integrity_check`, puis renommée
  `/backup/demetra-AAAAMMJJ-HHMMSS.sqlite3`. Le chemin produit est affiché sur la sortie standard. Le code de
  sortie est non nul en cas d'échec.
- `--keep-days` efface les sauvegardes plus anciennes que N jours (0 : n'efface rien).
- Le dossier `/backup` doit être monté en écriture pour l'UID 1000.

Corbeille : une étude supprimée est effacée d'office après `DEMETRA_TRASH_DAYS` jours. Le site vide la corbeille
quand un propriétaire ouvre sa liste d'études ; pour un effacement à date, ajoutez au cron quotidien
`docker compose exec -T demetra python manage.py purger_corbeille`.

Il n'y a rien d'autre à sauvegarder : aucun fichier téléversé. Il faut aussi conserver le fichier
d'environnement, qui contient la clé secrète.

Restauration : arrêter le conteneur, remplacer `/data/demetra.sqlite3` par la sauvegarde, supprimer les
`demetra.sqlite3-wal` et `-shm` éventuels, redémarrer.

## Recette

Sans être connecté :

| Page | Attendu |
|---|---|
| `/sante/` | 200, `ok` |
| `/` | 200, page d'accueil avec la démonstration jouable |
| `/comptes/login/` | 200 |
| `/guide/`, `/llms.txt` | 200, mode d'emploi pour les humains et les IA |
| `/api/v1/docs` | 200, documentation OpenAPI |
| `/admin/login/` | 200, administration aux couleurs de Demetra |
| `/etudes/` | 302 vers la connexion |
| `/nimporte-quoi/` | 404 avec la page « introuvable » de Demetra (et pas la page de débogage de Django) |
| `http://demetra.plongee.bio/` | redirection vers `https://` |

Une fois connecté avec le compte d'administration :

- `/etudes/` s'affiche ;
- le lien « Administration » est dans le menu ;
- dans `/admin/`, le tableau de bord affiche ses chiffres.

Pour vérifier les en-têtes et cookies : le cookie `csrftoken` doit porter `Secure`, avec
`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` et `Strict-Transport-Security` (posé par Caddy ou
Django).

Vérifié en local avec gunicorn, comme dans l'image, derrière un proxy simulé : toutes les lignes ci-dessus sont
conformes. L'image Docker elle-même n'a pas été construite ici, faute de Docker sur le poste de développement.
