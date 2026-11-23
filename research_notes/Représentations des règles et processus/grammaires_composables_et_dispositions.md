# Grammaires composables et algorithmes de disposition pour diagrammes déclaratifs

Notes de recherche — état constaté le 21 novembre 2026. Les versions et licences marquées « registre » ont été relevées directement ce jour-là dans les registres npm / PyPI et l'API GitHub (champ `license`, fichiers `LICENSE`), pas dans des articles de seconde main. Les affirmations issues d'un simple extrait de moteur de recherche (texte intégral non lu) sont signalées « (extrait de recherche, non vérifié en texte intégral) ».

## 1. Comment les langages déclaratifs de diagrammes et de graphiques structurent-ils leurs primitives, quelles familles couvrent-ils et où s'arrêtent-ils ?

### Takeaway
Deux lignées distinctes coexistent : les grammaires de graphiques (Grammar of Graphics, Vega-Lite) composent « données → transformations → marques → canaux d'encodage → échelles », puis combinent des vues par un petit nombre d'opérateurs (layer, concat, facet, repeat) ; les langages de diagrammes (DOT, D2, Mermaid, PlantUML, Structurizr) composent « nœuds + arêtes + conteneurs » et délèguent tout le placement à un moteur de disposition. Aucun système ne couvre les deux lignées avec un seul vocabulaire : Mermaid et PlantUML juxtaposent des dizaines de mini-syntaxes par type, tandis que D2 est le plus proche d'un petit noyau réutilisé (objets, connexions, conteneurs + deux dispositions spéciales « grille » et « séquence » + trois mots-clés de composition).

### Cited Findings

