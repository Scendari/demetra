# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Décidé par l'utilisateur : site web Python. Django + Django Ninja + django-allauth, SQLite pour le POC, géré avec uv. Pages rendues par le serveur (templates Django) et JavaScript natif sans framework. Pas de LLM embarqué, pas de MCP dans le POC (API REST seule).

## Users

- **Relecteur métier** (utilisateur principal) : connaît les règles de gestion de son domaine, pas forcément le code. Assis à son poste, il passe en revue des dizaines à des centaines de cas et rend un avis sur chacun : validé, refusé, à analyser, avec un commentaire.
- **Auteur de l'étude** : crée l'étude, branche son IA habituelle (Claude Code, Cursor…) avec un jeton personnel, lui fait déposer les règles et les cas, garde la main sur la représentation, partage l'étude.
- **IA externe** (utilisateur non humain) : lit le mode d'emploi, dépose et corrige des cas par l'API, lit la couverture, les avis et les commentaires, compose des représentations avec les briques du site et fixe celle de l'étude qu'elle dépose. Elle ne rend jamais d'avis.

Contexte : petite équipe, instance auto-hébergée. Interface en français.

## Product Purpose

Demetra permet de connaître les cas qui découlent d'une ou plusieurs règles de gestion ou d'un processus métier, et de voir ceux qui manquent encore : le site mesure la couverture, il ne garantit pas l'exhaustivité. Les règles sont traduites en cas ; chaque cas est montré comme un schéma qui évolue étape par étape ; chaque cas reçoit l'avis d'un humain. Le site sert de terrain commun entre l'utilisateur et son IA : l'IA propose, le site vérifie et mesure ce qui manque, l'humain tranche.

Succès : un relecteur sait à tout moment ce qui est couvert, ce qui manque, ce qui a changé depuis son dernier passage, et peut rendre un avis en une touche.

## Positioning

Un lieu durable où une IA externe dépose des cas illustrés et où des humains rendent un avis cas par cas. Le site est la partie déterministe du circuit : il valide la structure, rejoue les étapes, mesure la couverture et attache chaque avis à un contenu précis. Aucun voisin recensé (vérificateurs de tables de décision, animateurs de traces formelles, outils de revue de captures) ne réunit ces fonctions ; le substitut réel est la page HTML jetable générée par un agent.

## Operating Context

- Point de départ réel : un catalogue statique de 136 scénarios d'un ordonnanceur de workflows (`sources/catalogue/`), relu à la main, avis stockés dans le navigateur.
- Trois familles de règles à égalité : workflows et états, règles de décision (éligibilité, tarification), règles temporelles (délais, échéances).
- Depuis l'élargissement du catalogue (`reports/Représentations des règles et processus.md`), les règles logicielles et les processus métier sont couverts aussi : croisement de deux facteurs, calculs, seuils, objets métier dont des champs changent, jeux de règles en concurrence, cycles de vie, échanges entre acteurs.
- Circuit de travail : l'IA dépose un lot de cas → le site renvoie erreurs et combinaisons manquantes → l'humain relit, commente → l'IA relit les avis et corrige → les cas modifiés repassent « à analyser ».
- Les études sont privées par défaut et partagées par rôles : propriétaire, éditeur, commentateur, lecteur.

## Capabilities and Constraints

