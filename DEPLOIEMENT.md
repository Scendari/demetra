# Déploiement de Demetra

Image Docker construite depuis ce dépôt. Elle n'écrit que dans `/data` et se place derrière un reverse proxy
HTTPS (Caddy). Le docker-compose, le fichier d'environnement et la route Caddy restent sur le serveur, pas dans
le dépôt.

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

# Vitrine : les 14 études de démonstration (catalogue Lancelot et 13 exemples, avec leurs avis), et les comptes
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
