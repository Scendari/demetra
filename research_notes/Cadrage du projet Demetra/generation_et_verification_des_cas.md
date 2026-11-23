# Génération et vérification des cas : « l'IA écrit les cas » (A) contre « hybride » (B)

Notes de recherche arrêtées au 21 novembre 2026. Conventions : « vérifié » = lu dans la source pendant cette session ; « extrait de recherche » = chiffre vu dans un extrait de moteur de recherche, non relu dans le texte intégral ; « connaissance de fond » = non revérifié pendant cette session (placé en Inférences). Les versions et dates PyPI/GitHub ont été relevées par interrogation directe des API pypi.org et api.github.com le 21/11/2026.

## 1. Fiabilité des LLM pour énumérer exhaustivement des cas à partir de règles ou de code (2024-2026)

### Takeaway
Aucune étude trouvée ne montre qu'un LLM seul énumère exhaustivement les cas d'un jeu de règles : les mesures disponibles montrent un biais « chemin nominal », des trous systématiques sur les valeurs limites et les branches d'erreur, des oracles faux, et une variabilité d'une exécution à l'autre. Les gains mesurés viennent presque toujours d'une boucle externe déterministe (exécution du vrai code, mesure de couverture, contrôles structurels suivis de réparation), ce qui plaide pour au minimum « A + contrôles », et non pour A pur.

