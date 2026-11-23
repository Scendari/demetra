# Notations visuelles pour les processus, le comportement dans le temps et les interactions

Notes de recherche — état au 21 novembre 2026. Convention : tout fait de la rubrique « Cited Findings » porte sa source. Les mentions « (extrait de recherche) » signalent un fait lu dans un résumé de moteur de recherche et non dans la page complète. Les connaissances générales non revérifiées pendant cette session sont regroupées dans « Inferences » ou « Gaps » et marquées **[non vérifié en session]**.

Échecs d'accès à connaître : article zur Muehlen & Recker (Springer, accès payant), étude Compagnucci et al. 2023 (Springer payant, copie universitaire en 403), uml-diagrams.org (erreur de certificat), plusieurs pages de documentation Camunda/Stately en 404. Les détails de notation UML viennent donc de Wikipédia (qui cite la spécification OMG UML 2.5.1) et non de la spécification elle-même.

---

## Question 1 — Quelles notations sont réellement utilisées pour les processus métier et pour le comportement logiciel ? Quel sous-ensemble de BPMN sert vraiment ?

### Takeaway
BPMN est le standard de référence des diagrammes de processus, mais les praticiens n'en utilisent qu'une petite partie : moins de 20 % du vocabulaire sert régulièrement, et un modèle moyen emploie environ 9 symboles différents. Côté logiciel, UML est utilisé de façon sélective et informelle, avec trois diagrammes de comportement qui reviennent : séquence, activité, état.

### Cited Findings

