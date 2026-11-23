"use strict";

const runCatalog = (() => {
  const W = "WAITING", R = "RUNNING", RK = "RUNNING_KO", OK = "FINISHED_OK";
  const KO = "FINISHED_KO", B = "BLOCKED", D = "DEACTIVATED", AB = "ABORTED", WARN = "WARNING";
  const IGNORED = "KO_IGNORED", DP = "DEACTIVATED_PG";
  const scopes = { workflow: "Workflow", task: "Task", iteration: "Itération", step: "Step" };
  const workflowFamilies = new Set(["Capacité et concurrence", "Erreurs du Workflow", "Finalisation", "Limites et configurations refusées"]);
  const task = (id, name, options = {}) => ({ id, name, kind: "task", always_run: false, ignore_on_error: false, active: true, ...options });
  const step = (title, workflow, changes, note, extra = {}) => ({ title, workflow, changes, note, ...extra });
  const cases = [];
  function add(spec) {
    let states = Object.fromEntries(spec.nodes.map((node) => [node.id, { status: node.active ? W : D }]));
    const frames = spec.steps.map(({ changes, ...frame }) => {
      states = { ...states, ...Object.fromEntries(Object.entries(changes).map(([id, value]) => [id, typeof value === "string" ? { status: value } : value])) };
      return { ...frame, states };
    });
    const { steps, ...metadata } = spec;
    cases.push({
      stop_on_error: false, capacity: 3, mode: "parcours", level: "simple",
      scope: workflowFamilies.has(spec.family) ? "workflow" : "task",
      sources: ["decision"], tests: [], caution: "", edges: [], actions: [], ...metadata, frames,
    });
  }
  const chain = () => [task("A", "source"), task("B", "suite")];
  const triple = () => [task("A", "task_a"), task("B", "task_b"), task("C", "task_c")];
  const cleanup = () => [task("A", "source"), task("C", "cleanup", { always_run: true })];
  const decisionTest = "test_workflow_rework.py::test_scheduler_decisions";
  const finalTest = "test_workflow_rework.py::test_finalization_order";
  const realErrorTest = "test_workflow_rework.py::test_real_task_error_handler_propagates_ko_and_keeps_cleanup";
  const inactiveTest = "test_workflow.py::test_workflow_run_propagates_deactivation_before_blocking";
  const ending = (changes, note = "Le nettoyage et le bilan du Workflow sont terminés.") => step("Fin du Workflow", OK, changes, note);

  add({ id: "base-unique", family: "Bases", title: "Une seule Task", nodes: [task("A", "unique")],
    summary: "A n’a aucun prérequis. Elle peut démarrer dès qu’une place d’exécution est libre. Après sa réussite, le Workflow doit encore effectuer ses opérations de fin.",
    sources: ["decision", "finalization"], tests: [finalTest],
    steps: [step("A attend son lancement", W, {}, "A est WAITING : elle n’a pas encore démarré."), step("A travaille", R, { A: R }, "A occupe une place d’exécution."),
      step("A a réussi, le Workflow termine ses opérations", R, { A: OK }, "Le Workflow attend la fin complète de l’exécution de A, supprime les ressources temporaires puis prépare son bilan."), ending({})] });
  add({ id: "base-chaine", family: "Bases", title: "Une chaîne de dépendances", nodes: chain(), edges: [["A", "B"]],
    summary: "B dépend de A. B attend donc que A réussisse, quel que soit l’ordre des noms dans la configuration.", tests: [decisionTest],
    steps: [step("A démarre", R, { A: R }, "B reste WAITING car A travaille.", { decisions: { B: "WAIT" } }),
      step("A réussit", R, { A: OK }, "A a réussi : B peut maintenant démarrer si une place est libre.", { decisions: { B: "LAUNCH" } }),
      step("B démarre", R, { B: R }, "B travaille après A."), ending({ B: OK }, "B réussit à son tour. Le Workflow termine ses opérations de fin et passe à FINISHED_OK.")] });
  add({ id: "base-fork", family: "Bases", title: "B et C attendent A, puis peuvent travailler ensemble", nodes: triple(), edges: [["A", "B"], ["A", "C"]],
    summary: "B et C dépendent toutes les deux de A, mais pas l’une de l’autre. Après la réussite de A, elles peuvent travailler en parallèle si deux places sont libres.",
    steps: [step("A travaille", R, { A: R }, "B et C attendent la fin de A."),
      step("A a réussi", R, { A: OK }, "B et C peuvent maintenant démarrer.", { decisions: { B: "LAUNCH", C: "LAUNCH" } }),
      step("B et C travaillent ensemble", R, { B: R, C: R }, "Deux places sont libres dans cet exemple. B et C n’ont pas besoin d’attendre la fin l’une de l’autre."), ending({ B: OK, C: OK }, "B et C réussissent. Le Workflow termine ses opérations de fin et passe à FINISHED_OK.")] });
  add({ id: "base-join", family: "Bases", title: "Deux prérequis obligatoires", nodes: triple(), edges: [["A", "C"], ["B", "C"]],
    summary: "C dépend de A et de B. C doit attendre que les deux aient réussi ; la réussite d’une seule ne suffit pas.",
    steps: [step("Les sources travaillent", R, { A: R, B: R }, "C attend les deux résultats."),
      step("Un seul résultat", R, { A: OK }, "B travaille encore : C ne démarre pas.", { decisions: { C: "WAIT" } }),
      step("A et B ont réussi", R, { B: OK }, "Tous les prérequis de C sont satisfaits : C peut démarrer.", { decisions: { C: "LAUNCH" } }), ending({ C: OK }, "C s’exécute puis réussit. Le Workflow termine ses opérations de fin et passe à FINISHED_OK.")] });
  add({ id: "base-losange", family: "Bases", title: "D attend B et C, qui dépendent toutes deux de A", level: "composé",
    nodes: [...triple(), task("D", "convergence")], edges: [["A", "B"], ["A", "C"], ["B", "D"], ["C", "D"]],
    summary: "A doit réussir avant le lancement de B et C. D attend ensuite la réussite de B et de C, même si l’une termine avant l’autre.",
    steps: [step("A travaille", R, { A: R }, "B et C attendent A ; D attend B et C."),
      step("B et C travaillent", R, { A: OK, B: R, C: R }, "A a réussi. B et C peuvent maintenant travailler en parallèle."),
      step("B a réussi, C travaille encore", R, { B: OK }, "D doit encore attendre C.", { decisions: { D: "WAIT" } }),
      ending({ C: OK, D: OK }, "C réussit. D peut alors s’exécuter et réussit à son tour. Le Workflow termine en FINISHED_OK.")] });
  add({ id: "base-attente-non-bloquante", family: "Bases", title: "Une Task en attente ne retient pas les autres", nodes: triple(), edges: [["A", "B"]],
    summary: "B doit attendre A. C est indépendante : Lancelot peut lancer C sans attendre que B puisse démarrer.",
    sources: ["scheduling", "decision"],
    steps: [step("A travaille", R, { A: R }, "B attend A, mais C n’a pas de dépendance.", { decisions: { B: "WAIT", C: "LAUNCH" } }),
      step("C démarre", R, { C: R }, "Une place est libre : C travaille pendant que A continue et que B attend."),
      ending({ A: OK, B: OK, C: OK }, "A et C réussissent. B s’exécute après la réussite de A et réussit aussi. Le Workflow termine en FINISHED_OK.")] });
  for (const capacity of [1, 2]) {
    add({ id: `capacite-${capacity}`, family: "Capacité et concurrence", title: `${capacity} place${capacity > 1 ? "s" : ""} pour trois Tasks`, capacity,
      nodes: triple(), sources: ["capacity"], tests: ["test_workflow_rework.py::test_real_threads_respect_capacity_and_launch_each_task_once"],
      summary: `A, B et C sont indépendantes, mais seulement ${capacity} Task${capacity > 1 ? "s peuvent" : " peut"} travailler à la fois. Les autres restent WAITING jusqu’à ce qu’une place se libère. L’ordre montré est un exemple, pas une priorité garantie.`,
      steps: [step(capacity === 1 ? "A occupe la seule place" : "A et B occupent les deux places", R, capacity === 1 ? { A: R } : { A: R, B: R }, capacity === 1 ? "B et C pourraient démarrer sans prérequis, mais aucune place n’est libre." : "C pourrait démarrer sans prérequis, mais les deux places sont occupées."),
        step(capacity === 1 ? "A termine, B démarre" : "A termine, B continue", R, { A: OK, B: R }, capacity === 1 ? "A a réussi. B utilise la place libérée ; C attend encore." : "A a réussi et libère une place. B travaille encore ; C pourra être lancée lors d’un prochain examen."),
        step("C travaille", R, { B: OK, C: R }, "B a également réussi. C a obtenu une place et s’exécute."), ending({ C: OK }, "C réussit. Les trois Tasks ont été exécutées une seule fois ; le Workflow termine en FINISHED_OK.")] });
  }
  add({ id: "capacite-reevaluation", family: "Capacité et concurrence", title: "Un KO bloque les Tasks qui attendaient une place", level: "composé",
    nodes: triple(), stop_on_error: true, capacity: 1, sources: ["capacity", "decision"],
    summary: "Une seule Task peut s’exécuter à la fois. B et C attendent que A termine. Si A échoue, stop_on_error: true empêche leur lancement, même si elles ne dépendent pas de A.",
    steps: [step("A occupe la seule place", R, { A: R }, "B et C n’ont aucun prérequis, mais restent WAITING : la seule place disponible est occupée par A."),
      step("A échoue", RK, { A: KO }, "A libère la place, mais son échec déclenche stop_on_error: true. B et C ne seront pas lancées.", { decisions: { B: "BLOCK", C: "BLOCK" } }),
      step("B et C sont bloquées, le Workflow termine en erreur", KO, { B: { status: B, causes: ["A"] }, C: { status: B, causes: ["A"] } }, "B et C n’ont pas démarré. Elles passent à BLOCKED à cause de A ; le Workflow termine en FINISHED_KO.")] });
  add({ id: "capacite-double-lancement", family: "Capacité et concurrence", title: "Deux tentatives, une seule exécution", level: "limite",
    nodes: [task("A", "unique")], mode: "état ciblé", sources: ["capacity"],
    tests: ["test_workflow_rework.py::test_competing_schedulers_cannot_launch_the_same_task_twice"],
    summary: "Lorsque Lancelot a déjà choisi A pour la lancer, une seconde vérification ne doit pas lancer A une deuxième fois.",
    steps: [step("Le lancement de A est réservé", R, { A: { status: W, reserved: true } }, "Lancelot a choisi A et prépare son lancement. A affiche encore WAITING, mais elle ne peut plus être choisie une seconde fois."),
      step("L’exécution de A vient de démarrer", R, { A: { status: W, launched: true } }, "Le thread de A a démarré. Pendant ce court intervalle, son statut affiche encore WAITING."),
      step("A affiche RUNNING", R, { A: R }, "A travaille. Une nouvelle vérification ne la relance pas."), ending({ A: OK })] });

  add({ id: "warning-dependance", family: "Avertissements et erreurs ignorées", title: "B peut démarrer si A termine avec un avertissement", nodes: chain(), edges: [["A", "B"]],
    summary: "A termine avec WARNING, pas en erreur. B peut donc s’exécuter, comme si A avait terminé en FINISHED_OK.", sources: ["decision", "aggregation"], tests: [decisionTest, finalTest],
    steps: [step("A termine avec un avertissement", R, { A: WARN }, "L’avertissement de A n’empêche pas B de démarrer.", { decisions: { B: "LAUNCH" } }),
      step("B travaille", R, { B: R }, "Le Workflow attend la fin de B."), step("Fin avec avertissement", WARN, { B: OK }, "B réussit. Après ses opérations de fin, le Workflow termine en WARNING à cause de l’avertissement de A.")] });
  add({ id: "warning-ko-prioritaire", family: "Avertissements et erreurs ignorées", title: "Un KO l’emporte sur un WARNING", nodes: chain(),
    summary: "Les Tasks sont indépendantes ; leurs résultats diffèrent. L’avertissement ne masque pas l’échec.", sources: ["aggregation", "finalization"],
    steps: [step("A a un avertissement, B a échoué", RK, { A: WARN, B: KO }, "L’erreur de B impose un résultat en KO au Workflow."),
      step("Le Workflow termine en erreur", KO, {}, "Après ses opérations de fin, le Workflow affiche FINISHED_KO.")] });
  for (const stop of [false, true]) {
    add({ id: `ignore-transitoire-${stop}`, family: "Avertissements et erreurs ignorées", title: `Une erreur ignorée laisse C démarrer · stop_on_error: ${stop}`, stop_on_error: stop,
      level: "composé", nodes: [task("A", "erreur ignorée", { ignore_on_error: true }), task("B", "dépendante"), task("C", "indépendante")], edges: [["A", "B"]],
      summary: "A affiche RUNNING_KO avec ignore_on_error: true jusqu’à la fin de son exécution. Cela n’empêche pas C, indépendante, de démarrer. B dépend de A et attend sa fin, même si son erreur est ignorée.",
      sources: ["decision", "blocking", "task"], tests: ["test_workflow_rework.py::test_ignored_transient_ko_does_not_stop_independent_tasks", decisionTest],
      steps: [step("Erreur en cours", RK, { A: RK }, "C peut démarrer. B doit encore attendre la fin de A.", { decisions: { B: "WAIT", C: "LAUNCH" } }),
        step("A termine avec une erreur ignorée", R, { A: IGNORED, C: OK }, "A termine en KO_IGNORED, affiché comme WARNING. Son échec reste visible mais ne bloque pas B. C a réussi ; B peut maintenant démarrer.", { decisions: { B: "LAUNCH" } }),
        ending({ B: OK }, "B s’exécute puis réussit. L’erreur de A ayant été ignorée et aucune autre erreur n’étant survenue, le Workflow termine en FINISHED_OK.")] });
  }
  add({ id: "ignore-warning-aggregation", family: "Avertissements et erreurs ignorées", title: "Un avertissement reste visible avec une erreur ignorée",
    nodes: [task("A", "erreur ignorée", { ignore_on_error: true }), task("B", "avertissement")],
    summary: "A termine en KO_IGNORED et B en WARNING. L’erreur ignorée ne met pas le Workflow en KO ; l’avertissement de B détermine son statut final WARNING.",
    sources: ["aggregation", "finalization"],
    steps: [step("A et B travaillent", RK, { A: RK, B: R }, "A a signalé une erreur en cours ; B travaille encore. Le Workflow reste RUNNING_KO tant que A n’a pas fini."),
      step("A et B ont terminé", R, { A: IGNORED, B: WARN }, "L’erreur de A reste visible en KO_IGNORED. B termine avec WARNING ; aucun KO non ignoré ne subsiste."),
      step("Fin avec avertissement", WARN, {}, "Après la finalisation, le Workflow termine en WARNING à cause de B, sans transformer A en succès.")] });
  add({ id: "ignore-ko-definitif", family: "Avertissements et erreurs ignorées", title: "Une erreur d’initialisation de A reste bloquante", level: "limite", mode: "état ciblé",
    nodes: [task("A", "échec d’initialisation", { ignore_on_error: true }), task("B", "dépendante")], edges: [["A", "B"]], tests: [decisionTest],
    summary: "On part d’une Task A dont l’initialisation a échoué et qui est déjà en FINISHED_KO. Malgré ignore_on_error: true, B est bloquée par cet échec.",
    sources: ["blocking", "task"],
    caution: "Cet état ciblé suppose que l’échec a pu être enregistré sur A. Une erreur survenue très tôt ou une erreur de configuration du Workflow peut interrompre son initialisation avant cet ordonnancement.",
    steps: [step("L’initialisation de A a échoué", RK, { A: KO }, "B ne peut pas démarrer puisque son prérequis A est en FINISHED_KO.", { decisions: { B: "BLOCK" } }),
      step("B est bloquée, le Workflow termine en erreur", KO, { B: { status: B, causes: ["A"] } }, "B n’a pas été exécutée à cause de l’échec de A. Le Workflow termine en FINISHED_KO.")] });
  for (const stop of [false, true]) {
    add({ id: `ignore-et-ko-reel-${stop}`, family: "Avertissements et erreurs ignorées",
      title: stop ? "Un autre KO bloque C malgré l’erreur ignorée de A" : "C peut suivre A ignorée malgré le KO de B",
      stop_on_error: stop, level: "composé",
      nodes: [task("A", "erreur ignorée", { ignore_on_error: true }), task("B", "erreur réelle"),
        task("C", "dépend de A"), task("D", "dépend de B")],
      edges: [["A", "C"], ["B", "D"]],
      summary: stop
        ? "A finit en KO_IGNORED, mais B finit en FINISHED_KO. Avec stop_on_error: true, le KO réel de B bloque les Tasks ordinaires encore en attente, y compris C qui dépend uniquement de A. D est bloquée par son prérequis B."
        : "A finit en KO_IGNORED et B en FINISHED_KO. Avec stop_on_error: false, C peut démarrer après A ; D reste bloquée par B. Le Workflow finit en KO à cause de B.",
      sources: ["decision", "blocking", "aggregation"], tests: [decisionTest, realErrorTest],
      steps: [step("A signale une erreur ignorée ; B travaille", RK, { A: RK, B: R },
          "C dépend de A, mais attend la fin de son erreur. D attend B."),
        step("B échoue avant la fin de A", RK, {
          B: KO,
          ...(stop ? { C: { status: B, causes: ["B"] } } : {}),
          D: { status: B, causes: ["B"] },
        }, "D est bloquée par B. Avec stop_on_error: true, C est aussi bloquée par B ; sinon, C attend encore A.",
        { decisions: { C: stop ? "BLOCK" : "WAIT", D: "BLOCK" } }),
        step("A termine en KO_IGNORED", RK, { A: IGNORED,
          ...(!stop ? { C: W } : {}) },
          stop
            ? "C reste bloquée à cause du KO réel de B, pas de l’erreur ignorée de A."
            : "Le KO de B ne déclenche pas l’arrêt global. C dépend uniquement de A, désormais en KO_IGNORED, et peut démarrer.",
          { decisions: stop ? {} : { C: "LAUNCH" } }),
        ...(!stop ? [step("C réussit", RK, { C: OK }, "C a pu s’exécuter ; D reste bloquée. Le Workflow conserve le KO de B.")] : []),
        step("Fin du Workflow", KO, {}, "Le Workflow termine en FINISHED_KO à cause de B. L’erreur ignorée de A ne bloque pas à elle seule les dépendances.")] });
  }

  for (const stop of [false, true]) {
    add({ id: `ko-direct-${stop}`, family: "KO et blocages", title: stop ? "A échoue : B et C sont bloquées" : "A échoue : B est bloquée, C peut continuer", stop_on_error: stop,
      nodes: triple(), edges: [["A", "B"]], tests: [realErrorTest], sources: ["decision", "aggregation"],
      summary: stop ? "B dépend de A ; C est indépendante. Avec stop_on_error: true, le KO de A empêche le lancement de B et de C." : "Avec stop_on_error: false, le KO de A bloque B qui en dépend, mais n’empêche pas C, indépendante, de démarrer.",
      steps: [step("A échoue", RK, { A: KO }, "B dépend de A ; C est indépendante.", { decisions: { B: "BLOCK", C: stop ? "BLOCK" : "LAUNCH" } }),
        step(stop ? "B et C sont bloquées" : "B est bloquée, C travaille", RK, { B: { status: B, causes: ["A"] }, C: stop ? { status: B, causes: ["A"] } : R }, "BLOCKED signifie que la Task n’a pas démarré à cause d’une erreur ailleurs ; elle n’a pas elle-même échoué pendant une exécution."),
        step("Fin", KO, stop ? {} : { C: OK }, "La réussite d’une Task indépendante ne corrige pas le KO de A.")] });
  }
  add({ id: "ko-running", family: "KO et blocages", title: "B peut être bloquée avant la fin de A en erreur", nodes: chain(), edges: [["A", "B"]],
    summary: "A est encore en cours, mais affiche RUNNING_KO. Avec ignore_on_error: false, Lancelot peut déjà bloquer B qui dépend de A.", sources: ["blocking", "decision"], tests: [decisionTest],
    steps: [step("A est encore en cours avec une erreur", RK, { A: RK }, "L’erreur de A suffit pour décider de ne pas lancer B, sans attendre la fin de A.", { decisions: { B: "BLOCK" } }),
      step("B est bloquée, A continue de terminer", RK, { B: { status: B, causes: ["A"] } }, "B ne sera pas exécutée. Le Workflow doit néanmoins attendre la fin de A."),
      step("Fin de A puis du Workflow", KO, { A: KO }, "A a enfin terminé, puis le Workflow est finalisé.")] });
  add({ id: "ko-transitif", family: "KO et blocages", title: "A échoue : B puis C sont bloquées", nodes: triple(), edges: [["A", "B"], ["B", "C"]],
    summary: "B dépend de A, et C dépend de B. L’erreur de A empêche donc l’exécution de B puis de C. A reste identifiée comme l’origine des deux blocages.", sources: ["blocking"], tests: [decisionTest],
    steps: [step("A échoue", RK, { A: KO }, "B dépend de A : B ne pourra pas démarrer.", { decisions: { B: "BLOCK" } }),
      step("B est bloquée", RK, { B: { status: B, causes: ["A"] } }, "C dépend de B qui ne sera pas exécutée. C sera donc aussi bloquée, à cause de l’échec initial de A.", { decisions: { C: "BLOCK" } }),
      step("Fin", KO, { C: { status: B, causes: ["A"] } }, "Une erreur d’exécution, deux Tasks non exécutées.")] });
  add({ id: "ko-multiple", family: "KO et blocages", title: "C est bloquée par les échecs de A et de B", nodes: triple(), edges: [["A", "C"], ["B", "C"]],
    summary: "C dépend de A et de B. Les deux Tasks ont échoué : Lancelot conserve leurs deux noms comme causes du blocage de C.", sources: ["blocking"],
    tests: ["test_workflow_structured_contract.py::test_blocking_task_names_propagate_through_always_run_dependencies"],
    steps: [step("A et B ont toutes les deux échoué", RK, { A: KO, B: KO }, "C ne peut pas démarrer puisque ses deux prérequis sont en erreur.", { decisions: { C: "BLOCK" } }),
      step("C est bloquée, le Workflow termine en erreur", KO, { C: { status: B, causes: ["A", "B"] } }, "A et B sont toutes deux enregistrées comme causes du blocage de C. Le Workflow termine en FINISHED_KO.")] });
  add({ id: "ko-task-deja-lancee", family: "KO et blocages", title: "Une Task déjà lancée termine", stop_on_error: true, nodes: triple(),
    summary: "A et B ont déjà démarré quand A échoue. Avec stop_on_error: true, B peut terminer, mais C, qui attend encore son lancement, est bloquée.", sources: ["capacity", "aggregation"],
    steps: [step("A et B travaillent", R, { A: R, B: R }, "C attend une décision de lancement."),
      step("A échoue", RK, { A: KO, C: { status: B, causes: ["A"] } }, "B continue. C est bloquée."),
      step("Fin", KO, { B: OK }, "Le Workflow attend B avant de publier sa fin.")] });
  for (const flag of ["reserved", "launched"]) {
    add({ id: `ko-waiting-${flag}`, family: "Capacité et concurrence", title: `Le KO de A n’annule pas B ${flag === "reserved" ? "déjà choisie pour démarrer" : "déjà lancée"}`,
      level: "limite", mode: "état ciblé", stop_on_error: true, nodes: chain(), sources: ["capacity", "aggregation"],
      tests: ["test_workflow_structured_contract.py::test_workflow_upd_run_status_waits_for_launched_waiting_task"],
      summary: "B affiche encore WAITING, mais son lancement est déjà engagé quand A échoue. Même avec stop_on_error: true, Lancelot laisse B démarrer et attend sa fin.",
      steps: [step("A échoue pendant le lancement de B", RK, { A: KO, B: { status: W, [flag]: true } }, "B n’est plus une Task simplement en attente : son lancement est réservé ou son thread a déjà démarré. Le Workflow reste en cours avec RUNNING_KO."),
        step("B travaille", RK, { B: R }, "B affiche maintenant RUNNING. L’arrêt global ne l’a pas empêchée de démarrer."),
        step("B réussit, le Workflow reste en erreur", KO, { B: OK }, "B a pu s’exécuter et a réussi. Le Workflow termine néanmoins en FINISHED_KO à cause de A.")] });
  }

  add({ id: "always-succes", family: "always_run", title: "Même avec always_run, C doit attendre la fin de A", nodes: cleanup(), edges: [["A", "C"]],
    summary: "C dépend de A. L’option always_run: true ne permet pas à C de démarrer pendant que A travaille : elle doit attendre sa fin.", tests: [decisionTest],
    steps: [step("A travaille", R, { A: R }, "C attend A.", { decisions: { C: "WAIT" } }),
      step("A réussit", R, { A: OK }, "A a terminé : C peut maintenant démarrer.", { decisions: { C: "LAUNCH" } }),
      ending({ C: OK }, "C s’exécute puis réussit. Le Workflow termine ses opérations de fin et passe à FINISHED_OK.")] });
  add({ id: "always-apres-ko-ignore", family: "always_run", title: "always_run attend la fin de A puis accepte son KO_IGNORED",
    nodes: [task("A", "erreur ignorée", { ignore_on_error: true }), task("C", "cleanup", { always_run: true })],
    edges: [["A", "C"]],
    summary: "C avec always_run: true n’interrompt pas A et attend son statut terminal. Quand A termine en KO_IGNORED, C peut s’exécuter ; cette erreur ignorée ne met pas le Workflow en KO.",
    sources: ["decision", "transitive", "task"], tests: [decisionTest],
    steps: [step("A est encore en erreur ; C attend", RK, { A: RK }, "Le statut RUNNING_KO de A n’est pas terminal. C ne peut pas encore démarrer.", { decisions: { C: "WAIT" } }),
      step("A termine en KO_IGNORED", R, { A: IGNORED }, "A a terminé. always_run autorise C à continuer malgré le statut d’erreur ignorée.", { decisions: { C: "LAUNCH" } }),
      step("C effectue son nettoyage", R, { C: R }, "C démarre après la fin complète de A."),
      ending({ C: OK }, "C réussit. L’erreur de A reste visible, mais le Workflow termine en FINISHED_OK.")] });
  for (const stop of [false, true]) {
    add({ id: `always-ko-${stop}`, family: "always_run", title: `C s’exécute après l’échec de A · stop_on_error: ${stop}`, stop_on_error: stop,
      nodes: cleanup(), edges: [["A", "C"]], sources: ["decision", "finalization"], tests: [realErrorTest],
      summary: "A a terminé en erreur. Grâce à always_run: true, C peut tout de même démarrer pour effectuer son nettoyage. Le Workflow restera en erreur.",
      steps: [step("A termine en erreur", RK, { A: KO }, "C peut démarrer puisque A a terminé. always_run autorise ce lancement malgré l’erreur.", { decisions: { C: "LAUNCH" } }),
        step("C effectue son nettoyage", RK, { C: R }, "Le Workflow reste RUNNING_KO pendant l’exécution de C."),
        step("Fin", KO, { C: OK }, "La réussite de C ne transforme pas A en succès.")] });
  }
  for (const stop of [false, true]) {
    add({ id: `always-ancetre-${stop}`, family: "always_run", title: `B est bloquée, mais C doit encore attendre A · stop_on_error: ${stop}`, stop_on_error: stop, level: "composé",
      nodes: [task("A", "origine"), task("B", "intermédiaire"), task("C", "cleanup", { always_run: true })], edges: [["A", "B"], ["B", "C"]],
      sources: ["decision", "transitive"], tests: ["test_workflow_rework.py::test_always_run_waits_for_running_ko_ancestor"],
      summary: "C dépend de B, qui dépend de A. B est déjà BLOCKED, mais A travaille encore avec une erreur. always_run oblige C à attendre la fin de A, même si C ne dépend pas directement de A.",
      steps: [step("B est bloquée, A est encore en cours", RK, { A: RK, B: { status: B, causes: ["A"] } }, "B ne sera pas exécutée. A n’a pas fini : C doit encore attendre.", { decisions: { C: "WAIT" } }),
        step("A termine en erreur", RK, { A: KO }, "A et B ont maintenant un statut de fin. C peut démarrer.", { decisions: { C: "LAUNCH" } }),
        step("C effectue son nettoyage", RK, { C: R }, "C démarre seulement après la fin de A."), step("Fin", KO, { C: OK }, "C a réussi, mais le Workflow reste en erreur à cause de A.")] });
  }
  add({ id: "always-plusieurs-prerequis", family: "always_run", title: "D avec always_run accepte des prérequis aux résultats différents", level: "composé",
    nodes: [...triple(), task("D", "cleanup", { always_run: true })], edges: [["A", "D"], ["B", "D"], ["C", "D"]],
    summary: "D dépend de A, de B et de C. Avec always_run: true, D attend que les trois aient fini, mais n’exige pas qu’elles aient toutes réussi.", sources: ["decision", "transitive"],
    steps: [step("A et B ont fini, C travaille encore", RK, { A: OK, B: KO, C: R }, "D attend encore C, même si A et B ont déjà terminé.", { decisions: { D: "WAIT" } }),
      step("C termine avec un avertissement", RK, { C: WARN }, "Les trois Tasks ont fini : A a réussi, B a échoué et C a un avertissement. D peut démarrer.", { decisions: { D: "LAUNCH" } }),
      step("D réussit, le Workflow reste en erreur", KO, { D: OK }, "D s’est exécutée et a réussi malgré les résultats différents de ses prérequis. Le Workflow termine en FINISHED_KO à cause de B.")] });
  for (const nextAlways of [false, true]) {
    add({ id: `always-suite-${nextAlways}`, family: "always_run", title: nextAlways ? "C puis B peuvent s’exécuter après le KO de A" : "C réussit son nettoyage, mais B reste bloquée par A", level: "composé",
      nodes: [...cleanup(), task("B", "après cleanup", { always_run: nextAlways })], edges: [["A", "C"], ["C", "B"]],
      sources: ["blocking", "decision"], tests: ["test_workflow_structured_contract.py::test_scheduler_keeps_always_run_exception_and_blocks_its_descendants"],
      summary: nextAlways ? "A a échoué. C et B ont toutes les deux always_run: true : C peut s’exécuter après A, puis B après C." : "A a échoué. C peut s’exécuter grâce à always_run: true, mais B n’a pas cette option. La réussite de C ne suffit pas à autoriser B : le KO de A est toujours pris en compte.",
      steps: [step("C effectue son nettoyage", RK, { A: KO, C: R }, "A est terminée en erreur. C travaille ; B attend la fin de C."),
        step("C réussit", RK, { C: OK }, nextAlways ? "A et C ont fini. Grâce à son option always_run: true, B peut démarrer à son tour." : "C a réussi, mais B est bloquée à cause de l’échec initial de A.", { decisions: { B: nextAlways ? "LAUNCH" : "BLOCK" } }),
        step("Fin", KO, { B: nextAlways ? OK : { status: B, causes: ["A"] } }, nextAlways ? "B s’exécute puis réussit. Le Workflow reste FINISHED_KO à cause de A." : "B n’a pas été exécutée. Le Workflow termine en FINISHED_KO à cause de A.")] });
  }
  add({ id: "always-echec-nettoyage", family: "always_run", title: "Le nettoyage échoue à son tour", level: "composé",
    nodes: [...cleanup(), task("B", "dernier recours", { always_run: true })], edges: [["A", "C"], ["C", "B"]],
    summary: "A a échoué. C démarre avec always_run: true, mais échoue aussi. B, qui possède également always_run: true, pourra tout de même s’exécuter après C.",
    steps: [step("A et C ont terminé en erreur", RK, { A: KO, C: KO }, "Tous les prérequis de B ont fini. B peut démarrer grâce à always_run: true.", { decisions: { B: "LAUNCH" } }),
      step("B réussit, le Workflow reste en erreur", KO, { B: OK }, "B s’est exécutée et a réussi. Les échecs de A et de C maintiennent le Workflow en FINISHED_KO.")] });
  add({ id: "always-sans-dependance", family: "always_run", title: "C sans dépendance peut démarrer avant la fin de A",
    nodes: [task("A", "longue"), task("C", "cleanup", { always_run: true })],
    summary: "C a always_run: true, mais aucun prérequis. Cette option ne signifie pas « attendre toutes les Tasks » : C peut commencer pendant que A travaille. Pour attendre A, C doit déclarer une dépendance vers A.", tests: [decisionTest],
    steps: [step("A travaille", R, { A: R }, "C ne dépend pas de A et peut déjà démarrer.", { decisions: { C: "LAUNCH" } }),
      step("C a fini avant A", R, { C: OK }, "C a réussi son nettoyage alors que A travaille encore."), ending({ A: OK })] });
  add({ id: "always-ancetre-aborted", family: "always_run", title: "C avec always_run peut suivre une Task annulée", mode: "état ciblé", level: "limite",
    nodes: cleanup(), edges: [["A", "C"]], summary: "On part d’une Task A déjà ABORTED, c’est-à-dire annulée. Si Lancelot peut encore lancer des Tasks, C avec always_run: true n’a plus à attendre A.", tests: [decisionTest],
    caution: "Cet exemple commence dans un état choisi pour vérifier cette seule règle. Il ne signifie pas qu’un Workflow arrêté par une erreur fatale reprendra automatiquement son exécution.",
    steps: [step("A est déjà annulée", RK, { A: AB }, "A ne sera plus exécutée. C peut démarrer si le Workflow n’a pas arrêté les lancements.", { decisions: { C: "LAUNCH" } }),
      step("C démarre", RK, { C: R }, "L’exemple s’arrête au lancement de C. Sans connaître la raison de l’annulation de A et la suite de C, on ne fixe pas de résultat final au Workflow.")] });

  add({ id: "inactive-isolee", family: "Désactivation", title: "Une Task configurée inactive", nodes: [task("A", "inactive", { active: false }), task("B", "active")],
    sources: ["task", "aggregation"], summary: "A a active: false dès la configuration. Elle ne s’exécute pas et sa désactivation n’empêche pas B, indépendante, de réussir.",
    steps: [step("Départ", W, {}, "A est déjà DEACTIVATED ; B n’a pas de dépendance vers A."),
      step("B travaille", R, { B: R }, "A n’est pas lancée."), ending({ B: OK })] });
  add({ id: "inactive-toutes", family: "Désactivation", title: "Toutes les Tasks sont inactives", nodes: [task("A", "inactive", { active: false }), task("B", "inactive", { active: false })],
    summary: "L’absence de Task active n’est pas une erreur.", sources: ["scheduling", "aggregation"], tests: [finalTest],
    steps: [step("Aucun lancement", R, {}, "Le Workflow passe à sa finalisation."), ending({}, "Le Workflow finit en OK si sa préparation et sa finalisation réussissent.")] });
  add({ id: "inactive-vide", family: "Désactivation", title: "Le Workflow ne contient aucune Task à lancer", nodes: [], mode: "état ciblé",
    summary: "On examine un Workflow déjà construit, sans aucune Task. L’absence de travail ne provoque pas d’erreur dans le run.", sources: ["scheduling", "aggregation"],
    caution: "Ce cas vérifie le run, pas le chargement de la configuration. Il ne garantit pas qu’un fichier settings.yml vide sera accepté.",
    steps: [step("Aucune Task à lancer", R, {}, "Lancelot n’exécute aucune Task et passe directement aux opérations de fin du Workflow."), ending({})] });
  add({ id: "deactivation-chaine", family: "Désactivation", title: "T désactive A : B et C sont aussi désactivées", nodes: [...triple(), task("T", "déclencheur")],
    edges: [["A", "B"], ["B", "C"]], actions: [["T", "A"]], sources: ["deactivate", "propagation"], tests: [inactiveTest],
    summary: "T désactive A pendant le run, avant son lancement. B dépend de A, et C dépend de B : B et C sont donc aussi désactivées et ne s’exécuteront pas.",
    steps: [step("T travaille", R, { T: R }, "A, B et C sont encore en attente ; aucun de leurs lancements n’est réservé."),
      step("T désactive A, puis B et C le sont aussi", R, { A: D, B: D, C: D }, "L’appel deactivate_task(A) est accepté et renvoie 1. A, B et C passent à DEACTIVATED avant que Lancelot puisse en lancer une."),
      ending({ T: OK }, "Aucune erreur : le Workflow peut terminer en OK.")] });
  add({ id: "deactivation-join", family: "Désactivation", title: "Un seul prérequis désactivé suffit", nodes: [...triple(), task("T", "déclencheur")],
    edges: [["A", "C"], ["B", "C"]], actions: [["T", "A"]], sources: ["propagation"],
    summary: "C ne s’exécute pas si A est désactivée, même si B réussit.",
    steps: [step("B a réussi", R, { B: OK, T: R }, "C attend encore A."),
      step("T désactive A", R, { A: D, C: D }, "La désactivation l’emporte sur la réussite de B."), ending({ T: OK })] });
  add({ id: "deactivation-priorite-ko", family: "Désactivation", title: "Un prérequis en erreur et un autre désactivé : C est désactivée", level: "composé", mode: "état ciblé",
    nodes: triple(), edges: [["A", "C"], ["B", "C"]], sources: ["propagation", "classification"], tests: [inactiveTest],
    summary: "C dépend de A et de B. A a échoué, mais B est désactivée : C sera classée DEACTIVATED plutôt que BLOCKED.",
    steps: [step("A a échoué, B est désactivée", RK, { A: KO, B: D }, "C attend encore son lancement. Lancelot doit lui appliquer la désactivation de B."),
      step("C est désactivée à son tour", RK, { C: D }, "C passe à DEACTIVATED parce qu’elle dépend de B. Elle n’est pas classée BLOCKED à cause de A."),
      step("Fin", KO, {}, "Le KO de A reste présent dans le Workflow.")] });
  add({ id: "deactivation-blocked", family: "Désactivation", title: "C déjà bloquée devient désactivée quand T désactive B", level: "composé",
    nodes: [...triple(), task("T", "déclencheur")], edges: [["A", "C"], ["B", "C"]], actions: [["T", "B"]],
    sources: ["deactivate", "propagation"], tests: ["test_workflow.py::test_workflow_run_reclassifies_blocked_task_after_dynamic_deactivation"],
    summary: "C est déjà bloquée parce que A a échoué. T désactive ensuite son autre prérequis B : C change alors de statut et devient DEACTIVATED.",
    steps: [step("C est bloquée", RK, { A: KO, C: { status: B, causes: ["A"] }, T: R }, "B est encore WAITING et peut être désactivée."),
      step("T désactive B", RK, { B: D, C: D }, "B puis C passent à DEACTIVATED. C est désormais considérée comme désactivée, et non plus comme bloquée par A."),
      step("Fin", KO, { T: OK }, "Le résultat final reste en KO à cause de A.")] });
  add({ id: "deactivation-barriere", family: "Désactivation", title: "A désactivée : C peut s’exécuter, B reste désactivée", level: "composé",
    nodes: [task("A", "source"), task("C", "cleanup", { always_run: true }), task("B", "suite"), task("T", "déclencheur")],
    edges: [["A", "C"], ["C", "B"]], actions: [["T", "A"]], sources: ["propagation", "blocking"],
    tests: ["test_workflow_rework.py::test_deactivation_crosses_always_run_without_deactivating_cleanup"],
    summary: "T désactive A. C dépend de A mais reste active grâce à always_run: true. B dépend directement de C et indirectement de A : sans always_run, B est désactivée même si C réussit.",
    caution: "Règle mise à jour : always_run protège uniquement la Task qui porte cette option. Pour que B puisse aussi s’exécuter après C malgré la désactivation de A, B doit avoir always_run: true.",
    steps: [step("T désactive A ; B est aussi désactivée", R, { A: D, B: D, T: R }, "La désactivation traverse C sans la désactiver et atteint B. A a fini avec DEACTIVATED : C peut démarrer.", { decisions: { C: "LAUNCH" } }),
      step("C effectue son nettoyage", R, { C: R }, "C s’exécute grâce à always_run. B reste DEACTIVATED ; elle n’attend pas une réussite de C pour être relancée."),
      step("C et T ont réussi ; B reste désactivée", R, { C: OK, T: OK }, "La réussite de C ne réactive pas B. La désactivation de A n’est pas une erreur."),
      ending({}, "B n’a pas été exécutée. Sans erreur ni avertissement, le Workflow termine en FINISHED_OK.")] });
  add({ id: "deactivation-explicite-always", family: "Désactivation", title: "T peut désactiver C malgré always_run: true",
    nodes: [task("C", "cleanup", { always_run: true }), task("T", "déclencheur")], actions: [["T", "C"]],
    sources: ["deactivate", "propagation"], summary: "always_run: true n’empêche pas un appel direct pour désactiver C. Cet appel est accepté si C est encore WAITING, sans lancement réservé ni déjà démarré.",
    steps: [step("T travaille", R, { T: R }, "C attend encore ; Lancelot n’a pas engagé son lancement."),
      step("T désactive directement C", R, { C: D }, "L’appel deactivate_task(C) est accepté et renvoie 1. C ne s’exécutera pas malgré always_run: true."), ending({ T: OK })] });
  for (const [suffix, state, reason, title] of [
    ["running", { status: R }, "déjà en cours d’exécution", "T ne peut pas désactiver A qui travaille déjà"],
    ["reserved", { status: W, reserved: true }, "déjà choisie pour être lancée", "T ne peut pas désactiver A dont le lancement est réservé"],
    ["launched", { status: W, launched: true }, "déjà lancée mais encore affichée WAITING", "T ne peut pas désactiver A déjà lancée, même affichée WAITING"],
    ["finished", { status: OK }, "déjà terminée avec succès", "T ne peut pas désactiver A qui a déjà réussi"],
    ["blocked", { status: B, causes: ["origine externe"] }, "déjà bloquée, avec le statut BLOCKED", "Un appel direct ne peut pas désactiver A déjà BLOCKED"],
  ]) {
    add({ id: `deactivation-refus-${suffix}`, family: "Désactivation", title, mode: "état ciblé", level: "limite",
      nodes: [task("A", "cible"), task("T", "déclencheur")], actions: [["T", "A"]], sources: ["deactivate"],
      tests: ["test_workflow.py::test_workflow_explicit_deactivation_accepts_only_waiting_tasks"],
      summary: `T demande la désactivation de A, mais A est ${reason}. L’appel est refusé : il renvoie 2 et ne change pas le statut de A.`,
      caution: suffix === "blocked" ? "La Task à l’origine du blocage de A n’est pas représentée. Ce refus concerne un appel visant directement A. Si un prérequis de A est désactivé, cette désactivation peut en revanche faire passer A de BLOCKED à DEACTIVATED." : "",
      steps: [step("T va demander la désactivation de A", R, { A: state, T: R }, `A est ${reason}. Sa désactivation directe n’est donc plus autorisée.`),
        step("La demande est refusée", R, {}, "L’appel deactivate_task(A) renvoie 2. A conserve son statut. Cet exemple s’arrête à la réponse à cet appel, sans représenter la suite du Workflow.")] });
  }
  add({ id: "deactivation-inconnue", family: "Désactivation", title: "T demande la désactivation d’une Task inexistante", mode: "état ciblé",
    nodes: [task("T", "déclencheur")], sources: ["deactivate"], tests: ["test_workflow.py::test_workflow_get_iud_infos_and_deactivate_task_ignore_unknown_names"],
    summary: "T demande la désactivation d’une Task qui n’existe pas. Lancelot ne crée pas cette Task et ne modifie aucun statut ; l’appel renvoie 0.",
    steps: [step("T vise un nom inexistant", R, { T: R }, "L’appel deactivate_task('absente') renvoie 0 : aucune Task ne porte ce nom."), ending({ T: OK })] });
  for (const stop of [false, true]) {
    add({ id: `marge-complete-${stop}`, family: "Interactions avancées", title: stop ? "T est bloquée : I ne sera pas désactivée" : "T désactive I : D et A sont désactivées, C peut nettoyer", level: "avancé", stop_on_error: stop,
      nodes: [task("F", "failed"), task("I", "inactive"), task("D", "descendant"), task("C", "cleanup", { always_run: true }), task("A", "after_cleanup"), task("T", "trigger")],
      edges: [["F", "D"], ["I", "D"], ["D", "C"], ["C", "A"]], actions: [["T", "I"]], sources: ["decision", "propagation", "blocking", "transitive"],
      tests: ["test_workflow.py::test_workflow_run_waits_for_transitive_dependencies_before_always_run"],
      summary: stop ? "F a échoué. Avec stop_on_error: true, T ne peut pas démarrer pour désactiver I. I et D seront bloquées, ce qui permettra ensuite à C avec always_run de s’exécuter. A restera bloquée." : "F a échoué, mais stop_on_error: false laisse T démarrer. T désactive I, ce qui désactive D puis A, même à travers C. C reste active grâce à always_run et peut nettoyer ; A, sans cette option, ne sera pas exécutée.",
      caution: "L’ordre montré est un exemple. Selon le moment où Lancelot examine les Tasks, C peut démarrer dans le même passage que le changement de statut de ses prérequis, ou lors du passage suivant.",
      steps: stop ? [
        step("F a échoué, I attend encore", RK, { F: KO }, "C dépend de D, qui dépend de F et de I. F a fini, mais I attend encore : C ne peut pas démarrer."),
        step("I, D, T et A sont bloquées", RK, { D: { status: B, causes: ["F"] }, I: { status: B, causes: ["F"] }, T: { status: B, causes: ["F"] }, A: { status: B, causes: ["F"] } }, "I et D ne seront plus exécutées. Tous les prérequis directs et indirects de C ont un statut de fin : C peut démarrer.", { decisions: { C: "LAUNCH" } }),
        step("C effectue son nettoyage", RK, { C: R }, "T ne s’est pas exécutée : elle n’a donc pas désactivé I."),
        step("C réussit, A reste bloquée", KO, { C: OK }, "La réussite de C ne relance pas A. Le Workflow termine en FINISHED_KO à cause de F.")
      ] : [
        step("F a échoué, I attend encore", RK, { F: KO }, "D dépend à la fois de F et de I. C dépend de D et doit aussi attendre I, même sans lien direct vers I."),
        step("D est bloquée, T travaille", RK, { D: { status: B, causes: ["F"] }, T: R }, "C attend toujours I qui est WAITING. T, indépendante de F, peut s’exécuter.", { decisions: { C: "WAIT" } }),
        step("T désactive I ; D et A sont aussi désactivées", RK, { I: D, D: D, A: D, T: OK }, "T réussit. La désactivation de I traverse C avec always_run et atteint A, qui ne porte pas cette option. Tous les prérequis de C ont fini : C peut démarrer.", { decisions: { C: "LAUNCH" } }),
        step("C réussit son nettoyage ; A reste désactivée", RK, { C: OK }, "La réussite de C ne réactive pas A. Seule C bénéficie ici de always_run."),
        step("A n’a pas été exécutée, le Workflow reste en erreur", KO, {}, "A reste DEACTIVATED. F reste FINISHED_KO : le Workflow termine en erreur.")
      ] });
  }
  add({ id: "interaction-nettoyage-autre-branche", family: "Interactions avancées", title: "C peut nettoyer pendant que la Task indépendante L travaille", level: "composé", stop_on_error: true,
    nodes: [task("F", "échec"), task("L", "longue"), task("C", "cleanup", { always_run: true })], edges: [["F", "C"]],
    summary: "C dépend de F, pas de L. F a terminé en erreur : C avec always_run peut démarrer, même si L, déjà lancée, travaille encore.", sources: ["decision", "transitive"],
    steps: [step("F a échoué, L travaille", RK, { F: KO, L: R }, "C n’a pas à attendre L puisqu’elle n’en dépend pas.", { decisions: { C: "LAUNCH" } }),
      step("C a réussi, L continue", RK, { C: OK }, "Le nettoyage effectué par C est terminé, mais le Workflow doit encore attendre L."),
      step("L termine, puis le Workflow termine en erreur", KO, { L: OK }, "L a réussi. Le Workflow termine en FINISHED_KO à cause de F.")] });
  add({ id: "workflow-init-ko-nettoyage", family: "Erreurs du Workflow", title: "C peut encore nettoyer après un KO d’initialisation", level: "avancé", mode: "état ciblé", stop_on_error: true,
    nodes: cleanup(), edges: [["A", "C"]], sources: ["preparation", "decision"],
    summary: "L’exemple commence avec A déjà en erreur et le Workflow en FINISHED_KO. Si le run est tout de même appelé et que C attend encore, Lancelot vérifie si C avec always_run peut s’exécuter.",
    caution: "Certains contrôles de configuration empêchent tout appel au run. Ce cas ne garantit donc pas qu’une Task de nettoyage s’exécutera après n’importe quelle erreur d’initialisation.",
    steps: [step("A a échoué pendant l’initialisation", KO, { A: KO }, "Le Workflow est déjà en erreur, mais C existe encore et attend son lancement."),
      step("Le run est appelé malgré le KO initial", RK, {}, "Le Workflow repasse à RUNNING_KO pour traiter ce qui reste. A a fini : C peut démarrer.", { decisions: { C: "LAUNCH" } }),
      step("C réussit, le Workflow reste en erreur", KO, { C: OK }, "C s’est exécutée et a réussi. L’échec initial de A maintient le Workflow en FINISHED_KO.")] });
  add({ id: "workflow-udf-creation", family: "Erreurs du Workflow", title: "La création des fonctions SQL échoue avant le lancement des Tasks", stop_on_error: true,
    nodes: cleanup(), edges: [["A", "C"]], sources: ["preparation", "run", "abort"],
    tests: ["test_workflow_rework.py::test_phase_failure_is_reported_as_terminal_ko"],
    summary: "Avant de lancer les Tasks, Lancelot crée les fonctions SQL déclarées pour le run, appelées UDF. Si cette préparation échoue, le run s’arrête : même C avec always_run ne sera pas lancée.",
    steps: [step("Préparation des fonctions SQL", W, {}, "A et C n’ont pas encore démarré."),
      step("La création d’une fonction SQL échoue", RK, {}, "Lancelot enregistre l’erreur et abandonne le déroulement normal du run."),
      step("A et C sont annulées", KO, { A: AB, C: AB }, "Les Tasks qui attendaient sont ABORTED, y compris C malgré always_run. Le Workflow termine en FINISHED_KO sans effectuer sa séquence habituelle de finalisation.")] });
  add({ id: "workflow-thread-refuse", family: "Erreurs du Workflow", title: "Lancelot ne parvient pas à démarrer l’exécution de B", level: "avancé", nodes: chain(),
    sources: ["capacity", "run", "abort"], tests: ["test_workflow_rework.py::test_scheduler_error_waits_for_started_tasks_before_terminal_ko"],
    summary: "A et B sont indépendantes. A travaille déjà quand la création ou le démarrage du thread de B échoue. Lancelot libère la place prévue pour B, puis attend A avant de terminer le Workflow en erreur.",
    steps: [step("A travaille", R, { A: R }, "B va être lancée."),
      step("Échec du lancement de B", RK, {}, "B n’a pas commencé son travail. Sa place et sa réservation sont libérées ; A continue."),
      step("A termine", RK, { A: OK }, "Lancelot a attendu la fin complète de A avant de terminer le Workflow."),
      step("Fin", KO, { B: AB }, "B n’a pas été exécutée : elle est ABORTED, pas FINISHED_KO.")] });
  for (const [phase, label] of [
    ["drop_tables", "suppression des tables"],
    ["drop_all_udf", "suppression des UDF"],
    ["warn_data_usage", "contrôle d’usage des données"],
    ["task_logs", "bilan des Tasks"],
    ["show_logs_ending", "affichage du bilan"],
    ["run_audit", "audit"],
    ["wkf_logs", "logs finaux"],
  ]) {
    add({ id: `workflow-echec-${phase}`, family: "Erreurs du Workflow", title: `Erreur de finalisation · ${label}`, level: "composé",
      nodes: [task("A", "réussie")], sources: ["finalization", "run"],
      tests: ["drop_tables", "warn_data_usage", "task_logs", "run_audit"].includes(phase) ? ["test_workflow_rework.py::test_phase_failure_is_reported_as_terminal_ko"] : [],
      summary: `A a réussi, mais le Workflow doit encore terminer ses propres opérations. Si l’étape « ${label} » échoue, le Workflow termine en erreur malgré la réussite de A.`,
      caution: ["run_audit", "wkf_logs"].includes(phase) ? "Le Workflow affiche son résultat avant l’audit et les derniers logs. Une erreur pendant ces opérations peut donc faire passer le Workflow de FINISHED_OK à FINISHED_KO." : "",
      steps: [step("Tasks réussies", R, { A: OK }, "Le Workflow a encore sa finalisation à effectuer."),
        ...(["run_audit", "wkf_logs"].includes(phase) ? [step("Le Workflow affiche d’abord FINISHED_OK", OK, {}, "Les Tasks ont réussi et les opérations principales de fin sont terminées. Il reste encore l’audit et les derniers logs.")] : []),
        step("Une opération de fin échoue", KO, {}, `L’étape « ${label} » échoue. A conserve FINISHED_OK, mais le Workflow termine en FINISHED_KO.`)] });
  }
  add({ id: "final-attente-thread", family: "Finalisation", title: "A affiche FINISHED_OK, mais son exécution doit encore se terminer complètement", mode: "état ciblé", level: "limite",
    nodes: [task("A", "réussie")], sources: ["finalization"],
    tests: ["test_workflow_rework.py::test_finalization_joins_real_task_thread_before_cleanup"],
    summary: "Le statut de succès de A peut être visible juste avant la fin complète de son thread. Le Workflow attend cette fin pour ne pas supprimer des ressources que A utiliserait encore.",
    steps: [step("A affiche déjà FINISHED_OK", R, { A: { status: OK, threadPending: true } }, "L’exécution de A n’a pas encore totalement rendu la main. Le Workflow attend avant de nettoyer."),
      step("L’exécution de A est complètement terminée", R, { A: OK }, "Lancelot peut maintenant supprimer les ressources temporaires et terminer le bilan du Workflow."), ending({})] });
  add({ id: "final-classification", family: "Finalisation", title: "Le run se termine avec B, C et D encore en attente", mode: "état ciblé", level: "avancé", stop_on_error: true,
    nodes: [task("A", "échec"), task("B", "dépendante"), task("C", "cleanup", { always_run: true }), task("D", "indépendante")],
    edges: [["A", "B"], ["B", "C"]], sources: ["classification", "abort"],
    summary: "On examine le moment où Lancelot a cessé de lancer des Tasks après le KO de A. B, C et D attendent encore : leur statut doit indiquer pourquoi elles n’ont pas été exécutées.",
    caution: "Cet exemple commence dans les opérations de fin du Workflow. Il ne représente pas un run encore en cours où Lancelot pourrait lancer C pour effectuer le nettoyage.",
    steps: [step("Les opérations de fin commencent", RK, { A: KO }, "B, C et D n’ont pas démarré, et aucun de leurs lancements n’est réservé."),
      step("B et D sont bloquées, C est annulée", RK, { B: { status: B, causes: ["A"] }, C: AB, D: { status: B, causes: ["A"] } }, "B est BLOCKED parce qu’elle dépend de A. D est BLOCKED par stop_on_error: true. C avec always_run n’a pas été exécutée : elle est ABORTED, pas considérée comme réussie."),
      step("Fin", KO, {}, "Une Task de nettoyage ABORTED n’a pas effectué le nettoyage.")] });
  add({ id: "final-blocked-seuls", family: "Finalisation", title: "A est bloquée et B a réussi : le Workflow termine en erreur", mode: "état ciblé",
    nodes: [task("A", "bloquée"), task("B", "réussie")], sources: ["aggregation"],
    summary: "On part de A déjà BLOCKED et de B déjà FINISHED_OK. Même si la Task à l’origine du blocage n’est pas représentée ici, la présence de A bloquée empêche un résultat global en succès.",
    steps: [step("A est bloquée, B a réussi", RK, { A: B, B: OK }, "Les deux Tasks ont un statut de fin ; aucune ne travaille ni n’attend un lancement."),
      step("Le Workflow termine en erreur", KO, {}, "B a réussi, mais A n’a pas pu être exécutée. Le Workflow termine en FINISHED_KO.")] });
  add({ id: "final-aborted-seuls", family: "Finalisation", title: "A et B sont annulées : le Workflow termine en erreur", mode: "état ciblé",
    nodes: chain(), sources: ["aggregation"],
    summary: "A et B sont déjà annulées avec le statut ABORTED. Puisqu’aucune Task n’a été exécutée avec succès, le Workflow termine en erreur.",
    steps: [step("A et B sont déjà annulées", RK, { A: AB, B: AB }, "Les deux Tasks sont ABORTED ; aucune n’attend un lancement ni ne travaille."),
      step("Le Workflow termine en erreur", KO, {}, "Lorsque toutes les Tasks sont annulées, le Workflow termine en FINISHED_KO.")] });

  add({ id: "limite-cycle", family: "Limites et configurations refusées", title: "Cycle entre Tasks : configuration refusée", level: "limite", mode: "configuration",
    nodes: chain(), edges: [["A", "B"], ["B", "A"]], layout: { A: [0, 0], B: [1, 0] }, sources: ["validation"],
    tests: ["test_workflow.py::test_workflow_control_settings_dependency_graph"],
    summary: "A dépend de B, et B dépend de A. Le contrôle de settings.yml pour la commande run détecte cette dépendance circulaire et refuse la configuration avant de lancer les Tasks. Les cycles passant par davantage de Tasks sont également refusés.",
    caution: "Comportement corrigé : cette configuration ne reste plus en attente indéfiniment. Le contrôle concerne les Tasks actives de la commande run ; les commandes ciblées gardent leur périmètre habituel. Un ancien avis sur ce cas porte sur le comportement précédent.",
    steps: [step("Configuration circulaire demandée", "NON_DÉMARRÉ", {}, "A et B sont actives et se déclarent mutuellement comme prérequis. Aucune Task n’a démarré."),
      step("Le contrôle refuse le cycle", "CONTRÔLE_KO", {}, "Lancelot signale le cycle, par exemple a -> b -> a : chaque Task dépend de la suivante. Il faut corriger une dépendance dans settings.yml avant de lancer le run.")] });
  for (const [id, title, nodes, edges, note] of [
    ["soi", "Une Task dépend d’elle-même", [task("A", "auto-dépendance")], [["A", "A"]], "A se déclare elle-même comme prérequis. Cette configuration est interdite."],
    ["absente", "Une dépendance n’existe pas", [task("A", "active"), task("X", "absente", { missing: true })], [["X", "A"]], "X est uniquement un repère graphique : aucune Task X n’existe dans la configuration."],
    ["inactive", "Une Task active dépend d’une Task configurée inactive", [task("A", "inactive", { active: false }), task("B", "active")], [["A", "B"]], "B est active mais dépend de A configurée active: false. Le chargement refuse cette dépendance. Ce n’est pas la même situation qu’une désactivation demandée pendant un run."],
  ]) {
    add({ id: `config-${id}`, family: "Limites et configurations refusées", title, nodes, edges,
      ...(id === "soi" ? { layout: { A: [0, 0] } } : {}), mode: "configuration", level: "limite",
      sources: ["validation"], summary: "Le contrôle des dépendances de la commande run refuse cette configuration avant l’exécution.",
      caution: "Aucune Task n’est lancée dans ce scénario. Le schéma montre seulement la configuration refusée ; les étiquettes active: true ou false ne sont pas des statuts d’exécution.",
      steps: [step("Configuration demandée", "NON_DÉMARRÉ", {}, note),
        step("Le run ne peut pas démarrer", "CONTRÔLE_KO", {}, "La dépendance doit être corrigée dans settings.yml avant l’exécution.")] });
  }
  add({ id: "config-format-dependances", family: "Limites et configurations refusées", title: "depends_on n’est pas une liste", nodes: chain(),
    mode: "configuration", level: "limite", sources: ["validation"], summary: "depends_on doit contenir une liste de noms de Tasks. Un simple texte, même avec le bon nom, est refusé.",
    steps: [step("Le nom est fourni sans liste", "NON_DÉMARRÉ", {}, "Exemple refusé : depends_on: source. Il manque les crochets qui indiquent une liste ; aucune dépendance valide n’est représentée par une flèche."),
      step("Le format doit être corrigé", "CONTRÔLE_KO", {}, "Écrire par exemple depends_on: [source], ou la liste YAML équivalente sur plusieurs lignes. Une liste vide ou null signifie qu’aucune dépendance n’est déclarée.")] });

  for (const stop of [false, true]) {
    add({ id: `ignore-postsql-${stop}`, family: "Avertissements et erreurs ignorées",
      title: `Le post-SQL de A échoue mais B peut démarrer · stop_on_error: ${stop}`,
      stop_on_error: stop, nodes: [task("A", "post-SQL en erreur", { ignore_on_error: true }), task("B", "dépendante")],
      edges: [["A", "B"]], sources: ["task", "decision", "finalization"],
      tests: ["test_task.py::test_task_postsql_failure_keeps_sql_error_visible",
        "test_workflow_rework.py::test_ignored_postsql_failure_allows_dependent_task"],
      summary: "B dépend de A. Le post-SQL hors boucle de A échoue ; avec ignore_on_error: true, A termine en KO_IGNORED. L’erreur reste visible, mais B peut ensuite démarrer.",
      steps: [step("A travaille ; B attend", R, { A: R }, "A exécute son traitement et ses opérations de fin. B attend que A soit terminée.", { decisions: { B: "WAIT" } }),
        step("Le post-SQL de A échoue", RK, { A: RK }, "L’erreur est enregistrée. A reste en cours pendant ses opérations de fin ; B attend encore.", { decisions: { B: "WAIT" } }),
        step("A termine en KO_IGNORED", R, { A: IGNORED }, "L’erreur du post-SQL est ignorée pour l’ordonnancement, mais reste consultable. B peut démarrer.", { decisions: { B: "LAUNCH" } }),
        step("B travaille", R, { B: R }, "B s’exécute après la fin de A."),
        ending({ B: OK }, "B réussit. Sans autre erreur ni avertissement, le Workflow termine en FINISHED_OK ; A conserve KO_IGNORED.")] });
  }

  add({ id: "ignore-presql-outloop", family: "Avertissements et erreurs ignorées",
    title: "Le pré-SQL de A échoue : A s’arrête, B peut démarrer",
    stop_on_error: true, nodes: [task("A", "pré-SQL en erreur", { ignore_on_error: true }), task("B", "dépendante")],
    edges: [["A", "B"]], sources: ["task", "decision", "finalization"],
    tests: ["test_task.py::test_task_presql_failure_stops_task_and_preserves_error",
      "test_workflow_rework.py::test_presql_failure_stops_source_before_dependent_decision"],
    summary: "Le pré-SQL hors boucle de A échoue. Avec ignore_on_error: true, A s’arrête sans exécuter ses Steps ni son post-SQL et termine en KO_IGNORED. B, qui dépend de A, peut ensuite démarrer.",
    caution: "L’erreur reste consultable. Autoriser B ne garantit pas que les données attendues ont été préparées par A : le pré-SQL et les Steps de A n’ont pas tous réussi.",
    steps: [step("A démarre ; B attend", R, { A: R }, "A exécute son pré-SQL hors boucle. B attend la fin de A.", { decisions: { B: "WAIT" } }),
      step("Le pré-SQL de A échoue", RK, { A: RK }, "L’erreur est enregistrée. A interrompt son traitement : ses Steps et son post-SQL ne sont pas exécutés.", { decisions: { B: "WAIT" } }),
      step("A termine en KO_IGNORED", R, { A: IGNORED }, "L’échec reste visible mais n’empêche pas B de démarrer, même avec stop_on_error: true.", { decisions: { B: "LAUNCH" } }),
      step("B travaille", R, { B: R }, "B s’exécute après l’arrêt de A."),
      ending({ B: OK }, "B réussit. Sans autre erreur ni avertissement, le Workflow termine en FINISHED_OK ; A conserve KO_IGNORED.")] });

  cases.forEach((scenario, index) => {
    const number = index + 1;
    scenario.displayNumber = String(number >= 72 ? number + 4 : number >= 57 ? number + 2 : number).padStart(2, "0");
  });
  const initialization = cases.find((scenario) => scenario.id === "ignore-ko-definitif");
  const postsqlIndex = cases.findIndex((scenario) => scenario.id === "ignore-postsql-false");
  const [postsql] = cases.splice(postsqlIndex, 1);
  const presqlIndex = cases.findIndex((scenario) => scenario.id === "ignore-presql-outloop");
  const [presql] = cases.splice(presqlIndex, 1);
  initialization.displayNumber = "16-A";
  postsql.displayNumber = "16-B";
  presql.displayNumber = "16-C";
  cases.splice(cases.indexOf(initialization) + 1, 0, postsql, presql);

  add({ id: "ko-task-deja-lancee-stop-false", family: "KO et blocages",
    title: "B déjà lancée termine et C peut démarrer · stop_on_error: false",
    stop_on_error: false, nodes: triple(), sources: ["decision", "capacity", "aggregation"],
    tests: ["test_workflow_rework.py::test_running_and_independent_tasks_continue_after_failure_without_stop"],
    summary: "A, B et C sont indépendantes. A échoue alors que B travaille déjà et que C attend encore son lancement. Avec stop_on_error: false, B continue et C peut démarrer si une place est libre.",
    steps: [step("A et B travaillent", R, { A: R, B: R }, "A et B sont déjà lancées. C n’a pas encore démarré."),
      step("A échoue ; B continue", RK, { A: KO }, "L’échec de A n’interrompt pas B. C ne dépend pas de A : elle peut démarrer lorsqu’une place est disponible.", { decisions: { C: "LAUNCH" } }),
      step("B et C travaillent", RK, { C: R }, "C a obtenu une place et travaille pendant que B continue."),
      step("B réussit ; C travaille encore", RK, { B: OK }, "Le Workflow attend la fin de C et reste en erreur à cause de A."),
      step("C réussit, le Workflow termine en erreur", KO, { C: OK }, "B et C ont réussi, mais ne corrigent pas l’échec de A. Le Workflow termine en FINISHED_KO.")] });
  const alreadyRunningFalse = cases.pop();
  alreadyRunningFalse.displayNumber = "24-B";
  const alreadyRunningIndex = cases.findIndex((scenario) => scenario.id === "ko-task-deja-lancee");
  cases.splice(alreadyRunningIndex + 1, 0, alreadyRunningFalse);

  add({ id: "statut-waiting-presql", family: "Statuts pendant l’exécution",
    title: "A est RUNNING dès son pré-SQL · anomalie corrigée",
    mode: "observation réelle", nodes: [task("A", "pré-SQL de l’itération")],
    sources: ["task_run", "iteration_run", "task"],
    tests: ["test_task.py::test_task_is_running_before_preparation_and_presql",
      "test_task_iteration.py::test_taskiteration_is_running_before_preparation_and_presql",
      "wkf_16_catalogue_runs/verify.py --case c82_outloop --case c82_inloop"],
    summary: "A passe à RUNNING dès le début effectif de son exécution, avant son pré-SQL. Dans une boucle, l’itération courante passe elle aussi à RUNNING avant son pré-SQL ; les futures itérations et les Steps non démarrés restent WAITING.",
    caution: "Le cas 82 montrait auparavant A encore WAITING pendant une requête SQL réellement en cours. Cette anomalie a été corrigée ; les variantes c82_outloop et c82_inloop sont maintenant conformes. Le lien et les avis historiques sont conservés : un avis antérieur doit être relu pour le comportement corrigé. Les contrôles portent sur le moteur ; ils ne prouvent pas les transitions live de Blaise.",
    steps: [
      step("Avant le lancement de A", R, { A: W }, "A n’a pas encore commencé : son statut WAITING est normal."),
      step("Le pré-SQL travaille : A est RUNNING", R, { A: R }, "Le pré-SQL hors boucle s’exécute après le passage de A à RUNNING."),
      step("Le pré-SQL d’une itération travaille", R, {}, "A et l’itération courante sont RUNNING, même si aucun Step n’a encore démarré. Les itérations suivantes restent WAITING."),
      ending({ A: OK }, "Après ses itérations et son post-SQL, A termine avec succès. Sans autre erreur, le Workflow termine en FINISHED_OK."),
    ] });
  cases[cases.length - 1].displayNumber = "82";

  add({ id: "statut-workflow-creation-udf", displayNumber: "83", scope: "workflow", probability: 2,
    family: "Statuts pendant l’exécution", title: "Le Workflow est RUNNING pendant la création des UDF",
    mode: "état ciblé", nodes: [task("A", "en attente")], sources: ["preparation"],
    tests: ["test_workflow_rework.py::test_lifecycle_workflow_is_running_during_udf_creation"],
    summary: "La création des fonctions SQL déclarées fait déjà partie du run. Le Workflow est RUNNING pendant cette préparation ; A reste WAITING tant qu’elle n’a pas démarré.",
    steps: [step("Avant le run", W, {}, "Le Workflow et A attendent leur lancement."),
      step("Création des UDF", R, {}, "Le Workflow a commencé, mais aucune Task n’est encore lancée."),
      step("Préparation terminée", R, {}, "Le Workflow peut maintenant examiner les Tasks à lancer. Le test de référence contrôle le statut pendant la création des UDF.")] });

  add({ id: "iteration-sans-step-avant-lancement", displayNumber: "84", scope: "iteration", probability: 2,
    family: "Statuts pendant l’exécution", title: "Sans Step actif, une itération attend quand même son lancement",
    mode: "état ciblé", nodes: [task("I", "itération à lancer", { kind: "iteration", context: "Task A · aucun Step actif" })],
    sources: ["iteration_aggregation", "iteration_run"],
    tests: ["test_task.py::test_lifecycle_unlaunched_iteration_without_active_steps_waits"],
    summary: "Sans Step ne signifie pas sans travail : une itération peut encore exécuter son pré-SQL et son post-SQL. Elle reste WAITING avant son lancement. Le banc couvre aussi des Steps inactifs ; ce n’est pas une option de désactivation des Steps en run complet.",
    steps: [step("L’itération vient d’être construite", R, {}, "La Task A travaille. I n’a ni démarré ni exécuté ses éventuels scripts."),
      step("Les Steps sont initialisés, mais tous absents ou inactifs", R, {}, "I reste WAITING. Elle devra être lancée pour exécuter son pré-SQL et son post-SQL.")] });

  add({ id: "task-sans-step-scripts-deux-iterations", displayNumber: "85", scope: "task", probability: 2,
    family: "Scripts et boucles", title: "Deux itérations sans Step exécutent chacune leurs scripts",
    nodes: [task("A", "boucle sans Step")], sources: ["task_run", "iteration_run"],
    tests: ["test_task.py::test_lifecycle_task_runs_iteration_without_active_steps",
      "test_workflow.py::test_lifecycle_empty_steps_are_accepted_by_settings_validation"],
    summary: "steps: [] est accepté. Avec deux itérations, le pré-SQL puis le post-SQL de chaque itération sont exécutés. Le TNR relit quatre marqueurs en PostgreSQL ; un banc ciblé vérifie aussi les Steps inactifs avec quatre écritures SQLite.",
    steps: [step("A démarre", R, { A: R }, "Les deux itérations doivent être lancées ; l’absence de Steps ne les remplace pas par des résultats déjà terminés."),
      step("Première itération", R, {}, "Le pré-SQL puis le post-SQL de la première itération écrivent leurs marqueurs."),
      step("Deuxième itération", R, {}, "La deuxième itération exécute à son tour son pré-SQL et son post-SQL."),
      ending({ A: OK }, "Les quatre marqueurs sont présents, dans l’ordre pré-SQL, post-SQL, pré-SQL, post-SQL. Les deux itérations ont effectivement été lancées.")] });

  add({ id: "task-boucle-vide", displayNumber: "86", scope: "task", probability: 2,
    family: "Limites et configurations refusées", title: "Boucle vide : configuration refusée",
    mode: "configuration", level: "limite",
    nodes: [task("A", "boucle vide")], sources: ["loop_validation"],
    tests: ["test_workflow.py::test_workflow_control_settings_rejects_empty_loop"],
    summary: "loop: [] est refusé pour une Task à contrôler. Lancelot signale que la liste ne doit pas être vide et arrête le chargement avant toute exécution. Ce n’est ni une boucle réussie sans travail, ni une erreur technique IndexError.",
    caution: "Décision mise à jour : une boucle vide doit être refusée explicitement. Les anciens avis sur le cas 86, qui prévoyait une réussite sans itération, doivent être relus. En run complet, seules les Tasks actives sont contrôlées ; les commandes ciblées contrôlent la Task demandée.",
    steps: [step("Une boucle vide est déclarée pour A", "NON_DÉMARRÉ", {}, "La configuration contient loop: []. Aucune Task ni itération n’a démarré ; les nœuds sont des repères de configuration."),
      step("Le contrôle refuse les settings", "CONTRÔLE_KO", {}, "Message attendu : « Le paramètre loop de la Task a ne doit pas être une liste vide. » Le chargement s’arrête sans IndexError ni traceback. Fournir une boucle non vide pour cette Task.")] });

  for (const [scope, number, childName, initializedFlag, finishedFlag, test] of [
    ["workflow", 87, "Tasks", "tasks_initialized", "tasks_finished", "test_workflow.py::test_workflow_upd_run_status_preserves_state_before_task_initialization"],
    ["task", 88, "itérations", "task_iterations_initialized", "iterations_finished", "test_task.py::test_task_upd_run_status_preserves_state_before_iterations_initialized"],
    ["iteration", 89, "Steps", "steps_mgr_initialized", "steps_finished", "test_task_iteration.py::test_taskiteration_upd_run_status_preserves_state_before_step_initialization"],
  ]) {
    add({ id: `statut-${scope}-enfants-non-initialises`, displayNumber: String(number), scope, probability: 1,
      family: "Recalcul des statuts", title: `${scopes[scope]} : ne pas conclure avant l’initialisation des ${childName}`,
      mode: "état ciblé", level: "limite", nodes: [task("P", "parent en cours", { kind: scope, context: `${childName} non initialisés` })],
      sources: [scope === "workflow" ? "aggregation" : scope === "task" ? "task" : "iteration_aggregation"],
      tests: [test, ...(scope === "task" ? ["test_task.py::test_lifecycle_concurrent_recalculation_during_presql_keeps_iterations_unfinished"] : [])],
      summary: scope === "iteration"
        ? "Au démarrage, Lancelot prépare la liste des Steps de l’itération. Une liste encore en construction n’est pas une liste de Steps déjà terminés. Le test provoque un recalcul à cet instant : il ne doit ni annoncer la fin des Steps, ni modifier le statut de l’itération. Ce n’est pas une configuration à écrire."
        : `Tant que les ${childName} ne sont pas entièrement initialisés, un recalcul ne modifie ni le statut du parent ni l’indicateur de fin des enfants. Une liste encore en construction ne prouve pas qu’il n’y a rien à exécuter.`,
      caution: scope === "task" ? "Le recalcul concurrent pendant le pré-SQL a été provoqué par un test. Le défaut était reproductible, mais son déclenchement spontané en production n’a pas été démontré." : "",
      steps: [step("L’initialisation n’est pas terminée", R, { P: R }, `${initializedFlag}: false ; ${finishedFlag}: false. P a déjà démarré son activité propre.`),
        step("Un recalcul est demandé", R, {}, `P reste RUNNING et ${finishedFlag} reste false. Le même contrat est testé avec WAITING et les statuts d’erreur ; le recalcul ne démarre pas le parent et n’efface pas son KO.`)] });
  }

  for (const [scope, number, childName, test] of [
    ["workflow", 90, "Task", "test_workflow_rework.py::test_lifecycle_empty_tasks_preserve_workflow_status"],
    ["task", 91, "itération", "test_task.py::test_lifecycle_empty_children_preserve_parent_status"],
    ["iteration", 92, "Step", "test_task.py::test_lifecycle_empty_children_preserve_parent_status"],
  ]) {
    add({ id: `statut-${scope}-sans-enfant-actif`, displayNumber: String(number), scope, probability: 1,
      family: "Recalcul des statuts", title: `${scopes[scope]} : aucun enfant actif ne signifie pas démarrage du parent`,
      mode: "état ciblé", nodes: [task("P", "parent en erreur", { kind: scope, context: `Aucun enfant actif` })],
      sources: [scope === "workflow" ? "aggregation" : scope === "task" ? "task" : "iteration_aggregation"], tests: [test],
      summary: `Une fois la liste initialisée, sans ${childName} actif, le recalcul marque les enfants comme terminés mais conserve le statut propre du parent. Il ne remplace ni WAITING ni un KO par RUNNING.`,
      steps: [step("P est déjà en erreur", RK, { P: RK }, "État ciblé : le parent est RUNNING_KO et sa liste d’enfants est initialisée mais vide."),
        step("Le recalcul conserve le KO", RK, {}, "P reste RUNNING_KO. La fin des enfants n’est pas la fin de l’activité propre du parent. Le test vérifie aussi la conservation de WAITING, RUNNING et FINISHED_KO.")] });
  }

  for (const [scope, number, phase] of [["task", 93, "hors boucle"], ["iteration", 94, "dans la boucle"]]) {
    for (const [suffix, errorMode, result, ignore] of [
      ["A", "réussit", OK, false], ["B", "échoue", KO, false], ["C", "échoue avec une erreur ignorée", IGNORED, true],
    ]) {
      add({ id: `postsql-${scope}-${suffix.toLowerCase()}`, displayNumber: `${number}-${suffix}`, scope, probability: 2,
        family: "Scripts et boucles", title: `${scopes[scope]} : le post-SQL ${errorMode}`,
        mode: "état ciblé", nodes: [task("P", scope === "task" ? "Task en post-SQL" : "itération en post-SQL",
          { kind: scope, context: scope === "iteration" ? `Post-SQL ${phase}` : "", ignore_on_error: ignore })],
        sources: [scope === "task" ? "task_run" : "iteration_run"],
        tests: ["test_task.py::test_lifecycle_postsql_keeps_parent_active_until_sql_returns"],
        summary: `Le post-SQL ${phase} fait encore partie de l’exécution. P reste RUNNING tant que l’appel SQL n’a pas rendu la main, même si ses enfants ont terminé. Ici, le post-SQL ${errorMode} : P termine en ${result}.`,
        steps: [step("Le post-SQL travaille", R, { P: R }, "Un recalcul demandé pendant le SQL ne publie pas de résultat terminal prématuré."),
          step("Le post-SQL a rendu la main", result === KO || (scope === "iteration" && ignore) ? RK : R, { P: result },
            `P termine en ${result}.${ignore ? " L’erreur reste enregistrée et consultable." : ""} Le schéma s’arrête au résultat de P, sans anticiper la fin de ses parents.`)] });
    }
  }

  add({ id: "iteration-init-erreur-fatale", displayNumber: "95", scope: "iteration", probability: 2,
    family: "Avertissements et erreurs ignorées", title: "Une erreur d’initialisation d’itération reste fatale",
    mode: "état ciblé", nodes: [task("I", "initialisation en KO", { kind: "iteration", context: "Task A · erreur d’init." })],
    sources: ["iteration_run", "task"], tests: ["test_task.py::test_lifecycle_iteration_init_failure_remains_fatal"],
    summary: "ignore_on_error ne transforme pas une erreur d’initialisation de l’itération en erreur ignorée. Si une information obligatoire de cible manque, I reste FINISHED_KO et la Task échoue, sans lancer I.",
    steps: [step("L’initialisation échoue avant le lancement", RK, { I: KO }, "Le test provoque une cible manquante. I est FINISHED_KO, sans heure de démarrage et sans lancement."),
      step("La Task termine en échec", RK, {}, "A termine en FINISHED_KO même avec ignore_on_error: true. I n’est pas passée en KO_IGNORED.")] });

  add({ id: "workflow-nettoyage-recalcul-concurrent", displayNumber: "96", scope: "workflow", probability: 2,
    family: "Finalisation", title: "Le Workflow reste actif pendant son nettoyage",
    mode: "état ciblé", nodes: [task("A", "traitement terminé")], sources: ["aggregation", "finalization"],
    tests: ["test_workflow_rework.py::test_lifecycle_workflow_cleanup_survives_concurrent_status_updates"],
    summary: "La fin de toutes les Tasks ne termine pas le Workflow : son nettoyage doit encore aboutir. Un recalcul concurrent pendant cette phase conserve RUNNING, ou RUNNING_KO si une Task a échoué.",
    caution: "Le résultat terminal est publié avant l’audit afin que celui-ci puisse l’enregistrer. Cela ne signifie pas que l’audit et les derniers logs sont déjà terminés.",
    steps: [step("A a réussi ; le nettoyage travaille", R, { A: OK }, "Les Tasks ont terminé, mais le Workflow effectue encore ses opérations de fin."),
      step("Un recalcul intervient pendant le nettoyage", R, {}, "Le Workflow reste RUNNING. Dans la variante avec échec de A, il reste RUNNING_KO."),
      step("Le nettoyage est terminé, le résultat est publié", OK, {}, "Le Workflow publie FINISHED_OK, puis l’audit enregistre ce résultat. La variante en erreur conserve FINISHED_KO.")] });

  add({ id: "step-attente-prerequis", displayNumber: "97", scope: "step", probability: 2,
    family: "Dépendances entre Steps", title: "Un Step attend la fin de son prérequis",
    mode: "état ciblé", nodes: [task("S", "Step source", { kind: "step", context: "Même itération" }),
      task("T", "Step dépendant", { kind: "step", context: "Même itération" })],
    edges: [["S", "T"]], sources: ["step_scheduling"],
    tests: ["test_task_iteration.py::test_taskiteration_execute_steps_mgr_launches_step_after_dependency_is_finished"],
    summary: "T dépend du résultat de S dans la même itération. Même lorsque des Steps peuvent s’exécuter en parallèle, T reste WAITING tant que S travaille ; il peut être lancé après la fin de S.",
    steps: [step("S travaille", R, { S: R }, "T attend son prérequis, sans être lancé."),
      step("S a terminé ; T peut démarrer", R, { S: OK }, "Le prérequis est satisfait. T peut obtenir sa place d’exécution."),
      step("T est lancé", R, { T: R }, "Le test contrôle le lancement après le passage de S à FINISHED_OK. Le schéma ne préjuge pas du résultat SQL de T.")] });

  add({ id: "iteration-step-ko-ignore-sans-fin-prematuree", displayNumber: "98", scope: "iteration", probability: 2,
    family: "Avertissements et erreurs ignorées", title: "Une erreur de Step ignorée ne termine pas prématurément l’itération",
    mode: "état ciblé", nodes: [task("I", "itération courante", { kind: "iteration", context: "Task A · erreur ignorée" }),
      task("S", "Step en erreur", { kind: "step", context: "Dans l’itération I" })],
    sources: ["iteration_aggregation", "iteration_run"],
    tests: ["test_task_iteration.py::test_taskiteration_ignored_step_failure_does_not_publish_terminal_ko",
      "test_task_iteration.py::test_taskiteration_ignored_step_failure_finalizes_without_transient_ko"],
    summary: "Après le KO de S, aucun nouveau Step n’est lancé une fois l’erreur prise en compte ; les Steps déjà lancés peuvent finir. ignore_on_error: true permet de terminer I en KO_IGNORED, pas de poursuivre les Steps suivants. Avant sa finalisation, I reste RUNNING_KO ; S conserve son propre échec.",
    caution: "Le TNR vérifie que le deuxième Step reste ABORTED et n’est pas exécuté. L’absence de FINISHED_KO dans les observations échantillonnées ne prouve pas l’absence de tout état très bref ; les tests moteur cités contrôlent cette transition directement.",
    steps: [step("Le Step travaille", R, { I: R, S: R }, "S s’exécute dans I. Les deux nœuds montrent deux niveaux du même traitement, pas deux prérequis."),
      step("S échoue pendant l’exécution des Steps", RK, { I: RK, S: KO }, "L’erreur reste visible sur S. I reste en cours avec erreur, sans être annoncée terminée."),
      step("I termine en KO_IGNORED", RK, { I: IGNORED }, "I finalise son erreur ignorée sans exécuter son post-SQL. La Task A doit encore finaliser son propre résultat ; S n’est pas transformé en succès.")] });

  // Ces scénarios décrivent une évolution proposée, et non le moteur actuel.
  const proposed = (spec) => add({
    family: "Évolution · désactivation", proposal: true, probability: 2, sources: [],
    ...spec,
  });
  const proposedChain = () => [task("T", "décision"), task("A", "optionnelle"), task("B", "suite")];
  const proposedEdges = [["T", "A"], ["A", "B"]];
  for (const [number, id, label] of [
    ["99", "defaut", "sans option"],
    ["100", "explicite", "avec propagate: true"],
  ]) {
    proposed({ id: `evolution-pg-${id}`, displayNumber: number, title: `Propagation ${label}`,
      nodes: [...proposedChain(), task("C", "suite de B")], edges: [...proposedEdges, ["B", "C"]], actions: [["T", "A"]],
      summary: "T désactive A pendant son exécution. La propagation est activée par défaut comme explicitement : A et ses descendantes ordinaires B et C deviennent DEACTIVATED_PG.",
      steps: [step("T travaille", R, { T: R }, "A attend T ; B et C attendent leurs prérequis."),
        step("T désactive A avec propagation", R, { A: DP, B: DP, C: DP }, "A, B et C ne seront pas exécutées ; la propagation est immédiate."),
        ending({ T: OK }, "T réussit. La désactivation ne constitue pas un KO.")] });
  }
  proposed({ id: "evolution-sans-pg-chaine", displayNumber: "101", title: "Sans propagation : B attend T puis s’exécute",
    nodes: [...proposedChain(), task("C", "suite de B")], edges: [...proposedEdges, ["B", "C"]], actions: [["T", "A"]],
    summary: "T désactive A avec propagate: false. A est DEACTIVATED ; B puis C peuvent s’exécuter normalement, après leurs prérequis.",
    steps: [step("T travaille", R, { T: R }, "A, B et C attendent."),
      step("A est sautée", R, { A: D }, "T travaille encore : B attend T, même si A est déjà DEACTIVATED.", { decisions: { B: "WAIT" } }),
      step("T réussit", R, { T: OK }, "Le prérequis indirect T est satisfait ; B peut démarrer.", { decisions: { B: "LAUNCH" } }),
      step("B réussit", R, { B: OK }, "C attend B, pas seulement la désactivation de A."),
      ending({ C: OK }, "C réussit. A seule n’a pas été exécutée.")] });
  proposed({ id: "evolution-sans-pg-multiples-ancetres", displayNumber: "102", title: "A sautée : B attend tous les prérequis de A",
    nodes: [...proposedChain(), task("P", "autre prérequis de A")],
    edges: [...proposedEdges, ["P", "A"]], actions: [["T", "A"]],
    summary: "A dépend de T et de P ; B dépend de A. La désactivation sans propagation ne supprime aucune de ces attentes.",
    steps: [step("T et P travaillent", R, { T: R, P: R }, "A attend ses deux prérequis."),
      step("A est sautée puis T réussit", R, { A: D, T: OK }, "P travaille encore : B reste WAITING.", { decisions: { B: "WAIT" } }),
      step("P réussit", R, { P: OK }, "Tous les prérequis de A sont satisfaits ; B peut démarrer.", { decisions: { B: "LAUNCH" } }),
      ending({ B: OK }, "B réussit après T et P.")] });
  proposed({ id: "evolution-sans-pg-ko-ancetre", displayNumber: "103", title: "T échoue après avoir désactivé A",
    nodes: proposedChain(), edges: proposedEdges, actions: [["T", "A"]],
    summary: "B attend T à travers A sautée. Si T échoue sans que son erreur soit ignorée, B est BLOCKED, même avec stop_on_error: false.",
    steps: [step("T désactive A", R, { T: R, A: D }, "T travaille encore ; B attend."),
      step("T échoue", RK, { T: KO, B: { status: B, causes: ["T"] } }, "La désactivation sans propagation ne masque pas le KO de T."),
      step("Fin", KO, {}, "A reste DEACTIVATED ; B n’a pas été exécutée.")] });
  proposed({ id: "evolution-sans-pg-ko-ignore", displayNumber: "104", title: "Erreur ignorée d’un prérequis de A",
    nodes: [task("T", "erreur ignorée", { ignore_on_error: true }), task("A", "optionnelle"), task("B", "suite")],
    edges: proposedEdges, actions: [["T", "A"]],
    summary: "L’erreur ignorée de T ne bloque pas B, mais B attend la fin effective de T avant de démarrer.",
    steps: [step("T désactive A puis signale une erreur", RK, { T: RK, A: D }, "T est encore en cours ; B attend.", { decisions: { B: "WAIT" } }),
      step("T termine en erreur ignorée", R, { T: IGNORED }, "B peut démarrer après KO_IGNORED.", { decisions: { B: "LAUNCH" } }),
      ending({ B: OK }, "B réussit ; l’erreur ignorée ne met pas à elle seule le Workflow en KO.")] });
  proposed({ id: "evolution-sans-pg-warning", displayNumber: "105", title: "Un prérequis termine avec un avertissement",
    nodes: proposedChain(), edges: proposedEdges, actions: [["T", "A"]],
    summary: "Le WARNING de T satisfait le prérequis de B même si A est sautée ; le Workflow conserve l’avertissement.",
    steps: [step("T désactive A", R, { T: R, A: D }, "B attend la fin de T."),
      step("T termine avec WARNING", R, { T: WARN }, "B peut démarrer.", { decisions: { B: "LAUNCH" } }),
      step("Fin", WARN, { B: OK }, "B réussit et le Workflow termine avec WARNING.")] });
  proposed({ id: "evolution-sans-pg-join", displayNumber: "106", title: "B attend aussi son autre prérequis direct",
    nodes: [...proposedChain(), task("P", "autre prérequis de B")],
    edges: [...proposedEdges, ["P", "B"]], actions: [["T", "A"]],
    summary: "Sauter A ne supprime pas les autres dépendances de B : B attend T et P.",
    steps: [step("A est sautée", R, { T: R, P: R, A: D }, "T et P travaillent encore."),
      step("T réussit", R, { T: OK }, "B attend toujours P.", { decisions: { B: "WAIT" } }),
      step("P réussit", R, { P: OK }, "B peut démarrer.", { decisions: { B: "LAUNCH" } }),
      ending({ B: OK }, "B réussit après ses deux branches.")] });
  proposed({ id: "evolution-sans-pg-successives", displayNumber: "107", title: "Plusieurs Tasks sautées successivement",
    nodes: [task("T", "décision"), task("A", "sautée"), task("C", "sautée"), task("B", "suite")],
    edges: [["T", "A"], ["A", "C"], ["C", "B"]], actions: [["T", "A"], ["T", "C"]],
    summary: "T désactive A et C sans propagation. B traverse les deux Tasks sautées et attend T.",
    steps: [step("T désactive A et C", R, { T: R, A: D, C: D }, "B attend encore T à travers C et A.", { decisions: { B: "WAIT" } }),
      step("T réussit", R, { T: OK }, "B peut démarrer.", { decisions: { B: "LAUNCH" } }),
      ending({ B: OK }, "A et C ne sont pas exécutées ; B réussit.")] });
  proposed({ id: "evolution-sans-pg-always-intermediaire", displayNumber: "108", title: "Sans propagation à travers une always_run",
    nodes: [task("T", "décision"), task("A", "sautée"), task("C", "nettoyage", { always_run: true }), task("B", "suite")],
    edges: [["T", "A"], ["A", "C"], ["C", "B"]], actions: [["T", "A"]],
    summary: "Avec propagate: false, C puis B peuvent s’exécuter après A. C attend la fin des prérequis ; B attend aussi le résultat de C.",
    steps: [step("T désactive A", R, { T: R, A: D }, "C attend encore T ; B attend C."),
      step("T réussit ; C travaille", R, { T: OK, C: R }, "B ne démarre pas tant que C travaille."),
      step("C réussit", R, { C: OK }, "B peut démarrer.", { decisions: { B: "LAUNCH" } }),
      ending({ B: OK }, "B réussit ; A reste DEACTIVATED.")] });
  proposed({ id: "evolution-pg-always-intermediaire", displayNumber: "109", title: "Avec propagation : always_run ne protège pas sa descendante",
    nodes: [task("T", "décision"), task("A", "désactivée"), task("C", "nettoyage", { always_run: true }), task("B", "suite")],
    edges: [["T", "A"], ["A", "C"], ["C", "B"]], actions: [["T", "A"]],
    summary: "A devient DEACTIVATED_PG. La propagation traverse C sans la désactiver et désactive B ; C attend néanmoins la fin de T.",
    steps: [step("T désactive A avec propagation", R, { T: R, A: DP, B: DP }, "C attend T malgré la désactivation de A."),
      step("T réussit", R, { T: OK }, "C peut démarrer ; B reste DEACTIVATED_PG."),
      ending({ C: OK }, "C réussit sans réactiver B.")] });
  proposed({ id: "evolution-sans-pg-always-ko", displayNumber: "110", title: "B always_run après le KO d’un prérequis de A",
    nodes: [task("T", "décision"), task("A", "sautée"), task("B", "nettoyage", { always_run: true })],
    edges: proposedEdges, actions: [["T", "A"]],
    summary: "B always_run attend la fin de T, puis peut s’exécuter malgré son KO ; A reste désactivée sans propagation.",
    steps: [step("T désactive A puis signale un KO", RK, { T: RK, A: D }, "T travaille encore ; B attend sa fin."),
      step("T termine en KO", RK, { T: KO }, "B peut démarrer grâce à always_run.", { decisions: { B: "LAUNCH" } }),
      step("Fin", KO, { B: OK }, "B réussit, mais le Workflow conserve le KO de T.")] });
  proposed({ id: "evolution-pg-chemins-mixtes", displayNumber: "111", title: "Deux branches : sans propagation et avec propagation",
    nodes: [task("T", "décision"), task("A", "sautée"), task("P", "désactivée avec propagation"), task("B", "convergence")],
    edges: [["T", "A"], ["T", "P"], ["A", "B"], ["P", "B"]], actions: [["T", "A"], ["T", "P"]],
    summary: "T désactive A sans propagation et P avec propagation. B est désactivée par P, même si A seule ne l’aurait pas désactivée.",
    steps: [step("T saute A", R, { T: R, A: D }, "B attend encore T et P."),
      step("T désactive P avec propagation", R, { P: DP, B: DP }, "La branche P désactive B ; A reste DEACTIVATED."),
      ending({ T: OK }, "B n’est pas exécutée.")] });
  proposed({ id: "evolution-pg-traverse-saut", displayNumber: "112", title: "Une propagation atteint une Task déjà sautée",
    nodes: [task("T", "décision"), task("P", "prérequis"), task("A", "déjà sautée"), task("B", "suite")],
    edges: [["T", "P"], ["P", "A"], ["A", "B"]], actions: [["T", "A"], ["T", "P"]],
    summary: "T saute A sans propagation, puis désactive P avec propagation. Proposition : la propagation traverse A et désactive B.",
    caution: "Choix à valider : A passe ici de DEACTIVATED à DEACTIVATED_PG pour rendre visible la nouvelle cause de propagation.",
    steps: [step("T saute A", R, { T: R, A: D }, "B reste en attente des prérequis de A."),
      step("T désactive P avec propagation", R, { P: DP, A: DP, B: DP }, "La désactivation préalable de A ne fait pas écran à la propagation venant de P."),
      ending({ T: OK }, "B ne s’exécute pas.")] });
  for (const stop of [false, true]) {
    proposed({ id: `evolution-sans-pg-ko-independent-${stop}`, displayNumber: stop ? "114" : "113",
      title: `KO indépendant · stop_on_error: ${stop}`, stop_on_error: stop,
      nodes: [...proposedChain(), task("F", "échec indépendant")], edges: proposedEdges, actions: [["T", "A"]],
      summary: stop
        ? "Un KO indépendant bloque B avec stop_on_error: true, même si A a été sautée sans propagation."
        : "Avec stop_on_error: false, un KO indépendant ne bloque pas B ; B attend toujours ses propres prérequis.",
      steps: [step("T saute A et F échoue", RK, { T: R, A: D, F: KO, ...(stop ? { B: { status: B, causes: ["F"] } } : {}) },
          stop ? "B est BLOCKED par l’arrêt global. T, déjà lancée, peut finir." : "B reste WAITING jusqu’à la fin de T."),
        step("T réussit", RK, { T: OK }, stop ? "B reste bloquée." : "B peut démarrer.", { decisions: { B: stop ? "BLOCK" : "LAUNCH" } }),
        step("Fin", KO, stop ? {} : { B: OK }, "Le Workflow termine en KO à cause de F.")] });
  }
  proposed({ id: "evolution-pg-priorite-blocked", displayNumber: "115", title: "La propagation reclasse une Task BLOCKED",
    nodes: [task("T", "décision"), task("P", "à désactiver"), task("F", "échec"), task("B", "convergence")],
    edges: [["T", "P"], ["P", "B"], ["F", "B"]], actions: [["T", "P"]],
    summary: "B est bloquée par F. Une désactivation avec propagation de P lui donne la priorité et reclasse B en DEACTIVATED_PG.",
    steps: [step("F échoue", RK, { T: R, F: KO, B: { status: B, causes: ["F"] } }, "B est déjà BLOCKED."),
      step("T désactive P avec propagation", RK, { P: DP, B: DP }, "La propagation reste prioritaire sur le blocage."),
      step("Fin", KO, { T: OK }, "Le KO de F reste présent.")] });
  proposed({ id: "evolution-sans-pg-blocked", displayNumber: "116", title: "Sans propagation : une Task BLOCKED reste bloquée",
    nodes: [task("T", "décision"), task("A", "sautée"), task("F", "échec"), task("B", "convergence")],
    edges: [["T", "A"], ["A", "B"], ["F", "B"]], actions: [["T", "A"]],
    summary: "B est déjà bloquée par F. Sauter son autre prérequis A sans propagation ne réactive pas B et ne change pas sa cause.",
    steps: [step("F échoue", RK, { T: R, F: KO, B: { status: B, causes: ["F"] } }, "B est BLOCKED."),
      step("T saute A", RK, { A: D }, "B reste BLOCKED à cause de F."),
      step("Fin", KO, { T: OK }, "La désactivation de A ne corrige pas le KO.")] });
  for (const propagate of [false, true]) {
    proposed({ id: `evolution-cible-always-${propagate}`, displayNumber: propagate ? "118" : "117",
      title: `Désactiver explicitement une always_run · propagate: ${propagate}`,
      nodes: [task("T", "décision"), task("A", "always_run ciblée", { always_run: true }), task("B", "suite")],
      edges: proposedEdges, actions: [["T", "A"]],
      summary: "always_run ne protège pas contre une désactivation explicite. Le choix de propagation s’applique ensuite à B.",
      steps: [step("T désactive A", R, { T: R, A: propagate ? DP : D, ...(propagate ? { B: DP } : {}) },
          propagate ? "A et B sont DEACTIVATED_PG." : "A est DEACTIVATED ; B attend encore T."),
        step("T réussit", R, { T: OK }, propagate ? "B reste désactivée." : "B peut démarrer."),
        ending(propagate ? {} : { B: OK }, propagate ? "B n’est pas exécutée." : "B réussit.")] });
  }
  proposed({ id: "evolution-cible-reservee", displayNumber: "119", title: "Une cible déjà réservée ou lancée ne peut pas être désactivée",
    mode: "état ciblé", nodes: [task("T", "décision"), task("A", "réservée")], actions: [["T", "A"]],
    summary: "Quelle que soit l’option, une Task dont le lancement est réservé ou engagé ne peut pas être désactivée directement.",
    steps: [step("Le lancement de A est réservé", R, { T: R, A: { status: W, reserved: true } }, "A affiche encore WAITING mais son lancement est engagé."),
      step("La demande est refusée", R, {}, "A conserve son état ; aucune propagation ne part de cette demande.")] });
  proposed({ id: "evolution-descendante-reservee", displayNumber: "120", title: "Une descendante déjà réservée est préservée",
    mode: "état ciblé", nodes: [task("T", "décision"), task("A", "à désactiver"), task("B", "déjà réservée")],
    edges: [["A", "B"]], actions: [["T", "A"]],
    summary: "Avec propagation, une descendante déjà réservée ou lancée n’est pas interrompue ; la propagation s’arrête sur ce chemin ordinaire.",
    caution: "État ciblé : cette réservation peut résulter d’une autre chronologie ; elle ne décrit pas nécessairement un run ordinaire A → B.",
    steps: [step("B est déjà réservée", R, { T: R, B: { status: W, reserved: true } }, "T peut encore désactiver A."),
      step("T désactive A", R, { A: DP }, "B conserve son lancement réservé et n’est pas désactivée.")] });
  proposed({ id: "evolution-repetitions", displayNumber: "121", title: "Demandes répétées ou cible inconnue",
    nodes: proposedChain(), edges: proposedEdges, actions: [["T", "A"]],
    summary: "Après une désactivation acceptée, une nouvelle demande explicite ne modifie pas une Task déjà désactivée. Une cible inconnue ne crée aucune Task.",
    caution: "Proposition : une deuxième demande explicite avec une autre option ne change pas la politique choisie ; les retours internes restent 1, puis 2, et 0 pour un nom inconnu.",
    steps: [step("T saute A", R, { T: R, A: D }, "La première demande est acceptée."),
      step("T redemande A avec propagation et vise un nom absent", R, {}, "A reste DEACTIVATED ; B n’est pas désactivée par ces demandes."),
      step("T réussit", R, { T: OK }, "B peut démarrer."), ending({ B: OK })] });
  proposed({ id: "evolution-declencheur-independant", displayNumber: "122", title: "Le déclencheur indépendant n’est pas un prérequis",
    nodes: proposedChain(), edges: [["A", "B"]], actions: [["T", "A"]],
    summary: "T est indépendante de A et B. Si T saute A avant son lancement, B n’attend pas automatiquement T : seules les dépendances déclarées imposent cet ordre.",
    caution: "Pour garantir que la décision soit prise avant A, et que B attende T, déclarer T comme prérequis de A.",
    steps: [step("T travaille avant le lancement de A", R, { T: R }, "Cet ordre est un exemple ; sans dépendance, A pourrait aussi être choisie avant la demande."),
      step("T saute A", R, { A: D }, "A n’a pas de prérequis : B peut démarrer pendant que T travaille.", { decisions: { B: "LAUNCH" } }),
      step("B et T travaillent", R, { B: R }, "T n’est pas un prérequis de B."),
      ending({ T: OK, B: OK }, "Les deux Tasks réussissent.")] });
  proposed({ id: "evolution-plusieurs-cibles", displayNumber: "123", title: "Une liste de cibles reçoit la même option",
    nodes: [task("T", "décision"), task("A", "première cible"), task("P", "seconde cible"), task("B", "convergence")],
    edges: [["T", "A"], ["T", "P"], ["A", "B"], ["P", "B"]], actions: [["T", "A"], ["T", "P"]],
    summary: "Une seule demande vise A et P avec propagate: false. B ne démarre qu’après les prérequis des deux cibles.",
    steps: [step("T saute les deux cibles", R, { T: R, A: D, P: D }, "B attend encore T."),
      step("T réussit", R, { T: OK }, "B peut démarrer."), ending({ B: OK })] });
  proposed({ id: "evolution-option-invalide", displayNumber: "124", title: "Option propagate invalide",
    nodes: [task("T", "décision"), task("A", "cible")], edges: [["T", "A"]], actions: [["T", "A"]], mode: "état ciblé",
    summary: "Proposition : propagate doit être un booléen ; une valeur invalide est signalée avant de modifier les Tasks.",
    caution: "Choix à valider : type précis de l’erreur et traitement d’une liste contenant à la fois des noms valides et inconnus.",
    steps: [step("T transmet une valeur invalide", R, { T: R }, "La demande est refusée explicitement ; A reste inchangée."),
      step("Fin de l’exemple", R, {}, "Cet exemple ne fixe pas le résultat du Workflow après l’erreur.")] });
  proposed({ id: "evolution-aucune-task-restante", displayNumber: "125", title: "Toutes les Tasks restantes sont désactivées",
    nodes: [task("T", "décision"), task("A", "cible")], edges: [["T", "A"]], actions: [["T", "A"]],
    summary: "Une Task DEACTIVATED ou DEACTIVATED_PG est terminale et ne laisse pas le Workflow attendre indéfiniment.",
    steps: [step("T saute A", R, { T: R, A: D }, "T est la seule Task encore en cours."),
      ending({ T: OK }, "Sans erreur, le Workflow termine en FINISHED_OK ; le même résultat est attendu avec DEACTIVATED_PG.")] });
  for (const propagate of [false, true]) {
    proposed({ id: `evolution-concurrence-options-${propagate}`, displayNumber: propagate ? "126-B" : "126-A",
      title: propagate ? "Demandes concurrentes : la propagation gagne" : "Demandes concurrentes : la désactivation sans propagation gagne",
      mode: "état ciblé", nodes: [task("T", "sans propagation"), task("U", "avec propagation"), task("A", "cible"), task("B", "suite")],
      edges: [["A", "B"]], actions: [["T", "A"], ["U", "A"]],
      summary: "Les demandes concurrentes sont sérialisées avec la réservation du lancement. Une seule désactivation explicite est acceptée.",
      caution: "Proposition : la première demande acceptée fixe la politique ; l’autre est refusée. Aucun ordre entre T et U n’est garanti.",
      steps: [step("T et U demandent A", R, { T: R, U: R }, "Le premier appel sous verrou gagne."),
        step(propagate ? "U gagne avec propagation" : "T gagne sans propagation", R,
          propagate ? { A: DP, B: DP } : { A: D },
          propagate ? "La demande de T est refusée ; A et B sont DEACTIVATED_PG." : "La demande de U est refusée ; B n’est pas désactivée.")] });
  }
  proposed({ id: "evolution-prerequis-annule", displayNumber: "127", title: "Une Task sautée possède un prérequis ABORTED",
    mode: "état ciblé", nodes: proposedChain(), edges: proposedEdges,
    summary: "T est ABORTED ; A est sautée sans propagation. L’interprétation de ce prérequis pour B doit être décidée avant les TNR.",
    caution: "Point ouvert : conserver l’attente ordinaire actuelle face à ABORTED peut empêcher la fin du Workflow ; aucun résultat final n’est présumé ici.",
    steps: [step("T est annulée et A sautée", R, { T: AB, A: D }, "B reste en attente dans cet état ciblé ; le traitement final est à valider.")] });
  proposed({ id: "evolution-configuration-inactive", displayNumber: "128", title: "Task inactive dans les settings",
    mode: "configuration", nodes: [task("A", "inactive", { active: false }), task("B", "dépendante")], edges: [["A", "B"]],
    summary: "L’option de désactivation dynamique ne modifie pas la validation des settings : une Task active ne peut pas dépendre d’une Task configurée inactive.",
    steps: [step("Configuration refusée", KO, {}, "Le run est refusé avant le lancement ; ce cas ne constitue pas une désactivation dynamique.")] });
  proposed({ id: "evolution-monitoring", displayNumber: "129", title: "Monitoring : distinguer les deux désactivations",
    mode: "état ciblé", nodes: [task("A", "sans propagation"), task("P", "avec propagation")],
    summary: "Les informations du run et Blaise doivent rendre les deux statuts lisibles et reconnaître DEACTIVATED_PG comme terminal.",
    caution: "À qualifier aussi : couleurs, filtres, exports et interprétation des anciens runs DEACTIVATED, dont le libellé ne permet pas de retrouver la politique historique.",
    steps: [step("Deux Tasks désactivées", R, { A: D, P: DP }, "A est DEACTIVATED sans propagation ; P est DEACTIVATED_PG avec propagation.")] });
  proposed({ id: "evolution-pg-always-descendante", displayNumber: "130", title: "Une descendante always_run survit à la propagation",
    nodes: [task("T", "décision"), task("A", "désactivée"), task("B", "nettoyage", { always_run: true })],
    edges: proposedEdges, actions: [["T", "A"]],
    summary: "T désactive A avec propagation puis échoue. B est protégée par always_run et attend la fin de T avant de nettoyer.",
    steps: [step("T désactive A", R, { T: R, A: DP }, "B attend T, encore en cours."),
      step("T termine en erreur", RK, { T: KO }, "B peut démarrer malgré le KO grâce à always_run."),
      step("Fin", KO, { B: OK }, "B réussit ; le Workflow conserve le KO de T.")] });
  proposed({ id: "evolution-sans-pg-ko-derriere-always", displayNumber: "131", title: "Un nettoyage réussi ne masque pas un KO en amont",
    nodes: [task("T", "décision"), task("A", "sautée"), task("C", "nettoyage", { always_run: true }), task("B", "suite")],
    edges: [["T", "A"], ["A", "C"], ["C", "B"]], actions: [["T", "A"]],
    summary: "T saute A puis échoue. C always_run peut nettoyer, mais sa réussite ne débloque pas B ordinaire.",
    steps: [step("T saute A puis échoue", RK, { T: KO, A: D, B: { status: B, causes: ["T"] } }, "B est bloquée par T ; C peut démarrer."),
      step("C réussit", RK, { C: OK }, "La réussite de C ne fait pas disparaître le KO de T."),
      step("Fin", KO, {}, "B reste BLOCKED ; le Workflow termine en KO.")] });
  proposed({ id: "evolution-sans-pg-recalcul", displayNumber: "132", title: "Les recalculs ne changent pas la politique choisie",
    mode: "état ciblé", nodes: proposedChain(), edges: proposedEdges, actions: [["T", "A"]],
    summary: "Une Task DEACTIVATED sans propagation ne doit pas devenir une source de propagation lors d’un réexamen du graphe ou du classement final.",
    steps: [step("A a été sautée", R, { T: R, A: D }, "B attend T."),
      step("Le moteur réexamine les désactivations", R, {}, "A reste DEACTIVATED ; B reste WAITING et n’est pas désactivée."),
      step("T réussit", R, { T: OK }, "B peut démarrer."), ending({ B: OK })] });
  proposed({ id: "evolution-liste-resultats-mixtes", displayNumber: "133", title: "Une liste mélange une cible disponible et une cible déjà lancée",
    mode: "état ciblé", nodes: [task("T", "décision"), task("A", "disponible"), task("P", "réservée")],
    actions: [["T", "A"], ["T", "P"]],
    summary: "Proposition : chaque cible est traitée séparément ; A est désactivée, P réservée est conservée et son refus est journalisé.",
    caution: "Choix à valider : conserver le traitement partiel actuel plutôt que rendre toute la liste atomique ; la méthode publique ne retourne actuellement pas les codes individuels.",
    steps: [step("P est réservée", R, { T: R, P: { status: W, reserved: true } }, "A est encore disponible."),
      step("T demande les deux désactivations sans propagation", R, { A: D }, "A est désactivée ; la demande visant P est refusée sans annuler celle visant A.")] });

  const probabilityGroups = {
    1: [
      "capacite-double-lancement", "ko-waiting-reserved", "ko-waiting-launched",
      "always-ancetre-aborted", "inactive-vide",
      "deactivation-blocked", "deactivation-refus-reserved", "deactivation-refus-launched",
      "marge-complete-false", "marge-complete-true", "workflow-init-ko-nettoyage",
      "workflow-thread-refuse", "workflow-echec-warn_data_usage", "workflow-echec-task_logs",
      "workflow-echec-show_logs_ending", "workflow-echec-wkf_logs",
      "final-classification", "final-blocked-seuls", "final-aborted-seuls",
    ],
    2: [
      "warning-ko-prioritaire", "ignore-transitoire-false", "ignore-transitoire-true",
      "ignore-warning-aggregation", "ignore-ko-definitif",
      "ignore-postsql-false", "ignore-postsql-true", "ignore-presql-outloop",
      "ignore-et-ko-reel-false", "ignore-et-ko-reel-true", "ko-multiple",
      "always-apres-ko-ignore", "always-ancetre-false", "always-ancetre-true",
      "always-plusieurs-prerequis", "always-suite-false", "always-suite-true",
      "always-echec-nettoyage", "always-sans-dependance", "inactive-toutes",
      "deactivation-chaine", "deactivation-join", "deactivation-priorite-ko",
      "deactivation-barriere", "deactivation-explicite-always", "deactivation-refus-running",
      "deactivation-refus-finished", "deactivation-refus-blocked", "deactivation-inconnue",
      "interaction-nettoyage-autre-branche",
      "workflow-udf-creation", "workflow-echec-drop_tables", "workflow-echec-drop_all_udf",
      "workflow-echec-run_audit", "final-attente-thread", "limite-cycle",
      "config-soi", "config-absente", "config-inactive", "config-format-dependances",
    ],
    3: [
      "base-unique", "base-chaine", "base-fork", "base-join", "base-losange",
      "base-attente-non-bloquante", "capacite-1", "capacite-2", "capacite-reevaluation",
      "warning-dependance", "ko-direct-false", "ko-direct-true", "ko-running",
      "ko-transitif", "ko-task-deja-lancee", "ko-task-deja-lancee-stop-false",
      "always-succes", "always-ko-false", "always-ko-true", "inactive-isolee",
      "statut-waiting-presql",
    ],
  };
  const probabilities = Object.fromEntries(Object.entries(probabilityGroups)
    .flatMap(([score, ids]) => ids.map((id) => [id, Number(score)])));
  const tnrCases = {
    "83": ["c83"], "84": ["c84"], "85": ["c85_empty", "c85_inactive"], "86": ["c86", "c86_isolated"],
    "87": ["c87"], "88": ["c88"], "89": ["c89"], "90": ["c90"], "91": ["c91"], "92": ["c92"],
    "93-A": ["c93a"], "93-B": ["c93b"], "93-C": ["c93c"],
    "94-A": ["c94a"], "94-B": ["c94b"], "94-C": ["c94c"],
    "95": ["c95"], "96": ["c96"], "97": ["q_steps"], "98": ["c98"],
  };
  const targetedCases = new Set(["c83", "c84", "c85_inactive", "c86_isolated", "c87", "c88", "c89", "c90", "c91", "c92", "c95", "c96"]);
  cases.forEach((scenario) => {
    scenario.tnr = (tnrCases[scenario.displayNumber] || []).map((id) => ({
      id, kind: targetedCases.has(id) ? "banc ciblé" : "Workflow réel",
    }));
    scenario.probability = probabilities[scenario.id] ?? scenario.probability;
    if (["warning-ko-prioritaire", "ignore-warning-aggregation", "inactive-toutes", "inactive-vide"].includes(scenario.id)) {
      scenario.scope = "workflow";
    }
  });

  return {
    version: "2026-11-19.1",
    compatibleReviewVersions: ["2026-11-16.1", "2026-11-16.2", "2026-11-16.3", "2026-11-17.1", "2026-11-17.2", "2026-11-17.3", "2026-11-17.4", "2026-11-17.5", "2026-11-18.1", "2026-11-18.2", "2026-11-18.3"],
    retiredScenarioIds: ["workflow-erreur-false", "workflow-erreur-true", "limite-aborted-ordinaire", "limite-mixte-aborted-ok"],
    title: "Catalogue des runs Lancelot",
    scopes,
    sources: {
      decision: ["workflow.py", "_decide_task_run", 1447],
      scheduling: ["workflow.py", "_schedule_tasks", 1422],
      capacity: ["workflow.py", "_try_schedule_task / can_run_task", 1542],
      preparation: ["workflow.py", "_prepare_run", 1390],
      blocking: ["workflow.py", "_get_blocking_task_names", 1734],
      transitive: ["workflow.py", "_get_transitive_task_dependencies", 1791],
      propagation: ["workflow.py", "_deactivate_tasks_with_deactivated_dependencies", 1901],
      deactivate: ["workflow.py", "deactivate_task", 3199],
      classification: ["workflow.py", "set_blocked_status", 1962],
      aggregation: ["workflow.py", "upd_run_status", 2275],
      finalization: ["workflow.py", "_finalize_run", 1626],
      run: ["workflow.py", "run / end_ko", 1343],
      abort: ["workflow.py", "set_aborted_status", 1710],
      validation: ["workflow.py", "control_settings_dict · depends_on", 722],
      loop_validation: ["workflow.py", "control_settings_dict · loop vide", 670],
      task: ["task.py", "initialisation / upd_run_status / fin du run", 629],
      task_run: ["task.py", "_run · démarrage avant pré-SQL et itérations", 238],
      iteration_run: ["task_iteration.py", "_run · démarrage avant pré-SQL dans l’itération", 348],
      iteration_aggregation: ["task_iteration.py", "upd_run_status", 611],
      step_scheduling: ["task_iteration.py", "execute_steps_mgr", 408],
    },
    cases,
  };
})();
