# Jetons, portées et limites

Version {{version}}.

## S'authentifier

Chaque requête porte l'en-tête :

```
Authorization: Bearer dmt_xxxxxxxxxx_…
```

Le jeton est créé par l'utilisateur dans l'interface (**Compte › Jetons d'accès**). Il n'est affiché qu'une fois ; le site n'en conserve qu'un condensé. Il peut expirer, être révoqué à tout moment, et être limité à certaines études. Ne le placez jamais dans une URL.

Le jeton est un mot de passe : rangé dans la variable d'environnement `DEMETRA_TOKEN`, jamais collé dans la conversation d'une IA. Un outil de lecture de page web n'envoie pas d'en-tête et reçoit donc 401 : appelez l'API depuis un terminal. Voir **Brancher une IA en sécurité** (`/api/v1/guide/agents`).

`GET /api/v1/me` renvoie l'utilisateur, les portées du jeton, sa date d'expiration et les études auxquelles il est éventuellement limité.

## Portées

| Portée | Permet |
|---|---|
| `studies:read` | Lire études, cas, couverture, avis, commentaires, représentations. |
| `studies:write` | Créer et modifier des études, déposer et retirer des cas. |
| `representations:write` | Choisir la représentation d'une étude, pour vous ou pour un cas ; créer, ajuster, proposer des représentations ; signaler une brique manquante. |
| `share:request` | Demander un partage, toujours confirmé par un humain. Non cochée par défaut. |

Un jeton ne donne **jamais plus** que le rôle de son propriétaire sur l'étude : lecteur, commentateur, éditeur ou propriétaire. Écrire dans une étude demande au moins le rôle éditeur.

## Réponses d'accès

- **401** `unauthenticated` : jeton absent, inconnu, expiré ou révoqué.
- **403** `missing_scope` : la portée manque ; `forbidden` : le rôle est insuffisant ; `human_only` : l'action est réservée à un humain dans l'interface.
- **404** `not_found` : l'étude n'existe pas **ou** vous n'y avez pas accès (le site ne distingue pas les deux).

Chaque action faite avec un jeton est inscrite au journal d'audit de l'étude avec le nom du jeton.
