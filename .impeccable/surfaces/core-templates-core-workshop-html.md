---
version: 1
slug: "core-templates-core-workshop-html"
primary_target: "core/templates/core/workshop.html"
related_targets: ["core/templates/core/_workshop.html", "core/templates/core/_workshop_choice.html"]
---

# Onglet « Atelier » d'une étude

Mode : Operate. Surface entière dans le monde établi de Demetra (DESIGN.md fait foi, rien n'y est remplacé).

- **Qui, pour quoi** : le relecteur métier ou l'auteur de l'étude construit sa propre situation pour voir ce que les règles de l'étude en font, avant ou pendant la revue.
- **Tâche** : partir d'une page vide ; poser des briques du vocabulaire de l'étude, les nommer, les relier, régler leurs options, provoquer un évènement ; lire le résultat et le déroulé pas à pas, avec la règle appliquée à chaque pas ; garder la situation comme cas.
- **États** : page vide ; situation construite et stable ; situation où aucune règle ne s'applique ; situation qui ne se stabilise pas ; situation pleine (24 briques) ; étude sans règles déclarées ; lecteur sans droit d'enregistrer.
- **Contraintes** : rendu serveur, un seul script, jetons de `tokens.css`, deux thèmes, 390 px, tout au clavier, la page marche sans script, tout l'état tient dans l'adresse. Une situation ne reçoit jamais d'avis. Aucun cas déposé n'est affiché.

## Direction contract

THESIS : un établi, pas un navigateur de cas ni un formulaire de paramètres. On construit à gauche, le site répond à droite. Demande de l'utilisateur, le 24 novembre 2026 : « Je ne veux pas que ça affiche les cas, mais que l'utilisateur puisse "construire" son cas avec les briques disponibles pour qu'il voit ce que ça donne à la fin en terme de résultat. » Deux versions précédentes ont été refusées : la liste de cas à choisir, puis l'instrument à leviers sans construction.

OWN-WORLD : celui de DESIGN.md. Palette de boutons « + brique », fiches cernées `line-strong` portant une lettre en aplat `ink`, cases à cocher en pastilles (`accent` pour une option, `warning` pour un évènement). Le résultat est le plus grand texte de la colonne de droite.

STORY : « je pose trois tâches, je les relie, j'en fais échouer une, et je vois ce que les règles de l'étude en font ».

FIRST VIEWPORT : à gauche (23rem, collante), « Construire la situation » : palette, réglages, briques posées. À droite : « Résultat », le compte des briques par état final, la phrase sur l'origine, puis le schéma (plan de travail) et le déroulé. Page vide : le titre de l'atelier, une phrase, les règles de l'étude. Sous 900 px, la construction passe au-dessus, avec un lien « Voir le résultat ».

FORM : construction à gauche, réponse à droite. seed: none (pinned) — voir la demande ci-dessus.

Interaction signature : le schéma est le plan de travail — on y glisse une brique de la palette, on y tire un lien d'une brique à l'autre, et le site replace le tout. Chaque geste (poser, relier, cocher) redessine le résultat sur place ; « Dérouler » fait défiler les pas, un toutes les 0,9 s. Mouvement : aucun autre que les transitions d'état existantes.

Demande de l'utilisateur après la première version, le 24 novembre 2026 : « ajouter le glisser déposer et les liaisons ». Fait sur le schéma dessiné par le site. Non fait : placer les briques librement à la main (le site calcule la disposition), glisser une brique depuis la palette au doigt.

Demande de l'utilisateur, le 24 novembre 2026 : « C'est généralisable maintenant sur tous les autres type de représentation ? Tu peux faire l'atelier "Historique" en démo ? ». Fait : une seconde famille d'atelier, « périodes », sur le même écran — fiches à deux bornes, tableau « Historique obtenu », encadré de blocage. Non fait : tirer ou étirer une période directement sur la frise.

Demande de l'utilisateur, le 25 novembre 2026 : « tu peux tout faire » (les améliorations proposées). Fait pour l'atelier de périodes : le déroulé va au bout de l'axe ; chaque ligne de l'historique dit d'où elle vient (survol, clic, clavier), et chaque fiche dit les lignes qu'elle alimente ; après chaque geste, l'historique marque ses lignes nouvelles, modifiées et disparues ; une période se déplace et s'étire à la souris sur la frise, calée sur le pas de l'axe ; une étude peut déclarer des exécutions successives, et l'écran montre ce que chacune ajoute, ferme, modifie, retire ou laisse.

FINISH : revue de finition (`impeccable-finish-reviewer`) passée le 25 novembre 2026 sur les deux familles, à 1280 et 390 px, en clair et en sombre ; corrections matérielles appliquées (aucun liseré latéral sur une ligne marquée, tableau qui ne s'élargit plus quand les marques arrivent, statut jamais recouvert sur petit écran, cibles d'au moins 24 px, réserves de la provenance et du dernier geste, anneau de focus entier, mots de la famille « périodes », phrase d'une exécution, geste au doigt). Trois passes : la dernière ne relève plus rien de matériel (disposition « ship »). Sur petit écran, le mot du changement d'une exécution passe sur sa propre ligne au-dessus de la ligne qu'il qualifie. Traités ensuite : le mot du dernier geste passe lui aussi sur sa propre ligne sous 900 px, la période écartée garde un contour lisible, l'aide ne dit plus « cliquez », et les états rares ont été regardés à 1280 et 390 px (situation pleine, déroulé qui boucle ou atteint sa limite, lectrice sans droit d'enregistrer, page sans script, étude sans atelier) — un déroulé non stabilisé n'annonce plus de résultat d'ensemble. Restent au goût, non traités : la place du mot sur grand écran (en tête dans les exécutions, en fin de ligne dans le tableau principal), les blancs réservés à 390 px, les titres des deux colonnes, la largeur minimale de la frise, la taille des graduations.