### Cited Findings
- Revue systématique (21 études primaires, 2000-2025) : aucune approche de génération de tests depuis des exigences en langage naturel ne satisfait simultanément les six critères (automatisation, gestion de l'ambiguïté, applicabilité, traçabilité, rigueur d'évaluation, contrôle des hallucinations) ; hallucination et perte de traçabilité sont nommées comme risques propres aux LLM (vérifié sur le résumé). — [Folorunsho & Reza, arXiv 2606.06563, juin 2026](https://arxiv.org/abs/2606.06563)
- Même revue : la dégradation de la précision quand la complexité des exigences augmente est « bien documentée mais insuffisamment mesurée », avec une dégradation de la performance MC/DC quand les interactions conditionnelles augmentent (extrait de recherche du PDF, non relu en entier). — [arXiv 2606.06563 (PDF)](https://arxiv.org/pdf/2606.06563)
- LLM4Fin (ISSTA 2024, règles métier boursières) : pipeline où deux LLM affinés font l'extraction des règles et la génération de scénarios, et où « les autres étapes sont réalisées par des algorithmes » déterministes ; les auteurs annoncent de meilleurs résultats que ChatGPT généraliste et que des testeurs expérimentés. — [ISSTA 2024](https://2024.issta.org/details/issta-2024-papers/131/LLM4Fin-Fully-Automating-LLM-Powered-Test-Case-Generation-for-FinTech-Software-Accep)
- Chiffres LLM4Fin rapportés par la revue de 2026 (source secondaire, non recoupée avec l'article d'origine) : couverture moyenne des scénarios métier 91,89 % contre 49,65 % pour ChatGPT généraliste. — [arXiv 2606.06563 (PDF)](https://arxiv.org/pdf/2606.06563)
- Analyse des angles morts (octobre 2026, 14 320 tests générés par 4 LLM, 4 stratégies de prompt, Java) : couverture des arguments null 34,8 %, négatifs 23,8 %, vides 38,8 %, alors que les booléens dépassent 93 % ; adéquation du flot de contrôle 0,100 pour les blocs catch et 0,312 pour les branches default ; 15,6 % des échecs de tests dus à des assertions incorrectes ; biais « chemin nominal » ; les mêmes angles morts existent sur les fonctions peu complexes (vérifié sur le résumé). — [Shi et al., arXiv 2610.32548](https://arxiv.org/abs/2610.32548)
- Grande étude tests unitaires LLM contre EvoSuite (EMSE 2026) : les auteurs concluent que des approches hybrides combinant génération LLM, validation automatisée et raffinement par recherche sont nécessaires pour un résultat de niveau production (extrait de recherche). — [Ouédraogo et al., arXiv 2407.00225](https://arxiv.org/abs/2407.00225)
- La complexité cyclomatique de la méthode ciblée est un facteur limitant de la couverture obtenue par LLM (extrait de recherche). — [Seed&Steer, arXiv 2507.17271](https://arxiv.org/abs/2507.17271)
- MC/DC par IA générative (conférence 2026, dispositifs médicaux) : les suites générées naïvement pour des expressions logiques courantes sont déficientes ; un flux avec supervision humaine et outils d'analyse classiques les rend exploitables (extrait de recherche). — [Dorin, Leveraging AI for MC/DC Unit Test](https://researchonline.stthomas.edu/esploro/outputs/conferenceProceeding/Leveraging-AI-for-MCDC-Unit-Test/991015448628903691)
- Variabilité entre exécutions : sur 5 LLM réglés en mode « déterministe », 8 tâches et 10 exécutions, variations d'exactitude allant jusqu'à 15 % entre exécutions identiques (extrait de recherche). — [Atil et al., arXiv 2408.04667](https://arxiv.org/abs/2408.04667)
- Cause numérique : sorties différentes selon le nombre de GPU, la taille de lot ou le matériel, même en décodage glouton à graine fixe (extrait de recherche). — [arXiv 2506.09501](https://arxiv.org/abs/2506.09501)
- Machines à états depuis des exigences en texte libre (mars 2026) : F1 de 0,90 sur les états et 0,75 sur les transitions (Claude 3.5 Sonnet, prompt unique) ; F1 de 0,23 sur les gardes et 0,00 sur les actions (GPT-4o) (vérifié sur le résumé). — [Abdulkarim et al., arXiv 2604.00275](https://arxiv.org/abs/2604.00275)
- Banc LLM-FSM : même les modèles de pointe peinent sur le niveau difficile pour retrouver le comportement d'une FSM depuis une spécification en langage naturel (extrait de recherche). — [arXiv 2602.07032](https://arxiv.org/abs/2602.07032)
- Mitigation « exécuter le vrai code et filtrer » : TestGen-LLM (Meta) rejette les tests qui ne compilent pas, échouent de façon répétée ou n'ajoutent pas de couverture ; environ 57 % des cas générés sont exécutables et environ 25 % augmentent la couverture ; 73 % des recommandations acceptées par les ingénieurs (extrait de recherche). — [Alshahwan et al., arXiv 2402.09171](https://arxiv.org/abs/2402.09171)
- Mitigation « boucle de couverture » : CoverUp (Python) renvoie au LLM les lignes et branches non couvertes ; couverture médiane par module 80 % contre 47 % pour CodaMosa (v3) ; le dialogue itératif explique près de la moitié des générations réussies (extrait de recherche ; chiffres variables selon la version de l'article). — [CoverUp, arXiv 2403.16218](https://arxiv.org/abs/2403.16218)
- Mitigation « contrôles structurels déterministes puis réparation » : des règles détectant états orphelins, états inatteignables et transitions invalides, suivies d'une réparation itérative, font passer la validité structurelle de DeepSeek de 22,2 % à 88,9 %, la plupart des réparations aboutissant en deux itérations (extrait de recherche). — [ESEM 2026, LIPIcs](https://drops.dagstuhl.de/storage/00lipics/lipics-vol394-esem2026/LIPIcs.ESEM.2026.19/LIPIcs.ESEM.2026.19.pdf)

### Inferences
- Trois modes d'échec sont documentés et se transposent directement aux « cas » du produit : (1) omissions concentrées sur les limites, les erreurs et les combinaisons de conditions ; (2) comportement affirmé mais faux (oracle incorrect, ici une frame ou un statut inventé) ; (3) non-reproductibilité (deux analyses de la même règle ne donnent pas le même catalogue).
- Les états sont mieux retrouvés que les transitions, elles-mêmes mieux que les gardes et actions. Or un « cas » du prototype est précisément une suite de transitions gardées : c'est la partie la moins fiable qui porte la valeur.
- L'option A pure ne fournit aucun signal d'omission : un humain qui valide 70 cas un par un ne voit pas le 71e manquant. La revue humaine cas par cas vérifie la justesse, pas la complétude.
- Le schéma gagnant dans la littérature est « le LLM propose, un mécanisme déterministe mesure et renvoie un diagnostic, le LLM corrige ». Dans l'architecture du produit (IA externe via API/MCP), le site peut jouer ce rôle de mesure sans embarquer de LLM : la réponse de l'API porte le diagnostic.
- La plupart des mesures portent sur des modèles de 2024-2025 (GPT-4o, Claude 3.5 Sonnet, modèles ouverts). Les agents de fin 2026 qui exécutent le code sont vraisemblablement meilleurs, mais l'exhaustivité reste un problème combinatoire qu'un générateur ne peut pas s'auto-certifier.

### Gaps
- Aucune étude trouvée ne mesure directement, avec des agents de pointe de 2026, le taux d'omission lors de l'énumération exhaustive de scénarios pas à pas à partir de règles métier ; les chiffres ci-dessus viennent de tâches voisines (tests unitaires, exigences, FSM).
- Aucune mesure trouvée de l'incohérence entre exécutions spécifiquement pour la génération de cas de test.
- Les chiffres LLM4Fin n'ont pas été recoupés avec l'article d'origine. Les travaux de Meta sur les tests guidés par mutation n'ont pas été recherchés.

## 2. Représentations formelles pour un modèle générique de règles, et limites de la généricité

### Takeaway
Un schéma JSON neutre unique est réaliste s'il repose sur un noyau « variables d'état typées à domaines finis + règles gardées (condition, effets) + invariants », dont la table de décision et la machine à états sont deux cas particuliers ; la généricité casse sur le temps continu et les calendriers, l'arithmétique non bornée, les agrégats sur collections, les topologies paramétrées et la concurrence. Il faut un langage maison simple en JSON plutôt qu'un langage formel de niche : les LLM échouent massivement en TLA+ et en Alloy.

### Cited Findings
- Les tables de décision DMN ont une sémantique formelle publiée ; chaque règle s'interprète comme un hyper-rectangle dans un espace à N dimensions (une par colonne d'entrée), ce qui ramène chevauchement et règles manquantes à des problèmes géométriques. — [Calvanese et al., arXiv 1603.07466](https://arxiv.org/abs/1603.07466)
- Les politiques de résolution (hit policies) UNIQUE, ANY, COLLECT et RULE_ORDER conditionnent quels contrôles ont un sens : conflit et masquage ne sont pas vérifiés en COLLECT ou RULE_ORDER, le chevauchement n'est une erreur qu'en UNIQUE. — [dmn-check, README](https://github.com/red6/dmn-check)
- Le format JDM (JSON Decision Model) de GoRules montre qu'un format JSON couvre tables de décision, aiguillages (switch), expressions, fonctions et sous-décisions ; premier-trouvé par défaut, collecte par colonne de sortie depuis la 2.0. — [gorules/zen](https://github.com/gorules/zen)
- Statecharts : sismic les décrit en YAML, avec une sémantique fondée sur SCXML (à quelques exceptions, réglable), des contrats (préconditions, postconditions, invariants sur états et transitions) et des « property statecharts » vérifiés à l'exécution. — [sismic, documentation](https://sismic.readthedocs.io/en/latest/)
- python-statemachine 3.x gère états composés, régions parallèles, historique superficiel et profond, gardes ordonnées, et le chargement de machines depuis des documents déclaratifs (YAML, dictionnaires). — [python-statemachine sur PyPI](https://pypi.org/project/python-statemachine/)
- LLM et TLA+ : 30 LLM, 205 spécifications ; au mieux 26,6 % de correction syntaxique et 8,6 % de correction sémantique ; la taille du modèle ne prédit pas la qualité ; conclusion : supervision experte nécessaire. Limite : 25 modèles ouverts, 5 propriétaires testés seulement en few-shot (vérifié sur le résumé). — [Bisharat et al., arXiv 2606.05792](https://arxiv.org/abs/2606.05792)
- LLM et Alloy (modèles complets) : seul GPT-5 passe la vérification syntaxique après plusieurs essais, avec 0 % de correction à l'exécution, attribué à la rareté d'Alloy dans les données d'entraînement (extrait de recherche). — [SysMoBench, arXiv 2509.23130](https://arxiv.org/abs/2509.23130)
- Résultat contraire sur une tâche plus étroite : les LLM écrivent généralement bien des formules Alloy isolées depuis le langage naturel (extrait de recherche ; tâche non comparable). — [arXiv 2502.15441](https://arxiv.org/abs/2502.15441)
- Observation du prototype (lecture directe, pas d'URL) : environ 70 cas en 15 familles ; un cas déclare des nœuds avec options (`always_run`, `ignore_on_error`, `active`), des arêtes, et des steps exprimés en deltas de statut que le code replie en frames cumulées ; une dizaine de statuts ; des `decisions` par nœud (WAIT, LAUNCH) ; chaque cas référence des sources (fichier, fonction, ligne) et des tests. — prototype local `catalogue-runs-data.js`

### Inferences
- Le prototype est un système de transitions gardées : un état global (statut par nœud + configuration) et une fonction de décision appliquée à chaque pas. La fonction de décision est une table de décision ; l'enchaînement est une machine à états produit. Les deux formalismes se rejoignent dans le noyau « variables + règles gardées ».
- Proposition de noyau JSON neutre : `variables` (nom, type parmi enum, bool, entier borné, date ou durée discrétisée), `entities` optionnelles (nœuds, arêtes), `rules` (id, `when` = expression booléenne, `then` = affectations ou sortie, priorité ou hit policy), `events` (déclencheurs externes), `invariants`, `initial`, `terminal`. Une table de décision = règles sans état, évaluées une fois. Une FSM = une seule variable d'état. Un workflow = une variable de statut par nœud. Une règle temporelle = une variable d'horloge discrète ou des événements de type échéance.
- Le langage d'expression doit rester minimal (comparaisons, et/ou/non, appartenance, arithmétique entière bornée) pour être traduisible mécaniquement vers Z3 et évaluable en Python sans `eval`.
- Où la généricité casse : (a) temps réel, calendriers, fuseaux, jours ouvrés (demande une discrétisation ou une théorie dédiée) ; (b) tarification sur réels et tables volumineuses (domaines infinis : l'exhaustivité devient une partition en classes d'équivalence, pas une énumération) ; (c) agrégats et quantificateurs sur collections de taille variable ; (d) topologies paramétrées (« pour tout graphe de n tâches ») : on ne vérifie que des instances bornées ; (e) concurrence et entrelacements ; (f) effets externes (SQL, appels) non modélisables.
- Réseaux de Petri : pertinents pour concurrence et capacité (la famille « Capacité et concurrence » du prototype), mais un format de plus à faire écrire à l'IA ; les règles gardées avec compteur borné couvrent le besoin initial. DMN XML, SCXML et XState JSON sont à traiter comme formats d'import/export, pas comme modèle interne (connaissance de fond, non revérifiée ici : DMN définit aussi les hit policies PRIORITY, FIRST et OUTPUT ORDER ; SCXML est une recommandation W3C de 2015).
- Les LLM sont nettement plus fiables sur des formats structurés courants que sur des langages formels rares : un JSON validé par schéma, avec messages d'erreur précis, est le bon support d'échange avec une IA externe.

### Gaps
- Pas de source trouvée évaluant un schéma JSON unifié « table de décision + statechart + temporel » ; la proposition ci-dessus est une conception, pas un standard.
- Les formalismes de règles temporelles (logiques temporelles, calcul d'événements, automates temporisés) n'ont pas été approfondis.
- La conformité SCXML de python-statemachine 3.x et la liste exacte des hit policies dans la version courante de DMN n'ont pas été vérifiées à la source.

## 3. Contrôles déterministes faisables et utiles ; algorithmes et limites

### Takeaway
Les contrôles à meilleur rapport valeur/coût sont, dans l'ordre : validation structurelle et rejeu des frames, couverture combinatoire sur des dimensions déclarées, complétude et chevauchement des tables de décision, puis atteignabilité, règles mortes et invariants sur un modèle à états borné. L'explosion d'états est la limite dure : elle impose des instances bornées ou une couverture t-way plutôt que l'exhaustivité.

### Cited Findings
- Tables de décision : détection des règles chevauchantes (ensembles maximaux d'hyper-rectangles qui s'intersectent) et des règles manquantes (régions non couvertes) par algorithmes géométriques à balayage ; l'approche évite le découpage préalable des intervalles numériques, qui peut faire croître la table exponentiellement dans le pire cas ; implémenté dans l'éditeur dmn-js et évalué sur de grandes tables de crédit (extrait de recherche pour les détails algorithmiques ; résumé vérifié). — [Calvanese et al., arXiv 1603.07466](https://arxiv.org/abs/1603.07466)
- Contrôles statiques en production sur des fichiers DMN : règles dupliquées, conflictuelles (mêmes entrées, sorties différentes), masquées (jamais atteintes car une règle antérieure couvre tout), chevauchantes en UNIQUE, typage FEEL, structure, graphe d'exigences (connexité, acyclicité), règles fusionnables. Pas de contrôle de complétude dans le README. — [dmn-check](https://github.com/red6/dmn-check)
- GoRules 2.0 annonce une « Workspace analysis » avec typage statique, « exhaustiveness checking » et « write-conflict detection » ; la page ne précise pas s'il s'agit de trous et chevauchements de tables. — [gorules/zen](https://github.com/gorules/zen)
- Règle d'interaction NIST : la plupart des défaillances sont déclenchées par un ou deux facteurs, de moins en moins par trois ou plus ; tester toutes les combinaisons 4-way à 6-way est « effectivement exhaustif » ; la règle ne garantit pas de trouver tous les défauts. — [NIST ACTS, interactions](https://csrc.nist.gov/projects/automated-combinatorial-testing-for-software/combinatorial-methods-in-testing/interactions-involved-in-software-failures)
- Le pairwise ne suffit pas toujours : de nombreuses défaillances n'apparaissent qu'avec plus de deux conditions ; un rappel de dispositif médical a exigé une interaction à 4 facteurs. — [NIST ACTS, FAQ](https://csrc.nist.gov/projects/automated-combinatorial-testing-for-software/faqs)
- Ordre de grandeur donné sur une diapositive NIST pour un système exemple : 29, 137, 625, 2 532 et 9 168 configurations pour t = 2 à 6, soit 0,02 % à 5,3 % de l'exhaustif (extrait de recherche, diapositive non identifiée individuellement). — [NIST ACTS, FAQ et supports associés](https://csrc.nist.gov/projects/automated-combinatorial-testing-for-software/faqs)
- Contrôles structurels sur machines à états utilisés comme critères de validité dans la littérature LLM : états orphelins, états inatteignables, transitions invalides. — [ESEM 2026, LIPIcs](https://drops.dagstuhl.de/storage/00lipics/lipics-vol394-esem2026/LIPIcs.ESEM.2026.19/LIPIcs.ESEM.2026.19.pdf)
- Audit d'exigences par SMT : VeriMed formalise des exigences logicielles en un modèle SMT unique puis lance des requêtes d'audit et d'ambiguïté ; 2 exigences sur 64 signalées redondantes sur une spécification d'hémodialyse (extrait de recherche). — [arXiv 2605.13817](https://arxiv.org/abs/2605.13817)

### Inferences
- Niveau 0, sans modèle formel : schéma JSON ; intégrité référentielle (chaque nœud cité existe, chaque statut appartient au vocabulaire déclaré) ; graphe de prérequis acyclique ; rejeu des deltas en frames (le prototype le fait déjà en JavaScript) ; statut global final terminal ; détection de doublons par empreinte canonique. Coût faible, attrape les incohérences internes, pas les omissions.
- Niveau 1, dimensions déclarées : l'IA déclare les facteurs (par exemple `stop_on_error`, `always_run`, `ignore_on_error`, forme du graphe, issue de chaque tâche) et étiquette chaque cas ; le site calcule la matrice de couverture 1-way, 2-way, 3-way et liste les combinaisons absentes. Mesurer une couverture t-way est un simple dénombrement ; c'est le premier signal d'omission disponible sans modèle exécutable. Limite : la couverture n'est aussi bonne que la liste des facteurs.
- Niveau 2, tables de décision : complétude = satisfiabilité de « domaine ET NON (r1 OU … OU rn) » ; chaque modèle renvoyé par le solveur est une combinaison manquante concrète ; chevauchement = satisfiabilité de « ri ET rj », contradiction si les sorties diffèrent. Problème NP-difficile en général mais instantané à l'échelle métier (dizaines à centaines de règles). MC/DC : au minimum n+1 tests pour n conditions indépendantes (connaissance de fond).
- Niveau 3, modèle à états : exploration explicite en largeur depuis l'état initial ; produits dérivés : états et transitions atteignables, règles jamais déclenchables, états puits non terminaux, violation d'invariant avec trace contre-exemple (qui est elle-même un cas animable), couverture des transitions par les cas existants.
- Explosion d'états, calcul direct : avec 11 statuts par nœud, 4 nœuds donnent au plus 11^4 = 14 641 états (trivial), 10 nœuds au plus 11^10 ≈ 2,6 × 10^10 (hors de portée en exploration explicite Python). Il faut donc borner (petits graphes représentatifs), réduire par symétrie, ou passer au symbolique (Z3, vérification bornée). Travailler sur de petites instances est cohérent avec le prototype, dont les cas ont 1 à 4 nœuds.
- Les contre-exemples et combinaisons manquantes doivent être renvoyés à l'IA sous forme exploitable (« il manque le cas : A en échec, C always_run, stop_on_error vrai »), ce qui ferme la boucle de la section 1.

### Gaps
- Bornes de complexité exactes des algorithmes de Calvanese et al. non relevées (le résumé dit seulement « scalable »).
- Pourcentages cumulés de défaillances par niveau t (figure NIST) non récupérés : la figure est une image.
- Pas de retour d'expérience trouvé sur la vérification de modèles produits par LLM à l'échelle d'un produit grand public.

## 4. Bibliothèques Python : maturité, licence, adéquation (relevé du 21/11/2026)

### Takeaway
Les briques de base sont mûres et sous licences permissives (z3-solver, OR-Tools, networkx, hypothesis, pydantic, jsonschema, deepdiff, python-statemachine, zen-engine). En revanche il n'existe pas de vérificateur de tables de décision prêt à l'emploi en Python, et plusieurs bibliothèques citées sont à l'abandon (python-constraint, pypict, bkflow-dmn) ou sous licence contaminante (pm4py en AGPL, pyDMNrules en GPLv3).

### Cited Findings
- z3-solver : version 5.4.1.0 publiée le 2026-11-11, licence MIT, 58 versions depuis 2016 ; dépôt actif (poussée du 2026-11-21, environ 13 000 étoiles). Adéquation : complétude, chevauchement, invariants, vérification bornée. — [PyPI z3-solver](https://pypi.org/project/z3-solver/) ; [Z3Prover/z3](https://github.com/Z3Prover/z3)
- ortools (CP-SAT) : 9.15.6755 du 2026-01-14, Apache-2.0, Python >= 3.9, dépôt actif. Adéquation : énumération de solutions sur domaines finis, alternative à Z3 pour l'entier borné. — [PyPI ortools](https://pypi.org/project/ortools/)
- cpmpy : 1.1.1 du 2026-10-14, Apache-2.0 ; couche de modélisation au-dessus de plusieurs solveurs. — [PyPI cpmpy](https://pypi.org/project/cpmpy/)
- python-sat : 1.9.dev24 du 2026-11-19, MIT ; pysmt : 0.9.6 du 2024-06-24, Apache (peu actif). — [PyPI python-sat](https://pypi.org/project/python-sat/) ; [PyPI pysmt](https://pypi.org/project/pysmt/)
- python-constraint : 1.4.0 du 2018-11-05, à considérer comme non maintenu ; son successeur python-constraint2 : 2.9.0 du 2026-10-27, BSD-2-Clause, Python >= 3.11. — [PyPI python-constraint](https://pypi.org/project/python-constraint/) ; [PyPI python-constraint2](https://pypi.org/project/python-constraint2/)
- allpairspy : 2.5.1 du 2023-07-08, MIT, dernière poussée 2023-11 : stable mais plus développé, pairwise seulement en pratique. — [PyPI allpairspy](https://pypi.org/project/allpairspy/) ; [GitHub](https://github.com/thombashi/allpairspy)
- pypict (liaison Python de PICT) : 0.3.0 du 2021-12-30, MIT : à l'abandon ; l'outil PICT de Microsoft reste actif (poussée 2026-10-14) mais c'est un binaire à embarquer. — [PyPI pypict](https://pypi.org/project/pypict/) ; [microsoft/pict](https://github.com/microsoft/pict)
- covertable : 3.2.0 du 2026-08-19, Apache ; alternative maintenue pour le pairwise. — [PyPI covertable](https://pypi.org/project/covertable/)
- hypothesis : 6.170.17 du 2026-11-20, MPL-2.0, Python >= 3.11, très actif (1 596 versions). — [PyPI hypothesis](https://pypi.org/project/hypothesis/)
- networkx : 3.7 du 2026-09-21, BSD-3-Clause, Python >= 3.12. Adéquation : acyclicité, atteignabilité, composantes. — [PyPI networkx](https://pypi.org/project/networkx/)
- python-statemachine : 3.2.2 du 2026-10-14, MIT, Python >= 3.10, environ 1 300 étoiles, actif ; statecharts complets. — [PyPI](https://pypi.org/project/python-statemachine/) ; [GitHub](https://github.com/fgmacedo/python-statemachine)
- sismic : 1.6.14 du 2026-10-05, LGPLv3, Python >= 3.10, 172 étoiles, mainteneur unique mais régulier ; le plus orienté « vérification » (contrats, propriétés, BDD). — [PyPI sismic](https://pypi.org/project/sismic/) ; [documentation](https://sismic.readthedocs.io/en/latest/)
- transitions : 0.9.3 du 2025-07-02, MIT, environ 6 600 étoiles, dernière poussée 2025-09 : mûr, rythme ralenti. — [PyPI transitions](https://pypi.org/project/transitions/) ; [GitHub](https://github.com/pytransitions/transitions)
- pm4py : 2.7.23.13 du 2026-11-20, AGPL-3.0-or-later, Python >= 3.11. — [PyPI pm4py](https://pypi.org/project/pm4py/)
- pyDMNrules : 1.4.5 du 2026-08-22, GPLv3 ; lit les règles depuis des classeurs Excel (pas de DMN XML mentionné), FEEL via pySFeel, fonction `test()` intégrée, aucun contrôle de complétude ou de chevauchement décrit. — [PyPI pyDMNrules](https://pypi.org/project/pyDMNrules/)
- bkflow-dmn : 0.2.0 du 2023-11-30, MIT, 3 versions, 10 étoiles, dernière poussée 2024-09 : non maintenu de fait. — [PyPI bkflow-dmn](https://pypi.org/project/bkflow-dmn/) ; [GitHub](https://github.com/TencentBlueKing/bkflow-dmn)
- zen-engine (GoRules, cœur Rust) : 2.1.8 du 2026-11-20, MIT, environ 2 100 étoiles, 75 versions depuis 2023, très actif ; usage `zen.ZenEngine().create_decision(...).evaluate(...)`. — [PyPI zen-engine](https://pypi.org/project/zen-engine/) ; [gorules/zen](https://github.com/gorules/zen)
- SpiffWorkflow : 3.2.0 du 2026-08-10, LGPL-3.0, actif ; moteur de workflow en Python pur. — [PyPI SpiffWorkflow](https://pypi.org/project/SpiffWorkflow/) ; [GitHub](https://github.com/sartography/SpiffWorkflow)
- cdmn : 2.1.2 du 2024-05-26 (peu actif) ; rule-engine : 5.2.0 du 2026-10-28, BSD-3-Clause ; business-rules : 1.1.1 du 2022-03-18 et durable-rules : 2.0.28 du 2020-06-07 (à l'abandon). — [PyPI cdmn](https://pypi.org/project/cdmn/) ; [PyPI rule-engine](https://pypi.org/project/rule-engine/) ; [PyPI business-rules](https://pypi.org/project/business-rules/) ; [PyPI durable-rules](https://pypi.org/project/durable-rules/)
- dmn-check : Apache-2.0, actif (poussée 2026-11-10), mais écrit en Java (plugins Maven et Gradle exigeant Java 25, CLI, image Docker), certaines analyses propres à Camunda. — [red6/dmn-check](https://github.com/red6/dmn-check)
- Outillage de persistance, diff et approbation : pydantic 2.14.4 (MIT), jsonschema 4.26.0 (MIT), deepdiff 9.2.1 (MIT, 2026-11-18), syrupy 7.0.2 (MIT), approvaltests 20.0.1 (Apache-2.0). — [PyPI pydantic](https://pypi.org/project/pydantic/) ; [PyPI jsonschema](https://pypi.org/project/jsonschema/) ; [PyPI deepdiff](https://pypi.org/project/deepdiff/) ; [PyPI syrupy](https://pypi.org/project/syrupy/) ; [PyPI approvaltests](https://pypi.org/project/approvaltests/)

### Inferences
- Socle recommandé, tout en licences permissives : pydantic + jsonschema (structure), networkx (graphes), z3-solver (tables de décision, invariants), un explorateur d'états maison de quelques centaines de lignes (plus simple et mieux maîtrisé qu'une adaptation de sismic ou python-statemachine au modèle neutre), deepdiff (diff de versions).
- Le produit étant distribué pour auto-hébergement, AGPL (pm4py) et GPLv3 (pyDMNrules) sont à écarter du cœur sauf choix assumé d'une licence compatible ; LGPL (sismic, SpiffWorkflow) est utilisable comme dépendance non modifiée. À faire confirmer juridiquement.
- Le générateur pairwise est secondaire : le besoin premier est de mesurer la couverture des cas existants (dénombrement en Python pur), pas de générer des combinaisons.
- zen-engine sert d'exécuteur de tables au format JDM (import/export), pas de vérificateur : la vérification reste à écrire sur Z3.
- hypothesis sert à tester le produit lui-même et, côté IA, à explorer le vrai moteur avec des tests à états (connaissance de fond : `RuleBasedStateMachine`), pas à tourner dans le site.

### Gaps
- La licence de PICT et de hypothesis n'est pas renvoyée par l'API GitHub (« NOASSERTION ») ; PyPI indique MPL-2.0 pour hypothesis.
- La numérotation 5.x de z3-solver est celle renvoyée par PyPI ce jour ; les notes de version n'ont pas été lues (ruptures d'API éventuelles à vérifier).
- Dépôt GitHub de pyDMNrules non trouvé à l'adresse supposée ; activité du dépôt non vérifiée (PyPI seulement). Outils d'automates temporisés et de model checking en Python non évalués.

## 5. Option hybride : qui écrit le modèle formel ? Que font les systèmes comparables ?

### Takeaway
Les systèmes comparables font écrire le modèle formel par le LLM, mais dans un cadre contraint, avec vérification mécanique et relecture humaine du modèle. L'IA externe peut donc soumettre modèle et cas ; le site simule le modèle, régénère les frames et les compare aux cas. Ce recoupement détecte les incohérences entre modèle et cas, pas une erreur commune aux deux : il faut un ancrage externe (humain sur le modèle, ou exécution du vrai code).

### Cited Findings
- AWS Automated Reasoning checks : le service analyse un document de règles et construit une politique initiale (variables et règles en logique formelle) que l'utilisateur relit et modifie ; la vérification repose sur SAT/SMT ; les résultats indiquent quelle règle a conduit au constat et proposent des corrections. — [AWS News Blog](https://aws.amazon.com/blogs/aws/prevent-factual-errors-from-llm-hallucinations-with-mathematically-sound-automated-reasoning-checks-preview)
- Quint (Informal Systems, novembre 2025) : spécification exécutable placée entre langage naturel et code ; le test fondé sur le modèle rejoue les mêmes scénarios sur la spécification et sur l'implémentation ; dans l'étude de cas, l'IA modifie la spécification en traductrice de l'intention humaine et l'humain valide. Source : blog du projet, sans évaluation indépendante. — [quint-lang.org](https://quint-lang.org/posts/llm_era)
- Synthèse de modèles encadrée : un cadre fixe généré mécaniquement, le LLM remplit des trous du modèle, le modèle est testé et les erreurs renvoyées pour réparation ; les auteurs disent contenir l'hallucination par ce « cadre dur » (extrait de recherche). — [arXiv 2501.12972](https://arxiv.org/abs/2501.12972)
- Auto-formalisation vers SMT : gain de 34,8 % sur des tâches logiques mais perte de 44,5 % sur des tâches factuelles, sur cinq LLM de pointe (extrait de recherche). — [arXiv 2505.20047](https://arxiv.org/abs/2505.20047)
- VERGE : imposer la vérification formelle à chaque affirmation est inadapté au langage vague ; le système utilise les noyaux insatisfiables du solveur pour guider le LLM et route le reste vers un consensus de LLM (extrait de recherche). — [arXiv 2601.20055](https://arxiv.org/abs/2601.20055)
- Petites erreurs de formalisation : une spécification peut compiler tout en manquant le comportement voulu (extrait de recherche). — [arXiv 2606.05792](https://arxiv.org/html/2606.05792v1)
- Réparation guidée par contrôles déterministes : validité structurelle de 22,2 % à 88,9 % en deux itérations en général (extrait de recherche). — [ESEM 2026, LIPIcs](https://drops.dagstuhl.de/storage/00lipics/lipics-vol394-esem2026/LIPIcs.ESEM.2026.19/LIPIcs.ESEM.2026.19.pdf)

### Inferences
- Schéma proposé pour B : (1) l'IA soumet le modèle (JSON neutre) ; (2) le site le valide et l'analyse (complétude, règles mortes, invariants) ; (3) l'IA soumet les cas, soit comme frames complètes, soit comme « configuration + séquence d'événements » ; (4) le site simule le modèle sur chaque cas, régénère les frames et affiche le diff ; (5) le site calcule ce que les cas ne couvrent pas et le renvoie par l'API.
- Variante forte : le cas ne stocke que configuration et événements, les frames sont dérivées du modèle. Avantage : cohérence garantie, recalcul automatique quand le modèle change. Inconvénient : tout dépend de la justesse du modèle, et les notes pédagogiques par étape restent à rédiger par l'IA.
- Risque d'erreur de mode commun : si la même IA écrit modèle et cas à partir de la même lecture erronée du code, le recoupement passe. Trois ancrages possibles : relecture humaine du modèle (surface bien plus petite que 70 cas : quelques dizaines de règles) ; traces réelles issues des tests de non-régression ; seconde IA indépendante.
- Le modèle formel donne au relecteur humain un second objet de validation, plus compact : valider « la règle 7 » vaut pour tous les cas qui en découlent.
- L'auto-formalisation dégrade le contenu non logique : ne pas forcer tout dans le modèle. Les aspects vagues ou externes (effets SQL, messages, délais réels) restent en texte dans les notes des cas, hors périmètre de vérification, et doivent être affichés comme tels.
- Le modèle doit rester optionnel par famille de règles : certaines familles n'en auront jamais (observation réelle, cas de configuration refusée).

### Gaps
- Le taux de vérification « jusqu'à 99 % » parfois attribué à AWS n'a pas pu être confirmé par les sources consultées.
- Aucune mesure trouvée de la fréquence réelle des erreurs de mode commun (même LLM auteur du modèle et des cas).
- Pas d'évaluation indépendante de Quint avec LLM ; pas de résultat trouvé sur la qualité des modèles écrits par LLM dans un DSL JSON simple (par opposition à TLA+ ou Alloy).

## 6. Évolution des cas dans le temps : identité, versions, verdicts, tests

### Takeaway
Il faut dissocier identité stable du cas, numéro d'affichage et empreinte de contenu : un verdict humain s'attache à une empreinte, et devient « à revoir » dès que la partie sémantique du cas change. Le prototype contient déjà, à la main, les embryons de ce mécanisme (version de catalogue, versions de revue compatibles, identifiants retirés, liens vers des tests).

### Cited Findings
- Observation du prototype (lecture directe, pas d'URL) : le catalogue porte une `version` (« 2026-11-19.1 »), une liste `compatibleReviewVersions` de onze versions antérieures dont les revues restent valables, une liste `retiredScenarioIds` (quatre cas retirés), un `id` textuel stable distinct du `displayNumber`, une table reliant chaque cas à des tests de non-régression typés (« banc ciblé » ou « Workflow réel »), et des références de source (fichier, fonction, numéro de ligne). — prototype local `catalogue-runs-data.js`
- Tests d'approbation : la sortie est capturée, relue, approuvée, puis les exécutions suivantes sont comparées à l'instantané approuvé ; un fichier approuvé modifié doit être relu comme un changement de comportement du produit ; un échec affiche le diff et l'acceptation écrit le nouveau fichier approuvé (sources de type tutoriel, qualité moyenne). — [qaskills.sh](https://qaskills.sh/blog/approval-testing-golden-master-guide) ; [dev.to](https://dev.to/slava_ganzin_fdda591d6569/approval-testing-explained-what-it-is-and-how-it-works-c6g)
- Outils de revue d'instantanés : approbation ou rejet par instantané, branches en approbation automatique, déploiement conditionné à l'approbation ; comparaison appuyée sur les métadonnées git, « comme une revue de code ». — [Buddy](https://buddy.works/docs/tests/visual-tests/reviewing-approvals.md) ; [Sentry](https://docs.sentry.io/product/snapshots/reviewing-snapshots/)
- Bibliothèques Python correspondantes, maintenues : approvaltests 20.0.1, syrupy 7.0.2, deepdiff 9.2.1. — [PyPI approvaltests](https://pypi.org/project/approvaltests/) ; [PyPI syrupy](https://pypi.org/project/syrupy/) ; [PyPI deepdiff](https://pypi.org/project/deepdiff/)

### Inferences
- `compatibleReviewVersions` est un contournement manuel et global : une empreinte par cas le remplace avantageusement. Empreinte sémantique = hachage de la forme canonique de (nœuds et options, arêtes, configuration, suite des changements de statut, décisions). Titre, résumé, notes et mise en page n'y entrent pas : les corriger ne doit pas invalider un verdict.
- Modèle de données suggéré : `Study` → `StudyVersion` (immuable, créée à chaque soumission de l'IA) → `CaseRevision` (id stable, empreinte, contenu) ; `Verdict` (validé, refusé, à analyser, commentaire, auteur, date) pointant sur (id du cas, empreinte). À l'affichage : verdict « en vigueur » si l'empreinte courante est identique, « périmé, à revoir » sinon, avec diff entre révision validée et révision courante.
- Les numéros de ligne dans les références de source sont fragiles : préférer fichier + symbole + SHA de commit, la ligne étant indicative.
- Identité stable : identifiant choisi par l'IA (slug) et conservé d'une soumission à l'autre ; le site doit signaler les quasi-doublons (même empreinte sous deux identifiants) et les renommages probables, car un LLM ne garantit pas la stabilité des identifiants entre exécutions (section 1).
- Cas retirés : statut explicite avec motif et version de retrait, jamais de suppression, pour conserver l'historique des verdicts.
- Tests comme source de vérité : stocker pour chaque lien l'identifiant du test, le dernier résultat et le commit ; la CI pousse les résultats par l'API. Un cas lié à un test vert sur le commit courant a un niveau de preuve supérieur à un cas seulement affirmé par l'IA ; un test devenu rouge doit marquer le cas « à analyser ». Étape ultérieure : le test exporte la trace réellement observée et le site la compare aux frames.
- Avec un modèle formel (option B), un changement de règle permet de calculer quels cas sont affectés (ceux dont la simulation change) et de n'invalider que ces verdicts.
- Analogie utile (connaissance de fond, page de documentation non récupérée) : l'option « dismiss stale approvals » des branches protégées GitHub, qui annule les approbations quand de nouveaux commits arrivent.

### Gaps
- Pas de retour d'expérience d'ingénierie trouvé sur des catalogues de scénarios versionnés avec verdicts humains ; les sources sur les tests d'approbation sont des tutoriels.
- La documentation GitHub sur l'annulation des approbations périmées n'a pas pu être chargée (erreur 404).

## 7. Recommandation pragmatique et feuille de route par étapes

### Takeaway
Ne pas choisir A pur ni B complet d'emblée : démarrer par « A renforcé » (l'IA écrit, le site valide la structure, rejoue les frames et mesure la couverture sur des dimensions déclarées), en concevant dès le départ le schéma pour accueillir un modèle formel optionnel par famille de règles, puis ajouter les tables de décision vérifiées par Z3, puis le modèle à états simulé, puis l'ancrage sur les traces réelles.

### Cited Findings
- Les LLM seuls laissent des trous systématiques (limites, erreurs, combinaisons) et produisent des oracles faux. — [arXiv 2610.32548](https://arxiv.org/abs/2610.32548)
- Les pipelines qui réussissent sur des règles métier confient l'extraction au LLM et le reste à des algorithmes. — [LLM4Fin, ISSTA 2024](https://2024.issta.org/details/issta-2024-papers/131/LLM4Fin-Fully-Automating-LLM-Powered-Test-Case-Generation-for-FinTech-Software-Accep)
- Les boucles de retour déterministes apportent une grande part du gain (près de la moitié des réussites de CoverUp ; 22,2 % à 88,9 % de validité structurelle après réparation). — [arXiv 2403.16218](https://arxiv.org/abs/2403.16218) ; [ESEM 2026, LIPIcs](https://drops.dagstuhl.de/storage/00lipics/lipics-vol394-esem2026/LIPIcs.ESEM.2026.19/LIPIcs.ESEM.2026.19.pdf)
- Les LLM sont peu fiables sur les langages formels de niche (TLA+ : 8,6 % de correction sémantique au mieux) et sur gardes et actions (F1 de 0,23 et 0,00). — [arXiv 2606.05792](https://arxiv.org/abs/2606.05792) ; [arXiv 2604.00275](https://arxiv.org/abs/2604.00275)
- La couverture t-way donne une mesure d'exhaustivité graduée avec très peu de cas par rapport à l'exhaustif. — [NIST ACTS](https://csrc.nist.gov/projects/automated-combinatorial-testing-for-software/combinatorial-methods-in-testing/interactions-involved-in-software-failures)
- Aucun vérificateur de tables de décision n'existe prêt à l'emploi en Python ; l'outil de référence est en Java. — [red6/dmn-check](https://github.com/red6/dmn-check)

### Inferences
Comparaison des options (estimations de l'auteur des notes, à valider) :

| Critère | A pur | A renforcé (étapes 0-1) | B complet (étapes 2-3) |
|---|---|---|---|
| Détection d'omissions | aucune | partielle, sur dimensions déclarées | forte, dans les limites du modèle borné |
| Détection de cas faux | humain seul | incohérences internes | écart modèle/cas, puis écart au vrai moteur |
| Charge pour l'IA externe | faible | modérée (étiqueter, déclarer les facteurs) | élevée (écrire et corriger un modèle) |
| Effort de développement du site | faible | faible à modéré (quelques semaines) | élevé (langage d'expression, traduction Z3, simulateur : plusieurs mois) |
| Généricité multi-domaines | totale | totale | partielle (section 2) |
| Risque principal | fausse impression d'exhaustivité | dimensions mal choisies | modèle faux mais cohérent ; complexité perçue |

Feuille de route proposée :
- Étape 0, « A renforcé », socle : schéma strict (pydantic, JSON Schema publié pour l'IA), intégrité référentielle, graphe acyclique, rejeu des deltas côté serveur, empreintes et versions (section 6), erreurs de validation renvoyées par l'API/MCP dans un format que l'IA peut corriger. Aucune dépendance lourde.
- Étape 1, dimensions et invariants déclarés : l'IA déclare facteurs, valeurs, contraintes d'exclusion et invariants simples ; le site affiche matrice de couverture 2-way et 3-way, combinaisons absentes, frames violant un invariant ; point d'API « que manque-t-il ? » pour fermer la boucle. Premier vrai signal d'exhaustivité, pour un coût modeste et sans modèle exécutable.
- Étape 2, tables de décision vérifiées (famille « règles de décision ») : format de table en JSON, hit policy explicite, contrôles Z3 de complétude, chevauchement, contradiction et règle masquée ; génération automatique des cas manquants proposés à l'IA ou à l'humain. Domaine le plus facile et le mieux outillé théoriquement.
- Étape 3, modèle à états simulé (familles « workflow » et « états ») : règles gardées, explorateur borné, régénération des frames, diff avec les cas de l'IA, couverture des transitions, règles mortes, contre-exemples d'invariants convertis en cas animables.
- Étape 4, ancrage sur le réel : import par l'API des résultats et traces des tests de non-régression ; statut « observé » distinct de « affirmé » et de « dérivé du modèle ».
- Le temporel (échéances, calendriers) vient en dernier, par discrétisation, une fois les étapes 2 et 3 stabilisées.

Arbitrages à expliciter au décideur :
- Afficher partout le niveau de preuve d'un cas : affirmé par l'IA, cohérent structurellement, dérivé ou confirmé par le modèle, observé sur le vrai moteur, validé par un humain. C'est ce qui évite la fausse assurance de l'option A.
- Décision de conception à prendre dès l'étape 0 même si B est différé : un cas doit distinguer configuration, événements et états résultants, et porter des dimensions typées ; sinon la migration vers B imposera de réécrire les cas.
- Le modèle formel doit rester optionnel et par famille ; un produit qui l'exige partout perd les domaines où la généricité casse.
- B déplace une partie du travail de relecture humaine des cas vers le modèle : gain net seulement si le modèle est lisible par un métier (tables et règles gardées affichées en clair, pas du code).

### Gaps
- Les estimations d'effort ci-dessus sont des ordres de grandeur de l'auteur des notes, sans source externe.
- Pas de donnée sur l'acceptation par des utilisateurs métier d'un modèle formel à relire, ni sur le coût en jetons et en temps pour une IA externe d'écrire et réparer un modèle par rapport à des cas seuls.
- Pas de comparaison trouvée avec des produits concurrents proposant exactement ce flux (IA externe par MCP + vérification déterministe côté site).
