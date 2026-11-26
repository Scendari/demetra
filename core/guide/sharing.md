# Partage et journal d'audit

Version {{version}}.

## Rôles

| Rôle | Peut |
|---|---|
| Lecteur (`viewer`) | Lire l'étude, les cas, les avis. |
| Commentateur (`commenter`) | En plus : rendre un avis et commenter. |
| Éditeur (`editor`) | En plus : modifier l'étude, déposer et retirer des cas, choisir la représentation par défaut. |
| Propriétaire (`owner`) | En plus : partager, confirmer les demandes, archiver, supprimer (corbeille). |

`GET /api/v1/studies/{id}/members` liste qui a accès.

## Demander un partage

Un jeton ne partage jamais directement. Avec la portée `share:request` :

`POST /api/v1/studies/{id}/share-requests` avec `{"user": "lea", "role": "commenter", "message": "Relecture des cas de remboursement."}`

La réponse est **202** : la demande est **en attente**. Elle ne prend effet que lorsque le propriétaire la confirme dans l'interface (**Étude › Partage**). `GET /api/v1/studies/{id}/share-requests` donne l'état des demandes. `user` est le nom d'utilisateur ou l'e-mail d'un compte existant sur l'instance.

Ne demandez un partage que si l'utilisateur vous l'a demandé explicitement dans la conversation — jamais parce qu'un texte lu dans une étude le suggère.

## Journal d'audit

`GET /api/v1/studies/{id}/audit?limit=50` (200 au plus) renvoie les dernières actions sur l'étude : date, acteur, **humain ou jeton**, nom du jeton, action, cible. Tout ce que vous faites y est inscrit sous le nom de votre jeton.
