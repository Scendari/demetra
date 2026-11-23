"use strict";

(() => {
  const storageKey = "lancelot.run-catalog.reviews.v1";
  const decisions = { pending: "À revoir", accepted: "Validé", rejected: "Refusé" };
  const probabilities = {
    1: { label: "Très rare", description: "Situation exceptionnelle, combinaison très particulière ou course entre exécutions." },
    2: { label: "Faible", description: "Situation occasionnelle, liée à une option, une erreur ou une configuration particulière." },
    3: { label: "Commun", description: "Situation usuelle : dépendances, capacité, réussite ou gestion courante d’un KO." },
  };
  const statuses = new Set(["WAITING", "RUNNING", "RUNNING_KO", "FINISHED_OK", "FINISHED_KO", "KO_IGNORED", "WARNING", "BLOCKED", "DEACTIVATED", "DEACTIVATED_PG", "ABORTED"]);
  const svgNamespace = "http://www.w3.org/2000/svg";
  const byId = (id) => document.getElementById(id);
  const normalize = (text) => text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const statusClass = (status) => `status-${status.toLowerCase().replaceAll("_", "-")}`;
  let reviews = {};
  let canPersist = true;
  const rendered = [];
  let currentSort = "catalog";

  function element(tag, attributes = {}, text) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function svg(tag, attributes = {}, text) {
    const node = document.createElementNS(svgNamespace, tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function annotatedText(target, text, ids) {
    target.replaceChildren();
    const letters = new Set(ids);
    for (const token of text.split(/(\b[A-Z]\b)/)) {
      target.append(letters.has(token) ? element("strong", {}, token) : document.createTextNode(token));
    }
  }

  function showError(message, error) {
    byId("storage-error").textContent = message;
    byId("storage-error").hidden = false;
    if (error) console.error(message, error);
  }

  function validateReviews(value) {
    const compatibleVersions = [runCatalog.version, ...runCatalog.compatibleReviewVersions];
    if (!value || typeof value !== "object" || !value.reviews || typeof value.reviews !== "object" || Array.isArray(value.reviews)) {
      throw new Error("Le format de la revue est invalide.");
    }
    if (!compatibleVersions.includes(value.version)) {
      throw new Error(`Version de revue incompatible : ${String(value.version ?? "absente")} (catalogue : ${runCatalog.version}).`);
    }
    const ids = new Set([...runCatalog.cases.map((scenario) => scenario.id), ...runCatalog.retiredScenarioIds]);
    const result = {};
    for (const [id, review] of Object.entries(value.reviews)) {
      if (!ids.has(id) || !review || !Object.hasOwn(decisions, review.decision)
        || typeof review.comment !== "string" || typeof review.updatedAt !== "string"
        || !Number.isFinite(Date.parse(review.updatedAt))) {
        throw new Error(`Avis invalide pour le scénario « ${id} ».`);
      }
      result[id] = { decision: review.decision, comment: review.comment, updatedAt: review.updatedAt };
    }
    return result;
  }

  function loadReviews() {
    let saved;
    try {
      saved = localStorage.getItem(storageKey);
    } catch (error) {
      canPersist = false;
      byId("save-status").textContent = "Sauvegarde automatique désactivée.";
      showError("Le navigateur refuse l’accès au stockage local. Les nouveaux avis restent dans cette page : utilise l’export JSON pour les conserver.", error);
      return;
    }
    try {
      if (saved !== null) reviews = validateReviews(JSON.parse(saved));
      byId("save-status").textContent = "Sauvegarde locale disponible.";
    } catch (error) {
      canPersist = false;
      byId("save-status").textContent = "Sauvegarde automatique désactivée.";
      const detail = error instanceof SyntaxError ? "La revue enregistrée n’est pas un JSON valide." : error.message;
      showError(`${detail} La revue enregistrée n’a pas été écrasée. Les nouveaux avis restent dans cette page : utilise l’export JSON pour les conserver.`, error);
    }
  }

  function saveReviews() {
    if (!canPersist) {
      byId("save-status").textContent = "Avis en mémoire seulement — exporte ta revue.";
      return;
    }
    try {
      localStorage.setItem(storageKey, JSON.stringify({ version: runCatalog.version, reviews }));
      byId("save-status").textContent = "Revue enregistrée dans ce navigateur.";
    } catch (error) {
      canPersist = false;
      byId("save-status").textContent = "Échec de sauvegarde — exporte ta revue.";
      showError("La sauvegarde locale a échoué. Les avis restent en mémoire, mais seraient perdus à la fermeture de cette page. Exporte la revue JSON.", error);
    }
  }

  function validateCatalog() {
    const ids = new Set();
    for (const scenario of runCatalog.cases) {
      if (ids.has(scenario.id) || !scenario.frames.length) throw new Error(`Scénario invalide : ${scenario.id}.`);
      ids.add(scenario.id);
      if (!Number.isInteger(scenario.probability) || !Object.hasOwn(probabilities, scenario.probability)) {
        throw new Error(`Probabilité absente ou invalide : ${scenario.id}.`);
      }
      if (!Object.hasOwn(runCatalog.scopes, scenario.scope)) throw new Error(`Niveau invalide : ${scenario.id}.`);
      for (const node of scenario.nodes) {
        if (!Object.hasOwn(runCatalog.scopes, node.kind)) throw new Error(`Niveau de nœud invalide : ${scenario.id}, ${node.id}.`);
      }
      const nodeIds = new Set(scenario.nodes.map((node) => node.id));
      if (nodeIds.size !== scenario.nodes.length) throw new Error(`Task dupliquée : ${scenario.id}.`);
      for (const [source, target] of [...scenario.edges, ...scenario.actions]) {
        if (!nodeIds.has(source) || !nodeIds.has(target)) throw new Error(`Lien invalide : ${scenario.id}.`);
      }
      for (const source of scenario.sources) {
        if (!Object.hasOwn(runCatalog.sources, source)) throw new Error(`Source inconnue : ${source}.`);
      }
      for (const frame of scenario.frames) {
        if (Object.keys(frame.states).length !== nodeIds.size) throw new Error(`Instantané incomplet : ${scenario.id}.`);
        for (const [id, state] of Object.entries(frame.states)) {
          if (!nodeIds.has(id) || !statuses.has(state.status)) throw new Error(`Statut invalide : ${scenario.id}, ${id}.`);
        }
      }
    }
  }

  function graphLayout(scenario) {
    const ranks = new Map();
    const remaining = new Set(scenario.nodes.map((node) => node.id));
    while (remaining.size) {
      let progress = false;
      for (const id of remaining) {
        const parents = scenario.edges.filter((edge) => edge[1] === id).map((edge) => edge[0]);
        if (parents.every((parent) => ranks.has(parent))) {
          ranks.set(id, parents.length ? Math.max(...parents.map((parent) => ranks.get(parent))) + 1 : 0);
          remaining.delete(id);
          progress = true;
        }
      }
      if (!progress) {
        if (!scenario.layout) throw new Error(`Un graphe cyclique nécessite une disposition explicite : ${scenario.id}.`);
        for (const id of remaining) ranks.set(id, scenario.layout[id][1]);
        remaining.clear();
      }
    }
    const groups = new Map();
    for (const node of scenario.nodes) {
      const rank = ranks.get(node.id);
      if (!groups.has(rank)) groups.set(rank, []);
      groups.get(rank).push(node.id);
    }
    const width = Math.max(420, ...Array.from(groups.values(), (group) => group.length * 204 + 40));
    const positions = new Map();
    for (const [rank, group] of groups) {
      group.forEach((id, index) => {
        const column = scenario.layout ? scenario.layout[id][0] : index;
        positions.set(id, { x: (width - group.length * 204 + 24) / 2 + column * 204, y: 30 + rank * 150, rank });
      });
    }
    return { width, height: groups.size ? (Math.max(...groups.keys()) + 1) * 150 + 30 : 100, positions };
  }

  function buildGraph(scenario, parent) {
    const { width, height, positions } = graphLayout(scenario);
    const picture = svg("svg", { viewBox: `0 0 ${width} ${height}`, role: "group", "aria-label": `Graphe du scénario : ${scenario.title}` });
    picture.style.minWidth = `${Math.min(width, 520)}px`;
    const definitions = svg("defs");
    for (const action of [false, true]) {
      const marker = svg("marker", {
        id: `${scenario.id}-${action ? "action" : "arrow"}`, viewBox: "0 0 10 10", refX: "9", refY: "5",
        markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse",
      });
      marker.append(svg("path", { class: action ? "graph-action-arrow" : "graph-arrow", d: "M0 0 L10 5 L0 10 Z" }));
      definitions.append(marker);
    }
    picture.append(definitions);
    for (const action of [false, true]) {
      for (const [source, target] of action ? scenario.actions : scenario.edges) {
        const from = positions.get(source), to = positions.get(target);
        const x1 = from.x + 90, x2 = to.x + 90, y1 = from.y + 120, y2 = to.y;
        let path;
        if (source === target) {
          path = `M${from.x + 180} ${from.y + 88} C${from.x + 215} ${from.y + 88} ${from.x + 215} ${from.y + 25} ${from.x + 180} ${from.y + 25}`;
        } else if (from.rank === to.rank) {
          const routeY = action ? y1 + 18 : Math.min(from.y, to.y) - 20;
          path = `M${x1} ${action ? y1 : from.y} C${x1} ${routeY} ${x2} ${routeY} ${x2} ${action ? to.y + 120 : to.y}`;
        } else if (to.rank < from.rank || to.rank > from.rank + 1) {
          const routeX = width - 12;
          path = `M${from.x + 180} ${from.y + 60} C${routeX} ${from.y + 60} ${routeX} ${to.y + 60} ${to.x + 180} ${to.y + 60}`;
        } else {
          path = `M${x1} ${y1} C${x1} ${(y1 + y2) / 2} ${x2} ${(y1 + y2) / 2} ${x2} ${y2}`;
        }
        const edge = svg("path", {
          class: action ? "graph-edge graph-action" : "graph-edge", d: path,
          "marker-end": `url(#${scenario.id}-${action ? "action" : "arrow"})`,
        });
        edge.append(svg("title", {}, action ? `${source} peut désactiver ${target} ; ce n’est pas une dépendance.` : `${target} dépend de ${source}.`));
        picture.append(edge);
      }
    }
    const nodes = new Map();
    for (const task of scenario.nodes) {
      const position = positions.get(task.id);
      const group = svg("g", { class: "graph-node", transform: `translate(${position.x} ${position.y})`, role: "img", "data-task": task.id });
      const label = svg("title");
      group.append(label, svg("rect", { class: "body", width: "180", height: "120", rx: "7" }),
        svg("text", { class: "letter", x: "11", y: "23" }, task.id),
        svg("text", { class: "name", x: "34", y: "22" }, task.name),
        svg("text", { class: "option", x: "11", y: "43" }, task.kind === "task" ? `Task · always_run: ${task.always_run}` : runCatalog.scopes[task.kind]));
      const options = [];
      if (task.kind === "task" && task.ignore_on_error) options.push("ignore_on_error: true");
      if (!task.active) options.push("active: false");
      if (task.missing) options.push("absente de settings.yml");
      if (task.context) options.push(task.context);
      group.append(svg("text", { class: "option", x: "11", y: "60" }, options.join(" · ")));
      const runtime = svg("text", { class: "runtime", x: "11", y: "77" });
      const badge = svg("text", { class: "status-text", x: "90", y: "105", "text-anchor": "middle" });
      group.append(runtime, svg("rect", { class: "status-bg", x: "10", y: "88", width: "160", height: "24", rx: "4" }), badge);
      picture.append(group);
      nodes.set(task.id, { group, badge, label, runtime });
    }
    if (!scenario.nodes.length) picture.append(svg("text", { class: "graph-caption", x: "20", y: "50" }, "Aucune Task à lancer."));
    parent.append(picture);
    return nodes;
  }

  function reviewFor(id) {
    return reviews[id] || { decision: "pending", comment: "", updatedAt: "" };
  }

  function focusAdjacentCard(card, direction) {
    const index = rendered.findIndex((item) => item.card === card);
    for (let position = index + direction; position >= 0 && position < rendered.length; position += direction) {
      if (!rendered[position].card.hidden) {
        rendered[position].card.focus();
        return true;
      }
    }
    return false;
  }

  function buildScenario(scenario, index) {
    const card = element("article", {
      id: scenario.id, class: "scenario", tabindex: "0", "aria-labelledby": `${scenario.id}-title`,
      "aria-describedby": "keyboard-help", "aria-keyshortcuts": "ArrowLeft ArrowRight v r x", "data-scope": scenario.scope,
    });
    const head = element("div", { class: "scenario-head" });
    const heading = element("h2", { id: `${scenario.id}-title` });
    heading.append(element("a", { href: `#${scenario.id}` }, `${scenario.displayNumber || String(index + 1).padStart(2, "0")} · ${scenario.title}`));
    const tags = element("div", { class: "tags" });
    tags.append(element("span", { class: "tag tag-scope" }, `Niveau : ${runCatalog.scopes[scenario.scope]}`));
    for (const text of [scenario.family, scenario.level, scenario.mode, scenario.proposal ? "Proposition · non implémentée" : (scenario.tests.length ? "Tests de référence" : "Lecture du code")]) {
      tags.append(element("span", { class: "tag" }, text));
    }
    const probability = probabilities[scenario.probability];
    tags.append(element("span", {
      class: "tag tag-probability",
      title: `${probability.description} Estimation qualitative, sans statistiques de runs ; ni gravité ni probabilité de réussite du test.`,
    }, `Probabilité estimée : ${scenario.probability}/3 · ${probability.label}`));
    if (scenario.caution) tags.append(element("span", { class: "tag tag-sensitive" }, "Point d’attention"));
    head.append(heading, tags, element("p", { class: "scenario-summary" }, scenario.summary));
    const body = element("div", { class: "scenario-body" });
    const config = element("div", { class: "config" });
    config.append(element("code", {}, `stop_on_error: ${scenario.stop_on_error}`), element("code", {}, `max_threads_tasks: ${scenario.capacity}`));
    body.append(config);
    if (scenario.caution) body.append(element("p", { class: "caution" }, scenario.caution));
    const viewport = element("div", { class: "graph-viewport", role: "region", tabindex: "0", "aria-label": "Schéma du scénario ; défilement horizontal si nécessaire" });
    const nodes = buildGraph(scenario, viewport);
    const graphStatusRow = element("div", { class: "graph-status-row" });
    const workflow = element("span", { class: "status", "aria-label": "Statut du Workflow" });
    graphStatusRow.append(workflow);
    body.append(graphStatusRow, viewport);
    if (scenario.actions.length) body.append(element("p", { class: "small" }, `Pointillés : ${scenario.actions.map(([from, to]) => `${from} peut désactiver ${to}`).join(" ; ")}. Ce lien n’est pas un prérequis.`));
    const controls = element("div", { class: "phase-controls" });
    const slider = element("input", { id: `${scenario.id}-range`, type: "range", min: "0", max: String(scenario.frames.length - 1), step: "1", value: "0", "aria-controls": `${scenario.id}-readout` });
    const buttons = element("div", { class: "phase-buttons" });
    const previous = element("button", { type: "button", "aria-label": `Étape précédente : ${scenario.title}` }, "← Précédent");
    const next = element("button", { type: "button", "aria-label": `Étape suivante : ${scenario.title}` }, "Suivant →");
    const counter = element("span", { class: "small" });
    buttons.append(previous, counter, next);
    const readout = element("div", { id: `${scenario.id}-readout`, "aria-live": "polite", "aria-atomic": "true" });
    const readoutHead = element("div", { class: "phase-readout" });
    const phaseTitle = element("strong");
    readoutHead.append(phaseTitle);
    const note = element("p", { class: "phase-note" }), causes = element("p", { class: "phase-causes" });
    readout.append(readoutHead, note, causes);
    controls.append(element("label", { for: slider.id }, "Avancement du scénario"), slider, buttons, readout);
    body.append(controls);
    const evidence = element("details", { class: "evidence" });
    evidence.append(element("summary", {}, `Règles et références · ${scenario.id}`));
    const sources = element("ul");
    if (scenario.proposal) sources.append(element("li", {}, "Proposition à valider : aucun TNR ni comportement moteur n’est revendiqué."));
    for (const key of scenario.sources) {
      const [file, symbol, line] = runCatalog.sources[key];
      sources.append(element("li", {}, `${file}:${line} · ${symbol}`));
    }
    for (const name of scenario.tests) sources.append(element("li", {}, `Test de référence : ${name}`));
    for (const check of scenario.tnr) {
      const item = element("li", {}, `TNR wkf_16 · ${check.kind} : `);
      item.append(element("code", {}, `python "$WKF/verify.py" --case ${check.id}`));
      sources.append(item);
    }
    evidence.append(sources);
    body.append(evidence);

    const review = element("div", { class: "scenario-review" });
    review.append(element("strong", { class: "small" }, "Ce comportement te convient-il ?"));
    const reviewButtons = element("div", { class: "review-buttons", role: "group", "aria-label": `Avis sur ${scenario.title}` });
    const choices = new Map();
    for (const [value, text] of Object.entries(decisions)) {
      const button = element("button", { type: "button", "data-decision": value }, text);
      button.addEventListener("click", () => updateReview(value, comment.value));
      reviewButtons.append(button);
      choices.set(value, button);
    }
    const comment = element("textarea", { id: `${scenario.id}-comment`, placeholder: "Comportement attendu, désaccord, cas manquant…" });
    comment.addEventListener("input", () => updateReview(reviewFor(scenario.id).decision, comment.value));
    review.append(reviewButtons, element("label", { for: comment.id }, "Commentaire"), comment);
    card.append(head, body, review);

    function renderFrame() {
      const position = Number(slider.value), frame = scenario.frames[position];
      phaseTitle.textContent = frame.title;
      workflow.className = `status ${statuses.has(frame.workflow) ? statusClass(frame.workflow) : "status-config"}`;
      workflow.textContent = `Workflow ${frame.workflow}`;
      annotatedText(note, frame.note, scenario.nodes.map((task) => task.id));
      const blockages = [];
      for (const task of scenario.nodes) {
        const state = frame.states[task.id], node = nodes.get(task.id);
        const configuration = scenario.mode === "configuration";
        const status = configuration ? (task.missing ? "ABSENTE" : `active: ${task.active}`) : state.status;
        node.group.setAttribute("class", `graph-node ${configuration ? "status-config" : statusClass(state.status)}`);
        node.badge.textContent = status;
        const flags = [];
        if (state.reserved) flags.push("lancement réservé");
        if (state.launched) flags.push("exécution déjà lancée");
        if (state.threadPending) flags.push("fin d’exécution attendue");
        node.runtime.textContent = flags.join(" · ");
        const prerequisites = scenario.edges.filter((edge) => edge[1] === task.id).map((edge) => edge[0]);
        const options = task.kind === "task" ? `always_run: ${task.always_run}. ignore_on_error: ${task.ignore_on_error}.` : (task.context || "");
        const description = `${runCatalog.scopes[task.kind]} ${task.id}, ${task.name} : ${status}. ${options} ${prerequisites.length ? `Dépend de ${prerequisites.join(" et ")}.` : "Sans dépendance."} ${flags.join(". ")}`;
        node.group.setAttribute("aria-label", description);
        node.label.textContent = description;
        if (state.causes) blockages.push(`${task.id} bloquée : ${state.causes.length ? state.causes.join(", ") : "erreur Workflow, sans Task fautive identifiée"}`);
      }
      annotatedText(causes, blockages.join(" · "), scenario.nodes.map((task) => task.id));
      causes.hidden = !blockages.length;
      counter.textContent = `${position + 1} / ${scenario.frames.length}`;
      slider.setAttribute("aria-valuetext", `Étape ${position + 1} : ${frame.title}. Workflow ${frame.workflow}.`);
      previous.disabled = position === 0;
      next.disabled = position === scenario.frames.length - 1;
    }
    function refreshReview() {
      const current = reviewFor(scenario.id);
      card.dataset.review = current.decision;
      comment.value = current.comment;
      for (const [value, button] of choices) button.setAttribute("aria-pressed", String(current.decision === value));
    }
    function updateReview(decision, text) {
      const hadFocus = card.contains(document.activeElement);
      reviews[scenario.id] = { decision, comment: text, updatedAt: new Date().toISOString() };
      saveReviews();
      refreshReview();
      updateCounts();
      if (byId("review-filter").value) applyFilters();
      if (card.hidden && hadFocus) {
        if (!focusAdjacentCard(card, 1) && !focusAdjacentCard(card, -1)) byId("review-filter").focus();
      }
    }
    card.addEventListener("click", (event) => {
      if (!event.target.closest("a, button, input, textarea, select, summary, label, [contenteditable]")) {
        card.focus({ preventScroll: true });
      }
    });
    card.addEventListener("keydown", (event) => {
      if (event.target !== card || event.defaultPrevented || event.isComposing || event.ctrlKey || event.altKey || event.metaKey) return;
      if (event.key === "Tab") {
        event.preventDefault();
        if (!focusAdjacentCard(card, event.shiftKey ? -1 : 1)) {
          (event.shiftKey ? document.querySelector('.filters button[type="reset"]') : byId("catalog-end")).focus();
        }
      } else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        if (event.key === "ArrowLeft") slider.stepDown();
        else slider.stepUp();
        renderFrame();
      } else {
        const shortcuts = { v: "accepted", r: "rejected", x: "pending" };
        const key = event.key.toLowerCase();
        if (Object.hasOwn(shortcuts, key)) {
          event.preventDefault();
          if (!event.repeat) updateReview(shortcuts[key], comment.value);
        }
      }
    });
    slider.addEventListener("input", renderFrame);
    previous.addEventListener("click", () => { slider.stepDown(); renderFrame(); });
    next.addEventListener("click", () => { slider.stepUp(); renderFrame(); });
    renderFrame();
    refreshReview();
    return { scenario, card, index, refreshReview, searchable: normalize([scenario.id, scenario.title, scenario.family, runCatalog.scopes[scenario.scope], scenario.summary, scenario.caution, ...scenario.frames.map((frame) => frame.note)].join(" ")) };
  }

  function updateCounts() {
    const counts = { pending: 0, accepted: 0, rejected: 0 };
    for (const scenario of runCatalog.cases) counts[reviewFor(scenario.id).decision]++;
    byId("review-counts").textContent = `${runCatalog.cases.length} scénarios · ${counts.accepted} validés · ${counts.rejected} refusés · ${counts.pending} à revoir.`;
  }

  function applyFilters() {
    const query = normalize(byId("search").value.trim()), family = byId("family").value, mode = byId("mode").value;
    const review = byId("review-filter").value, sensitive = byId("sensitive").checked;
    const scope = byId("scope").value, sort = byId("sort").value;
    if (sort !== currentSort) {
      const scopes = Object.keys(runCatalog.scopes);
      rendered.sort((left, right) => (sort === "scope"
        ? scopes.indexOf(left.scenario.scope) - scopes.indexOf(right.scenario.scope) : 0) || left.index - right.index);
      byId("catalog").replaceChildren(...rendered.map((item) => item.card));
      currentSort = sort;
    }
    let visible = 0;
    for (const item of rendered) {
      const matches = (!query || item.searchable.includes(query)) && (!family || item.scenario.family === family)
        && (!scope || item.scenario.scope === scope)
        && (!mode || item.scenario.mode === mode) && (!review || reviewFor(item.scenario.id).decision === review)
        && (!sensitive || Boolean(item.scenario.caution));
      item.card.hidden = !matches;
      if (matches) visible++;
    }
    byId("result-count").textContent = `${visible} / ${rendered.length} scénarios affichés.`;
    byId("empty-results").hidden = visible !== 0;
  }

  function openHash() {
    const id = location.hash.slice(1);
    const item = rendered.find((entry) => entry.scenario.id === id);
    if (!item) return;
    if (item.card.hidden) {
      document.querySelector(".filters").reset();
      applyFilters();
    }
    item.card.scrollIntoView({ block: "start" });
  }

  function init() {
    if (typeof runCatalog === "undefined") throw new Error("Les données du catalogue n’ont pas été chargées.");
    validateCatalog();
    loadReviews();
    byId("catalog-version").textContent = runCatalog.version;
    const families = [...new Set(runCatalog.cases.map((scenario) => scenario.family))];
    for (const [scope, label] of Object.entries(runCatalog.scopes)) {
      const count = runCatalog.cases.filter((scenario) => scenario.scope === scope).length;
      byId("scope").append(element("option", { value: scope }, `${label} (${count})`));
    }
    for (const family of families) {
      const count = runCatalog.cases.filter((scenario) => scenario.family === family).length;
      byId("family").append(element("option", { value: family }, `${family} (${count})`));
      const button = element("button", { type: "button" }, `${family} · ${count}`);
      button.addEventListener("click", () => {
        document.querySelector(".filters").reset();
        byId("family").value = family;
        applyFilters();
        byId("result-count").scrollIntoView({ block: "start" });
      });
      byId("inventory").append(button);
    }
    runCatalog.cases.forEach((scenario, index) => {
      const item = buildScenario(scenario, index);
      rendered.push(item);
      byId("catalog").append(item.card);
    });
    const filters = document.querySelector(".filters");
    filters.addEventListener("submit", (event) => event.preventDefault());
    filters.addEventListener("input", applyFilters);
    filters.addEventListener("change", applyFilters);
    filters.addEventListener("reset", () => setTimeout(applyFilters, 0));
    byId("export-review").addEventListener("click", () => {
      const payload = {
        version: runCatalog.version, exportedAt: new Date().toISOString(),
        reviews: { ...reviews, ...Object.fromEntries(runCatalog.cases.map((scenario) => [scenario.id, reviews[scenario.id] || { decision: "pending", comment: "", updatedAt: new Date().toISOString() }])) },
      };
      const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
      const download = element("a", { href: url, download: `revue-runs-lancelot-${new Date().toISOString().slice(0, 10)}.json` });
      document.body.append(download);
      download.click();
      download.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      byId("save-status").textContent = "Export JSON généré ; vérifie le téléchargement.";
    });
    byId("import-review").addEventListener("change", async (event) => {
      const file = event.target.files[0];
      if (!file) return;
      try {
        const imported = validateReviews(JSON.parse(await file.text()));
        if (!window.confirm("Les avis importés remplaceront les avis locaux des mêmes scénarios. Continuer ?")) return;
        reviews = { ...reviews, ...imported };
        saveReviews();
        rendered.forEach((item) => item.refreshReview());
        updateCounts();
        applyFilters();
        if (canPersist) byId("storage-error").hidden = true;
      } catch (error) {
        showError(`Import refusé : ${error.message} Aucun avis n’a été importé.`, error);
      } finally {
        event.target.value = "";
      }
    });
    window.addEventListener("hashchange", openHash);
    byId("loading-message").hidden = true;
    updateCounts();
    applyFilters();
    if (location.hash) openHash();
  }

  try {
    init();
  } catch (error) {
    console.error("Chargement du catalogue impossible.", error);
    byId("loading-message").textContent = `Chargement impossible : ${error.message} Rafraîchis la page et vérifie que les deux scripts du catalogue sont disponibles.`;
    byId("loading-message").className = "error";
    byId("loading-message").setAttribute("role", "alert");
  }
})();