- Vocabulaire fixe : étude, règle, cas, étape, statut, dimension, représentation, brique, avis (validé / refusé / à analyser).
- Les statuts sont définis par chaque étude ; un statut n'est jamais indiqué par la couleur seule.
- Les représentations sont des assemblages de briques fournies par le site (formes, dispositions, liaisons donnée→visuel, évolution dans le temps, composition), décrits par un document JSON validé. Le site n'exécute jamais de code fourni par l'IA.
- Seize représentations fournies : sept d'origine (graphe, tables, frise, couloirs, vignettes) et neuf pour les règles et processus (matrice croisée, calcul pas à pas, axe à bandes, avant / après, table de règles, arbre de décision, table d'états, diagramme d'états, diagramme de séquence). Toutes sont dessinées par le site, sans bibliothèque de mise en page.
- Le format de cas porte, en option : valeurs chiffrées, champs d'entité, messages entre acteurs, mesures ; l'étude peut déclarer des tranches, un jeu de règles et des cycles de vie. Le site contrôle la cohérence entre les deux et donne le chemin exact de chaque erreur.
- Atelier : l'onglet « Atelier » part d'une page vide. L'utilisateur y construit sa propre situation avec les briques que l'étude déclare (il les pose, les relie, règle leurs options, provoque un évènement), et le site montre ce que les règles de l'étude en font, pas après pas. Aucun cas déposé n'y figure. Les règles sont déclarées par l'étude dans un vocabulaire fermé, que le site exécute lui-même : aucun code fourni par l'étude ne l'est. Une étude sans règles déclarées n'a pas d'atelier et garde ses cas. Le résultat est toujours donné pour ce qu'il est, ce que disent les règles déclarées, et ne reçoit jamais d'avis ; un humain peut enregistrer la situation comme cas, pas une IA. Deux familles d'atelier existent, une par étude : des éléments reliés qui changent d'état, ou des périodes datées que le site combine en un historique (l'étude déclare alors ses sources et la façon de composer une image, pas une table de règles).
- Cas paramétré : un cas peut couvrir plusieurs situations par des paramètres et des étapes conditionnelles, dans un vocabulaire fermé ; le site rejoue chaque combinaison au dépôt. L'avis porte sur le cas entier.
- **Une étude = une représentation.** L'IA qui dépose l'étude la fixe ; le relecteur peut en changer pour lui, pour un cas ou pour toute l'étude — c'est son choix et sa responsabilité. Un jeton ne remplace pas un choix humain fait pour l'étude.
- Licences : tout composant doit être gratuit et permis en usage commercial d'entreprise, sans flou juridique. Ni ELK, ni Graphviz, ni aucune licence EPL, MPL, LGPL, GPL ou AGPL.
- La zone d'avis, le libellé d'étape et la légende des statuts sont affichés par l'application, hors de la représentation.
- Un jeton d'IA lit les avis mais ne peut pas en poser ; un partage demandé par jeton attend la confirmation d'un humain dans l'interface.
- Un avis est attaché à l'empreinte du contenu du cas : modifier un titre ne l'invalide pas, modifier le déroulé le fait repasser « à analyser ».
- Non décidé : exposition de l'instance sur Internet, OAuth, PostgreSQL, licence de distribution.

## Brand Commitments

- Nom : **Demetra**, pour **DÉ**cisions **MÉ**tier **TR**acées et **A**rbitrées (acronyme choisi le 22/11/2026). Il figure en petit sous le nom, sur l'accueil.
- Exigence explicite de l'utilisateur : « très UX ».
- Accroche de l'accueil (choisie le 22/11/2026) : « Vos règles, cas par cas, étape par étape. » Elle ne promet pas
  l'exhaustivité : le site mesure ce qui manque, il ne garantit pas que « tous les cas » existent.
- L'accueil doit faire effet dès le premier écran : un cas fictif s'y déroule seul, dans le diagramme d'états
  (cycle de vie d'une commande), et se pilote aux flèches.

## Evidence on Hand

- `sources/catalogue/` : prototype réel (136 cas, 15 familles, 11 statuts), importé comme étude de démonstration.
- `reports/Cadrage du projet Demetra.md` : rapport de cadrage et ses notes de recherche.
- `reports/Représentations des règles et processus.md` : rapport sur les représentations à ajouter, et ses notes de recherche.
- Les études « règles de décision » et « règles temporelles » de démonstration, l'étude de cas paramétrés, l'étude du circuit de validation (qui déclare ses règles d'atelier), ainsi que les neuf études qui illustrent le catalogue élargi, sont synthétiques : elles sont marquées « Exemple · données fictives » dans l'interface.
- Aucun client, témoignage, chiffre d'usage ni tarif n'existe : ne pas en inventer.

## Product Principles

1. **L'humain tranche, le site prouve, l'IA propose.** Chaque écran distingue ce qui est affirmé par l'IA, vérifié par le site et jugé par un humain.
2. **Montrer ce qui manque autant que ce qui est là.** La couverture et les cas modifiés sont aussi visibles que les cas eux-mêmes.
3. **Une touche, un avis.** La revue de centaines de cas doit rester rapide, au clavier, avec annulation.
4. **La représentation sert le cas, jamais l'inverse.** Aucune représentation ne peut modifier ni masquer l'avis, l'étape ou la légende. Une étude en a une ; le relecteur peut toujours en changer.
5. **Rien ne change sous les yeux du relecteur.** Les mises à jour venues de l'IA s'annoncent ; elles ne remplacent pas l'écran en cours de lecture.

## Accessibility & Inclusion

- Cible WCAG 2.2 AA : contraste, cibles de 24 px, focus visible, tout au clavier.
- Statuts encodés par couleur + icône + libellé.
- Respect du réglage « réduire les animations ».
- Thèmes clair et sombre.
