# Typologie des règles métier et des comportements de processus (ce qu'un outil doit pouvoir représenter)

Notes de recherche, état au 21 novembre 2026. Conventions de fiabilité utilisées dans les « Cited Findings » :
- **[lu]** = texte de la source lu directement pendant cette recherche (page ou PDF extrait).
- **[résumé]** = information issue d'un résumé de résultat de recherche ou d'une source secondaire ; à confirmer avant citation littérale.
- Les exemples marqués « exemple illustratif » sont rédigés par le chercheur pour les besoins de l'inventaire ; ils ne proviennent pas d'une source.

---

## Question 1 — Quelles taxonomies de règles métier font autorité, et comment classent-elles les règles ?

### Takeaway
Toutes les taxonomies de référence convergent vers la même coupure : d'un côté les règles **définitionnelles/structurelles** (termes, faits, calculs, inférences, décisions : elles ne peuvent pas être « violées », seulement mal calculées), de l'autre les règles **comportementales/opératives** (contraintes, autorisations, prérequis, échéances, réactions : elles peuvent être violées et portent un niveau d'application). Il n'existe pas de classification unique acceptée (une revue de 2019 en recense dix), mais environ quatorze types élémentaires reviennent partout et suffisent comme inventaire de travail.

### Cited Findings

#### a) Business Rules Group (BRG, ex-GUIDE), « Defining Business Rules ~ What Are They Really? » — source ancienne (rév. 1.3, juillet 2000 ; travaux initiaux des années 1990) mais toujours la référence d'origine
- Le document est le « Final Report, revision 1.3, July 2000 » du Business Rules Group, « formerly known as the GUIDE Business Rules Project », préparé par David Hay et Keri Anderson Healy (chef de projet Allan Kolber) **[lu]** — [BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)
- Définition de la règle métier (Hay & Healy 2000) : « a statement that defines or constrains some aspect of the business, intending to assert business structure or to control the behavior of the business » **[lu, citée dans]** — [de Haan, Spruit & Zoet 2019](https://liacs.leidenuniv.nl/~spruitmr/pub/2019%20-%20Haan%20Spruit%20Zoet.pdf)
- Trois grandes familles : **assertions structurelles** (termes et faits), **assertions d'action** (contraintes) et **dérivations** **[lu]** — [BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)
- Une dérivation est soit un **calcul mathématique** (« charge rate multiplied by hours »), qui « produces a DERIVED FACT according to a specified mathematical algorithm », soit une **inférence**, qui produit un fait dérivé « using logical induction (from particulars) or deduction (from general principles) » **[lu]** — [BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)
- Le BRG note que la distinction fait de base / fait dérivé contient des hypothèses implicites sur **l'ordre dans lequel l'information devient disponible** (taux et heures connus avant le coût total) **[lu]** — [BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)
- Les assertions d'action se classent de trois façons indépendantes **[lu]** — [BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf) :
  - par **classe** : *condition* (« an assertion that if something is true, another business rule will apply » ; un « test »), *contrainte d'intégrité* (« an assertion that must always be true », à effet immédiat : elle interdit toute action qui la rendrait fausse), *autorisation* (« (Only) x may do y », x étant un acteur capable d'activité indépendante) ;
  - par **type** : *enabler* (si vrai, permet ou entraîne l'existence/l'exécution de l'objet correspondant ; sinon l'action est bloquée), *timer* (teste, active/désactive, crée/supprime quand un seuil est atteint ; « countdown timer » ou « alarm clock »), *executive* (exige/cause l'exécution d'une ou plusieurs actions). Le texte précise que cette liste « is by no means exhaustive » ;
  - par **force** : *action controlling* (must / must not) contre *action influencing* (should / should not), ces dernières étant des lignes directrices que l'entreprise ne code pas en contrainte dure mais dont elle peut vouloir être notifiée en cas de violation.
- Exemples donnés par le BRG (location de voitures) **[lu]** — [BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf) :
  - contrainte d'intégrité : « A car must have a registration number » ;
  - prérequis/transition d'état : « A car cannot be handed over to the customer unless a provisional charge has been accepted against the customer's credit card » (la remise est « a state change on a rental ») ;
  - autorisation : « only a branch manager of the 'losing' branch may assign a car for transfer to another branch » ;
  - combinaison timer + executive : « if a customer is three months in arrears, then repossess the car » (la mesure des trois mois est « a CONDITION of type TIMER », la reprise du véhicule « an INTEGRITY CONSTRAINT of type EXECUTIVE »).
- L'annexe C (liste étendue reprise de Ronald Ross, *The Business Rule Book*) ajoute des types plus fins **[lu]** — [BRG 2000, annexe C](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf) :
  - *instance verifiers* : mandatory, limited (nombre d'instances), restricted, pre-existing, antecedent ;
  - *type verifiers* : mutual, mutually exclusive, mutually dependent, mutually prohibited ;
  - *sequence verifiers* (« These rules control changes in state ») : initializing, forward, progressive, retrogressive, re-initializing, cyclical ;
  - *position selectors* : lowest/highest, oldest/newest ;
  - *functional evaluators* : unique, fluctuating, ascending, descending, non-renewable, patterned, functional ;
  - *comparative evaluators* (=, ≠, <, ≤, >, ≥) ;
  - *calculators* (somme, soustraction, maximum, médiane…).

#### b) SBVR (OMG) et Ronald Ross — la coupure définitionnel / comportemental
- La version formelle courante de SBVR est la **1.5 (décembre 2019)** ; versions antérieures 1.0 (janv. 2008) à 1.4 (mai 2017) **[lu]** — [OMG SBVR](https://www.omg.org/spec/SBVR)
- SBVR : *definitional rule* = « rule that is a claim of necessity » ; *behavioral rule* = « business rule that is a claim of obligation ». Base modale : aléthique (vrai par définition, ne peut pas être violé) contre déontique (peut être violé ; porte sur ce que les personnes doivent ou ne doivent pas faire, même quand l'activité est automatisée). Les termes plus anciens « structural rule » et « operative rule » restent valides mais sont moins employés **[lu]** — [Ross, Business Rules Journal, nov. 2014](https://www.brcommunity.com/articles.php?id=b783)
- Les formulations structurelles utilisent les opérateurs aléthiques (nécessité, possibilité), les formulations opératives les opérateurs déontiques (obligatoire, permis, interdit) **[résumé]** — [Franconi et al., papier CILC](https://www.inf.unibz.it/~franconi/papers/cilc_fullpaper.pdf)
- Exemples : structurel « It is possible that an order has more than one line item » ; comportemental « Each order must be paid within 24 hours » ; les règles comportementales expriment des attentes « with the understanding that such expectations are not always met » **[résumé]** — [papier IBM, AAAI Spring Symposium 2008](https://cdn.aaai.org/Symposia/Spring/2008/SS-08-01/SS08-01-010.pdf)
- Une proposition de Ross à l'OMG demande d'aligner le texte SBVR sur « definitional / behavioral », jugés plus clairs que « structural / operative » **[résumé]** — [OMG issue SBVR14-15](https://issues.omg.org/issues/SBVR14-15)
- **Niveaux d'application** (enforcement levels) d'une règle comportementale, échelle graduée inspirée du Business Motivation Model : *strict* (pénalité inévitable) ; *deferred* (strict mais application différée, p. ex. en attente d'une ressource qualifiée) ; *pre-authorized* (exception avec accord préalable d'acteurs habilités) ; *post-justified* (exception permise, sanction si non approuvée après coup) ; *override* (dérogation avec explication, commentaire obligatoire) ; *guideline* (suggéré, non appliqué) **[lu]** — [Ross, Business Rules Journal, déc. 2019](https://www.brcommunity.com/articles.php?id=c016)
- Le niveau d'application est indépendant de la logique de la règle ; ces questions s'appliquent aux règles comportementales et à aucune règle définitionnelle ou de décision ; niveau et réponse à la violation peuvent dépendre des circonstances **[résumé]** — [Ross, « How Strongly Should a Business Rule Be Enforced? »](https://www.modernanalyst.com/Resources/Articles/tabid/115/ID/1637/How-Strongly-Should-a-Business-Rule-Be-Enforced.aspx)

#### c) Barbara von Halle (*Business Rules Applied*, 2001 — ancien, encore cité)
- von Halle (1994), citée : « depending on whom you ask, business rules may encompass some or all relationship verbs, mathematical calculations, inference rules, step-by-step instructions, database constraints, business goals and policies, and business definitions » **[lu]** — [de Haan, Spruit & Zoet 2019](https://liacs.leidenuniv.nl/~spruitmr/pub/2019%20-%20Haan%20Spruit%20Zoet.pdf)
- Classification attribuée à von Halle : termes, faits, puis règles = contraintes obligatoires, lignes directrices (guidelines), activateurs d'action (action enablers), calculs (computations), inférences. Les contraintes bloquent l'achèvement d'un évènement, les activateurs en déclenchent un ; une inférence établit un fait nouveau quand ses conditions sont vraies **[résumé, source secondaire faible]** — [billet CSDN reprenant von Halle](https://blog.csdn.net/weixin_39830588/article/details/115564377)
- La partie condition/conclusion (« if-part / then-part ») comme structure de base d'une règle est attribuée à von Halle & Goldberg (2009, *The Decision Model*) **[lu]** — [de Haan, Spruit & Zoet 2019](https://liacs.leidenuniv.nl/~spruitmr/pub/2019%20-%20Haan%20Spruit%20Zoet.pdf)

#### d) Gerd Wagner — règles d'intégrité, de dérivation, de réaction (ECA), de production
- Trois types de base identifiés dans la littérature (Taveter & Wagner 2001) **[lu]** — [Wagner, « Seven Golden Rules for a Web Rule Language », IEEE Intelligent Systems 18(5), 2003](https://www-docs.b-tu.de/fg-internet-technologie/public/publications/wagner/7GR.pdf) :
  - *Integrity rules* : « assertions that must hold in all evolving states and state transition histories of an enterprise viewed as a discrete dynamic system ». Exemple : « The driver of a rental car must be at least 25 years old ».
  - *Derivation rules* : « statements of knowledge that is derived from other knowledge by an inference or a mathematical calculation ». Exemple : « A gold customer is a customer with more than $1MM on deposit ».
  - *Reaction rules* : « expressions of policies specifying actions in response to events ». Exemple : « When a share price drops by more than 5%, and the investment is exempt from profit tax, then sell it ».
- Correspondance avec SQL : assertions = règles d'intégrité ; vues = règles de dérivation ; triggers = règles de réaction limitées aux évènements de mise à jour **[lu]** — [Wagner 2003](https://www-docs.b-tu.de/fg-internet-technologie/public/publications/wagner/7GR.pdf)
- « Rules are not implications » : une règle de dérivation n'a pas de valeur de vérité, elle sert à engendrer des énoncés dérivés **[lu]** — [Wagner 2003](https://www-docs.b-tu.de/fg-internet-technologie/public/publications/wagner/7GR.pdf)
- Dans les travaux REWERSE/URML ultérieurs : les quatre types « most used in practice » sont intégrité, dérivation, production, réaction ; une règle de réaction déclenche des actions à l'occurrence d'un évènement si ses conditions sont satisfaites (forme évènement–condition–action) ; intégrité, dérivation et réaction existent au niveau métier (CIM) et au niveau conception (PIM), alors que production et transformation n'existent qu'au niveau conception ; une règle de production peut simuler une règle de réaction ou de dérivation **[résumé]** — [Lukichev & Jarrar 2009](https://www.jarrar.info/publications/LJ09.pdf) ; [Wagner et al., « Towards a General Rule Markup Language »](https://www-docs.b-tu.de/fg-internet-technologie/public/publications/i1papers/TowardsGRML.pdf)

#### e) Graham Witt (*Writing Effective Business Rules*, 2012)
- Witt reprend la coupure opératif / définitionnel et répartit les modèles d'énoncés en quatre catégories : **règles définitionnelles, règles de données, règles d'activité, règles de parties (acteurs)** ; le chapitre 4 contient « A complete taxonomy of rules » **[résumé]** — [Witt, table des matières O'Reilly](https://www.oreilly.com/library/view/writing-effective-business/9780123850515/) ; [Witt, BRJ partie 18](https://www.brcommunity.com/articles.php?id=b740) ; [Witt, BRJ partie 25](https://brcommunity.com/articles.php?id=b773)
- Une règle d'activité peut confiner une activité à une période (p. ex. l'enregistrement en ligne d'un vol) ; une règle de partie dit quels acteurs peuvent exécuter quelles activités, par rôle **[résumé]** — [entretien avec Graham Witt](https://www.dataqualitypro.com/blog/how-to-create-effective-business-rules-graham-witt)

#### f) DMN (OMG) — la logique de décision
- Version formelle courante : **DMN 1.6 (septembre 2026)** d'après la page OMG consultée ; historique 1.0 (sept. 2015), 1.1 (juin 2016), 1.2 (janv. 2019), 1.3 (févr. 2021), 1.4 (avr. 2023), 1.5 (août 2024) ; une 1.7 bêta est en cours **[lu]** — [OMG DMN](https://www.omg.org/spec/DMN)
- Une table de décision DMN porte une **politique de résolution** (hit policy) qui fait partie du sens de la règle **[lu]** — [documentation Camunda, hit policies](https://docs.camunda.io/docs/components/modeler/dmn/decision-table-hit-policy/) :
  - *Unique* : au plus une règle satisfaite ; plusieurs correspondances = violation et échec de l'évaluation ;
  - *Any* : plusieurs règles peuvent correspondre mais doivent donner la même sortie ;
  - *First* : sortie de la première règle qui correspond (l'ordre des lignes devient signifiant) ;
  - *Rule order* : toutes les sorties, dans l'ordre des règles ;
  - *Collect* : liste de toutes les sorties, éventuellement agrégée par SUM, MIN, MAX ou COUNT.
- Les règles de dérivation correspondent, selon les schémas, aux catégories : inference rules, computation rules, derivation rules, classification, decision rules, calculation rules, rounding rules **[lu]** — [de Haan, Spruit & Zoet 2019](https://liacs.leidenuniv.nl/~spruitmr/pub/2019%20-%20Haan%20Spruit%20Zoet.pdf)

#### g) Absence de consensus
- « Not one commonly accepted way to classify business rules exists » ; dix schémas de classification différents recensés (Boyer & Mili 2011 ; Caron, Vanthienen & Baesens 2013 ; do Prado Leite & Leonardi 1998 ; Hay & Healy 2000 ; OMG 2008, 2013 ; Sangers-van Cappellen 2014 ; von Halle 2001 ; Wan-Kadir & Loucopoulos 2004 ; Zoet 2014), avec des noms différents pour des catégories semblables ou non **[lu]** — [de Haan, Spruit & Zoet, rapport technique UU-CS-2019-010, Université d'Utrecht, déc. 2019](https://liacs.leidenuniv.nl/~spruitmr/pub/2019%20-%20Haan%20Spruit%20Zoet.pdf)

### Inferences

#### Table de correspondance entre taxonomies (synthèse du chercheur à partir des sources ci-dessus)

| Type élémentaire | BRG 2000 | SBVR / Ross | von Halle | Wagner | Witt | DMN |
|---|---|---|---|---|---|---|
| Terme, définition | assertion structurelle : terme | définitionnel | terme | (vocabulaire) | définitionnelle | — |
| Fait, relation, cardinalité | assertion structurelle : fait | définitionnel | fait | intégrité (en partie) | définitionnelle / données | — |
| Contrainte d'intégrité | contrainte d'intégrité ; verifiers, evaluators | selon le cas définitionnel ou comportemental | contrainte obligatoire | règle d'intégrité | règle de données | — |
| Calcul | dérivation : calcul | définitionnel | computation | dérivation | définitionnelle (calcul) | expression littérale, table |
| Inférence, classification | dérivation : inférence | définitionnel | inférence | dérivation | définitionnelle | table de décision |
| Décision à cas multiples | (condition + dérivation) | règle de décision | inférence | dérivation / production | — | table + hit policy |
| Autorisation | autorisation | comportemental | contrainte | intégrité (déontique) | règle de partie | — |
| Prérequis, activateur | enabler | comportemental | action enabler | réaction / intégrité | règle d'activité | — |
| Transition d'état | sequence verifiers | comportemental (souvent) | contrainte | intégrité sur historiques | règle de données / activité | — |
| Temporel, échéance | timer | comportemental | contrainte / enabler | réaction (évènement temps) | règle d'activité | — |
| Réaction (ECA) | executive | comportemental | action enabler | règle de réaction | règle d'activité | — |
| Production (si-alors-faire) | — | — (niveau technique) | — | règle de production | — | — |
| Ligne directrice | action influencing | niveau d'application « guideline » | guideline | — | — | — |

#### Fiches par type de règle (définition sourcée, exemples illustratifs, ce qui varie, ce que le relecteur doit voir)

Les définitions renvoient aux sources citées plus haut ; les exemples, les axes de variation et les besoins du relecteur sont une synthèse du chercheur.

| # | Type | Définition précise | Exemple logiciel (illustratif) | Exemple processus métier (illustratif) | Ce qui varie d'un cas à l'autre | Ce que le relecteur doit voir pour juger UN cas |
|---|---|---|---|---|---|---|
| R1 | Terme / définition | Énoncé qui fixe le sens d'un concept ; règle de nécessité, non violable ([Ross 2014](https://www.brcommunity.com/articles.php?id=b783)) | « Un compte *actif* est un compte avec une connexion dans les 90 derniers jours » | « Un client *gold* est un client avec plus de 1 M$ en dépôt » ([Wagner 2003](https://www-docs.b-tu.de/fg-internet-technologie/public/publications/wagner/7GR.pdf)) | Valeurs des attributs qui font basculer dans ou hors du concept ; date d'évaluation | L'objet, la valeur de chaque critère, le verdict d'appartenance, et les cas juste de part et d'autre du seuil |
| R2 | Fait structurel (relation, cardinalité, sous-types) | Assertion sur ce qui peut ou doit être relié à quoi ([BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)) | « Une commande a au moins une ligne » | « Un dossier a exactement un gestionnaire référent » | Nombre d'instances liées (0, 1, n, max) ; type de l'objet | Les objets liés présents ou absents, le compte, la borne attendue |
| R3 | Contrainte d'intégrité | Assertion qui doit toujours être vraie ; interdit toute action qui la rendrait fausse ([BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)) | « Le solde ne peut pas être négatif » ; unicité d'un identifiant | « Le conducteur d'une voiture de location doit avoir au moins 25 ans » ([Wagner 2003](https://www-docs.b-tu.de/fg-internet-technologie/public/publications/wagner/7GR.pdf)) | Valeurs comparées, moment du contrôle (création, modification, suppression), action tentée | L'état avant, l'action tentée, la valeur fautive, le résultat (accepté/rejeté) et le message de rejet |
| R4 | Condition / garde | Test : si vrai, une autre règle s'applique ([BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)) | « Si le panier dépasse 100 €, la règle de livraison gratuite s'applique » | « Si le client est en retard de paiement, la procédure de relance s'applique » | Valeurs d'entrée, combinaison de conditions (ET/OU) | La valeur de chaque condition élémentaire (vrai/faux) et la règle rendue applicable |
| R5 | Calcul | Produit un fait dérivé selon un algorithme mathématique donné ([BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)) | TVA, remise, arrondi, prorata | Coût total = taux × heures ([BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)) ; pénalité de retard | Montants, taux, quantités, dates, règle d'arrondi, devise | Entrées, formule appliquée, étapes intermédiaires, résultat, arrondi ; cas limites (zéro, négatif, plafond) |
| R6 | Inférence / classification | Produit un fait dérivé par déduction ou induction logique ([BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)) | Niveau de risque d'une transaction | Éligibilité à une aide ; catégorie de client | Attributs d'entrée, chaîne de règles traversée | Les faits de départ, les règles déclenchées dans l'ordre, la conclusion (trace d'explication) |
| R7 | Décision à cas multiples (table) | Ensemble de règles condition → conclusion évalué selon une politique de résolution ([Camunda / DMN](https://docs.camunda.io/docs/components/modeler/dmn/decision-table-hit-policy/)) | Table de tarification | Table d'acceptation de crédit | Combinaison des entrées ; ligne(s) qui correspondent ; politique (unique, first, collect…) | La ligne qui a « gagné », les lignes concurrentes, la politique de résolution, les trous (aucune ligne) et les recouvrements |
| R8 | Autorisation | « (Only) x may do y » : prérogative d'un acteur sur une action ([BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)) | « Seul un administrateur peut supprimer un utilisateur » | « Seul le responsable de l'agence cédante peut affecter un véhicule au transfert » ([BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)) | Acteur, rôle, périmètre (son agence, son dossier), action, état de l'objet | Qui agit, à quel titre, sur quel objet, résultat permis/refusé ; le cas voisin avec un autre rôle |
| R9 | Prérequis / activateur | Si vrai, permet l'exécution d'une action ; sinon elle est bloquée ([BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)) | « Le bouton Payer n'est actif que si l'adresse est validée » | « Pas de remise du véhicule sans pré-autorisation acceptée sur la carte » ([BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)) | Présence ou non du prérequis, ordre des évènements | Le prérequis attendu, son état au moment de la tentative, l'issue (bloqué/autorisé) |
| R10 | Transition d'état | Règle qui détermine dans quel ordre un objet peut prendre ses états ([BRG 2000, annexe C](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)) | « Une commande *expédiée* ne peut pas revenir à *brouillon* » | Cycle de vie d'un sinistre : déclaré → instruit → réglé → clos | État de départ, évènement, état d'arrivée, historique | État avant, déclencheur, état après, et la liste des transitions interdites depuis cet état |
| R11 | Temporel (échéance, délai, période) | Teste, active ou désactive quelque chose quand un seuil de temps est atteint ([BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)) | « Le lien de réinitialisation expire après 24 h » | « Chaque commande doit être payée sous 24 heures » ([papier IBM 2008](https://cdn.aaai.org/Symposia/Spring/2008/SS-08-01/SS08-01-010.pdf)) | Instant de départ, durée, calendrier (jours ouvrés, fuseau), instant de l'évènement | Une ligne de temps : départ, échéance, instant réel, verdict avant/après ; cas pile à l'échéance |
| R12 | Réaction (évènement–condition–action) | Politique qui spécifie des actions en réponse à des évènements, si les conditions sont satisfaites ([Wagner 2003](https://www-docs.b-tu.de/fg-internet-technologie/public/publications/wagner/7GR.pdf)) | « À la création d'un compte, envoyer un courriel de bienvenue » | « Si le client a trois mois de retard, reprendre le véhicule » ([BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)) | Évènement déclencheur, conditions, action(s), destinataire | Le déclencheur, l'état au moment du déclenchement, l'action produite (ou l'absence d'action) et ses effets |
| R13 | Production (si condition alors action, sans évènement) | Règle de niveau conception, exécutée par un moteur ; peut simuler dérivation ou réaction ([Lukichev & Jarrar 2009](https://www.jarrar.info/publications/LJ09.pdf)) | Règles d'un moteur de règles | — (forme technique d'une règle métier d'un autre type) | Faits en mémoire, ordre de déclenchement, priorités | Les règles déclenchées, leur ordre, les faits ajoutés ou modifiés |
| R14 | Ligne directrice / règle dérogeable | Règle « should », suggérée ou appliquée avec dérogation ([BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf) ; [Ross 2019](https://www.brcommunity.com/articles.php?id=c016)) | Avertissement non bloquant | Dépassement de plafond avec justification ou accord préalable | Niveau d'application, acteur qui déroge, justification, approbation a posteriori | La violation détectée, le niveau d'application, qui a dérogé, la justification, la suite (sanction, notification) |

- La coupure définitionnel / comportemental change la nature du jugement : pour un cas définitionnel le relecteur vérifie **une valeur** (le résultat est-il le bon ?) ; pour un cas comportemental il vérifie **une issue** (l'action a-t-elle été permise, bloquée, signalée, dérogée comme prévu ?) et donc aussi ce qui se passe en cas de violation.
- Les trois axes de classement du BRG (classe, type, force) sont orthogonaux : une même règle est à la fois, par exemple, condition + timer + contrôlante. Un inventaire visuel devra probablement traiter ces axes comme des attributs combinables plutôt que comme des cases exclusives.
- La politique de résolution d'une table de décision (R7) est invisible dans les lignes mais change le résultat : la représenter fait partie de ce que le relecteur doit voir.

### Gaps
- **von Halle** : aucune source primaire lue. La classification (termes, faits, contraintes obligatoires, lignes directrices, activateurs d'action, calculs, inférences) n'est confirmée que par une source secondaire faible et par la mémoire du chercheur ; à vérifier dans *Business Rules Applied* (2001).
- **Ross, familles « rejectors / producers / projectors »** (*Principles of the Business Rule Approach*, 2003) : connue de mémoire, non retrouvée dans une source lue pendant cette recherche ; non citée ci-dessus.
- **Witt, taxonomie détaillée** : seuls les quatre grands groupes sont confirmés. Le détail (de mémoire, non vérifié : règles de cardinalité, de contenu et de mise à jour des données ; règles de restriction, d'obligation, de précondition et de conflit d'activités ; règles de restriction de partie, de séparation et de liaison de rôles, d'accès à l'information, de responsabilité) est à vérifier au chapitre 4 du livre.
- **DMN** : la liste des politiques *Priority* et *Output order*, ainsi que les expressions encadrées (table, expression littérale, contexte, invocation, fonction, liste, relation, et depuis 1.4 conditionnelle, itérateur, filtre) et le graphe d'exigences de décision (décision, donnée d'entrée, modèle de connaissance métier, source de connaissance, service de décision) n'ont pas été relus dans la spécification pendant cette recherche ; à confirmer dans le PDF OMG.
- **SBVR** : les définitions formelles n'ont pas été lues dans la spécification elle-même, seulement via Ross et des sources secondaires.
- Le contenu du texte OMG PRR (Production Rule Representation) n'a pas été consulté.

---

## Question 2 — Quels types de comportement apparaissent dans les processus métier et les moteurs de workflow ?

### Takeaway
La référence reste l'initiative Workflow Patterns (van der Aalst, ter Hofstede, Russell et al., 2003–2006, site maintenu jusqu'en 2023) : 43 motifs de flot de contrôle, 43 motifs de ressources, des motifs de données et un cadre de traitement des exceptions à 5 types d'exception × 15 traitements de tâche × 3 traitements de cas × 3 actions de reprise. Les moteurs modernes y ajoutent des paramètres explicites de réessai et de délai (intervalle, coefficient de recul, nombre maximal de tentatives).

### Cited Findings

#### a) Flot de contrôle — 43 motifs (source de 2003, révisée en 2006 ; toujours la référence)
- Les 20 motifs d'origine (van der Aalst, ter Hofstede, Kiepuszewski, Barros, *Distributed and Parallel Databases* 14(3), 2003) ont été révisés et complétés par 23 nouveaux (Russell, ter Hofstede, van der Aalst, Mulyar, rapport BPM-06-22, 2006), chacun formalisé en réseau de Petri coloré et évalué sur quatorze offres commerciales **[lu]** — [Workflow Patterns, flot de contrôle](http://www.workflowpatterns.com/patterns/control/) (site accessible en HTTP ; le certificat HTTPS était invalide le 21/11/2026)
- Liste complète par groupe **[lu]** — [Workflow Patterns, flot de contrôle](http://www.workflowpatterns.com/patterns/control/) :
  - **De base** : 1 Sequence, 2 Parallel Split, 3 Synchronization, 4 Exclusive Choice, 5 Simple Merge.
  - **Branchement et synchronisation avancés** : 6 Multi-Choice, 7 Structured Synchronizing Merge, 8 Multi-Merge, 9 Structured Discriminator, 28 Blocking Discriminator, 29 Cancelling Discriminator, 30 Structured Partial Join, 31 Blocking Partial Join, 32 Cancelling Partial Join, 33 Generalised AND-Join, 37 Local Synchronizing Merge, 38 General Synchronizing Merge, 41 Thread Merge, 42 Thread Split.
  - **Instances multiples** : 12 sans synchronisation, 13 avec connaissance a priori à la conception, 14 avec connaissance a priori à l'exécution, 15 sans connaissance a priori à l'exécution, 34 Static Partial Join for MI, 35 Cancelling Partial Join for MI, 36 Dynamic Partial Join for MI.
  - **Fondés sur l'état** : 16 Deferred Choice, 17 Interleaved Parallel Routing, 18 Milestone, 39 Critical Section, 40 Interleaved Routing.
  - **Annulation et achèvement forcé** : 19 Cancel Task, 20 Cancel Case, 25 Cancel Region, 26 Cancel Multiple Instance Activity, 27 Complete Multiple Instance Activity.
  - **Itération** : 10 Arbitrary Cycles, 21 Structured Loop, 22 Recursion.
  - **Terminaison** : 11 Implicit Termination, 43 Explicit Termination.
  - **Déclencheurs** : 23 Transient Trigger, 24 Persistent Trigger.
- Les motifs de branchement avancés sont dits « relatively commonplace in practice » mais « often not directly supported or even able to be represented in many commercial offerings » **[lu]** — [Workflow Patterns, flot de contrôle](http://www.workflowpatterns.com/patterns/control/)

#### b) Ressources (acteurs) — 43 motifs (Russell, ter Hofstede, Edmond, van der Aalst, 2004)
- Groupes et motifs **[lu]** — [Workflow Patterns, ressources](http://www.workflowpatterns.com/patterns/resource/) :
  - **Création** (limites fixées à la conception sur qui peut exécuter) : Direct Distribution, Role-Based Distribution, Deferred Distribution, Authorization, Separation of Duties, Case Handling, Retain Familiar, Capability-Based Distribution, History-Based Distribution, Organisational Distribution, Automatic Execution.
  - **Push** (le système offre ou alloue le travail) : Distribution by Offer – Single Resource, by Offer – Multiple Resources, by Allocation – Single Resource, Random Allocation, Round Robin Allocation, Shortest Queue, Early Distribution, Distribution on Enablement, Late Distribution.
  - **Pull** (la ressource prend le travail) : Resource-Initiated Allocation, Resource-Initiated Execution (allocated / offered work item), System-Determined Work Queue Content, Resource-Determined Work Queue Content, Selection Autonomy.
  - **Détour** : Delegation, Escalation, Deallocation, Stateful Reallocation, Stateless Reallocation, Suspension-Resumption, Skip, Redo, Pre-Do.
  - **Démarrage automatique** : Commencement on Creation, Commencement on Allocation, Piled Execution, Chained Execution.
  - **Visibilité** : Configurable Unallocated / Allocated Work Item Visibility.
  - **Ressources multiples** : Simultaneous Execution, Additional Resources.
- Cycle de vie d'un élément de travail utilisé par ces motifs : offered → allocated → started → completed, avec les états failed et withdrawn **[lu]** — [Russell, van der Aalst & ter Hofstede, « Workflow Exception Patterns », CAiSE 2006](https://www.vdaalst.com/publications/p325.pdf)

#### c) Données
- Groupes de motifs de données : visibilité (tâche, bloc, portée, instance multiple, cas, dossier, workflow, environnement), interaction interne (tâche à tâche, vers/depuis sous-processus, vers/depuis instances multiples, cas à cas), interaction externe (push/pull entre tâche, cas ou workflow et l'environnement), transfert (par valeur, copie entrée/sortie, par référence avec ou sans verrou, transformation en entrée/sortie), routage fondé sur les données **[lu]** — [Workflow Patterns, données](http://www.workflowpatterns.com/patterns/data/)

#### d) Exceptions, reprise, compensation (Russell, van der Aalst, ter Hofstede, 2006 — ancien, toujours la référence)
- Cinq types d'exception **[lu]** — [« Workflow Exception Patterns », CAiSE 2006](https://www.vdaalst.com/publications/p325.pdf) :
  - *Work item failure* : l'élément de travail ne peut plus progresser (abandon par l'utilisateur, panne matérielle, logicielle ou réseau, échec signalé par l'utilisateur) ;
  - *Deadline expiry* : l'échéance (d'achèvement, parfois de démarrage) est atteinte ; il est utile de spécifier à la conception quoi faire dans ce cas ;
  - *Resource unavailability* : donnée requise indisponible, aucune ressource ne satisfait les critères d'allocation, ou la ressource allouée ne peut plus exécuter ; « may involve some form of escalation or manual intervention » ;
  - *External trigger* : signal venant d'ailleurs (autre tâche non reliée, autre processus, environnement) ; on ne peut prédire ni si ni quand il arrivera ; conséquence générale : la tâche courante doit être arrêtée, éventuellement défaite, et une autre action entreprise ;
  - *Constraint violation* : invariant sur le flot, les données ou les ressources, à surveiller en continu.
- Quinze traitements au niveau de l'élément de travail, selon son état : offert (continue-offer, reoffer, force-fail-o, force-complete-o), alloué (continue-allocation, reallocate, reoffer-a, force-fail-a, force-complete-a), démarré (continue-execution, restart, reallocate-s, reoffer-s, force-fail, force-complete). *Restart* = l'exécution courante est arrêtée et l'élément est relancé du début par la même ressource ; *force-complete* déclenche les éléments suivants, *force-fail* non **[lu]** — [CAiSE 2006](https://www.vdaalst.com/publications/p325.pdf)
- Trois traitements au niveau du cas : continuer le cas (CWC), retirer le cas courant (RCC), retirer tous les cas du même modèle (RAC) **[lu]** — [CAiSE 2006](https://www.vdaalst.com/publications/p325.pdf)
- Trois actions de reprise : aucune (NIL), **rollback** (RBK : défaire les effets, avec le point de retour à préciser), **compensation** (COM : exécuter la ou les tâches de compensation désignées) **[lu]** — [CAiSE 2006](https://www.vdaalst.com/publications/p325.pdf)
- Un motif d'exception est un triplet, par exemple SFF-CWC-COM pour un échec de tâche : arrêter la tâche démarrée, la marquer en échec, lancer la tâche de compensation, ne pas toucher aux autres tâches du cas ; 135 combinaisons possibles (15 × 3 × 3), toutes ne s'appliquant pas à chaque type d'exception **[lu]** — [CAiSE 2006](https://www.vdaalst.com/publications/p325.pdf)

#### e) Réessais et délais dans un moteur moderne (exemple : Temporal)
- Une politique de réessai est un ensemble déclaratif de réglages : intervalle initial (défaut 1 s), coefficient de recul (défaut 2,0), intervalle maximal (défaut 100 × l'intervalle initial), nombre maximal de tentatives (défaut illimité ; 1 = pas de réessai), erreurs non réessayables (défaut aucune). Les activités sont réessayées par défaut, les exécutions de workflow non **[lu]** — [documentation Temporal, retry policies](https://docs.temporal.io/encyclopedia/retry-policies)
- Délai avant réessai = min(intervalle initial × coefficient^nombre de réessais, intervalle maximal) ; le délai global « schedule-to-close » est le moyen recommandé de borner la durée totale des réessais d'une activité, plutôt que le nombre de tentatives **[lu]** — [documentation Temporal](https://docs.temporal.io/encyclopedia/retry-policies)

#### f) Éléments BPMN qui portent ces comportements
- BPMN 2.0 compte plus de 85 éléments ; parmi ceux relevés dans les modèles publics : évènements minuterie (intermédiaire, de bordure interrompant ou non, de départ), évènements de bordure erreur, compensation, annulation, escalade, signal, message, condition ; fin erreur, fin annulation, fin terminate ; passerelles exclusive, parallèle, inclusive, complexe, fondée sur évènement ; tâche à instances multiples, activité en boucle, transaction, sous-processus ad hoc, call activity, business rule task **[lu]** — [Compagnucci, Corradini, Fornari & Re, « Trends on the Usage of BPMN 2.0 from Publicly Available Repositories »](https://ivancomp.github.io/assets/file/BIR.pdf)

#### g) Surveillance de conformité (Ly et al. 2015)
- Dix fonctionnalités de surveillance de conformité (CMF), tirées d'une revue systématique et de cinq études de cas : 1 temps (qualitatif avant/après et quantitatif : échéances, délais), 2 données, 3 ressources (acteurs, rôles), 4 activités non atomiques (avec durée), 5 cycles de vie d'activité, 6 instances multiples d'une règle, 7 gestion réactive (détecter, signaler, continuer, déclencher une compensation), 8 gestion proactive (détecter une violation future inévitable), 9 explication de la cause racine, 10 degré de conformité **[lu en partie : 100 000 premiers caractères sur 164 520]** — [Ly, Maggi, Montali, Rinderle-Ma & van der Aalst, *Information Systems* 54, 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4581012/)
- Familles de motifs de conformité : occurrence (une activité est exécutée ou non), ordre (entre paires d'activités), ressources (contraintes sur les exécutants de paires d'activités : séparation des tâches, liaison des tâches) **[résumé]** — [Ly et al. 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4581012/)

### Inferences

#### Fiches par type de comportement (définitions tirées des sources ci-dessus ; exemples illustratifs, axes de variation et besoins du relecteur : synthèse du chercheur)

| # | Comportement | Définition | Exemple logiciel (illustratif) | Exemple processus métier (illustratif) | Ce qui varie d'un cas à l'autre | Ce que le relecteur doit voir pour juger UN cas |
|---|---|---|---|---|---|---|
| B1 | Séquence | Une étape n'est activée qu'après la fin de la précédente (WCP 1) | Valider puis enregistrer | Instruire puis payer | Ordre réel des étapes | L'ordre attendu contre l'ordre observé |
| B2 | Parallélisme et synchronisation | Division en branches concurrentes puis attente de toutes (WCP 2, 3, 33) | Appels simultanés à deux services | Contrôle juridique et contrôle financier en parallèle | Ordre d'arrivée des branches, branche lente ou en échec | L'état de chaque branche à chaque instant et le moment où la suite démarre |
| B3 | Choix exclusif ou multiple | Une branche (WCP 4) ou plusieurs (WCP 6) choisies selon des données | Routage selon le type de compte | Circuit court si montant < seuil | Données de décision, branche(s) prise(s) | La condition évaluée, sa valeur, la branche prise et celles non prises |
| B4 | Jonction partielle / discriminateur | Continuer dès que 1 ou N branches sur M ont fini ; les autres sont attendues, bloquées ou annulées (WCP 9, 28–32) | Première réponse de plusieurs fournisseurs | Deux avis favorables sur trois suffisent | N, M, ordre d'arrivée, sort des branches restantes | Quelles branches ont compté, à quel moment le seuil est atteint, ce que deviennent les autres |
| B5 | Boucle / itération | Répétition d'une étape ou d'un bloc (WCP 10, 21, 22) | Ressaisie tant que le formulaire est invalide | Aller-retour de correction avec le demandeur | Nombre de tours, condition de sortie, borne maximale | Chaque tour, la condition de sortie à chaque tour, le cas « borne atteinte » |
| B6 | Instances multiples | Plusieurs exécutions d'une même activité, nombre connu à la conception, à l'exécution ou inconnu (WCP 12–15, 34–36) | Un traitement par ligne de commande | Une consultation par fournisseur | Nombre d'instances, achèvements partiels, annulation des restantes | Le nombre d'instances, l'état de chacune, la règle d'achèvement |
| B7 | Choix différé, jalon, section critique, entrelacement | Le choix est fait par l'environnement (premier évènement arrivé) ; activité possible seulement tant qu'un état dure ; exclusion mutuelle (WCP 16–18, 39, 40) | Réponse de l'utilisateur OU expiration | Rétractation possible tant que la commande n'est pas expédiée | Quel évènement arrive le premier, état du cas au moment de la tentative | La course entre évènements sur une ligne de temps ; l'état qui ouvre ou ferme la possibilité |
| B8 | Annulation et terminaison | Retrait d'une tâche, d'une région ou du cas entier ; fin implicite ou explicite (WCP 19, 20, 25–27, 11, 43) | Annuler une tâche en file | Le client annule sa demande en cours d'instruction | Moment de l'annulation, périmètre, travaux déjà faits | Ce qui était en cours, ce qui est retiré, ce qui reste acquis, l'état final |
| B9 | Déclencheur externe | Signal extérieur, perdu s'il n'est pas attendu (transient) ou conservé (persistent) (WCP 23, 24) | Webhook reçu avant que le traitement soit prêt | Pièce justificative reçue avant l'ouverture du dossier | Moment d'arrivée par rapport à l'état d'attente | L'instant du signal, l'état du cas, signal pris en compte ou perdu |
| B10 | Exception | Échec de tâche, échéance dépassée, ressource indisponible, déclencheur externe, violation de contrainte ([CAiSE 2006](https://www.vdaalst.com/publications/p325.pdf)) | Service tiers en panne | Aucun agent habilité disponible | Type d'exception, état de la tâche (offerte, allouée, démarrée) | Le triplet : sort de la tâche, sort du cas, action de reprise |
| B11 | Réessai | Relance d'une tâche échouée selon intervalle, recul, maximum, erreurs exclues ([Temporal](https://docs.temporal.io/encyclopedia/retry-policies)) | Nouvel appel après 1 s, 2 s, 4 s… | Nouvelle présentation d'un prélèvement rejeté | Nombre de tentatives, délais, type d'erreur, tentative qui réussit | Chaque tentative datée, la cause, l'issue finale (succès, abandon), le cas « erreur non réessayable » |
| B12 | Compensation / rollback | Défaire les effets, ou exécuter une tâche compensatoire désignée ([CAiSE 2006](https://www.vdaalst.com/publications/p325.pdf)) | Annuler une réservation après échec du paiement | Avoir émis après facturation erronée | Étapes déjà achevées, ordre des compensations, compensation qui échoue | Ce qui avait été fait, ce qui est défait et dans quel ordre, l'état résiduel |
| B13 | Délai / échéance | Limite de temps sur le démarrage ou l'achèvement, avec traitement prévu à l'expiration ([CAiSE 2006](https://www.vdaalst.com/publications/p325.pdf)) | Délai d'appel dépassé | Réponse due sous 5 jours ouvrés | Instant de départ, durée, calendrier, instant d'achèvement | La ligne de temps, le franchissement, l'action déclenchée à l'expiration |
| B14 | Escalade, délégation, réallocation | Le travail change de main ; avec ou sans conservation de l'état ([Workflow Patterns](http://www.workflowpatterns.com/patterns/resource/)) | Ticket réassigné au niveau 2 | Dossier transmis au supérieur après dépassement | Qui détenait, qui reçoit, pourquoi, état conservé ou perdu | La chaîne des détenteurs, le motif de chaque passage, ce qui est conservé |
| B15 | Distribution du travail et habilitations | Qui peut ou doit exécuter : rôle, capacité, historique, séparation des tâches, même exécutant qu'avant ([Workflow Patterns](http://www.workflowpatterns.com/patterns/resource/)) | Valideur différent de l'auteur | Principe des quatre yeux sur un virement | Acteurs, rôles, historique du cas | Qui a fait chaque étape, la règle d'exclusion ou de liaison, le cas interdit |
| B16 | Capacité et limites de ressources | File la plus courte, exécution simultanée, ressources additionnelles, section critique, indisponibilité ([Workflow Patterns](http://www.workflowpatterns.com/patterns/resource/)) | Limite de traitements concurrents | Un seul contrôleur pour dix dossiers | Charge, nombre de ressources, ordre d'arrivée | L'occupation des ressources dans le temps, qui attend, qui passe |
| B17 | Passation entre acteurs et systèmes | Échanges entre participants (bassins, flux de messages), interaction avec l'environnement ([Compagnucci et al.](https://ivancomp.github.io/assets/file/BIR.pdf) ; [Workflow Patterns, données](http://www.workflowpatterns.com/patterns/data/)) | Appel d'API et réponse asynchrone | Demande au client puis attente de sa réponse | Qui envoie quoi à qui, délais de réponse, message absent ou en double | Les couloirs par acteur, chaque message daté, les attentes |
| B18 | Routage et conditions fondés sur les données | Pré/postconditions de tâche et choix de branche dépendant de valeurs ([Workflow Patterns, données](http://www.workflowpatterns.com/patterns/data/)) | Tâche sautée si le champ est déjà rempli | Contrôle renforcé si le pays est à risque | Valeurs des données au moment du test | La donnée, sa valeur au moment du test, la conséquence sur le flot |

- Les dix-huit comportements se regroupent en quatre perspectives qui reprennent celles de l'initiative Workflow Patterns : flot de contrôle (B1–B9), exceptions et reprise (B10–B13), ressources et acteurs (B14–B17), données (B18). La surveillance de conformité de Ly et al. ajoute le temps comme perspective à part entière.
- Presque tous les comportements au-delà de B1–B3 ont pour variable principale **le temps ou l'ordre d'arrivée** (course entre évènements, tentatives successives, échéances) : le jugement d'un cas exige une trace datée, pas seulement une paire entrée/sortie.
- Pour les exceptions, le cadre de 2006 fournit directement la forme d'un « cas » : (type d'exception, état de la tâche) → (sort de la tâche, sort du cas, reprise). C'est une structure tabulaire à trois sorties.

### Gaps
- La spécification BPMN (OMG, 2.0.2, et ISO/IEC 19510) n'a pas été relue pendant cette recherche ; les éléments BPMN cités le sont via l'étude d'usage de Compagnucci et al.
- Le détail des motifs de « routage fondé sur les données » (préconditions et postconditions de tâche, déclencheurs fondés sur les données) n'a pas été lu : la page était tronquée à ce titre.
- Les motifs de saga (compensation dans les architectures de microservices) et les politiques de délai d'activité autres que « schedule-to-close » (start-to-close, heartbeat) n'ont pas été documentés à partir d'une source lue.
- Les motifs d'interaction de services et le langage déclaratif Declare (contraintes « response », « precedence », « not co-existence »…) n'ont pas été couverts.

---

## Question 3 — Quelle est la fréquence de chaque type en pratique ?

### Takeaway
Les données existent pour les **comportements de processus** (études de dépôts de modèles BPMN : la séquence, les tâches, le choix exclusif et le parallélisme dominent ; minuteries dans environ un modèle sur cinq ; erreur, compensation, escalade, annulation et boucles marquées dans moins de 4 % des modèles chacune). Pour les **types de règles métier**, aucune étude quantitative de bases de règles réelles n'a été trouvée : c'est une lacune de la littérature accessible, pas seulement de cette recherche.

### Cited Findings

#### a) Usage des éléments BPMN dans 25 590 modèles publics (Compagnucci, Corradini, Fornari & Re, Université de Camerino)
- 25 590 modèles retenus après filtrage, issus de six dépôts (BIT process library d'IBM, Camunda BPMN, eCH-BPM de l'administration suisse, GenMyModel, GitHub, modèles tirés de la littérature), soit 1 038 084 éléments **[lu]** — [Compagnucci et al.](https://ivancomp.github.io/assets/file/BIR.pdf)
- La distribution suit une loi de puissance ; cinq éléments sont présents dans plus de 50 % des modèles (Sequence Flow, End None Event, Start None Event, Task, Exclusive Gateway) ; 65 des 85 éléments sont présents dans moins de 10 % des modèles ; 36 sur 85 dans moins de 1 % **[lu]** — [Compagnucci et al.](https://ivancomp.github.io/assets/file/BIR.pdf)
- Part des modèles contenant chaque élément (lecture de la figure 1 par extraction du texte du PDF ; alignement noms/valeurs vérifié sur les points cités dans le corps du texte, à recontrôler sur la figure avant publication) **[lu, extraction de figure]** — [Compagnucci et al.](https://ivancomp.github.io/assets/file/BIR.pdf) :

| Comportement | Élément BPMN | % des modèles |
|---|---|---|
| Séquence | Sequence Flow | 99,65 |
| Fin / début simples | End None Event / Start None Event | 82,62 / 82,04 |
| Tâche non typée | Task | 60,91 |
| Choix exclusif | Exclusive Gateway | 54,45 |
| Multi-acteurs | Pool / Lane | 49,53 / 40,29 |
| Tâche humaine | User Task | 43,83 |
| Parallélisme | Parallel Gateway | 34,85 |
| Échange entre participants | Message Flow | 28,33 |
| Tâche automatique | Service Task | 21,75 |
| Attente / délai | Intermediate Catch Timer Event | 19,27 |
| Attente d'un message | Intermediate Catch Message Event | 17,22 |
| Terminaison explicite | End Terminate Event | 15,35 |
| Choix différé | Event-Based Gateway | 14,63 |
| Flux conditionnel | Conditional Flow | 12,30 |
| Appel de sous-processus | Call Activity | 7,84 |
| Choix multiple | Inclusive Gateway | 5,12 |
| Appel de règles / décision | Business Rule Task | 4,30 |
| Délai sur une activité | Boundary Timer Event (interrompant) | 4,08 |
| Erreur | Boundary Error Event | 3,46 |
| Instances multiples | Task Multiple Instance | 2,80 |
| Fin en erreur | End Error Event | 1,74 |
| Compensation | Boundary Compensate Event | 1,38 |
| Annulation | End Cancel Event | 1,31 |
| Délai non interrompant | Boundary Timer Event (non interrompant) | 0,96 |
| Transaction | Transaction | 0,95 |
| Escalade | Boundary Escalation Event | 0,48 |
| Boucle marquée | Task Loop Activity | 0,20 |

- Parmi les passerelles (en nombre d'occurrences) : exclusive 54,63 %, parallèle 35,37 %, autres 10 % ; parmi les évènements : fin 41,17 %, début 35,16 %, intermédiaires 19,28 %, de bordure 4,38 % ; évènements de bordure interrompants 91,26 %, non interrompants 8,74 % **[lu]** — [Compagnucci et al.](https://ivancomp.github.io/assets/file/BIR.pdf)
- Un modèle contient en moyenne 40 à 41 éléments (médiane 31) et utilise en moyenne 8,85 types d'éléments différents ; plus de 54 % des modèles utilisent entre 5 et 8 types ; moins de 1 % en utilisent plus de 18 **[lu]** — [Compagnucci et al.](https://ivancomp.github.io/assets/file/BIR.pdf)
- Une version étendue de cette étude porterait sur 54 500 modèles issus de sept collections **[résumé ; document non accessible]** — [« BPMN Notation Usage », Université de Camerino](https://pubblicazioni.unicam.it/retrieve/9087bda7-8080-4bb3-adaf-33b28d869ad6/BPMN_Notation_Usage.pdf)

#### b) Étude d'origine : zur Muehlen & Recker 2008 (ancienne, fondatrice)
- Analyse statistique de 120 diagrammes BPMN : moins de 20 % du vocabulaire est utilisé régulièrement ; un modèle moyen contient environ 9 constructions différentes ; l'usage ressemble à la distribution de fréquence des mots d'une langue naturelle **[résumé]** — [zur Muehlen & Recker, CAiSE 2008](https://www.doi.org/10.1007/978-3-540-69534-9_35) ; [fiche Stevens](https://researchwith.stevens.edu/en/publications/how-much-language-is-enough-theoretical-and-practical-use-of-the-/) ; [rétrospective 2013](https://www.springerprofessional.de/we-still-don-t-know-how-much-bpmn-is-enough-but-we-are-getting-c/4070814)
- Catégories par fréquence : noyau et noyau étendu (éléments présents dans au moins 25 % des diagrammes : évènements de début et de fin, tâches, flux de séquence, bassins et couloirs, passerelles exclusives), ensemble spécialisé (sous-processus, évènements d'attente), « overhead » (évènements déclenchant des flux d'exception, tout type d'évènement d'erreur) **[lu]** — [commentaire critique, BPMInstitute](https://www.bpminstitute.org/resources/articles/bpms-watch-how-much-bpmn-do-you-need/)
- Objection : la fréquence est « the wrong standard » ; retirer la catégorie « overhead » empêcherait de décrire le traitement des exceptions, qualifié de « fundamental » ; la valeur de BPMN tiendrait aux évènements et aux sous-processus **[lu]** — [BPMInstitute](https://www.bpminstitute.org/resources/articles/bpms-watch-how-much-bpmn-do-you-need/)

#### c) Prise en charge par les outils comme indicateur indirect
- Sur huit offres évaluées (dont Staffware, WebSphere MQ, FLOWer, COSA, iPlanet, et les langages XPDL, BPEL, BPMN) : « Only deadline expiry enjoys widespread support » ; seules deux gèrent l'échec de tâche ; déclencheurs externes et violations de contraintes sont à peine gérés ; aucune ne gère l'indisponibilité de ressource par exception **[lu]** — [« Workflow Exception Patterns », CAiSE 2006](https://www.vdaalst.com/publications/p325.pdf)

#### d) Propriétés temporelles (Dwyer, Avrunin & Corbett, ICSE 1999 — ancien, référence pour les motifs d'ordre et d'occurrence)
- Le système de motifs de spécification de propriétés a été bâti sur l'examen de plus de 500 spécifications temporelles tirées de la littérature **[lu]** — [support de cours KIT](https://formal.kastel.kit.edu/beckert/teaching/Spezifikation-Verifikation-SS08/030708.pdf)
- Environ 92 % des spécifications recensées correspondent à l'un des motifs proposés **[résumé]** — [fiche de l'article ICSE 1999](https://typeset.io/papers/patterns-in-property-specifications-for-finite-state-126awsf84j)
- Les motifs se répartissent en motifs d'occurrence et motifs d'ordre **[lu]** — [dépôt Property Specification Patterns](https://matthewbdwyer.github.io/psp/patterns.html)

#### e) Règles de conformité
- La plupart des approches proposent et utilisent des motifs de conformité liés au flot de contrôle ; des contraintes orientées données rencontrées en pratique ne sont pas couvertes par les motifs existants **[résumé]** — [Voglhofer & Rinderle-Ma, *Business & Information Systems Engineering*, 2019](https://link.springer.com/article/10.1007/s12599-019-00594-3)
- Dans les tables de motifs de Ly et al. : 8 motifs de co-occurrence, 5 d'ordre, 5 de ressources (décompte fait par l'outil de lecture, à revérifier) **[lu en partie]** — [Ly et al. 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4581012/)

#### f) Règles métier : pas de distribution publiée trouvée
- L'étude de de Haan, Spruit et Zoet a codé 37 motifs et 252 règles de dérivation, mais ne publie pas de répartition entre types de règles (l'échantillon ne contient par construction que des dérivations) et reconnaît que la généralisation n'est pas assurée vu la taille de l'échantillon **[lu]** — [de Haan, Spruit & Zoet 2019](https://liacs.leidenuniv.nl/~spruitmr/pub/2019%20-%20Haan%20Spruit%20Zoet.pdf)

### Inferences
- Hiérarchie de fréquence des comportements, déduite des chiffres ci-dessus : (1) quasi universels : séquence, tâche, début/fin ; (2) majoritaires : choix exclusif, plusieurs acteurs ; (3) fréquents (20–35 %) : parallélisme, échanges de messages ; (4) courants (10–20 %) : attente temporelle, attente de message, choix différé, terminaison explicite ; (5) rares dans les modèles (< 5 %) : choix multiple, appel de décision, délai sur activité, erreur, instances multiples ; (6) très rares (< 1,5 %) : compensation, annulation, transaction, escalade, boucle marquée.
- Ces chiffres mesurent ce que les modélisateurs **dessinent**, pas ce qui arrive dans les systèmes. Les dépôts publics (GitHub, GenMyModel) contiennent beaucoup de modèles d'apprentissage ; les boucles sont souvent dessinées par un retour de flux et non par le marqueur de boucle, donc sous-comptées ; les réessais et délais vivent dans la configuration du moteur ou dans le code et n'apparaissent pas dans les diagrammes. La rareté d'un comportement dans les modèles ne dit donc rien de son importance pour un relecteur, ce que souligne l'objection publiée contre l'étude de 2008.
- Le contraste entre « seule l'échéance est largement gérée » (2006) et le poids des minuteries dans les modèles (environ 19 % en attente, 4 % en bordure) désigne l'échéance comme le comportement non nominal le plus courant, devant l'erreur.
- Un modèle moyen n'utilise qu'environ 9 types d'éléments : un outil de représentation peut viser un petit noyau de formes pour la majorité des cas et réserver des formes spécialisées aux comportements rares.

### Gaps
- **Aucune étude empirique trouvée sur la fréquence des types de règles métier** (part des calculs, contraintes, autorisations, échéances, etc. dans des bases de règles ou des cahiers des charges réels). Les textes de Ross, du BRG et de von Halle consultés ne donnent pas de proportions.
- **Dwyer et al. 1999** : la répartition par motif et par portée n'a pas pu être lue. De mémoire, non vérifié : 555 spécifications, 511 conformes aux motifs, le motif « response » étant le plus fréquent (un peu moins de la moitié), suivi d'« universality » et d'« absence », avec une portée « global » très majoritaire. À confirmer dans l'article avant toute citation.
- **zur Muehlen & Recker 2008** : les pourcentages par construction n'ont pas été obtenus (article derrière une authentification).
- L'année et le lieu de publication exacts de l'étude de Compagnucci et al. n'apparaissent pas dans le texte extrait (le nom du fichier suggère la conférence BIR ; à vérifier). La version étendue à 54 500 modèles n'a pas pu être consultée.
- Aucune donnée trouvée sur la fréquence des réessais, délais et compensations dans des systèmes en production, ni sur l'usage des politiques de résolution DMN dans des tables réelles.

---

## Question 4 — Quels types se combinent le plus souvent dans un même cas ?

### Takeaway
Aucune étude ne mesure directement la co-occurrence des types de règles, mais les sources donnent des combinaisons canoniques récurrentes : **échéance + réaction** (timer + executive), **transition d'état + prérequis**, **autorisation + action sur un objet dans un certain état**, **règle comportementale + niveau d'application + dérogation habilitée**, **contrainte d'ordre + temps métrique + données**, **exception + sort de la tâche + sort du cas + reprise**, **réessai + délai global**. Côté modèles, les seules co-occurrences mesurées sont celles d'éléments BPMN.

### Cited Findings
- **Échéance + réaction** : « if a customer is three months in arrears, then repossess the car » est analysé par le BRG comme une condition de type timer suivie d'une assertion de type executive ; le BRG en fait l'exemple de la façon dont les types « can be combined in various ways » **[lu]** — [BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)
- **Transition d'état + prérequis** : « A car cannot be handed over to the customer unless a provisional charge has been accepted » ; la remise est enregistrée comme changement d'état de la location **[lu]** — [BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)
- **Autorisation + périmètre + action** : « only a branch manager of the 'losing' branch may assign a car for transfer to another branch » (rôle, rattachement à l'agence, action) **[lu]** — [BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)
- **Timer contrôlant une autre règle** : un timer peut « turn on » une autre assertion d'action, ou fixer/tester la valeur d'un attribut ; un enabler peut permettre une autre assertion d'action **[lu]** — [BRG 2000](https://www.businessrulesgroup.org/first_paper/BRG-whatisBR_3ed.pdf)
- **Évènement + deux conditions (seuil calculé et statut) + action** : « When a share price drops by more than 5%, and the investment is exempt from profit tax, then sell it » **[lu]** — [Wagner 2003](https://www-docs.b-tu.de/fg-internet-technologie/public/publications/wagner/7GR.pdf)
- **Règle comportementale + niveau d'application + habilitation** : les niveaux « pre-authorized » (accord préalable d'acteurs habilités à déroger), « post-justified » et « override » (explication obligatoire) associent à toute règle comportementale une autorisation et une justification **[lu]** — [Ross 2019](https://www.brcommunity.com/articles.php?id=c016)
- **Contrainte + échéance** : l'exemple type de règle comportementale est « Each order must be paid within 24 hours » **[résumé]** — [papier IBM 2008](https://cdn.aaai.org/Symposia/Spring/2008/SS-08-01/SS08-01-010.pdf)
- **Flot de contrôle + temps métrique ; flot de contrôle + données ; ressources sur des paires d'activités** : combinaisons relevées comme typiques dans la littérature sur la conformité ; les règles à instances multiples sont instanciées par des horodatages, des données ou des ressources ensemble ; la plupart des approches traitent à la fois le temps et la gestion réactive des violations **[lu en partie]** — [Ly et al. 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4581012/)
- **Exception = combinaison par construction** : chaque motif d'exception est un triplet (sort de la tâche, sort du cas, reprise), p. ex. SFF-CWC-COM = échec + poursuite du cas + compensation ; l'indisponibilité de ressource « may involve some form of escalation or manual intervention » **[lu]** — [CAiSE 2006](https://www.vdaalst.com/publications/p325.pdf)
- **Réessai + délai** : le délai global « schedule-to-close » borne la durée totale des réessais ; le nombre maximal de tentatives et les erreurs non réessayables s'y ajoutent **[lu]** — [documentation Temporal](https://docs.temporal.io/encyclopedia/retry-policies)
- **Décision + politique de résolution** : sous la politique *Unique*, plusieurs correspondances provoquent l'échec de l'évaluation et un incident dans l'instance de processus, ce qui relie logique de décision et traitement d'erreur du processus **[lu]** — [documentation Camunda](https://docs.camunda.io/docs/components/modeler/dmn/decision-table-hit-policy/)
- **Co-occurrences mesurées entre éléments BPMN** (corrélation de Pearson sur 25 590 modèles) : passerelle exclusive–flux de séquence 0,87 ; tâche d'envoi–tâche de réception 0,79 ; début simple–fin simple 0,78 ; flux de séquence–tâche 0,71 ; passerelle inclusive–passerelle exclusive 0,65 ; passerelle exclusive–tâche 0,57 ; bassin–flux de message 0,53 ; bassin–couloir 0,52. Aucune paire ne présente de corrélation inverse moyenne ou forte **[lu]** — [Compagnucci et al.](https://ivancomp.github.io/assets/file/BIR.pdf)
- Ross a consacré un article à la rencontre entre règles comportementales et logique de décision (titre : « What Happens When Behavioral Business Rules and Decision Logic Collide? ») **[titre seulement, contenu non lu]** — [Business Rules Journal](https://www.brcommunity.com/articles.php?id=b987)

### Inferences
Combinaisons à prévoir en priorité pour un outil qui montre « tous les cas » (classement du chercheur, par solidité des appuis ci-dessus) :

| Combinaison | Types en jeu | Ce que le cas combiné doit montrer |
|---|---|---|
| Décision + échéance | R7 + R11 (+ R12) | Les entrées de la décision ET la position dans le temps ; le résultat change au franchissement de l'échéance |
| Machine à états + autorisation | R10 + R8 | État de l'objet × rôle de l'acteur × action → permis/refusé : une matrice à trois dimensions |
| Machine à états + prérequis | R10 + R9 | La transition demandée, le prérequis manquant ou présent, l'état résultant |
| Échéance + réaction + escalade | R11 + R12 + B13 + B14 | La ligne de temps, l'action à l'expiration, le changement de détenteur |
| Contrainte + niveau d'application + dérogation | R3/R14 + R8 | La violation, qui peut déroger, la justification, la suite |
| Calcul + plafonds/seuils + arrondi | R5 + R3 + R4 | Les étapes de calcul et l'endroit où un plafond ou une condition modifie le résultat |
| Exception + réessai + compensation | B10 + B11 + B12 + B13 | Les tentatives datées, le point d'abandon, ce qui est défait |
| Parallélisme + annulation / jonction partielle | B2 + B4 + B8 | L'état de chaque branche et le sort des branches perdantes |
| Choix + données + acteurs | B3 + B18 + B15 | La donnée testée, la branche prise, l'acteur qui hérite du travail |
| Séparation des tâches sur deux étapes | B15 + B1 | Qui a fait la première étape, qui tente la seconde, l'issue |

- Les trois axes du BRG et l'indépendance, affirmée par Ross, entre la logique d'une règle et son niveau d'application impliquent qu'un cas « réel » est presque toujours un produit de plusieurs types : au minimum (logique) × (niveau d'application) pour toute règle comportementale.
- Le temps est le partenaire de combinaison le plus fréquent dans les sources : il apparaît avec la réaction (BRG), avec la contrainte (SBVR/IBM), avec l'ordre des activités (Ly et al.), avec le réessai (Temporal) et avec l'exception (échéance, seule exception largement gérée en 2006).
- Les co-occurrences BPMN mesurées confirment surtout des évidences structurelles (choix + flux, bassin + message) ; elles ne renseignent pas sur les combinaisons de comportements non nominaux, trop rares dans les modèles pour ressortir.

### Gaps
- **Aucune mesure directe de co-occurrence entre types de règles métier** dans des bases de règles ou des spécifications réelles n'a été trouvée ; le classement ci-dessus est qualitatif.
- Les exemples « décision + échéance » et « machine à états + autorisation » sont appuyés par des exemples canoniques (BRG, SBVR) et non par des comptages.
- L'article de Ross sur la collision entre règles comportementales et logique de décision n'a pas été lu ; il pourrait préciser la combinaison décision + règle comportementale.
- La dernière partie de l'article de Ly et al. (études de cas, environ 64 000 caractères) n'a pas été lue ; elle peut contenir des comptages de règles par dimension (temps, données, ressources) dans des cas réels.
- Les corrélations BPMN au-delà des dix paires les plus fortes (et l'analyse par groupes d'éléments de la section 5.2 de l'étude) n'ont pas été extraites.