**Grammar of Graphics et grammaire en couches**
- Wickham (2010) présente la grammaire comme un outil permettant de décrire de façon concise les composants d'un graphique et de « dépasser les graphiques nommés (par ex. le "scatterplot") » pour atteindre la structure sous-jacente ; l'article s'appuie sur Wilkinson (2006) et s'en distingue par une hiérarchie de valeurs par défaut et par l'intégration dans un langage de programmation — [Wickham, A layered grammar of graphics, JCGS 19(1), 2010](https://vita.had.co.nz/papers/layered-grammar.html)
- Dans cette grammaire en couches, un graphique est défini par : un jeu de données et des correspondances esthétiques par défaut, une ou plusieurs couches (chacune avec un objet géométrique, une transformation statistique, un ajustement de position, et facultativement son propre jeu de données et ses correspondances), une échelle par correspondance esthétique, un système de coordonnées et une spécification de facettes (extrait de recherche citant l'article, non vérifié en texte intégral) — [ggplot2-book, chapitre « mastery »](https://ggplot2-book.org/mastery)

**Vega-Lite (v6.5.0, BSD-3-Clause)**
- Vega-Lite combine une grammaire de graphiques (règles d'encodage visuel + une algèbre de composition pour vues en couches et multi-vues) avec une grammaire d'interaction ; les sélections définissent le traitement des événements d'entrée, les points d'intérêt et un prédicat d'inclusion, et peuvent paramétrer les encodages (comme données d'entrée, comme étendue d'échelle, ou pour piloter une logique conditionnelle) ; le compilateur produit automatiquement le flux de données et la gestion d'événements. Référence : Satyanarayan, Moritz, Wongsuphasawat, Heer, « Vega-Lite: A Grammar of Interactive Graphics », IEEE TVCG (InfoVis), 2017, DOI 10.1109/TVCG.2016.2599030 — [page de l'article, UW IDL](https://idl.uw.edu/papers/vega-lite)
- Quatre opérateurs de composition : « facet, layer, concatenate, and repeat » ; une vue composée peut elle-même être composée avec d'autres (« hierarchical composition »), ce qui permet de décrire un tableau de bord entier en une seule spécification ; le compilateur infère la réutilisation des données et si les domaines d'échelle doivent être unis ou indépendants — [Vega-Lite docs, Composition](https://vega.github.io/vega-lite/docs/composition.html)
- La résolution (`resolve`) se déclare par canal pour les échelles, axes et légendes, avec deux valeurs seulement : `"shared"` et `"independent"` — [Vega-Lite docs, Resolve](https://vega.github.io/vega-lite/docs/resolve.html)
- Les paramètres (`params`) sont « the basic building block in Vega-Lite's grammar of interaction » : soit de simples variables, soit des sélections qui convertissent une entrée utilisateur en requête sur les données — [Vega-Lite docs, Parameter](https://vega.github.io/vega-lite/docs/parameter.html)
- Inventaire relevé dans le schéma JSON officiel v6 : 7 formes de spécification de premier niveau (Unit, Facet, Layer, Repeat, Concat, VConcat, HConcat) ; 14 marques primitives (`arc, area, bar, image, line, point, rect, rule, text, tick, trail, circle, square, geoshape`) ; 38 canaux d'encodage (dont `x, y, x2, y2, xOffset, yOffset, color, fill, stroke, opacity, size, shape, angle, text, tooltip, href, detail, key, order, theta, radius, time`) ; le schéma pèse 1 879 222 octets et contient 458 définitions (mesure directe du fichier) — [schéma Vega-Lite v6](https://vega.github.io/schema/vega-lite/v6.json)
- Les transformations documentées sont : Aggregate, Bin, Calculate, Density, Extent, Filter, Flatten, Fold, Impute, Join Aggregate, Loess, Lookup, Pivot, Quantile, Regression, Sample, Stack, Time Unit, Window ; les marques composites documentées incluent Box Plot, Error Band, Error Bar — [Vega-Lite docs, Composition (menu de navigation)](https://vega.github.io/vega-lite/docs/composition.html)

**Graphviz DOT (EPL-2.0)**
- Dix « moteurs » sélectionnables sur la même description : `dot` (« hierarchical or layered drawings of directed graphs »), `neato` (« spring model »), `fdp` (Force-Directed Placement), `sfdp` (Scalable Force-Directed Placement), `circo` (circulaire), `twopi` (radial), `osage` (graphes à grappes), `patchwork` (carte arborescente « squarified treemap »), `nop`/`nop2` (ré-impression) — [Graphviz, Layout Engines](https://graphviz.org/docs/layouts/)

**Mermaid (v12.3.0, MIT)**
- 32 types de diagrammes listés dans la documentation : Flowchart, Swimlanes (bêta), Sequence, Class, State, Entity Relationship, User Journey, Gantt, Pie, Quadrant, Requirement, Use Case (bêta), GitGraph, C4, Mindmaps, Timeline, ZenUML, Sankey, XY Chart, Block, Packet, Kanban, Architecture (bêta), Radar (bêta), Event Modeling, Treemap, Venn (bêta), Ishikawa, Wardley (bêta), Cynefin (bêta), TreeView (bêta), Agentflow — [Mermaid, Syntax reference](https://mermaid.js.org/intro/syntax-reference.html)
- La configuration par « frontmatter » YAML est fragile : les clés mal orthographiées sont ignorées silencieusement, mais des paramètres mal formés cassent le diagramme — [Mermaid, Syntax reference](https://mermaid.js.org/intro/syntax-reference.html)
- Le choix du moteur de disposition ne s'applique qu'à sept types (flowchart, state, class, entity relationship, requirement, use case, agentflow) ; les autres types ont leur propre rendu — [Mermaid, Layouts](https://mermaid.js.org/config/layouts.html)
- Sécurité : `securityLevel` vaut `strict` par défaut (balises HTML encodées, clics désactivés) ; autres valeurs `antiscript`, `loose`, `sandbox` (rendu dans une iframe isolée) — [Mermaid, Usage](https://mermaid.js.org/config/usage.html)
- Les exports PNG de Mermaid passent par un navigateur sans interface (Chromium), contrairement à D2 qui rend directement — [D2, Exports](https://d2lang.com/tour/exports/)

**D2 (v0.9.0 du 7 septembre 2026, MPL-2.0)**
- Le dépôt regroupe six modules de disposition : `d2dagrelayout`, `d2elklayout`, `d2talalayout`, `d2grid`, `d2sequence`, `d2near` — c'est-à-dire trois moteurs de graphe généraux plus des dispositions dédiées pour grilles, séquences et ancrages relatifs — [dépôt D2, dossier d2layouts](https://github.com/terrastruct/d2/tree/master/d2layouts)
- Diagramme de séquence = une simple propriété (`shape: sequence_diagram`) posée sur un conteneur : « Unlike other tools, there is no special syntax to learn » ; deux différences seulement avec le reste du langage : la portée (tous les enfants partagent la même portée) et l'ordre (« in sequence diagrams, order matters. The order in which you define everything is the order they will appear ») — [D2, Sequence Diagrams](https://d2lang.com/tour/sequence-diagrams/)
- Grille : « Two keywords do all the magic: grid-rows, grid-columns » ; les cellules s'étendent pour remplir l'espace lorsqu'une seule dimension est fixée — [D2, Grid Diagrams](https://d2lang.com/tour/grid-diagrams/)
- Composition en « planches » (boards) par trois mots-clés : `layers` (n'hérite de rien, nouvelle base), `scenarios` (hérite de la couche de base), `steps` (hérite de l'étape précédente) — [D2, Composition](https://d2lang.com/tour/composition/)

**PlantUML (v1.2026.10)**
- Sept variantes de licence distribuées pour la même version : GPL v3, GPL v2, LGPL, Apache 2.0 (ASL), BSD, EPL 2.0, MIT ; les variantes non-GPL perdent Ditaa (absent des versions ASL/BSD/EPL/MIT), Jcckit et Sudoku, mais « can still generate all UML diagrams » ; l'intégration ELK n'est présente que dans la variante EPL — [PlantUML, Download](https://plantuml.com/download)

**Structurizr DSL (v2026.10.26, Apache-2.0)**
- Séparation stricte modèle / vues : un `workspace` contient un `model` (person, softwareSystem, container, component, group, nœuds de déploiement, `element` personnalisé, relations `->`) et des `views` (systemLandscape, systemContext, container, component, filtered, dynamic, deployment, custom, image) ; les styles sont indexés par étiquette (« tag ») — [Structurizr DSL, Language reference](https://docs.structurizr.com/dsl/language)
- Disposition automatique paramétrée par trois valeurs seulement : `autoLayout [tb|bt|lr|rl] [rankSeparation] [nodeSeparation]` (300 px par défaut) — [Structurizr DSL, Language reference](https://docs.structurizr.com/dsl/language)
- Le DSL peut exécuter du code : `!script` exécute des scripts « in a number of JVM compatible languages » (groovy, kotlin, ruby, javascript) et `!plugin` exécute des greffons Java ; la page consultée ne décrit pas de mode restreint — [Structurizr DSL, Language reference](https://docs.structurizr.com/dsl/language)

**Kroki (v0.36.0 du 9 novembre 2026, MIT)**
- Kroki n'est pas une grammaire mais une passerelle HTTP unifiée vers une trentaine d'outils : BlockDiag, BPMN, Bytefield, SeqDiag, ActDiag, NwDiag, PacketDiag, RackDiag, C4 (PlantUML), D2, DBML, Ditaa, Erd, Excalidraw, GoAT, GraphViz, Lini, Mermaid, Nomnoml, Pikchr, PlantUML, Structurizr, Svgbob, Symbolator, TikZ, UMlet, Vega, Vega-Lite, WaveDrom, WireViz — [Kroki](https://kroki.io/)

**Penrose (@penrose/core 3.3.1, MIT)**
- Trois programmes séparés : Domain (« the types of objects, predicates, and functions that comprise diagrams in this domain »), Substance (« defines the objects and relationships in the diagram ») et Style (« tells Penrose how to display the objects and relationships ») ; la plupart des utilisateurs n'écrivent que le programme Substance — [Penrose, documentation de référence](https://penrose.cs.cmu.edu/docs/ref)
- La disposition est obtenue en « converting the three programs into an optimization problem that it solves using symbolic differentiation » ; formes disponibles : Circle, Ellipse, Equation, Group, Image, Line, Path, Polygon, Polyline, Rectangle, Text — [Penrose, documentation de référence](https://penrose.cs.cmu.edu/docs/ref)

### Inferences
- Trois « noyaux » réutilisables se dégagent des systèmes étudiés, et un vocabulaire compact devrait les réunir : (a) un noyau **graphe** (nœuds, arêtes, conteneurs, ports/étiquettes d'arête) rendu par un moteur de disposition ; (b) un noyau **échelle + marque** à la Vega-Lite (un champ lié à une position par une échelle, marques `rect / rule / tick / text / point / bar`) qui suffit pour frises chronologiques, droites numériques, barres de décomposition de calcul ; (c) un noyau **grille** (lignes/colonnes, cellules) pour tableaux et matrices. D2 démontre qu'un même langage peut porter (a) et (c) plus la séquence avec seulement deux exceptions de sémantique.
- L'approche « un mini-langage par type » de Mermaid (32 types) et PlantUML maximise la couverture mais pas la composabilité : chaque type a sa syntaxe, son moteur et ses défauts propres, ce qui est exactement ce qu'un vocabulaire contraint cherche à éviter.
- La séparation modèle / vues de Structurizr et la séparation Substance / Style de Penrose sont deux formulations de la même idée utile pour un document JSON écrit par une IA : l'IA déclare *ce qui existe* (objets, relations, valeurs) et un nombre très réduit de paramètres de présentation ; le serveur possède entièrement le style et la disposition.
- Les opérateurs de composition de Vega-Lite (layer = superposer, concat = juxtaposer, facet = répéter par sous-ensemble de données, repeat = répéter par champ) et sa règle de résolution à deux valeurs (`shared` / `independent`) constituent un modèle directement transposable pour composer plusieurs représentations d'une même règle (par ex. un diagramme de processus à côté d'un tableau).
- Limites constatées par lignée : Vega-Lite n'a aucune primitive nœud-lien ni disposition de graphe dans sa liste de marques et de transformations (voir inventaire ci-dessus) ; à l'inverse DOT, Mermaid flowchart et Structurizr n'ont pas d'échelles quantitatives. Penrose est le plus général (optimisation sous contraintes) mais sa disposition par optimisation numérique est la moins prévisible pour des diagrammes de processus classiques.
- Plusieurs systèmes ne respectent pas la contrainte « aucune exécution de code fourni » tels quels : Structurizr DSL (`!script`, `!plugin`), Mermaid en mode `loose` (HTML et clics), et tout langage à expressions. Un vocabulaire JSON fermé (énumérations, pas d'expressions libres) évite le problème par construction.

### Gaps
- Le texte intégral de Wilkinson, *The Grammar of Graphics* (2e éd., 2005) n'a pas été consulté ; la liste exacte de ses composants (données, transformations, échelles, coordonnées, éléments, guides) n'est donc pas sourcée ici autrement que via Wickham (2010).
- Le PDF de l'article Vega-Lite n'a pas été lu en entier ; les détails de l'algèbre (règles de fusion d'échelles par opérateur) viennent de la documentation, pas de l'article.
- Le langage d'expressions de Vega / Vega-Lite (`calculate`, `expr`) et l'existence d'un interpréteur « sûr » sans `eval` n'ont pas été vérifiés ; à confirmer si Vega-Lite devait être embarqué tel quel.
- Les transformations de disposition de Vega (bas niveau : force, tree, treemap…) n'ont pas été vérifiées dans la documentation Vega.
- Pour PlantUML, l'API GitHub détecte « LGPL-3.0 » sur le dépôt alors que la page de téléchargement présente la GPL v3 comme variante principale : la licence du dépôt source par rapport aux archives distribuées reste à clarifier — [dépôt PlantUML](https://github.com/plantuml/plantuml) ; [PlantUML, Download](https://plantuml.com/download)
- Limites documentées de Penrose (performance, taille maximale) : la page de référence n'en dit rien.

## 2. Quels algorithmes de disposition pour quelle famille de diagrammes, et quelles implémentations de référence ?

### Takeaway
La disposition en couches (méthode de Sugiyama) couvre à elle seule organigrammes de processus, arbres de décision, machines à états (avec cycles et boucles sur soi) et couloirs ; ELK Layered est l'implémentation la plus complète (ports, arêtes orthogonales, auto-boucles, partitions), dagre la plus simple. Les diagrammes de séquence, grilles/tableaux et axes temporels ne relèvent pas du tracé de graphes : les outils les traitent par des dispositions dédiées, déterministes et bien plus simples.

### Cited Findings

**Disposition en couches (Sugiyama) — DAG, organigrammes, machines à états**
- ELK Layered : « Layer-based algorithm provided by the Eclipse Layout Kernel. Arranges as many edges as possible into one direction by placing nodes into subsequent layers » ; trois styles de routage (« straight, orthogonal, splines ») ; « if orthogonal routing is selected, arbitrary port constraints are respected » ; la méthode remonte à Sugiyama, Tagawa et Toda (1981) — [ELK Layered, référence](https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html)
- Caractéristiques de graphe prises en charge par ELK Layered : auto-boucles (« Self Loops »), auto-boucles internes, arêtes multiples, étiquettes d'arête, ports, graphes composés (hiérarchie), grappes — [ELK Layered, référence](https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html)
- Valeurs par défaut d'ELK Layered révélant les étapes de l'algorithme : rupture de cycles `GREEDY`, mise en couches `NETWORK_SIMPLEX`, minimisation des croisements `LAYER_SWEEP`, placement des nœuds `BRANDES_KOEPF`, routage des arêtes `ORTHOGONAL` ; options de contrainte : `layerConstraint`, `considerModelOrder` (respect de l'ordre d'écriture), modes interactifs — [ELK Layered, référence](https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html)
- ELK est décrit par ses auteurs comme « a collection of graph drawing algorithms that supports compound graph layout and ports as explicit anchor points of edges », avec ELK Layered comme algorithme phare ; ELK et sa version transpilée en JavaScript elkjs sont intégrés à de nombreux projets académiques et commerciaux — [Domrös et al., The Eclipse Layout Kernel, arXiv 2311.00533](https://arxiv.org/abs/2311.00533)
- dagre suit le squelette de Gansner et al., « A Technique for Drawing Directed Graphs » (simplexe de réseau pour le rang), Jünger & Mutzel pour la minimisation des croisements, Barth et al. pour le comptage des croisements, Brandes & Köpf pour l'affectation des coordonnées, Sander (« Layout of Compound Directed Graphs ») pour les grappes ; options principales : `rankdir` (TB, BT, LR, RL), `acyclicer` (`greedy` = heuristique d'ensemble d'arcs de retour), `ranker` (`network-simplex`, `tight-tree`, `longest-path`) — [wiki dagre](https://github.com/dagrejs/dagre/wiki)
- Graphviz `dot` produit des « hierarchical or layered drawings of directed graphs » — [Graphviz, Layout Engines](https://graphviz.org/docs/layouts/)
- Mermaid a changé de moteur par défaut : ELK remplace dagre depuis la v12.0.0 pour les diagrammes à graphe ; dagre reste sélectionnable (`layout: dagre`) ; la version « tiny » omet ELK et retombe sur dagre — [Mermaid, Layouts](https://mermaid.js.org/config/layouts.html)

**Couloirs / dispositions partitionnées**
- ELK Layered offre un partitionnement natif : `partitioning.activate` (désactivé par défaut) et `partitioning.partition` (affecte un nœud à une partition) — [ELK Layered, référence](https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html)
- Mermaid propose un type « Swimlanes » distinct, en bêta, depuis la v11.16.0 — [Mermaid, Swimlanes](https://mermaid.js.org/syntax/swimlanes.html)

**Routage orthogonal**
- TALA (moteur de D2, ouvert sous MPL-2.0 le 7 septembre 2026 et intégré à D2 v0.9.0) est « primarily an orthogonal layout engine » destiné aux diagrammes d'architecture ; il évalue les dispositions selon plusieurs critères esthétiques (symétrie, distance médiane, flux, regroupement), essaie 3 graines aléatoires par défaut et garde la meilleure ; faiblesses reconnues par l'auteur : moins bon que dagre/ELK sur les longs graphes orientés, instable (ajouter un nœud peut changer tout le diagramme), temps de calcul non linéaire sur de grands diagrammes — [D2 blog, « TALA is open source »](https://d2lang.com/blog/tala-is-open-source/)
- ELK liste un algorithme `org.eclipse.elk.alg.libavoid` (routage d'arêtes évitant les obstacles) parmi ses 21 algorithmes — [ELK, liste des algorithmes](https://eclipse.dev/elk/reference/algorithms.html) ; la bibliothèque libavoid-js correspondante est sous LGPL-2.1-or-later — [npm libavoid-js](https://www.npmjs.com/package/libavoid-js)

**Arbres (arbres de décision, hiérarchies)**
- `d3.tree` « produces tidy node-link diagrams of trees using the Reingold–Tilford "tidy" algorithm, improved to run in linear time by Buchheim et al. » — [d3-hierarchy, Tree](https://d3js.org/d3-hierarchy/tree)
- ELK fournit `org.eclipse.elk.mrtree` (ELK Mr. Tree) et `org.eclipse.elk.radial` ; Mermaid propose un moteur `tidy-tree` via le paquet séparé `@mermaid-js/layout-tidy-tree` — [ELK, liste des algorithmes](https://eclipse.dev/elk/reference/algorithms.html) ; [Mermaid, Layouts](https://mermaid.js.org/config/layouts.html)
- python-igraph expose `layout_reingold_tilford`, `layout_reingold_tilford_circular` et `layout_sugiyama` — [python-igraph, API Graph](https://python.igraph.org/en/stable/api/igraph.Graph.html)

**Dirigé par les forces / contraintes**
- ELK : `org.eclipse.elk.force`, `org.eclipse.elk.stress` ; Graphviz : `neato`, `fdp`, `sfdp` ; Mermaid utilise `cose-bilkent` pour les cartes mentales — [ELK, liste des algorithmes](https://eclipse.dev/elk/reference/algorithms.html) ; [Graphviz, Layout Engines](https://graphviz.org/docs/layouts/) ; [Mermaid, Layouts](https://mermaid.js.org/config/layouts.html)
- NetworkX fournit `spring_layout`, `kamada_kawai_layout`, `forceatlas2_layout`, `arf_layout`, `spectral_layout`, `circular_layout`, `shell_layout`, `spiral_layout`, `planar_layout`, `bipartite_layout`, `multipartite_layout`, `bfs_layout`, `random_layout` — aucune fonction Sugiyama ni de routage d'arêtes dans cette liste — [NetworkX, Drawing](https://networkx.org/documentation/stable/reference/drawing.html)

**Diagrammes de séquence (lignes de vie)**
- Schulze, Hoops et von Hanxleden (Université de Kiel, rapport technique 1804, 2018) : « There is research on desirable aesthetics, but to our knowledge no published layout algorithms, although several have been developed. This might be due to the rigid specification of sequence diagrams that seems to make laying them out quite easy. However, as we argue here, naive algorithms do not always produce desirable solutions » ; leur algorithme calcule l'ordre des lignes de vie selon différents critères d'optimisation, ajoute une compaction verticale et une gestion des étiquettes pour compacter horizontalement ; évaluation sur 50 diagrammes réels — [Automatic Layout and Label Management for UML Sequence Diagrams](https://macau.uni-kiel.de/receive/macau_mods_00002025?lang=en)
- D2 traite la séquence par un module dédié (`d2sequence`), où l'ordre de déclaration fixe l'ordre d'apparition des acteurs et des messages — [dépôt D2, d2layouts](https://github.com/terrastruct/d2/tree/master/d2layouts) ; [D2, Sequence Diagrams](https://d2lang.com/tour/sequence-diagrams/)

**Grilles, tableaux, emboîtements**
- D2 : module `d2grid` piloté par `grid-rows` / `grid-columns` — [D2, Grid Diagrams](https://d2lang.com/tour/grid-diagrams/)
- ELK : `org.eclipse.elk.box`, `org.eclipse.elk.rectpacking`, `org.eclipse.elk.topdownpacking` (empaquetage de rectangles) ; Graphviz : `osage` et `patchwork` — [ELK, liste des algorithmes](https://eclipse.dev/elk/reference/algorithms.html) ; [Graphviz, Layout Engines](https://graphviz.org/docs/layouts/)

**Options Python**
- grandalf : « written in pure python », implémente deux dispositions (« the Sugiyama hierarchical layout and the force-driven or energy minimization approach ») ; environ 1 500 lignes au total, « the code involved in drawing the Sugiyama (dot) layout fits in less than 600 lines » ; il calcule les coordonnées des nœuds à partir de leurs dimensions et route les arêtes (lignes ou NURBS) sans dépendance graphique ; statut « Under Development », version 0.8 — [dépôt grandalf, README](https://github.com/bdcht/grandalf)
- grandalf 0.8 date du 10 janvier 2023 sur PyPI et le dernier push du dépôt date d'août 2024 — [PyPI grandalf](https://pypi.org/project/grandalf/) ; [dépôt grandalf](https://github.com/bdcht/grandalf)
- OGDF (C++) : dernière version publiée « foxglove-202510 » (27 octobre 2025) ; un enrobage Python `ogdf-python` 0.3.5 existe — [dépôt OGDF](https://github.com/ogdf/ogdf) ; [PyPI ogdf-python](https://pypi.org/project/ogdf-python/)

### Inferences
- Tableau de correspondance proposé (synthèse des constats ci-dessus) :

| Famille de représentation | Disposition nécessaire | Implémentation de référence |
|---|---|---|
| Diagramme de processus, organigramme | En couches (Sugiyama) + routage orthogonal, direction TB/LR | ELK Layered ; dagre ; Graphviz `dot` |
| Processus avec couloirs | En couches + partitions | ELK Layered (`partitioning.*`) |
| Machine à états (cycles, auto-boucles) | En couches avec rupture de cycles + auto-boucles + étiquettes d'arête | ELK Layered (auto-boucles et étiquettes natives) ; dagre (`acyclicer: greedy`) |
| Arbre de décision | Arbre ordonné « tidy » (Reingold–Tilford / Buchheim) | d3-hierarchy ; ELK Mr. Tree |
| Diagramme de séquence | Colonnes = participants (ordre déclaré), lignes = messages (ordre déclaré) ; pas de moteur de graphe | Disposition dédiée (comme `d2sequence`) |
| Tableau, matrice | Grille lignes × colonnes, tailles de cellule par contenu | Disposition dédiée (comme `d2grid`) ou tableau HTML |
| Frise chronologique, droite numérique | Échelle (temps ou linéaire) → position ; évitement de chevauchement d'étiquettes | Échelles à la Vega-Lite ; pas de moteur de graphe |
| Décomposition de calcul | Arbre (opérandes → résultat) ou barres empilées sur une échelle | Arbre « tidy » ou échelle + marques `bar`/`rect` |

- Pour des diagrammes de petite taille (quelques dizaines de nœuds) produits par une IA, trois dispositions maison simples (grille, séquence, axe/échelle) plus **un** moteur en couches suffisent à couvrir toutes les familles demandées ; les dispositions dirigées par les forces sont inutiles ici et nuisent à la stabilité (cf. critique de TALA sur l'aléa).
- Le respect de l'ordre d'écriture (`considerModelOrder` dans ELK ; ordre déclaré dans les séquences D2) est une propriété précieuse quand l'auteur est une IA : le résultat reste stable d'une régénération à l'autre et l'auteur peut influencer la disposition sans coordonnées.
- Côté serveur Python sans exécuter de JavaScript, les choix réalistes sont : (1) appeler le binaire Graphviz (`dot`) et relire les coordonnées ; (2) grandalf en choisissant sa licence EPL ; (3) écrire une disposition en couches minimale (rang par plus long chemin, ordre par barycentre, coordonnées simples) — plausible puisque grandalf tient en moins de 600 lignes pour Sugiyama ; (4) lancer elkjs ou dagre dans un processus Node séparé. Aucune bibliothèque Python pure, permissive, activement maintenue et complète (ports, routage orthogonal, auto-boucles) n'a été trouvée.
- `multipartite_layout` de NetworkX peut servir de placement en couches rudimentaire si les couches sont calculées à part, mais sans minimisation des croisements ni routage (déduction à partir de la liste des fonctions ; comportement détaillé non vérifié).

### Gaps
- La page listant les algorithmes ELK ne donne que les identifiants ; les descriptions d'une ligne (stress, DisCo, SPOrE, VertiFlex, etc.) et la dépendance des enrobages Graphviz d'ELK à un binaire externe n'ont pas été vérifiées page par page.
- La prise en charge des auto-boucles et des étiquettes d'arête par dagre 3.x n'a pas été confirmée dans son wiki.
- Aucune source primaire lue sur l'algorithme interne du routeur orthogonal d'ELK, ni sur les algorithmes de disposition de séquence de Mermaid et PlantUML (Teoz).
- Le rapport de Kiel (TR 1804) n'a été lu que par son résumé ; les critères d'ordonnancement des lignes de vie ne sont pas détaillés ici.
- Aucune mesure comparative indépendante de qualité de disposition (croisements, surface) entre ELK, dagre, Graphviz et TALA n'a été trouvée ; un article secondaire en donne mais ses chiffres ne sont pas vérifiables.
- Les dispositions de rustworkx (Apache-2.0) n'ont pas été examinées.

## 3. Licences précises de chaque bibliothèque ou outil, et caractère permissif ou non

### Takeaway
Les briques permissives au sens strict existent pour presque tout (dagre, d3-hierarchy, Vega/Vega-Lite, Mermaid, Kroki, Penrose, NetworkX, MSAGL sont MIT/BSD/ISC), mais les deux meilleurs moteurs de disposition en couches — ELK/elkjs et Graphviz — sont sous EPL-2.0, et D2/TALA sous MPL-2.0 : ce sont des licences à copyleft faible (au niveau du fichier), pas des licences permissives pures. À exclure : OGDF, igraph, netgraph, fa2 (GPL), libavoid (LGPL), pygal (LGPL), bpmn-js (clause de filigrane).

### Cited Findings

Relevés du 21 novembre 2026 (registre npm, PyPI, API GitHub, fichiers LICENSE).

**Grammaires et langages de diagrammes**

| Composant | Version (date) | Licence | Classement | Source |
|---|---|---|---|---|
| Vega | 6.4.0 (2026-08-14) | BSD-3-Clause | Permissive | [npm vega](https://www.npmjs.com/package/vega) |
| Vega-Lite | 6.5.0 (2026-10-08) | BSD-3-Clause | Permissive | [npm vega-lite](https://www.npmjs.com/package/vega-lite) ; [dépôt](https://github.com/vega/vega-lite) |
| vega-embed | 7.4.0 (2026-11-20) | BSD-3-Clause | Permissive | [npm vega-embed](https://www.npmjs.com/package/vega-embed) |
| Altair (Python) | 6.3.0 (2026-09-15) | BSD (classifieur PyPI) | Permissive | [PyPI altair](https://pypi.org/project/altair/) |
| vl-convert-python | 1.9.0.post1 (2026-01-21) | BSD-3-Clause | Permissive | [PyPI vl-convert-python](https://pypi.org/project/vl-convert-python/) |
| Observable Plot | 0.6.19 (2026-11-05) | ISC | Permissive | [npm @observablehq/plot](https://www.npmjs.com/package/@observablehq/plot) |
| plotnine (Python, grammaire en couches) | 0.15.9 (2026-11-03) | MIT | Permissive | [PyPI plotnine](https://pypi.org/project/plotnine/) |
| Mermaid | 12.3.0 (2026-11-03) | MIT | Permissive | [npm mermaid](https://www.npmjs.com/package/mermaid) ; [dépôt](https://github.com/mermaid-js/mermaid) |
| @mermaid-js/layout-elk | 1.0.2 (2026-11-03) | MIT (enrobage ; dépend d'elkjs) | Permissive pour l'enrobage | [npm @mermaid-js/layout-elk](https://www.npmjs.com/package/@mermaid-js/layout-elk) |
| beautiful-mermaid | 1.1.3 (2026-02-26) | MIT | Permissive | [npm beautiful-mermaid](https://www.npmjs.com/package/beautiful-mermaid) |
| PlantUML | 1.2026.10 | Au choix : GPL v3, GPL v2, LGPL, Apache-2.0, BSD, EPL-2.0, MIT (archives distinctes) | Permissive si variante MIT/BSD/Apache choisie ; sinon copyleft | [PlantUML, Download](https://plantuml.com/download) |
| D2 | v0.9.0 (2026-09-07) | MPL-2.0 | Copyleft faible (fichier) — hors liste permissive stricte | [dépôt D2](https://github.com/terrastruct/d2) |
| TALA (moteur de D2) | intégré à D2 v0.9.0 | MPL-2.0 depuis le 7 sept. 2026 (auparavant propriétaire ; l'ancien dépôt `terrastruct/TALA` est archivé avec une licence « Other ») | Copyleft faible (fichier) | [D2 blog, « TALA is open source »](https://d2lang.com/blog/tala-is-open-source/) ; [ancien dépôt TALA](https://github.com/terrastruct/TALA) |
| @terrastruct/d2 (paquet npm) | 0.1.33 (2025-08-17) | MPL-2.0 | Copyleft faible ; en retard sur D2 v0.9.0 | [npm @terrastruct/d2](https://www.npmjs.com/package/@terrastruct/d2) |
| Graphviz | — | EPL-2.0 (« Eclipse Public License - v 2.0 » ; les anciennes versions relevaient de la Common Public License 1.0 puis de l'AT&T Source Code Agreement) | Copyleft faible — acceptée dans la consigne (famille EPL) | [Graphviz, License](https://graphviz.org/license/) ; [fichier LICENSE](https://gitlab.com/graphviz/graphviz/-/raw/main/LICENSE) |
| Structurizr (dont DSL) | v2026.10.26 | Apache-2.0 | Permissive | [dépôt structurizr](https://github.com/structurizr/structurizr) |
| Kroki | v0.36.0 (2026-11-09) | MIT (la passerelle ; chaque outil appelé garde sa licence) | Permissive pour la passerelle | [dépôt Kroki](https://github.com/yuzutech/kroki) |
| Penrose | @penrose/core 3.3.1 (2026-08-30) | MIT | Permissive | [npm @penrose/core](https://www.npmjs.com/package/@penrose/core) ; [dépôt](https://github.com/penrose/penrose) |
| LikeC4 | — | MIT | Permissive | [dépôt likec4](https://github.com/likec4/likec4) |
| nomnoml | 1.7.0 (2024-12-14) | MIT | Permissive | [npm nomnoml](https://www.npmjs.com/package/nomnoml) |
| Pintora | — | MIT | Permissive | [dépôt pintora](https://github.com/hikerpig/pintora) |
| WaveDrom | 3.8.0 (2026-10-25) | MIT | Permissive | [npm wavedrom](https://www.npmjs.com/package/wavedrom) |
| markmap-lib | 0.18.13 (2026-11-06) | MIT | Permissive | [npm markmap-lib](https://www.npmjs.com/package/markmap-lib) |
| Excalidraw | — | MIT | Permissive | [dépôt excalidraw](https://github.com/excalidraw/excalidraw) |
| draw.io | — | Apache-2.0 (détection GitHub) | Permissive | [dépôt drawio](https://github.com/jgraph/drawio) |
| bpmn-js | 18.33.1 (2026-11-20) | Licence MIT modifiée : le code affichant le filigrane bpmn.io « MUST NOT be removed or changed » et le filigrane doit rester entièrement visible | Restreinte | [fichier LICENSE bpmn-js](https://github.com/bpmn-io/bpmn-js/blob/develop/LICENSE) |
| bpmn-auto-layout | 1.3.0 (2026-03-11) | MIT | Permissive | [npm bpmn-auto-layout](https://www.npmjs.com/package/bpmn-auto-layout) |
| blockdiag / seqdiag / nwdiag (Python) | 3.0.0 (2021-12-06) | Apache-2.0 | Permissive, mais sans version depuis 2021 | [PyPI blockdiag](https://pypi.org/project/blockdiag/) ; [PyPI seqdiag](https://pypi.org/project/seqdiag/) |
| diagrams (Python, mingrammer) | 0.25.1 (2025-11-22) | MIT | Permissive (s'appuie sur Graphviz) | [PyPI diagrams](https://pypi.org/project/diagrams/) |
| schemdraw (Python) | 0.23 (2026-05-29) | MIT | Permissive | [PyPI schemdraw](https://pypi.org/project/schemdraw/) |

**Moteurs de disposition**

| Composant | Version (date) | Licence | Classement | Source |
|---|---|---|---|---|
| ELK (Java) | v0.12.1 (2026-10-28) | EPL-2.0 | Copyleft faible — acceptée dans la consigne | [dépôt ELK](https://github.com/eclipse-elk/elk) ; [LICENSE](https://raw.githubusercontent.com/eclipse-elk/elk/master/LICENSE.md) |
| elkjs | 0.12.1 (2026-10-28) | `EPL-2.0 OR GPL-3.0-or-later` dans package.json (fichier LICENSE = EPL v2.0) | Copyleft faible en choisissant l'EPL-2.0 | [npm elkjs](https://www.npmjs.com/package/elkjs) ; [dépôt elkjs](https://github.com/kieler/elkjs) |
| @dagrejs/dagre | 3.1.3 (2026-10-24) | MIT | Permissive | [npm @dagrejs/dagre](https://www.npmjs.com/package/@dagrejs/dagre) ; [dépôt](https://github.com/dagrejs/dagre) |
| dagre (ancien paquet) | 0.8.5 (2019-12-03) | MIT | Permissive, mais abandonné au profit de @dagrejs/dagre | [npm dagre](https://www.npmjs.com/package/dagre) |
| @dagrejs/graphlib | 4.0.7 (2026-10-24) | MIT | Permissive | [npm @dagrejs/graphlib](https://www.npmjs.com/package/@dagrejs/graphlib) |
| d3-hierarchy | 3.1.3 | ISC | Permissive | [npm d3-hierarchy](https://www.npmjs.com/package/d3-hierarchy) |
| d3-force | 3.0.1 | ISC | Permissive | [npm d3-force](https://www.npmjs.com/package/d3-force) |
| d3-dag | 1.3.0 (2026-11-01) | MIT | Permissive | [npm d3-dag](https://www.npmjs.com/package/d3-dag) |
| d3-sankey | 0.12.3 (2019-09-02) | BSD-3-Clause | Permissive | [npm d3-sankey](https://www.npmjs.com/package/d3-sankey) |
| MSAGL (JS) @msagl/core | 1.1.25 (2026-11-17) | MIT | Permissive | [npm @msagl/core](https://www.npmjs.com/package/@msagl/core) ; [dépôt msagljs](https://github.com/microsoft/msagljs) |
| Cytoscape.js | 3.35.0 (2026-11-10) | MIT | Permissive | [npm cytoscape](https://www.npmjs.com/package/cytoscape) |
| WebCola | 3.4.0 (2019-05-10) | MIT | Permissive, sans version depuis 2019 | [npm webcola](https://www.npmjs.com/package/webcola) |
| @antv/layout | 2.0.0 (2026-02-11) | MIT | Permissive | [npm @antv/layout](https://www.npmjs.com/package/@antv/layout) |
| @xyflow/react (React Flow) | 13.0.2 (2026-11-17) | MIT | Permissive | [npm @xyflow/react](https://www.npmjs.com/package/@xyflow/react) |
| @hpcc-js/wasm-graphviz | 1.30.0 (2026-10-21) | Apache-2.0 (enrobage ; Graphviz embarqué reste EPL-2.0) | Permissive pour l'enrobage | [npm @hpcc-js/wasm-graphviz](https://www.npmjs.com/package/@hpcc-js/wasm-graphviz) |
| @viz-js/viz | 3.31.0 (2026-09-28) | MIT (enrobage) | Permissive pour l'enrobage | [npm @viz-js/viz](https://www.npmjs.com/package/@viz-js/viz) |
| libavoid-js | 0.5.0-beta.6 (2026-11-16) | LGPL-2.1-or-later | Copyleft — à exclure | [npm libavoid-js](https://www.npmjs.com/package/libavoid-js) |
| OGDF (C++) | foxglove-202510 (2025-10-27) | GPL v2 ou v3, avec exceptions de liaison limitées (Tulip, COIN-OR Osi, etc.) | Copyleft fort — à exclure | [LICENSE OGDF](https://github.com/ogdf/ogdf/blob/master/LICENSE.txt) |
| ogdf-python | 0.3.5 (2026-03-12) | Apache-2.0 pour l'enrobage ; OGDF sous-jacent GPL | À exclure de fait | [PyPI ogdf-python](https://pypi.org/project/ogdf-python/) |
| grandalf (Python) | 0.8 (2023-01-10) | Double licence au choix : GPL v2 **ou** Eclipse Public License v1.0 | Copyleft faible en choisissant l'EPL-1.0 ; peu actif | [fichier LICENSE grandalf](https://github.com/bdcht/grandalf/blob/master/LICENSE) ; [PyPI grandalf](https://pypi.org/project/grandalf/) |
| NetworkX (Python) | 3.7 (2026-09-21) | BSD-3-Clause | Permissive | [PyPI networkx](https://pypi.org/project/networkx/) |
| igraph (C) / python-igraph | 1.0.1 (C, 2025-12-26) / 1.0.0 (Python, 2025-10-23) | GPL-2.0 | Copyleft fort — à exclure | [dépôt igraph](https://github.com/igraph/igraph) ; [dépôt python-igraph](https://github.com/igraph/python-igraph) |
| rustworkx (Python) | 0.18.1 (2026-07-30) | Apache-2.0 | Permissive | [PyPI rustworkx](https://pypi.org/project/rustworkx/) |
| graphviz (enrobage Python) | 0.21 (2025-06-15) | MIT (enrobage ; nécessite Graphviz EPL-2.0) | Permissive pour l'enrobage | [PyPI graphviz](https://pypi.org/project/graphviz/) |
| pygraphviz | 2.0.4 (2026-10-15) | BSD-3-Clause (enrobage) | Permissive pour l'enrobage | [PyPI pygraphviz](https://pypi.org/project/pygraphviz/) |
| pydot | 4.0.1 (2025-06-17) | MIT (enrobage) | Permissive pour l'enrobage | [PyPI pydot](https://pypi.org/project/pydot/) |
| netgraph (Python) | 4.13.2 (2023-12-11) | GPLv3 | Copyleft fort — à exclure | [PyPI netgraph](https://pypi.org/project/netgraph/) |
| fa2 (ForceAtlas2 Python) | 1.1.2 (2026-03-23) | GPL-3.0-only | Copyleft fort — à exclure | [PyPI fa2](https://pypi.org/project/fa2/) |
| graph-tool (Python) | 2.11 sur PyPI | GPL (classifieur PyPI) | Copyleft — à exclure | [PyPI graph-tool](https://pypi.org/project/graph-tool/) |
| pygal (Python, graphiques SVG) | 3.1.3 (2026-06-18) | LGPL v3+ | Copyleft — à exclure | [PyPI pygal](https://pypi.org/project/pygal/) |

**Outils de rendu et de validation utiles (hors disposition)**

| Composant | Version (date) | Licence | Source |
|---|---|---|---|
| drawsvg (Python) | 2.5.1 (2026-11-19) | MIT | [PyPI drawsvg](https://pypi.org/project/drawsvg/) |
| svgwrite (Python) | 1.4.3 (2022-07-14) | MIT | [PyPI svgwrite](https://pypi.org/project/svgwrite/) |
| jsonschema (Python) | 4.26.0 (2026-01-07) | MIT | [PyPI jsonschema](https://pypi.org/project/jsonschema/) |
| pydantic (Python) | 2.14.4 (2026-11-19) | MIT | [PyPI pydantic](https://pypi.org/project/pydantic/) |
| Ajv (JS) | 8.20.0 (2026-04-24) | MIT | [npm ajv](https://www.npmjs.com/package/ajv) |
| Gemini (grammaire de transitions animées) | dernier push 2023-03 | BSD-3-Clause | [dépôt uwdata/gemini](https://github.com/uwdata/gemini) |

Autres constats :
- PlantUML : la variante LGPL est celle « without embedded GraphViz » ; l'intégration ELK n'existe que dans la variante EPL — [PlantUML, Download](https://plantuml.com/download)
- Mermaid embarque désormais ELK par défaut dans le paquet principal (« bundled with Mermaid and needs no setup ») ; seule la version « tiny » l'omet — [Mermaid, Layouts](https://mermaid.js.org/config/layouts.html)
- L'article ELK de 2023 consacre une section aux « potential threats to open-source graph drawing libraries » — [Domrös et al., arXiv 2311.00533](https://arxiv.org/abs/2311.00533)

### Inferences
- Attention de classification : la consigne range l'EPL parmi les licences permissives, mais l'EPL-2.0 (ELK, elkjs, Graphviz), l'EPL-1.0 (option de grandalf) et la MPL-2.0 (D2, TALA) sont des licences à copyleft faible : elles n'imposent rien au code de l'application qui les *utilise* sans les modifier, mais les modifications apportées aux fichiers sous EPL/MPL doivent être redistribuées sous la même licence. La MPL-2.0 n'est pas dans la liste « acceptable » de la consigne : D2 et TALA demandent donc une décision explicite (leur régime est proche de celui de l'EPL).
- Conséquence indirecte : utiliser Mermaid ≥ 12 complet revient à embarquer elkjs (EPL-2.0) même si Mermaid lui-même est MIT ; pour rester en MIT pur il faudrait la version « tiny » (dagre seul).
- Chaîne entièrement permissive (MIT/BSD/ISC/Apache uniquement) réalisable : dagre (couches) + d3-hierarchy (arbres) + dispositions maison (grille, séquence, axe) + Vega-Lite/échelles maison (quantitatif) + jsonschema/pydantic (validation) + drawsvg ou génération SVG directe. Elle sacrifie surtout le routage orthogonal avec ports, les couloirs natifs et les auto-boucles soignées d'ELK.
- Chaîne « permissive + EPL » : ajouter elkjs (processus Node) ou Graphviz `dot` (binaire) comme moteur en couches apporte ces capacités sans obligation sur le code propre, tant que ces composants ne sont pas modifiés.
- Les enrobages Python de Graphviz (graphviz, pygraphviz, pydot) et WASM (@hpcc-js/wasm-graphviz, @viz-js/viz) sont permissifs mais ne changent pas la licence de Graphviz lui-même (EPL-2.0).
- Risque de pérennité : grandalf (dernière version 2023), WebCola (2019), d3-sankey (2019), blockdiag (2021) et l'ancien paquet `dagre` (2019) sont peu ou plus maintenus ; @dagrejs/dagre, elkjs, Mermaid, Vega-Lite, Kroki, MSAGL-JS et D2 ont tous publié en 2026.

### Gaps
- La date exacte du passage de Graphviz à l'EPL-2.0 n'est pas établie : la page de licence mentionne en pied une modification « from Common Public License Version 1.0 to Eclipse Public License version 2.0 » sans date fiable.
- La raison du champ `EPL-2.0 OR GPL-3.0-or-later` d'elkjs (clause de licence secondaire de l'EPL-2.0 ?) n'a pas été recherchée.
- Les licences des dépendances transitives (par ex. polices embarquées, Chromium pour les exports Mermaid) n'ont pas été auditées.
- draw.io : seule la détection automatique GitHub (Apache-2.0) a été relevée ; le texte du fichier de licence et d'éventuelles conditions complémentaires n'ont pas été lus.
- Avis juridique : la compatibilité de l'EPL-2.0 et de la MPL-2.0 avec la politique interne de l'entreprise reste à valider par qui de droit ; ces notes ne font que relever les licences.

## 4. À quoi ressemblent en pratique les spécifications de diagrammes écrites par un LLM et validées par schéma ? Modes d'échec et garde-fous

### Takeaway
La validation par schéma élimine les erreurs de syntaxe mais pas les erreurs de sens : références d'arêtes vers des identifiants inexistants, éléments manquants, graphiques valides mais vides, encodages incohérents. Les garde-fous qui fonctionnent dans les systèmes publiés sont, dans l'ordre : un format cible petit et fermé (JSON plutôt que syntaxe texte), une validation en couches (schéma → intégrité référentielle → rendu réel), des corrections algorithmiques sans rappel du modèle, puis une boucle de réparation bornée (jusqu'à 5 essais) qui renvoie le message d'erreur exact.

### Cited Findings

**Taux d'erreur observés**
- MermaidSeqBench (IBM Research, NeurIPS 2025 workshop) : 132 paires texte → diagramme de séquence Mermaid, six critères notés de 0 à 1 (Syntax, Mermaid Only, Logic, Completeness, Activation Handling, Error & Status Tracking) ; la gestion des activations est le critère le plus faible pour tous les modèles et sous les deux juges ; scores de syntaxe (juge DeepSeek-V3 / juge GPT-OSS) : Qwen 2.5-0.5B 58,90 / 48,95 ; Llama 3.2-1B 68,98 / 46,15 ; Granite 3.3-2B 75,27 / 39,60 ; Qwen 2.5-7B 91,29 / 85,97 ; Llama 3.1-8B 92,01 / 68,89 ; Granite 3.3-8B 86,97 / 65,15 — [Shbita, Ahmed, DeLuca, MermaidSeqBench, arXiv 2511.14967](https://arxiv.org/html/2511.14967v1)
- GenAI-DrawIO-Creator (Claude 3.7 générant du XML draw.io ; 10 tâches de 3 à 15 éléments) : XML valide du premier coup dans 9 cas sur 10 ; environ 94 % des composants et relations demandés présents au premier essai, environ 100 % après un tour de correction ; clarté de disposition notée 4,34/5 par 5 évaluateurs ; modes d'échec rapportés : caractères spéciaux non échappés et balises dépareillées, **connecteurs pendants (arêtes pointant vers des identifiants inexistants)**, mauvaise interprétation des relations spatiales, performance dégradée au-delà d'environ 20 composants et sur les types de diagrammes spécialisés. Évaluation petite et qualifiée de « simulated » par les auteurs — [Yu & Jiang, GenAI-DrawIO-Creator, arXiv 2601.05162](https://arxiv.org/html/2601.05162v2)
- VegaChat (GPT-4o-mini → Vega-Lite) : avec boucle de validation, taux de spécifications invalides 0,0 % et taux de graphiques vides ou invalides 0,3 % (jeu NLV) et 0,8 % (jeu ChartLLM), contre 35,1 % et 21,4 % pour LIDA/Altair sans auto-correction (comparaison non équitable, soulignée par le résumé) ; modes d'échec : champs et API Vega-Lite inventés, faiblesse sur les fonctions avancées (transformations, facettes), graphiques valides mais vides — [VegaChat, arXiv 2601.15385](https://arxiv.org/html/2601.15385v1)
- DracoGPT : les erreurs observées dans les complétions Vega-Lite étaient sémantiques plutôt que syntaxiques (par ex. définition d'échelle sur un champ catégoriel, variable requise non encodée) ; GPT-3.5-Turbo ne produisait des complétions Vega-Lite valides que 19,10 % du temps, GPT-4-Turbo plus de 90 % (extrait de recherche, non vérifié en texte intégral) — [Wang, Gordon, Battle, Heer, DracoGPT, IEEE VIS 2024, arXiv 2408.06845](https://arxiv.org/abs/2408.06845)
- Mermaid en texte libre : « syntax matters and LLM sometimes get it wrong » ; exemple d'une flèche `->` au lieu de `-->` qui empêche tout rendu — [GenAIScript blog, « Mermaids Unbroken », 16 mai 2025](https://microsoft.github.io/genaiscript/blog/mermaids)

**Garde-fous documentés**
- Validation en couches de VegaChat : contrôle contre le schéma Vega-Lite + heuristiques ; détection des graphiques vides à partir du graphe de scène de Vega ; renvoi au LLM de la trace de validation d'Altair ; corrections algorithmiques évitant un nouvel appel (par ex. normalisation d'une chaîne de date « 2006-01-01 » en objet année/mois/jour) ; jusqu'à cinq tentatives de correction ; les auteurs suggèrent en perspective de contraindre la génération à un sous-ensemble du schéma Vega-Lite — [VegaChat, arXiv 2601.15385](https://arxiv.org/html/2601.15385v1)
- Garde-fous de GenAI-DrawIO-Creator : contrôle de bonne formation XML avec réparation automatique (remplacement de chaînes ou invite d'auto-correction) ; contrôle sémantique que le nombre de formes correspond au nombre d'éléments demandés ; **contrôle que la source et la cible de chaque arête correspondent à des identifiants de sommets existants** ; le modèle ne fournit pas de coordonnées (positions par défaut ou disposition de graphe simple) — [Yu & Jiang, arXiv 2601.05162](https://arxiv.org/html/2601.05162v2)
- Boucle de réparation de GenAIScript : un « repairer » repère les blocs Mermaid dans la sortie, tente de les analyser et, en cas d'erreur, ajoute au dialogue un message contenant l'erreur d'analyse exacte ; « In most cases, the LLM is able to fix the syntax error and generate a valid diagram using the error message » — [GenAIScript blog, « Mermaids Unbroken »](https://microsoft.github.io/genaiscript/blog/mermaids)
- Query2Diagram : affinage de Qwen2.5-Coder-14B sur des « diagram representations in a structured JSON format » plutôt que sur une syntaxe texte, avec détection automatique de défauts structurels ; le résumé annonce les meilleurs scores F1 et des taux de défauts inférieurs à ceux des LLM de pointe, sans chiffres dans la page consultée — [Baryshnikov, Alekseev, Nikolenko, Query2Diagram, arXiv 2604.23816](https://www.alphaxiv.org/abs/2604.23816)
- MermaidSeqBench recommande des évaluations multi-critères à grain fin plutôt que de simples contrôles de conformité ou de rendu, et l'usage de plusieurs juges LLM (un juge s'est montré systématiquement plus indulgent que l'autre) — [MermaidSeqBench, arXiv 2511.14967](https://arxiv.org/html/2511.14967v1)

**Génération contrainte par schéma JSON : capacités et limites**
- JSONSchemaBench : le décodage contraint est devenu la technologie dominante pour imposer des sorties structurées et s'est standardisé autour de JSON Schema ; le banc d'essai comprend 10 000 schémas réels et évalue six cadres (Guidance, Outlines, Llamacpp, XGrammar, OpenAI, Gemini) sur l'efficacité, la couverture des types de contraintes et la qualité des sorties — [Geng et al., JSONSchemaBench, arXiv 2501.10868](https://arxiv.org/abs/2501.10868)
- Limites publiées d'une implémentation commerciale de sorties structurées : jusqu'à 5 000 propriétés d'objet au total et 10 niveaux d'imbrication ; 120 000 caractères au total pour noms de propriétés, noms de définitions, valeurs d'énumération et constantes ; 1 000 valeurs d'énumération au maximum ; `additionalProperties: false` obligatoire sur tout objet ; tous les champs doivent être requis (optionnel = union avec `null`) ; la racine doit être un objet et ne peut pas être un `anyOf` ; mots-clés non pris en charge : `allOf`, `not`, `dependentRequired`, `dependentSchemas`, `if/then/else` ; schémas récursifs acceptés via `$defs` ou `#` — [OpenAI, Structured Outputs — Supported schemas](https://developers.openai.com/api/docs/guides/structured-outputs)
- La même documentation précise que la sortie structurée contraint la forme, mais que l'application doit encore « validate any business rules that the schema does not express » — [OpenAI, Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- Le schéma Vega-Lite v6 complet pèse 1,88 Mo pour 458 définitions et sa racine est un `anyOf` de sept formes — [schéma Vega-Lite v6](https://vega.github.io/schema/vega-lite/v6.json)
- « Good-Enough Structured Generation » (NeurIPS 2025) soutient que le décodage contraint par grammaire est limité aux grammaires hors contexte alors que les schémas réels exigent des validations sensibles au contexte, et rapporte que l'utilisation des échecs de validation comme retour au modèle fait mieux, au prix d'une latence plus élevée (extrait de recherche, non vérifié en texte intégral) — [page NeurIPS 2025](https://neurips.cc/virtual/2025/131662)
- IterGen applique pendant le décodage des contraintes propres à Vega-Lite (noms de champs valides, compatibilité des types, valeurs d'agrégation restreintes) avec retour arrière (extrait de recherche, non vérifié en texte intégral) — [IterGen, arXiv 2410.07295](https://arxiv.org/pdf/2410.07295)

### Inferences
- Le schéma Vega-Lite complet est mal adapté à la génération contrainte : sa racine en `anyOf` est interdite par au moins une implémentation, et sa taille (1,88 Mo, 458 définitions) rend le respect des plafonds de caractères et de propriétés incertain. Un vocabulaire maison petit, à énumérations fermées, sans `allOf`/`if-then-else`, avec racine objet et un discriminant `type` par bloc, est directement compatible avec ces contraintes — ce qui rejoint la piste « sous-ensemble du schéma » évoquée par VegaChat.
- Un schéma JSON ne peut pas exprimer l'intégrité référentielle (« toute arête cite un nœud déclaré ») : c'est une validation sensible au contexte. Il faut donc une seconde passe de vérification (« linter ») côté serveur, dont les règles minimales ressortent des échecs publiés : identifiants uniques ; extrémités d'arêtes existantes ; pas de nœud orphelin non voulu ; états/étapes référencés existants ; valeurs liées présentes dans les données ; diagramme non vide.
- Les seuils de taille sont un garde-fou nécessaire : la seule donnée chiffrée trouvée situe la dégradation au-delà d'environ 20 composants. Des limites explicites dans le schéma (`maxItems` sur nœuds, arêtes, lignes, étapes ; longueur maximale des libellés) et une règle de repli (« au-delà de N nœuds, scinder en plusieurs vues ou basculer en tableau ») sont cohérentes avec ce constat.
- Ordre des garde-fous par coût croissant : (1) schéma fermé + génération contrainte ; (2) normalisations déterministes (dates, casse des identifiants, échappement des libellés) ; (3) linter sémantique ; (4) essai de rendu réel et détection de résultat vide ; (5) boucle de réparation bornée avec message d'erreur précis ; (6) repli automatique vers une représentation plus simple (tableau ou liste) si tout échoue.
- Ne pas laisser le modèle fournir des coordonnées : les systèmes étudiés confient le placement à un moteur, et la mauvaise interprétation des relations spatiales figure parmi les échecs rapportés. Le document JSON devrait ne contenir que structure, ordre et indications de direction.
- Passer par un JSON intermédiaire validé puis convertir de façon déterministe supprime par construction la classe d'erreurs de syntaxe qui domine les retours d'expérience Mermaid ; les erreurs restantes sont de complétude et de logique, que seul un contrôle sémantique ou une relecture peut attraper.

### Gaps
- Aucune étude trouvée ne catégorise systématiquement les échecs de spécifications Vega-Lite produites *sous décodage contraint par schéma JSON* ; les données disponibles (IterGen, DracoGPT) sont à petite échelle.
- Aucun banc d'essai trouvé sur les erreurs de syntaxe Mermaid pour organigrammes, diagrammes d'états ou de classes : MermaidSeqBench ne couvre que les séquences et ne catalogue pas les types d'erreur.
- Aucune source chiffrée sur les dispositions illisibles ou trop denses (croisements, chevauchements) produites par des LLM ; le seuil « environ 20 composants » vient d'une seule étude à 10 tâches.
- Un retour d'expérience de l'Université Humboldt de Berlin (pipeline en deux temps JSON → Mermaid déterministe, taux de succès passé de 70 % à 95 % grâce à la validation et au rendu d'essai par Mermaid CLI) est apparu dans les résultats de recherche, mais la page renvoie une erreur 404 : chiffres non vérifiables — [page HU Berlin (inaccessible)](https://llm-enabled-development-41d6d8.pages.cms.hu-berlin.de/en/experiments/diagram/diagram-long)
- Les chiffres de MermaidSeqBench portent sur de petits modèles ouverts (0,5 à 8 milliards de paramètres) ; aucun chiffre comparable pour les modèles de pointe de 2026.
- Les limites de schéma des autres fournisseurs de sorties structurées n'ont pas été relevées.
- Query2Diagram : schéma JSON, liste des défauts structurels détectés et résultats chiffrés non obtenus (seul le résumé a été lu).

## 5. Comment ces systèmes représentent-ils un état qui évolue dans le temps sur un diagramme (images d'animation, étapes, petits multiples) ?

### Takeaway
Trois mécanismes déclaratifs distincts existent : le temps comme canal d'encodage lié à un champ de données (Vega-Lite : une valeur du champ = une image clé), les étapes à héritage cumulatif sur un même diagramme (D2 `steps`/`scenarios`, Structurizr `animation`), et la juxtaposition statique en petits multiples (Vega-Lite `facet`/`concat`). Le modèle « étapes qui héritent de la précédente » de D2 est le plus directement adapté à un diagramme de processus ou d'états dont on veut montrer l'avancement.

### Cited Findings

**Temps comme canal d'encodage (Vega-Lite)**
- Animated Vega-Lite modélise les visualisations animées comme des requêtes de données variant dans le temps : « we represent time as an encoding channel. Time encodings map a data field to animation keyframes » ; pour combiner animation et interaction, le temps est aussi un flux d'événements : les sélections sont pilotées « not only by input events but by timer ticks as well » ; l'approche privilégie l'unification avec les abstractions existantes plutôt que l'expressivité maximale — [Zong, Pollock, Wootton, Satyanarayan, Animated Vega-Lite, arXiv 2208.03869 (IEEE VIS 2022)](https://arxiv.org/abs/2208.03869)
- Les entretiens avec cinq développeurs de grammaires d'animation identifient trois arbitrages : le processus de conception du langage, les types de transitions animées prises en charge, et la façon dont les systèmes modélisent les images clés — [Animated Vega-Lite, arXiv 2208.03869](https://arxiv.org/abs/2208.03869)
- État de l'implémentation : la demande de fusion « feat: frame animations with time encoding and timer param » a été fusionnée dans Vega-Lite le 14 novembre 2024 — [vega-lite PR #8921](https://github.com/vega/vega-lite/pull/8921) ; le canal `time` figure bien parmi les 38 canaux du schéma v6 — [schéma Vega-Lite v6](https://vega.github.io/schema/vega-lite/v6.json) ; mais la demande de fusion de documentation correspondante est toujours ouverte — [vega-lite PR #9535](https://github.com/vega/vega-lite/pull/9535)

**Étapes et scénarios (D2)**
- « A "Step" represents a step in a sequence of events. Each Step inherits from its the Step before it. The first step inherits from its parent, whether that's a Scenario or Layer » ; un objet défini à l'étape 1 existe donc à l'étape 3 sans être redéclaré — [D2, Steps](https://d2lang.com/tour/steps/)
- Sémantique d'héritage des trois types de planches : `layers` = « Boards which do not inherit. They are a new base » ; `scenarios` = hérite de la couche de base ; `steps` = hérite de l'étape précédente — [D2, Composition](https://d2lang.com/tour/composition/)
- Les planches « cannot be visible at the same time », donc les exports s'adaptent : SVG animé, PPTX (« useful for giving presentations when used with composition (e.g. diagram with multiple Layers, Scenarios, Steps) »), GIF (« useful … with short compositions. For example, show two Scenarios, show a couple of steps »), PDF (moins interactif : le mot-clé `animate` n'y apparaît pas) ; formats de sortie : svg, png, pdf, pptx, gif, ascii — [D2, Exports](https://d2lang.com/tour/exports/)

**Étapes d'animation et vues dynamiques (Structurizr)**
- Bloc `animation` dans une vue : « Each animation step should be defined on a separate line, inside the block », chaque ligne listant les identifiants d'éléments révélés à cette étape — [Structurizr DSL, Language reference](https://docs.structurizr.com/dsl/language)
- Vue `dynamic` : liste ordonnée d'instances de relations (`a -> b "description"`), avec un préfixe facultatif `order:` pour fixer explicitement la séquence — [Structurizr DSL, Language reference](https://docs.structurizr.com/dsl/language)

**Petits multiples (juxtaposition statique)**
- L'opérateur `facet` de Vega-Lite permet de « partition the data and create a view for each subset to create a trellis plot » ; raccourcis par les canaux `row` et `column` ; `concat` et `repeat` juxtaposent des vues, et `resolve` décide si les échelles sont partagées ou indépendantes — [Vega-Lite docs, Composition](https://vega.github.io/vega-lite/docs/composition.html) ; [Vega-Lite docs, Resolve](https://vega.github.io/vega-lite/docs/resolve.html)

**Stabilité de la disposition d'une étape à l'autre**
- TALA « uses randomness, so adding one node can change the whole diagram, unlike Dagre and ELK » ; à graines et entrée identiques, la sortie est identique — [D2 blog, « TALA is open source »](https://d2lang.com/blog/tala-is-open-source/)
- ELK Layered propose des modes interactifs et le respect de l'ordre du modèle (`considerModelOrder`, `interactiveLayout`, contraintes de couche) — [ELK Layered, référence](https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html)

### Inferences
- Trois modèles de « temps » à offrir dans un vocabulaire compact, du plus simple au plus riche : (a) **petits multiples** — même représentation répétée par valeur d'un champ, lisible à l'impression et sans script ; (b) **étapes cumulatives** — une liste ordonnée de deltas (éléments ajoutés, surlignés, valeurs modifiées) appliqués à une base, sémantique « hérite de l'étape précédente » ; (c) **canal temps lié aux données** — chaque valeur d'un champ devient une image, adapté aux représentations quantitatives.
- Pour un rendu serveur en SVG/HTML sans code fourni, le modèle (b) se réalise sans JavaScript d'auteur : soit une série de SVG statiques (un par étape) avec navigation gérée par l'application, soit un SVG unique avec classes d'état par étape. C'est l'équivalent des exports PPTX/GIF/SVG animé de D2.
- La disposition doit être calculée **une seule fois sur l'union de toutes les étapes**, puis les éléments masqués/affichés ou restylés par étape : c'est la seule façon de garantir qu'un nœud ne « saute » pas entre deux étapes (problème d'instabilité explicitement signalé pour les moteurs à aléa). L'héritage cumulatif de D2 et le bloc `animation` de Structurizr (révélation progressive d'éléments d'une vue déjà disposée) vont dans ce sens.
- Distinguer « état du système à l'instant t » (jeton sur un état actif, valeur courante d'une variable — un *lien de données* vers un style) de « construction progressive du diagramme » (révélation pédagogique) : les deux se décrivent par des étapes, mais le premier ne change que des liaisons de style sur une structure fixe, ce qui est plus simple à valider.
- Les scénarios de D2 (variantes héritant toutes de la même base, sans ordre) correspondent au besoin « même processus, cas différents » (par ex. cas nominal / cas d'erreur) et pourraient se décrire avec le même mécanisme de deltas, sans notion d'ordre.

### Gaps
- La syntaxe exacte et les limites de l'animation native de Vega-Lite (marques prises en charge, interpolation entre images, paramètres `animationDuration` / `framesPerSecond`) ne sont pas documentées officiellement à ce jour : la page de documentation attendue n'existe pas (erreur 404) et la demande de fusion de documentation reste ouverte.
- Aucun mécanisme d'étapes ou d'animation n'a été trouvé dans la documentation Mermaid consultée ; non recherché de façon exhaustive, ni pour PlantUML (`newpage`) ni pour Graphviz.
- La page D2 consultée ne détaille ni l'option de ligne de commande réglant l'intervalle d'animation du SVG, ni le mécanisme de liens entre planches.
- Gemini (grammaire de transitions animées entre deux graphiques Vega-Lite, dépôt BSD-3-Clause inactif depuis 2023) n'a pas été étudié au-delà de sa licence ; d'autres grammaires d'animation (Canis, Data Animator) n'ont pas été examinées.
- Aucune source trouvée sur la manière dont les moteurs de disposition préservent la « carte mentale » entre deux versions successives d'un même graphe (disposition incrémentale), au-delà des options interactives d'ELK.