**BPMN : sous-ensemble utilisé**
- Étude zur Muehlen & Recker (CAiSE 2008, LNCS 5074, p. 465-479) : analyse statistique de 120 diagrammes BPMN issus d'usages académique, de conseil et général. Résultats : les symboles se regroupent en quelques grappes bien définies ; moins de 20 % du vocabulaire est utilisé régulièrement ; certains symboles n'apparaissent dans aucun modèle ; un modèle moyen utilise environ 9 symboles différents, mais deux modèles de cette taille n'en partagent que 4 à 5. — [Stevens Institute, fiche et résumé de l'article](https://researchwith.stevens.edu/en/publications/how-much-language-is-enough-theoretical-and-practical-use-of-the-/) ; [DOI](https://www.doi.org/10.1007/978-3-540-69534-9_35)
- Lecture de cette étude par Bruce Silver : le noyau et le noyau étendu réunissent « tous les éléments utilisés dans au moins 25 % des diagrammes étudiés », soit événements de début et de fin, tâches et flux de séquence, pools et couloirs, passerelles exclusives. L'ensemble « spécialiste » contient les sous-processus et les événements attendus (wait-for). L'ensemble « superflu » (overhead) contient les événements non sollicités déclenchant un flux d'exception (délai dépassé, annulation par le client en cours de route) et tous les événements d'erreur. — [BPM Institute, « How Much BPMN Do You Need? »](https://www.bpminstitute.org/resources/articles/bpms-watch-how-much-bpmn-do-you-need/)
- Objection de Silver : la fréquence d'usage est un mauvais critère. Sans événements non sollicités ni événements d'erreur, « un analyste métier ne peut plus décrire le traitement des exceptions dans le modèle ». — [BPM Institute](https://www.bpminstitute.org/resources/articles/bpms-watch-how-much-bpmn-do-you-need/)
- Suite de 2013 des mêmes auteurs (« We Still Don't Know How Much BPMN Is Enough, But We Are Getting Closer ») : la distribution d'usage des symboles BPMN ressemble à la distribution de fréquence des mots d'une langue naturelle ; l'article de 2008 a alimenté le débat sur la génération suivante du standard (extrait de recherche). — [Springer Professional](https://www.springerprofessional.de/we-still-don-t-know-how-much-bpmn-is-enough-but-we-are-getting-c/4070814)
- Enquête mondiale de Recker (2007, 590 modélisateurs BPMN, plus de trente pays) : 36 % se limitent au jeu de base, 37 % utilisent un jeu étendu, le reste la spécification complète ; environ 14 % seulement ont reçu une formation formelle à BPMN (extrait de recherche, attribution à vérifier). — [Recker, « BPMN Modeling – Who, Where, How and Why »](https://typeset.io/pdf/bpmn-modeling-who-where-how-and-why-2e4lj8hha1.pdf)
- Étude plus récente, Compagnucci, Corradini, Fornari et Re (Business & Information Systems Engineering, vol. 66 n° 1, p. 43-66, en ligne juin 2023) : 54 500 modèles BPMN collectés dans sept collections en ligne, couvrant collaboration, chorégraphie et conversation ; analyse des éléments utilisés, de leurs combinaisons et des violations du standard et des bonnes pratiques (extrait de recherche ; résultats chiffrés non obtenus). — [DOI](https://dx.doi.org/10.1007/s12599-023-00818-7)
- Travail antérieur d'auteurs en partie communs : 25 590 modèles de six dépôts ; la distribution des éléments BPMN suit une loi de puissance (extrait de recherche). — [Référence](https://unpaywall.org/10.1007%2F978-3-030-87205-2_6)

**BPMN face aux autres notations de processus**
- L'OMG décrit BPMN comme « le standard de fait pour les diagrammes de processus métier », avec une notation proche de l'organigramme, indépendante de l'environnement d'implémentation ; version formelle la plus récente : 2.0.2, janvier 2014. — [OMG, About BPMN 2.0.2](https://www.omg.org/spec/BPMN/2.0.2/About-BPMN)
- Avis contraire : le BPM Report 2019 (Imgrund, université de Würzburg) conclut qu'il n'y a « pas d'indication claire d'un standard de fait pour la modélisation des processus, ni BPMN, ni la notation longtemps favorite EPC » (extrait de recherche). — [Imgrund, BPM Report 2019](https://opus.bibliothek.uni-wuerzburg.de/files/17924/WPS_BWL_Issue6_Imgrund.pdf)

**UML en pratique (comportement logiciel)**
- Étude de Petre « UML in Practice » (ICSE 2013), d'après une recension : parmi les utilisateurs sélectifs d'UML, diagrammes de classes cités 7 fois, séquence 6, activité 6, machine à états 3, cas d'utilisation 1 ; conclusion : on utilise des parties d'UML, pas la notation entière. — [Never Work in Theory, recension](https://neverworkintheory.org/2013/06/13/uml-in-practice-2.html)
- Enquête de 2003-2004 : seul le diagramme de classes est utilisé régulièrement par plus de la moitié des répondants ; séquence et cas d'utilisation par environ la moitié (extrait de recherche, attribution à vérifier). — [« How UML is used »](https://condor.depaul.edu/dmumaugh/readings/handouts/SE430/How%20UML%20is%20used.pdf)

**Indice d'usage par l'outillage libre**
- Mermaid (outil de diagrammes en texte très répandu) liste en 2026 : Flowchart, Swimlanes (bêta), Sequence, Class, State, Entity Relationship, User Journey, Gantt, Pie, Quadrant, Requirement, Use Case (bêta), GitGraph, C4, Mindmaps, Timeline, ZenUML, Sankey, XY Chart, Block, Packet, Kanban, Architecture (bêta), Radar (bêta), Event Modeling, Treemap, Venn (bêta), Ishikawa, Wardley (bêta), Cynefin (bêta), TreeView (bêta), Agentflow. BPMN, réseaux de Petri, EPC, CMMN et cartes de flux de valeur n'y figurent pas. — [Mermaid, introduction](https://mermaid.js.org/intro/)

### Inferences
- Le « noyau » BPMN qui couvre la majorité des diagrammes réels tient en sept symboles : événement de début, événement de fin, tâche, flux de séquence, passerelle exclusive, pool, couloir. La passerelle parallèle, le sous-processus et l'événement intermédiaire temporisateur ou message forment le cercle suivant.
- Pour montrer UN cas d'une règle, l'objection de Silver pèse lourd : les cas intéressants sont souvent les exceptions (délai dépassé, annulation, erreur). Un outil limité au noyau statistique ne saurait pas les montrer. Il faut donc ajouter au noyau au moins l'événement temporisateur et l'événement de bordure.
- La liste Mermaid donne un bon indicateur de ce que les équipes logicielles dessinent sans outil spécialisé : organigramme, séquence, état, Gantt, parcours utilisateur, chronologie, Kanban. Les notations formelles de processus (BPMN, Petri, EPC, CMMN) restent le domaine d'outils dédiés.
- Les deux enquêtes UML sont anciennes (2004 et 2013) et les deux études BPMN chiffrées datent de 2007-2008. La tendance (usage partiel, petit sous-ensemble) est cohérente dans le temps, mais les pourcentages ne doivent pas être présentés comme actuels.

### Gaps
- Tableau des fréquences par symbole de zur Muehlen & Recker non obtenu (article payant). Seuls le résumé et la lecture de Silver sont disponibles.
- Résultats chiffrés de l'étude de 2023 sur 54 500 modèles non obtenus (accès refusé). C'est la source la plus récente et la plus large ; à lire si le rapport a besoin de pourcentages par élément.
- Aucune enquête récente (2023-2026) trouvée donnant la part de marché de BPMN face aux organigrammes, à EPC ou à UML activité.
- Contexte de l'étude de Petre **[non vérifié en session]** : de mémoire, 50 praticiens interrogés, dont 35 n'utilisaient pas UML et 11 l'utilisaient de façon sélective. À confirmer dans l'article (DOI 10.1109/icse.2013.6606618).
- Sous-classes de conformité de BPMN 2.0 (Descriptive, Analytic, Common Executable) **[non vérifié en session]** : la spécification définit elle-même un sous-ensemble « descriptif » restreint, ce qui serait la référence normative d'un noyau. À confirmer dans le chapitre « Conformance » de la spécification OMG.

---

## Question 2 — Catalogue : pour chaque notation, à quoi elle sert, ses briques visuelles, ses forces et faiblesses, son statut de standard, et le sous-ensemble minimal

### Takeaway
Toutes ces notations se ramènent à cinq familles de briques : nœuds et flèches (flux), boîtes d'états et transitions, lignes de vie et messages, barres sur un axe de temps, colonnes ou couloirs avec cartes. La seule limite de taille chiffrée et sourcée est celle des modèles de processus : au-delà de 50 éléments, la probabilité d'erreur dépasse 50 %.

### Cited Findings

**BPMN 2.0**
- Statut : spécification OMG formelle 2.0.2 (janvier 2014), aucune version ultérieure listée. — [OMG](https://www.omg.org/spec/BPMN/2.0.2/About-BPMN). Également ratifiée comme norme ISO 19510 ; la version 2.0 de janvier 2011 a ajouté une sémantique d'exécution. — [Wikipédia, BPMN](https://en.wikipedia.org/wiki/Business_Process_Model_and_Notation)
- Quatre catégories d'éléments : objets de flux (événements = cercles, activités = rectangles à coins arrondis, passerelles = losanges) ; objets de liaison (flux de séquence = trait plein fléché, flux de message = trait pointillé avec cercle vide au départ et flèche vide, association = trait pointillé) ; couloirs (pool, couloir) ; artefacts (objet de données, groupe, annotation). — [Wikipédia, BPMN](https://en.wikipedia.org/wiki/Business_Process_Model_and_Notation)
- Événements : début = bord fin simple ; intermédiaire = double bord, peut émettre ou recevoir ; fin = bord épais. Sous-processus replié marqué d'un « + » ; transaction à double bord ; activité d'appel à bord gras. Sept passerelles listées : exclusive, fondée sur événements, parallèle, inclusive, exclusive fondée sur événements, complexe, parallèle fondée sur événements. — [Wikipédia, BPMN](https://en.wikipedia.org/wiki/Business_Process_Model_and_Notation)
- Règle : « un flux de message ne peut jamais relier des activités ou des événements d'un même pool ». — [Wikipédia, BPMN](https://en.wikipedia.org/wiki/Business_Process_Model_and_Notation)

**Diagramme d'activité UML**
- Sert à représenter des enchaînements d'activités avec choix, itération et concurrence, pour des processus informatiques ou organisationnels, avec les flux de données associés. — [Wikipédia, Activity diagram](https://en.wikipedia.org/wiki/Activity_diagram)
- Briques : actions, losanges de décision, barres de séparation et de jonction des activités concurrentes, cercle noir (nœud initial), cercle noir entouré (nœud final), flèches d'ordre ; nœuds d'objet portant les données le long des flux d'objet. — [Wikipédia, Activity diagram](https://en.wikipedia.org/wiki/Activity_diagram)
- Depuis UML 2, la sémantique est « de type réseau de Petri » (jetons) ; en UML 1.x c'était une forme spécialisée de diagramme d'états. — [Wikipédia, Activity diagram](https://en.wikipedia.org/wiki/Activity_diagram)
- Conflit de sources : Wikipédia dit que les actions sont dessinées en forme de « stade » ; la spécification UML parle de rectangle à coins arrondis **[second point non vérifié en session]**. — [Wikipédia, Activity diagram](https://en.wikipedia.org/wiki/Activity_diagram)

**Machines à états UML et statecharts de Harel**
- Origine : Harel, « Statecharts: a visual formalism for complex systems », Science of Computer Programming 8(3), 1987, p. 231-274. Le formalisme répond à l'explosion du nombre d'états et au manque de modularité des automates plats par la hiérarchie d'états, les composants orthogonaux (concurrence), la communication par diffusion, les entrées par défaut et l'historique (extrait de recherche). — [Harel 1987, copie université d'Édimbourg](https://www.inf.ed.ac.uk/teaching/courses/seoc/2006_2007/resources/statecharts.pdf)
- La machine à états UML est une variante orientée objet des statecharts de Harel. États = rectangles à coins arrondis ; transitions = flèches étiquetées « déclencheur [garde] / action » ; transition initiale partant d'un disque plein ; états imbriqués (les sous-états héritent du comportement du sur-état) ; régions orthogonales ; actions d'entrée et de sortie ; transitions internes ; variables d'état étendu ; traitement « run-to-completion » (un événement est entièrement traité avant le suivant). — [Wikipédia, UML state machine](https://en.wikipedia.org/wiki/UML_state_machine)
- Exprime bien : systèmes réactifs pilotés par événements, où la réaction dépend de l'événement et de l'état courant ; factorisation de comportements communs par hiérarchie. — [Wikipédia, UML state machine](https://en.wikipedia.org/wiki/UML_state_machine)
- Exprime mal : « les diagrammes d'états représentent mal la séquence des traitements » ; la complexité d'un automate plat « croît beaucoup plus vite que celle du système décrit » ; la syntaxe des gardes et actions n'est pas définie par UML ; les pseudo-états encombrent le diagramme. — [Wikipédia, UML state machine](https://en.wikipedia.org/wiki/UML_state_machine)
- Standard ouvert d'exécution : SCXML 1.0, recommandation W3C du 1er septembre 2015, sémantique de Harel en XML, avec états imbriqués et élément « parallel ». — [W3C SCXML](https://www.w3.org/TR/scxml/)
- Taille : des expériences répliquées trouvent que le nombre de transitions, d'états et d'activités influence la compréhension, sans seuil validé ; les résultats sur les états composites se contredisent selon les expériences (extrait de recherche). — [Cruz-Lemus et al., Empirical Software Engineering 2009](https://link.springer.com/doi/10.1007/s10664-009-9106-z)

**Diagramme de séquence UML**
- Montre des interactions rangées dans l'ordre du temps : objets impliqués et messages échangés. Lecture de haut en bas. — [Wikipédia, Sequence diagram](https://en.wikipedia.org/wiki/Sequence_diagram)
- Briques : lignes de vie (traits verticaux parallèles) ; messages (flèches horizontales : tête pleine = appel synchrone, tête ouverte = message asynchrone, trait pointillé = réponse) ; boîtes d'activation (rectangles opaques sur la ligne de vie) ; destruction (X en bas de la ligne) ; message « trouvé » partant d'un disque plein ; porte sur le bord du cadre ; fragments combinés pour le parallélisme, les branches conditionnelles et les interactions optionnelles. — [Wikipédia, Sequence diagram](https://en.wikipedia.org/wiki/Sequence_diagram)
- Variante « diagramme de séquence système » : le système est une boîte noire unique, on ne montre que les événements qui franchissent sa frontière. — [Wikipédia, Sequence diagram](https://en.wikipedia.org/wiki/Sequence_diagram)
- Référence normative citée : OMG UML 2.5.1, formal/2017-12-05, décembre 2017. — [Wikipédia, Sequence diagram](https://en.wikipedia.org/wiki/Sequence_diagram)

**Message Sequence Charts (MSC)**
- Standard UIT-T Z.120 : première version en mars 1993, version 1996 (références, expressions en ligne, MSC de haut niveau), MSC 2000 (données, temps, appels distants), dernière version février 2011. Défini comme « langage de traces » pour le comportement de communication. — [Wikipédia, Message sequence chart](https://en.wikipedia.org/wiki/Message_sequence_chart)
- Briques : instances (lignes verticales avec boîte en haut, boîte ou croix en bas) ; messages (flèches horizontales) ; temporisateurs (démarrage, annulation, expiration) et contraintes de temps ; conditions (souvent un état de l'automate sous-jacent) ; actions (boîtes) ; expressions en ligne (alternative, séquence, exception, option, parallèle, boucle) ; références à un autre MSC ; corégion (événements non ordonnés) ; MSC de haut niveau pour enchaîner des MSC. — [Wikipédia, Message sequence chart](https://en.wikipedia.org/wiki/Message_sequence_chart)
- Différence avec UML : en MSC une ligne verticale est une entité autonome et une flèche est le plus souvent un message asynchrone ; en UML une ligne de vie est le plus souvent un objet et une flèche un appel synchrone. Critique de Harel : sémantique d'ordre partiel trop faible, d'où sa proposition des Live Sequence Charts. — [Wikipédia, Message sequence chart](https://en.wikipedia.org/wiki/Message_sequence_chart)

**Diagramme de temps UML (timing diagram)**
- Type de diagramme d'interaction centré sur les contraintes de temps ; sert à explorer le comportement d'objets pendant une période. Le temps croît de gauche à droite ; les lignes de vie sont empilées en compartiments. Deux notations : concise et robuste. — [Wikipédia, Timing diagram (UML)](https://en.wikipedia.org/wiki/Timing_diagram_(Unified_Modeling_Language))

**Réseaux de Petri**
- Graphe biparti orienté à deux types d'éléments, places et transitions ; dû à Carl Adam Petri (thèse de 1962). Places = cercles ; transitions = rectangles étroits ; arcs orientés uniquement entre place et transition ; jetons = points dans les places ; le marquage est la répartition des jetons. — [Wikipédia, Petri net](https://en.wikipedia.org/wiki/Petri_net)
- Règle de tir : une transition est activable quand ses places d'entrée contiennent assez de jetons ; le tir consomme les jetons d'entrée et en produit en sortie ; il est atomique ; sans politique d'exécution, l'ordre de tir est non déterministe. — [Wikipédia, Petri net](https://en.wikipedia.org/wiki/Petri_net)
- Extensions : réseaux colorés (jetons typés), temporisés et stochastiques, à priorités, hiérarchiques, arcs inhibiteurs ; les workflow nets sont une sous-classe pour les processus (une place source, une place puits, propriété de validité « soundness »). — [Wikipédia, Petri net](https://en.wikipedia.org/wiki/Petri_net)
- Par rapport aux diagrammes d'activité UML, à BPMN et aux EPC : mêmes notions de choix, itération et concurrence, mais les réseaux de Petri ont « une définition mathématique exacte de leur sémantique d'exécution » (affirmation marquée « référence nécessaire » sur la page). — [Wikipédia, Petri net](https://en.wikipedia.org/wiki/Petri_net)

**EPC (chaînes de processus événementielles)**
- Créées en 1992 par Keller, Nüttgens et Scheer (université de la Sarre, projet avec SAP), technique centrale d'ARIS. — [Wikipédia, Event-driven process chain](https://en.wikipedia.org/wiki/Event-driven_process_chain)
- Briques : événement = hexagone (élément passif) ; fonction = rectangle à coins arrondis (élément actif) ; unité d'organisation = ellipse avec trait vertical ; objet d'information, de matière ou de ressource = rectangle ; connecteurs logiques ET, OU, OU exclusif ; flux de contrôle = flèche en pointillé ; chemin de processus (renvoi vers un autre EPC). Un EPC doit commencer et finir par un événement. — [Wikipédia, Event-driven process chain](https://en.wikipedia.org/wiki/Event-driven_process_chain)
- Faiblesse : les structures non triviales avec parallélisme ont une sémantique d'exécution mal définie ; la sémantique est « non locale ». — [Wikipédia, Event-driven process chain](https://en.wikipedia.org/wiki/Event-driven_process_chain). Les lignes directrices 7PMG recommandent d'éviter les connecteurs OU à cause des « ambiguïtés de la sémantique de la jonction OU, qui mènent à des paradoxes et à des problèmes d'implémentation ». — [Mendling, Reijers, van der Aalst, 7PMG](https://www.vdaalst.com/publications/p574.pdf)

**CMMN (gestion de cas)**
- Spécification OMG : version 1.0 en mai 2014, version 1.1 formelle en décembre 2016, aucune version ultérieure listée. Définit un méta-modèle, une notation et un format d'échange pour exprimer un « cas ». — [OMG, About CMMN 1.1](https://www.omg.org/spec/CMMN/1.1/About-CMMN)
- Positionnement : BPMN traite les processus prévisibles ; CMMN vise les processus « intrinsèquement imprévisibles, non répétables, faiblement structurés et à forte intensité de connaissance ». — [Wikipédia, CMMN](https://en.wikipedia.org/wiki/CMMN)

**Organigramme (flowchart)**
- Représente un processus ou un algorithme par des boîtes de formes variées reliées par des flèches. Origine : « flow process chart » des Gilbreth présenté à l'ASME en 1921. Norme en vigueur : ISO 5807, publiée en 1985. — [Wikipédia, Flowchart](https://en.wikipedia.org/wiki/Flowchart)
- Symboles courants : terminal (forme de stade, début ou fin) ; traitement (rectangle) ; décision (losange) ; entrée/sortie (parallélogramme) ; ligne de flux (flèche) ; connecteur sur la page (cercle) et hors page (pentagone) ; annotation ; traitement prédéfini (rectangle à bords verticaux doublés) ; base de données (cylindre) ; document (base ondulée). Le parallélisme se note par des barres horizontales. — [Wikipédia, Flowchart](https://en.wikipedia.org/wiki/Flowchart)
- L'organigramme interfonctionnel découpe le dessin par unité d'organisation, pour situer la responsabilité de chaque action ou décision. — [Wikipédia, Flowchart](https://en.wikipedia.org/wiki/Flowchart)
- Faiblesse : pas de moyen propre d'exprimer la concurrence ; les barres ne règlent le problème qu'en partie. — [Wikipédia, Activity diagram](https://en.wikipedia.org/wiki/Activity_diagram)

**Diagramme à couloirs (swimlane)**
- Élément de diagramme qui distingue visuellement qui est responsable de chaque sous-processus : un couloir par personne, groupe ou sous-processus ; disposition horizontale ou verticale. Apparu dans les années 1940 comme « diagramme multi-colonnes » ; nom popularisé par Rummler et Brache (1990). Présent dans BPMN et dans les diagrammes d'activité UML. — [Wikipédia, Swimlane](https://en.wikipedia.org/wiki/Swimlane)

**Diagramme de Gantt**
- Diagramme à barres d'un planning : tâches sur l'axe vertical, temps sur l'axe horizontal, largeur de barre = durée. Les versions modernes ajoutent les dépendances, l'avancement (barre ombrée selon le pourcentage réalisé) et un trait vertical « aujourd'hui » ; chemin critique en couleur. Premier outil de ce type : harmonogramme d'Adamiecki (1896) ; Gantt vers 1910-1915. — [Wikipédia, Gantt chart](https://en.wikipedia.org/wiki/Gantt_chart)
- Force : lisible sans formation. Faiblesse : avec les liens de dépendance, il « devient vite encombré sauf dans les cas les plus simples ». — [Wikipédia, Gantt chart](https://en.wikipedia.org/wiki/Gantt_chart)

**Carte de flux de valeur (VSM)**
- Méthode Lean pour analyser l'état actuel et concevoir un état futur ; montre les étapes critiques et quantifie temps et volumes à chaque étape, pour le flux de matière et le flux d'information. Classe les opérations en valeur ajoutée, sans valeur ajoutée, sans valeur ajoutée mais nécessaires. Emploie « habituellement » des symboles standards. — [Wikipédia, Value-stream mapping](https://en.wikipedia.org/wiki/Value-stream_mapping)
- Symboles (extraits de recherche) : stock = triangle ; flèche « poussée » = matière passant d'une étape à la suivante ; boîte de données = informations nécessaires à l'analyse ; ligne de temps en bas = temps à valeur ajoutée et temps d'attente, pour calculer le délai total ; éclair « kaizen » = besoin d'amélioration. Les variantes graphiques existent d'un outil à l'autre, le sens des symboles de base reste stable. — [Visual Paradigm, guide VSM](https://online.visual-paradigm.com/knowledge/value-stream-mapping/what-is-value-stream-mapping/) ; [Creately, symboles VSM](https://creately.com/guides/value-stream-mapping-symbols/)

**Carte de parcours utilisateur (journey map)**
- « Visualisation du processus qu'une personne traverse pour atteindre un but. » Composants : un acteur (un seul par carte), un scénario et des attentes, des phases, puis par phase des actions, des pensées et des émotions (les émotions forment une ligne continue avec ses hauts et ses bas), enfin des opportunités. Disposition : acteur et scénario en haut, phases au milieu, enseignements en bas. — [Nielsen Norman Group, Journey Mapping 101](https://www.nngroup.com/articles/journey-mapping-101/)
- Variante : le « service blueprint » prolonge la carte en montrant ce qui se passe en coulisses (personnes, processus, systèmes). — [Nielsen Norman Group](https://www.nngroup.com/articles/journey-mapping-101/)

**Graphe de dépendances (DAG des moteurs d'orchestration)**
- Dans Airflow, « chaque nœud représente une tâche, les arêtes montrent les dépendances ». — [Documentation Airflow 3.4.0, interface](https://airflow.apache.org/docs/apache-airflow/stable/ui.html)
- Dans AWS Step Functions, le graphe d'exécution affiche les états, dont les états « Map » (itérations) et « Parallel » (branches) ; le graphe peut être orienté horizontalement ou verticalement. — [Documentation AWS Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-view-execution-details.html)
- Limite d'un outil : la vue de dépendances de Jaeger se désactive au-delà de 200 services par défaut. — [Documentation Jaeger, interface](https://www.jaegertracing.io/docs/latest/frontend-ui/)

**Tableau Kanban**
- Outil visuel pour suivre le travail à travers les étapes d'un processus : une colonne par étape, une carte par élément de travail, les cartes vont de gauche à droite ; couloirs horizontaux possibles ; limites de travail en cours nécessaires pour appliquer la méthode Kanban. Jeux de colonnes typiques : « à faire, en cours, fait », ou « Backlog, Ready, Coding, Testing, Approval, Done ». Sert à repérer goulots et surcharges. — [Wikipédia, Kanban board](https://en.wikipedia.org/wiki/Kanban_board)

**Limites de taille (toutes notations de processus)**
- Lignes directrices 7PMG (Mendling, Reijers, van der Aalst, 2010) : G1 utiliser le moins d'éléments possible ; G2 limiter les chemins par élément ; G3 un seul événement de début et un seul de fin ; G4 modéliser de façon structurée (chaque séparation a sa jonction du même type) ; G5 éviter les connecteurs OU ; G6 libellés verbe-objet ; G7 décomposer un modèle de plus de 50 éléments. Justification de G7 : « pour les modèles de plus de 50 éléments, la probabilité d'erreur tend à dépasser 50 % ». — [7PMG, texte de l'article](https://www.vdaalst.com/publications/p574.pdf)
- Un modèle BPMN moyen n'utilise qu'environ 9 symboles différents. — [Stevens Institute](https://researchwith.stevens.edu/en/publications/how-much-language-is-enough-theoretical-and-practical-use-of-the-/)

### Inferences

Tableau de synthèse. Les colonnes « sous-ensemble minimal » et « seuil de lisibilité » sont mes propositions, fondées sur les faits ci-dessus et sur des connaissances générales **[non vérifiées en session]** ; seul le seuil de 50 éléments est sourcé.

| Notation | Exprime bien | Exprime mal | Sous-ensemble minimal proposé | Seuil de lisibilité (estimation) | Standard ouvert |
|---|---|---|---|---|---|
| BPMN 2.0 | Enchaînement d'étapes, branches, parallélisme, plusieurs acteurs, délais et exceptions | États durables d'un objet, règles de décision détaillées, travail non structuré | Début, fin, tâche, flux de séquence, passerelle exclusive, passerelle parallèle, pool, couloir, événement temporisateur, événement de bordure, flux de message | 50 éléments (sourcé, 7PMG) | Oui (OMG, ISO 19510) |
| Activité UML | Comme BPMN, plus flux d'objets | Peu connu des métiers ; moins riche en événements | Nœud initial, nœud final, action, décision/fusion, barre de séparation/jonction, partition | Comme BPMN | Oui (OMG UML 2.5.1) |
| Machine à états / statechart | Cycle de vie d'un objet, réaction à des événements selon l'état | Ordre des traitements, plusieurs acteurs | État, transition « événement [garde] / action », état initial, état final, état composite | 7 à 15 états par niveau | Oui (OMG ; W3C SCXML) |
| Séquence UML / MSC | Un scénario précis entre plusieurs acteurs, ordre des messages | Toutes les variantes d'une règle ; logique interne d'un acteur | Ligne de vie, message, réponse, activation, cadres alt / opt / loop | 5 à 8 lignes de vie, 20 à 30 messages | Oui (OMG ; UIT-T Z.120) |
| Diagramme de temps | Durées, échéances, changement d'état sur un axe de temps | Branches et choix | Ligne de vie, ligne d'état, graduation, contrainte de durée | 3 à 6 lignes | Oui (OMG) |
| Réseau de Petri | Concurrence, synchronisation, ressources partagées, vérification formelle | Lisibilité métier, données, acteurs | Place, transition, arc, jeton | 20 à 30 nœuds | Oui (norme ISO/CEI 15909, à vérifier) |
| EPC | Enchaînement événement-fonction, lien avec l'organisation | Sémantique d'exécution (jonction OU) | Événement, fonction, connecteurs ET / OU exclusif, flux | 50 éléments | Non (standard de fait ARIS/SAP) |
| CMMN | Travail au cas par cas, tâches facultatives, jalons | Séquence stricte ; notation peu connue | Cas, étape, tâche, jalon, critère d'entrée, critère de sortie | 15 à 20 éléments | Oui (OMG) |
| Organigramme | Suite d'étapes et décisions, compris de tous | Parallélisme, temps, acteurs (sans couloirs) | Début/fin, traitement, décision, flèche | 15 à 25 boîtes | Oui (ISO 5807:1985), peu suivi |
| Couloirs | Qui fait quoi | Rien de plus que la notation portée | Couloir + noyau de l'organigramme | 4 à 7 couloirs | Via BPMN ou UML |
| Gantt / chronologie | Durées, chevauchements, échéances, avancement | Branches conditionnelles, raisons d'un choix | Ligne par tâche, barre, jalon, lien, trait « maintenant » | 20 à 40 lignes | Non |
| Carte de flux de valeur | Délai total, attentes, stocks entre étapes | Branches, exceptions | Boîte d'étape, boîte de données, triangle de stock, flèche, ligne de temps | 10 à 15 étapes | Conventions Lean (norme ISO 22468 à vérifier) |
| Parcours utilisateur | Vécu d'un acteur, phase par phase | Logique de décision, plusieurs acteurs | Phases, actions, ligne d'émotion, opportunités | 4 à 7 phases | Non |
| DAG d'orchestration | Dépendances entre tâches, parallélisme, état de chaque tâche | Boucles, attente d'événements externes, acteurs humains | Nœud tâche, arête de dépendance, groupe | Quelques dizaines de nœuds | Non (propre à chaque moteur) |
| Tableau Kanban | Où en est chaque élément, goulots | Ordre obligatoire des transitions, branches, temps | Colonne d'état, carte, limite de travail en cours, couloir | 5 à 8 colonnes | Non |

- Détails de notation utiles au rapport mais **[non vérifiés en session]** :
  - BPMN : types d'événements (message, temporisateur, erreur, escalade, signal, conditionnel, compensation, lien, terminaison) ; événement de bordure attaché au bord d'une activité, à double trait plein s'il interrompt, à double trait pointillé s'il n'interrompt pas ; types de tâches (utilisateur, service, envoi, réception, manuelle, règle métier, script) ; marqueurs de boucle et d'instances multiples.
  - Activité UML : nœud de fin de flux (cercle barré), action d'envoi de signal (pentagone convexe), d'acceptation d'événement (pentagone concave), d'événement temporel (sablier), région interruptible (cadre pointillé), partitions.
  - Machine à états UML : pseudo-états choix (losange), jonction, historique superficiel (H) et profond (H*), points d'entrée et de sortie, terminaison ; événements temporels « after(...) » et « at(...) ».
  - Séquence UML : opérateurs alt, opt, loop, par, break, critical, neg, assert, strict, seq, ignore, consider ; cadre « ref » ; contraintes de durée entre accolades.
  - Diagramme de temps UML : ligne d'état en escalier (notation robuste), bandes de valeur avec croisements (notation concise), règle graduée, contraintes de durée.
  - CMMN : modèle de cas en forme de dossier ; étape = rectangle à coins coupés ; tâche = rectangle arrondi avec icône de type (humaine, processus, cas, décision) ; jalon = pastille allongée ; écouteur d'événement = double cercle (temporisateur, utilisateur) ; critères d'entrée (losange blanc) et de sortie (losange noir) sur le bord ; éléments facultatifs à bord pointillé ; décorateurs activation manuelle, obligatoire « ! », répétition « # », achèvement automatique.
  - Gantt : jalon en losange ; quatre types de liens (fin-début, début-début, fin-fin, début-fin).
- Pour montrer un cas pas à pas, trois familles suffisent à couvrir presque tous les besoins : un diagramme de flux à couloirs (BPMN réduit), un diagramme d'états, un diagramme de séquence ou une chronologie. Les autres notations sont soit des variantes (activité UML, EPC, organigramme), soit des outils d'analyse d'ensemble plutôt que de cas unique (VSM, Kanban, parcours utilisateur).

### Gaps
- Aucun seuil de lisibilité chiffré et sourcé trouvé pour les diagrammes de séquence, les diagrammes d'états, les Gantt, les DAG ou les tableaux Kanban. Les valeurs du tableau sont des estimations de pratique, à présenter comme telles.
- Notation détaillée de CMMN, des événements BPMN et du diagramme de temps UML non lue dans les spécifications pendant cette session (pages secondaires inaccessibles ou trop succinctes). À confirmer dans les spécifications OMG avant de figer une légende.
- Norme ISO/CEI 15909 (réseaux de Petri de haut niveau, format PNML) et norme ISO 22468 (gestion du flux de valeur) : existence connue de mémoire, non confirmée par les sources lues.
- Adoption actuelle de CMMN non documentée ; de mémoire, plusieurs éditeurs de moteurs l'ont mis en maintenance ou retiré **[non vérifié en session]**.

---

## Question 3 — Comment les outils existants montrent-ils UNE exécution ou UN scénario sur le diagramme ?

### Takeaway
Les outils combinent toujours le même petit jeu de techniques : colorer chaque nœud selon son état, surligner le chemin parcouru, marquer la position courante (jeton ou pastille), et synchroniser le diagramme avec un journal d'événements, un panneau de données et une barre de temps. L'animation de jetons sert surtout à apprendre ; les consoles d'exploitation préfèrent la coloration d'état et la liste d'événements.

### Cited Findings

**Simulation de jetons sur BPMN**
- bpmn-js-token-simulation : simulateur de jetons conforme à BPMN 2.0, construit comme extension de bpmn-js, ajouté comme module à l'éditeur ou à la visionneuse ; licence MIT. — [Dépôt GitHub bpmn-io/bpmn-js-token-simulation](https://github.com/bpmn-io/bpmn-js-token-simulation)
- Dans Camunda Web Modeler : « lancer, mettre en pause et avancer pas à pas dans un processus » ; on démarre en cliquant sur l'icône de lecture qui apparaît sur un événement de début ; palette lecture/pause, remise à zéro, affichage du journal de simulation ; réglage de la vitesse d'animation ; l'édition est désactivée pendant la simulation. Avertissement : « outil d'apprentissage de BPMN, pas un moteur BPMN complet ». — [Documentation Camunda, Token simulation](https://docs.camunda.io/docs/components/modeler/web-modeler/token-simulation)
- Principes de conception : « un jeton qui bouge vaut tout un tas de diagrammes BPMN statiques » ; l'accent est mis sur les comportements d'attente, de jonction et de séparation ; les visualisations se superposent au diagramme réel ; ce n'est ni un simulateur de traitement par lots, ni un outil d'analyse, ni un vérificateur d'interblocage ; moteur à instance unique. — [Présentation « Making of bpmn-js Token Simulation »](https://nikku.github.io/talks/2021-token-simulation)
- Depuis la version 0.32.0, les passerelles inclusives sont prises en charge, ce qui complète le support de « tous les éléments BPMN sans magie » ; l'outil est utilisé en formation BPMN. — [Blog bpmn.io, 2023](https://bpmn.io/blog/posts/2023-the-case-for-bpmn-token-simulation)
- Limite signalée par les auteurs sur le forum (fil ancien, peut-être dépassé) : la simulation vise des scénarios simples sans participants multiples ; les flux de message ne sont pas pris en charge. — [Forum Camunda](https://forum.camunda.io/t/token-simulation-user-guide/17002)

**Consoles de moteurs de processus**
- Camunda 7 Cockpit, vue d'une instance : diagramme BPMN interactif ; arbre des instances d'activité contenant « un nœud pour chaque activité actuellement active » ; diagramme, arbre et table des variables restent synchronisés ; sélectionner un nœud de l'arbre le surligne dans le diagramme ; panneau de détail (variables, incidents, instances appelées, tâches) ; surcouche sur les activités d'appel pour descendre dans l'instance appelée. — [Documentation Camunda 7.24, Process Instance View](https://docs.camunda.org/manual/latest/webapps/cockpit/bpmn/process-instance-view/)
- Camunda 7 Cockpit, historique : journal d'audit des activités (début, fin, état) et historique des valeurs de variables ; carte de chaleur superposée au diagramme montrant les nœuds et flux les plus parcourus (vue de définition). Fonction réservée à l'édition entreprise. — [Documentation Camunda 7, History in Cockpit](https://docs.camunda.org/manual/latest/webapps/cockpit/bpmn/process-history-views/)
- Camunda 8 Operate, page d'une instance : en-tête (clé, version, état), diagramme montrant la progression, panneau « Instance History » listant les éléments avec recherche et filtre d'état, onglets Variables, Listeners, Operations Log, et Incidents s'il y en a ; cliquer un élément ouvre ses détails. — [Documentation Camunda 8, navigation Operate](https://docs.camunda.io/docs/next/components/operate/userguide/basic-operate-navigation/)
- Exemple d'intégration par l'API d'Operate avec bpmn-js : « des flèches bleues montrent le chemin parcouru et un point vert montre l'état courant ». — [Blog Camunda, septembre 2023](https://camunda.com/blog/2023/09/monitor-process-instance-progress-bpmn-diagram-operate-api/)

**Moteurs d'orchestration et graphes de tâches**
- AWS Step Functions, détail d'une exécution : vue graphe avec légende de l'état d'exécution ; choisir une étape ouvre ses détails (entrée, sortie, durée, définition, tentatives) ; vue tableau synchronisée avec le graphe ; colonne « Timeline » optionnelle montrant la durée de chaque état sur une barre linéaire colorée (segments rouges pour les tentatives échouées, gris clair pour l'attente entre tentatives) ; table des événements colorée par statut ; sélecteur d'itération pour les états Map ; le message d'erreur renvoie à l'étape fautive, surlignée dans le graphe et le tableau. — [Documentation AWS Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-view-execution-details.html)
- Airflow 3.4.0 : vue grille (« chaque ligne est une tâche, chaque colonne une exécution ») ; vue graphe où l'on choisit une exécution pour superposer l'état de chaque tâche, chaque nœud portant un indicateur de durée ; dans le détail d'une exécution, chaque ligne de tâche comporte une mini-barre de type Gantt ; tâches en échec ou relancées repérées par couleur et info-bulle. — [Documentation Airflow 3.4.0](https://airflow.apache.org/docs/apache-airflow/stable/ui.html)
- Temporal : quatre vues de l'historique d'une exécution — Timeline (ordre chronologique avec résumé), All, Compact (regroupement logique des activités, signaux et temporisateurs), JSON ; onglet Relationships (arbre parent-enfants) ; activités en attente ; pile d'appels montrant où le code attend. — [Documentation Temporal Web UI](https://docs.temporal.io/web-ui)
- Temporal, principe de couleur : la couleur indique d'abord le statut d'un événement, ensuite sa catégorie ; des lignes relient les événements liés (extrait de recherche). — [Blog Temporal](https://temporal.io/blog/the-dark-magic-of-workflow-exploration)

**Machines à états**
- Stately Inspector : à partir de trois types d'événements d'inspection (création d'acteur, communication entre acteurs, changement d'état), l'outil produit en temps réel deux diagrammes : diagramme de machine à états et diagramme de séquence. — [Documentation Stately Inspector](https://stately.ai/docs/inspector)
- Inspecteur XState v4 : la machine est dessinée et son état courant est surligné ; les événements suivants mettent à jour cet état (extrait de recherche). — [Documentation XState v4, inspector](https://stately.ai/docs/xstate-v4/tools/inspector)

**Visionneuses de traces**
- Jaeger : page d'une trace avec en-tête, mini-carte et chronologie des segments ; vue « graphe de trace » ; mise en évidence du chemin critique de chaque segment (activée par défaut) ; vue JSON. — [Documentation Jaeger, interface](https://www.jaegertracing.io/docs/latest/frontend-ui/)

**Fouille de processus**
- Rejeu par jetons (token-based replay) : on rejoue une trace sur le modèle en comptant les jetons produits, consommés, manquants et restants ; faiblesse connue : « inondation de jetons » sur les modèles concurrents ; les alignements sont devenus la technique de référence (extrait de recherche). — [Wikipédia, Token-based replay](https://en.wikipedia.org/wiki/Token-based_replay)

### Inferences
- Répertoire des techniques observées, de la plus pédagogique à la plus opérationnelle :
  1. Jeton animé qui suit les flèches (bpmn-js token simulation).
  2. Commandes de lecture : lecture, pause, pas à pas, vitesse, remise à zéro.
  3. Position courante marquée par une pastille ou un surlignage (point vert, état surligné).
  4. Chemin parcouru surligné, le reste du diagramme restant visible mais atténué (flèches bleues).
  5. Coloration de chaque nœud par statut : réussi, en cours, échoué, sauté, en attente (Step Functions, Airflow).
  6. Panneaux synchronisés : journal ou arbre d'événements, données d'entrée et de sortie de l'étape choisie, variables (Cockpit, Operate, Step Functions).
  7. Barre de temps du même cas : durée de chaque étape, tentatives, attentes (Step Functions, Airflow, Temporal, Jaeger).
  8. Second diagramme dérivé de la même trace : diagramme de séquence produit à partir des événements d'une machine à états (Stately).
- Appariement notation / technique naturelle : flux (BPMN, activité, EPC, organigramme, DAG) → jeton ou chemin surligné plus statut des nœuds ; états → état courant surligné et transition empruntée ; séquence → révélation progressive des messages de haut en bas, activation sur la ligne de vie ; Gantt et chronologie → curseur « maintenant » et barres qui se remplissent ; Kanban → carte qui change de colonne ; Petri → jetons dans les places (c'est la notation dont l'exécution est native).
- Point d'attention licences : le module de simulation de jetons est sous licence MIT (vérifié). La bibliothèque bpmn-js sur laquelle il repose a, de mémoire, une licence propre à bpmn.io imposant de conserver le logo **[non vérifié en session]** ; à contrôler avant toute réutilisation. La licence de Mermaid n'est pas indiquée sur la page consultée (MIT de mémoire, **[non vérifié en session]**).
- Les consoles d'exploitation montrent l'état à un instant donné et l'historique sous forme de liste ; la relecture pas à pas d'un cas terminé, avec curseur de temps, est peu documentée dans ces outils. C'est un espace libre pour un outil d'explication de règles.

### Gaps
- Détail visuel de la simulation de jetons (couleur par instance, compteurs sur les éléments, points de pause, choix manuel de la branche d'une passerelle exclusive) non confirmé par les pages lues ; à vérifier dans le dépôt ou sur la démonstration en ligne.
- Marqueurs exacts d'Operate sur le diagramme (badges actif, incident, terminé, annulé ; surlignage des flux parcourus) non décrits dans la page de navigation ; le tutoriel d'API correspondant est en 404.
- Outils d'animation de fouille de processus (rejeu animé de cas sur la carte de processus) : aucune source primaire trouvée.
- Aucune légende de couleurs chiffrée trouvée pour Airflow, Step Functions ou Temporal.
- Visionneuse Stately : la documentation lue ne décrit pas le rendu de l'état actif dans la version actuelle (seule la documentation v4 le dit).
- Statut actuel de Camunda 7 (fin de vie de l'édition communautaire, de mémoire) **[non vérifié en session]**.

---

## Question 4 — Quelles notations traitent le temps (échéances, délais, durées) et lesquelles traitent plusieurs acteurs ?

### Takeaway
Deux axes séparent les notations. Celles qui ont un axe de temps (Gantt, chronologie, diagramme de temps, carte de flux de valeur) montrent bien les durées mais mal les choix. Celles qui ont des couloirs ou des lignes de vie (BPMN, activité UML, séquence, MSC) montrent bien plusieurs acteurs. Seuls BPMN, MSC et les machines à états combinent des échéances explicites avec une logique de branchement.

### Cited Findings

**Temps**
- Diagramme de temps UML : centré sur les contraintes de temps, le temps croît de gauche à droite. — [Wikipédia, Timing diagram (UML)](https://en.wikipedia.org/wiki/Timing_diagram_(Unified_Modeling_Language))
- MSC : temporisateurs (démarrage, annulation, expiration) et contraintes de temps font partie de la notation ; MSC 2000 a affiné le traitement du temps. — [Wikipédia, Message sequence chart](https://en.wikipedia.org/wiki/Message_sequence_chart)
- Séquence UML : l'ordre des messages est donné par l'axe vertical ; c'est un ordre, pas une échelle de durée. — [Wikipédia, Sequence diagram](https://en.wikipedia.org/wiki/Sequence_diagram)
- Gantt : la largeur des barres donne la durée ; trait « aujourd'hui » et ombrage d'avancement. — [Wikipédia, Gantt chart](https://en.wikipedia.org/wiki/Gantt_chart)
- Carte de flux de valeur : la ligne de temps sépare temps à valeur ajoutée et temps d'attente pour calculer le délai total (extrait de recherche). — [Visual Paradigm, guide VSM](https://online.visual-paradigm.com/knowledge/value-stream-mapping/what-is-value-stream-mapping/)
- BPMN : un délai dépassé ou une annulation en cours de route se modélisent par des événements non sollicités déclenchant un flux d'exception. — [BPM Institute](https://www.bpminstitute.org/resources/articles/bpms-watch-how-much-bpmn-do-you-need/)
- Réseaux de Petri : le temps n'est pas dans la notation de base ; il existe des extensions temporisées et stochastiques. — [Wikipédia, Petri net](https://en.wikipedia.org/wiki/Petri_net)
- Moteurs d'orchestration : Step Functions affiche pour chaque tâche les délais « TimeoutSeconds » et « HeartbeatSeconds », et montre sur la barre de temps les tentatives et l'attente entre tentatives. — [Documentation AWS Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-view-execution-details.html). Temporal regroupe activités, signaux et temporisateurs dans sa vue compacte. — [Documentation Temporal Web UI](https://docs.temporal.io/web-ui)
- Parcours utilisateur : adapté aux « scénarios qui se déroulent dans le temps », découpés en phases et non en durées mesurées. — [Nielsen Norman Group](https://www.nngroup.com/articles/journey-mapping-101/)

**Plusieurs acteurs**
- BPMN : pools et couloirs ; le flux de message relie uniquement des pools différents. — [Wikipédia, BPMN](https://en.wikipedia.org/wiki/Business_Process_Model_and_Notation)
- Couloirs : un couloir par personne, groupe ou sous-processus ; utilisés dans BPMN et les diagrammes d'activité UML. — [Wikipédia, Swimlane](https://en.wikipedia.org/wiki/Swimlane)
- Séquence UML : une ligne de vie par participant. — [Wikipédia, Sequence diagram](https://en.wikipedia.org/wiki/Sequence_diagram). MSC : chaque ligne verticale est une entité d'exécution autonome. — [Wikipédia, Message sequence chart](https://en.wikipedia.org/wiki/Message_sequence_chart)
- EPC : unité d'organisation et responsable de processus rattachés aux fonctions. — [Wikipédia, Event-driven process chain](https://en.wikipedia.org/wiki/Event-driven_process_chain)
- Machine à états UML : décrit un seul objet ; les régions orthogonales expriment la concurrence interne, pas des acteurs distincts. — [Wikipédia, UML state machine](https://en.wikipedia.org/wiki/UML_state_machine). L'outil Stately complète par un diagramme de séquence pour la communication entre acteurs. — [Documentation Stately Inspector](https://stately.ai/docs/inspector)
- Parcours utilisateur : un seul acteur par carte ; le « service blueprint » ajoute les personnes et systèmes en coulisses. — [Nielsen Norman Group](https://www.nngroup.com/articles/journey-mapping-101/)
- Kanban : couloirs horizontaux possibles pour distinguer types de travail ou équipes. — [Wikipédia, Kanban board](https://en.wikipedia.org/wiki/Kanban_board)
- Organigramme : la variante interfonctionnelle situe la responsabilité de chaque action ou décision. — [Wikipédia, Flowchart](https://en.wikipedia.org/wiki/Flowchart)

### Inferences

Matrice de synthèse (mon appréciation à partir des faits ci-dessus ; « ++ » natif et central, « + » possible, « – » absent ou artificiel).

| Notation | Échéance / délai déclencheur | Durée mesurée sur un axe | Plusieurs acteurs | Branches et choix |
|---|---|---|---|---|
| BPMN 2.0 | ++ (événement temporisateur, bordure) | – | ++ (pools, couloirs, messages) | ++ |
| Activité UML | + (événement temporel) | – | + (partitions) | ++ |
| Machine à états | + (transition temporelle) | – | – | + (gardes) |
| Séquence UML | + (contraintes) | – (ordre seulement) | ++ | + (cadres alt/opt) |
| MSC | ++ (temporisateurs) | – | ++ | + |
| Diagramme de temps | ++ | ++ | + | – |
| Réseau de Petri | + (extensions) | – | – | ++ |
| EPC | – | – | + (unités d'organisation) | ++ |
| CMMN | + (écouteur temporisé) | – | + (rôles) | + (critères) |
| Organigramme | – | – | + (variante à couloirs) | ++ |
| Gantt / chronologie | + (jalons) | ++ | + (ligne par ressource) | – |
| Carte de flux de valeur | – | ++ | – | – |
| Parcours utilisateur | – | + (phases) | – (un acteur) | – |
| DAG d'orchestration | + (délais, tentatives) | + (vue Gantt de l'exécution) | – | + |
| Kanban | – | – | + (couloirs) | – |

- Aucune notation ne couvre seule les quatre colonnes. Les outils d'exploitation contournent le problème en associant deux vues synchronisées du même cas : le graphe (choix, acteurs) et la barre de temps (durées). C'est le modèle à retenir pour montrer un cas d'une règle comportant des délais.
- Pour un cas concret, le temps réel écoulé appartient à l'exécution et non au modèle : même une notation sans axe de temps (BPMN, états) peut afficher les durées par des étiquettes sur les étapes ou par une chronologie jointe.
- Pour une règle à échéance (« si pas de réponse sous N jours, alors… »), les trois représentations directes sont : l'événement temporisateur de bordure en BPMN, la transition temporelle d'une machine à états, le temporisateur d'un MSC. Sur un Gantt ou une chronologie, l'échéance n'est qu'un repère, la conséquence n'est pas visible.

### Gaps
- Les cotes « + » pour CMMN, activité UML, machine à états et séquence UML reposent sur des éléments de notation **[non vérifiés en session]** (écouteur temporisé, action d'événement temporel, déclencheur « after », contraintes de durée).
- Aucune étude comparative trouvée mesurant la compréhension du temps ou des acteurs selon la notation auprès de lecteurs non techniques.
- Service blueprint et chorégraphie BPMN (deux notations multi-acteurs) non approfondis.
