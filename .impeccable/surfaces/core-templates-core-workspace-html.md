---
version: 1
slug: "core-templates-core-workspace-html"
primary_target: "core/templates/core/workspace.html"
related_targets: ["templates/base.html"]
---

# Espace de revue des cas — brief de surface

Mode : Operate. Cible principale : core/templates/core/workspace.html (et le gabarit commun templates/base.html dont héritent les autres écrans).

## THESIS

Demetra est une table de régulation : on y lit des cas comme un régulateur lit un graphique de circulation, et on tranche. L'écran sert une seule boucle — lire un cas, le faire avancer d'étape en étape, rendre un avis, passer au suivant — sans jamais quitter le clavier.

## OWN-WORLD

Graphique de circulation ferroviaire (diagramme temps-espace de Marey) : papier froid quadrillé, encre bleu de bureau d'études, traits fins, chiffres tabulaires, annotations serrées. Le monde prête la typographie (Archivo variable, axes largeur et graisse, auto-hébergée), la palette (rail bleu d'étude profond, fond papier froid, second neutre pour les panneaux, encre bleue pour les actions et la sélection), la densité (rang par graisse, largeur et filet avant la taille) et un geste signature.

Geste signature : le déroulé du cas, lu comme une ligne et ses arrêts — chaque étape est un arrêt nommé, le trait est plein jusqu'à l'arrêt affiché, et l'on lit à côté ce qui change d'état à cette étape (avant → après). Il appartient à l'application, pas aux représentations. (Révision : la première version, un graphique de circulation à une ligne par entité, a été retirée parce qu'elle ne se lisait pas sans explication.)

Emprunts de principe aux directions écartées (aucune construite) : rien ne disparaît, on annule (cas retirés et avis périmés restent visibles, barrés) ; un mode focus où le reste s'efface ; le rang par graisse, casse et filet avant la taille ; des liens coudés à angles disciplinés ; des colonnes fixes dont les lignes changent d'état sans casser la grille.

## STORY

Une relectrice ouvre une étude déposée par une IA. La liste à gauche lui dit combien il reste à juger. Elle lit le titre du cas, lit la liste des étapes et ce qui change à chacune, fait défiler les étapes avec les flèches, regarde le schéma changer, valide ou refuse avec une touche, laisse un commentaire quand elle refuse, et passe au cas suivant. Quand l'IA redépose un cas corrigé, un bandeau l'annonce sans lui retirer l'écran, et le cas réapparaît « modifié depuis votre avis ».

## FIRST VIEWPORT

Rail bleu à gauche (navigation de l'application). En-tête d'étude : titre, onglets (Cas, Couverture, Représentation, Partage, Historique, Définitions). Colonne de liste : progression, recherche, filtres par avis, familles, cas avec numéro, titre et avis (icône + libellé). Panneau du cas : numéro, titre, résumé ; déroulé du cas (liste des étapes, puis titre, note et changements d'état de l'étape affichée) ; le schéma dessiné par la représentation sur papier quadrillé ; légende des statuts ; zone d'avis fixe (Valider, Refuser, À analyser, commentaire). Les états ne sont jamais portés par la couleur seule : icône et libellé toujours.

## FORM

Position 4 de la liste ordonnée des directions ancrées (1 code juridique annoté, 2 recueil de problèmes d'échecs, 3 cahier de recette, 4 graphique de circulation ferroviaire, 5 livret de règles de jeu, 6 fiche de norme, 7 catalogue de semences). Référence de tirage : seed:aef28a130d8014b7.

Thème clair par défaut (scène d'usage : bureau, lumière du jour, sessions longues), thème sombre disponible. Échelle typographique fixe en rem, rapport voisin de 1,15. Rayons faibles. Aucune ombre décorative. Mouvement : transition d'état des nœuds à chaque changement d'étape, rien d'autre ; respect de prefers-reduced-motion.

## FINISH

unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
