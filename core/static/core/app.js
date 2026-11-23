/* Demetra — script de l'interface. Aucun cadre, aucune dépendance. */
(function () {
  "use strict";
  const doc = document;
  const root = doc.documentElement;
  root.classList.add("js");
  const $ = (sel, el) => (el || doc).querySelector(sel);
  const $$ = (sel, el) => Array.from((el || doc).querySelectorAll(sel));
  const store = {
    get(key) { try { return localStorage.getItem(key); } catch (e) { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* stockage indisponible */ } },
  };
  const csrf = () => (doc.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || "";

  /* ---------------------------------------------------------------- Panneaux repliables */
  const DOCKS = {
    rail: ["railMini", "demetra-rail"], list: ["listHidden", "demetra-list"],
    facts: ["foldFacts", "demetra-fold-facts"], legend: ["foldLegend", "demetra-fold-legend"],
  };
  const docked = (name) => DOCKS[name][0] in root.dataset;
  function syncDock() {
    const text = docked("rail") ? "Agrandir le menu" : "Réduire le menu";
    $$('[data-dock="rail"]').forEach((button) => {
      button.title = text;
      const label = $("[data-dock-label]", button);
      if (label) label.textContent = text;
    });
    // Sections dépliables : l'état vit sur <html>, le bouton ne fait que le refléter.
    $$("[data-fold-btn]").forEach((button) => button.setAttribute("aria-expanded", String(docked(button.dataset.foldBtn))));
  }
  function setDock(name, on) {
    if (on) root.dataset[DOCKS[name][0]] = "1"; else delete root.dataset[DOCKS[name][0]];
    store.set(DOCKS[name][1], on ? "1" : "0");
    syncDock();
  }
  syncDock();

  /* ---------------------------------------------------------------- Thème */
  doc.addEventListener("click", (event) => {
    const fold = event.target.closest("[data-fold-btn]");
    if (fold) setDock(fold.dataset.foldBtn, !docked(fold.dataset.foldBtn));
    const dock = event.target.closest("[data-dock]");
    if (dock) {
      const name = dock.dataset.dock;
      setDock(name, !docked(name));
      // Le bouton qui vient d'être masqué rend la main à son pendant, pour ne pas perdre le focus clavier.
      if (name === "list" && event.detail === 0) { const other = $$('[data-dock="list"]').find((button) => button.offsetParent !== null); if (other) other.focus(); }
    }
    const toggle = event.target.closest("[data-theme-toggle]");
    if (toggle) {
      const next = root.dataset.theme === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      store.set("demetra-theme", next);
    }
    const menu = event.target.closest(".rail-toggle");
    if (menu) {
      const rail = menu.closest(".rail");
      const open = rail.classList.toggle("is-open");
      menu.setAttribute("aria-expanded", String(open));
    }
    const copy = event.target.closest("[data-copy]");
    if (copy) {
      const source = $(copy.dataset.copy);
      const label = $("[data-copy-label]", copy);
      if (source && navigator.clipboard) {
        navigator.clipboard.writeText(source.textContent.trim()).then(() => {
          if (label) { label.textContent = "Copié"; setTimeout(() => { label.textContent = "Copier"; }, 1800); }
        });
      }
    }
  });
  doc.addEventListener("change", (event) => {
    if (event.target.matches("[data-autosubmit]")) event.target.form.submit();
  });

  /* ---------------------------------------------------------------- Étapes d'une représentation */
  function applyRep(rep, step) {
    let statuses = rep._statuses;
    if (!statuses) {
      try { statuses = JSON.parse(rep.dataset.statuses || "{}"); } catch (e) { statuses = {}; }
      rep._statuses = statuses;
    }
    $$("[data-st]", rep).forEach((el) => {
      const key = el.dataset.st.split("|")[step] || "";
      const info = statuses[key] || ["neutral", key, key];
      const changed = (el.dataset.ch || "")[step] === "1";
      el.dataset.role = info[0];
      el.dataset.status = key;
      el.classList.toggle("is-changed", changed);
      if (el.dataset.fo) el.classList.toggle("is-focus", el.dataset.fo[step] === "1");
      $$("[data-si]", el).forEach((use) => use.setAttribute("href", "#ic-" + info[0]));
      $$("[data-sl]", el).forEach((text) => { text.textContent = text.dataset.sl === "short" ? info[2] : info[1]; });
      if (el.hasAttribute("title")) el.setAttribute("title", info[1]);
      if (el.dataset.emph) {
        let rules = el._emph;
        if (!rules) { try { rules = JSON.parse(el.dataset.emph); } catch (e) { rules = []; } el._emph = rules; }
        ["fx-halo", "fx-bold", "fx-fade"].forEach((cls) => el.classList.remove(cls));
        rules.forEach((rule) => {
          const when = rule.when || {};
          if (when.role && !when.role.includes(info[0])) return;
          if (when.status && !when.status.includes(key)) return;
          if (when.changed && !changed) return;
          el.classList.add("fx-" + rule.effect);
        });
      }
    });
    $$("[data-ch]:not([data-st])", rep).forEach((el) => el.classList.toggle("is-changed", el.dataset.ch[step] === "1"));
    $$("[data-tx]", rep).forEach((el) => {
      let texts = el._tx;
      if (!texts) { try { texts = JSON.parse(el.dataset.tx); } catch (e) { texts = []; } el._tx = texts; }
      const value = texts[step] || "";
      const target = el.hasAttribute("data-tx-target") ? el : $("[data-tx-target]", el) || el;
      target.textContent = value;
      el.classList.toggle("is-empty", !value);
    });
    $$("[data-step-is]", rep).forEach((el) => el.classList.toggle("is-current", Number(el.dataset.stepIs) === step));
    // Classes par étape : celles de l'étape quittée s'effacent, celles de l'étape atteinte se posent.
    $$("[data-cls]", rep).forEach((el) => {
      let list = el._cls;
      if (!list) { try { list = JSON.parse(el.dataset.cls); } catch (e) { list = []; } el._cls = list; }
      (el.dataset.clsOn || "").split(" ").forEach((cls) => { if (cls) el.classList.toggle(cls, false); });
      const now = list[step] || "";
      now.split(" ").forEach((cls) => { if (cls) el.classList.toggle(cls, true); });
      el.dataset.clsOn = now;
    });
    $$("[data-xs]", rep).forEach((el) => {
      const x = el.dataset.xs.split(" ")[step];
      if (x !== undefined) el.setAttribute("transform", "translate(" + x + " 0)");
    });
    $$("[data-ws]", rep).forEach((el) => {
      const w = el.dataset.ws.split(" ")[step];
      if (w !== undefined) el.setAttribute("width", w);
    });
    rep.dataset.step = String(step);
  }

  function setStep(panel, step, options) {
    let steps = panel._steps;
    if (!steps) { try { steps = JSON.parse(panel.dataset.steps || "[]"); } catch (e) { steps = []; } panel._steps = steps; }
    if (!steps.length) return;
    step = Math.max(0, Math.min(steps.length - 1, step));
    panel.dataset.step = String(step);
    $$("[data-rep]", panel).forEach((rep) => applyRep(rep, step));
    const info = steps[step];
    $$(".stop-btn", panel).forEach((button) => {
      const index = Number(button.dataset.step);
      if (index === step) button.setAttribute("aria-current", "step"); else button.removeAttribute("aria-current");
      button.parentElement.classList.toggle("is-past", index < step);
    });
    // Le détail de chaque étape est déjà dans la page, empilé dans une même case : on ne fait que changer celui qui se voit.
    $$("[data-step-pane]", panel).forEach((pane) => pane.classList.toggle("is-current", Number(pane.dataset.stepPane) === step));
    const set = (sel, value) => { const el = $(sel, panel); if (el) el.textContent = value; };
    set("[data-step-n]", String(step + 1));
    set("[data-step-title]", info.title);
    const prev = $("[data-step-prev]", panel), next = $("[data-step-next]", panel);
    if (prev) prev.disabled = step === 0;
    if (next) next.disabled = step === steps.length - 1;
    const current = $('.stop-btn[aria-current="step"]', panel);
    if (current && current.scrollIntoView && !(options && options.quiet)) current.scrollIntoView({ block: "nearest", inline: "nearest" });
    if (panel.dataset.key && !(options && options.quiet)) {
      const url = new URL(location.href);
      url.searchParams.set("cas", panel.dataset.key);
      if (step > 0) url.searchParams.set("etape", String(step + 1)); else url.searchParams.delete("etape");
      history.replaceState(history.state, "", url);
    }
  }
  const stepOf = (panel) => Number(panel.dataset.step || 0);

  doc.addEventListener("click", (event) => {
    const panel = event.target.closest("[data-panel]");
    if (panel) {
      const button = event.target.closest(".stop-btn");
      if (button) return setStep(panel, Number(button.dataset.step));
      if (event.target.closest("[data-step-prev]")) return setStep(panel, stepOf(panel) - 1);
      if (event.target.closest("[data-step-next]")) return setStep(panel, stepOf(panel) + 1);
      const stepCell = event.target.closest("[data-step-is]");
      if (stepCell && stepCell.closest("[data-rep]")) return setStep(panel, Number(stepCell.dataset.stepIs));
    }
    const tab = event.target.closest(".rep-tab");
    if (tab) {
      const rep = tab.closest(".rep");
      $$(".rep-tab", rep).forEach((other) => {
        const on = other === tab;
        other.setAttribute("aria-selected", String(on));
        other.tabIndex = on ? 0 : -1;
        const view = doc.getElementById(other.getAttribute("aria-controls"));
        if (view) view.hidden = !on;
      });
    }
  });
  $$("[data-panel]").forEach((panel) => setStep(panel, stepOf(panel), { quiet: true }));

  /* ---------------------------------------------------------------- Démonstration de l'accueil */
  // Le cas avance seul, une étape toutes les 2,2 s, puis recommence. Toute action de la personne
  // (clic, flèche, bouton) arrête la lecture ; le bouton lecture/pause la relance. Si le système demande
  // moins d'animation, rien ne démarre seul.
  const demo = $("[data-autoplay]");
  if (demo && !$("[data-workspace]")) {
    const button = $("[data-autoplay-btn]", demo);
    const total = () => (demo._steps || []).length;
    let timer = null;
    const show = (playing) => {
      if (!button) return;
      button.setAttribute("aria-pressed", String(playing));
      button.setAttribute("aria-label", playing ? "Mettre en pause" : "Lire le cas");
    };
    const stop = () => { clearInterval(timer); timer = null; show(false); };
    const play = () => {
      clearInterval(timer);
      show(true);
      timer = setInterval(() => {
        if (doc.hidden) return;
        setStep(demo, stepOf(demo) + 1 >= total() ? 0 : stepOf(demo) + 1, { quiet: true });
      }, 2200);
    };
    demo.addEventListener("click", (event) => {
      if (event.target.closest("[data-autoplay-btn]")) { if (timer) stop(); else play(); return; }
      if (event.target.closest("[data-step-prev], [data-step-next], [data-step-is]")) stop();
    });
    doc.addEventListener("keydown", (event) => {
      if (event.target.matches("input, textarea, select") || event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      event.preventDefault();
      stop();
      setStep(demo, stepOf(demo) + (event.key === "ArrowRight" ? 1 : -1), { quiet: true });
    });
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) show(false); else play();
  }

  /* ---------------------------------------------------------------- Espace de revue */
  const ws = $("[data-workspace]");
  if (!ws) return;
  const sid = ws.dataset.sid;
  const detail = $("[data-detail]", ws);
  const list = $("[data-cases]", ws);
  const items = list ? $$(".case-item", list) : [];
  const filters = { q: "", decision: "", family: "", stale: false, retired: false, sort: "number" };
  const LABELS = { accepted: "Validé", rejected: "Refusé", to_analyze: "À analyser" };
  let lastVerdict = null;
  let toastTimer = null;

  const panelNow = () => $("[data-panel]", detail || doc);
  const visibleItems = () => items.filter((li) => !li.hidden);
  const currentItem = () => items.find((li) => $(".case", li).getAttribute("aria-current") === "true");

  function applyFilters() {
    if (!list) return;
    const q = filters.q.trim().toLowerCase();
    const words = q ? q.split(/\s+/) : [];
    let shown = 0;
    items.forEach((li) => {
      const retired = li.hasAttribute("data-retired");
      let ok = filters.retired ? retired : !retired;
      if (ok && filters.decision) ok = li.dataset.decision === filters.decision;
      if (ok && filters.family) ok = li.dataset.family === filters.family;
      if (ok && filters.stale) ok = li.hasAttribute("data-stale");
      if (ok && words.length) ok = words.every((word) => li.dataset.search.includes(word));
      li.hidden = !ok;
      if (ok) shown += 1;
    });
    const grouped = filters.sort === "number";
    const order = items.slice();
    const rank = { to_analyze: 0, rejected: 1, accepted: 2 };
    if (filters.sort === "todo") order.sort((a, b) => rank[a.dataset.decision] - rank[b.dataset.decision] || a.dataset.n - b.dataset.n);
    else if (filters.sort === "changed") order.sort((a, b) => b.dataset.changed - a.dataset.changed || a.dataset.n - b.dataset.n);
    else if (filters.sort === "title") order.sort((a, b) => $(".case-title", a).textContent.localeCompare($(".case-title", b).textContent, "fr"));
    else order.sort((a, b) => a.dataset.n - b.dataset.n);
    $$(".fam", list).forEach((head) => head.remove());
    let family = null;
    order.forEach((li) => {
      if (grouped && !li.hidden && li.dataset.family !== family) {
        family = li.dataset.family;
        const head = doc.createElement("li");
        head.className = "fam";
        const title = doc.createElement("h2");
        title.textContent = family;
        head.appendChild(title);
        list.appendChild(head);
      }
      list.appendChild(li);
    });
    const total = items.filter((li) => (filters.retired ? li.hasAttribute("data-retired") : !li.hasAttribute("data-retired"))).length;
    const count = $("[data-list-count]", ws);
    const filtered = q || filters.decision || filters.family || filters.stale;
    if (count) count.textContent = filtered ? shown + " cas affichés sur " + total : "";
    const none = $("[data-no-match]", ws);
    if (none) none.hidden = shown > 0;
  }

  function setDecisionFilter(value) {
    filters.decision = value;
    $$("[data-filter-decision]", ws).forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.filterDecision === value)));
    applyFilters();
  }

  if (list) {
    // « search » : le navigateur vide lui-même un champ de recherche (touche Échap, croix) sans émettre « input ».
    ["input", "search"].forEach((type) => ws.addEventListener(type, (event) => {
      if (event.target.matches("[data-filter-q]") && filters.q !== event.target.value) { filters.q = event.target.value; applyFilters(); }
    }));
    ws.addEventListener("change", (event) => {
      const target = event.target;
      if (target.matches("[data-filter-family]")) filters.family = target.value;
      else if (target.matches("[data-sort]")) { filters.sort = target.value; store.set("demetra-sort", target.value); }
      else if (target.matches("[data-filter-stale]")) filters.stale = target.checked;
      else if (target.matches("[data-filter-retired]")) filters.retired = target.checked;
      else return;
      applyFilters();
    });
    const savedSort = store.get("demetra-sort");
    const sortSelect = $("[data-sort]", ws);
    if (savedSort && sortSelect && $$("option", sortSelect).some((o) => o.value === savedSort)) { sortSelect.value = savedSort; filters.sort = savedSort; }
    applyFilters();
  }

  function resetFilters() {
    filters.q = ""; filters.family = ""; filters.stale = false; filters.retired = false;
    const q = $("[data-filter-q]", ws); if (q) q.value = "";
    const family = $("[data-filter-family]", ws); if (family) family.value = "";
    $$("[data-filter-stale], [data-filter-retired]", ws).forEach((box) => { box.checked = false; });
    setDecisionFilter("");
  }

  /* Ouverture d'un cas sans recharger la page */
  let loading = 0;
  function openCase(key, options) {
    options = options || {};
    const li = items.find((item) => item.dataset.key === key);
    if (!li) return Promise.resolve();
    items.forEach((item) => $(".case", item).removeAttribute("aria-current"));
    $(".case", li).setAttribute("aria-current", "true");
    if (!options.keepScroll) $(".case", li).scrollIntoView({ block: "nearest" });
    if (options.focusItem) $(".case", li).focus({ preventScroll: true });
    const ticket = ++loading;
    const url = ws.dataset.panelUrl.replace("__KEY__", encodeURIComponent(key)) + (options.step ? "?etape=" + options.step : "");
    return fetch(url, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" })
      .then((response) => { if (!response.ok) throw new Error(String(response.status)); return response.text(); })
      .then((html) => {
        if (ticket !== loading) return;
        detail.innerHTML = html;
        detail.scrollTop = 0;
        const panel = panelNow();
        setStep(panel, stepOf(panel), { quiet: true });
        syncFocusButton();
        syncDock();
        const target = new URL(location.href);
        target.searchParams.set("cas", key);
        if (options.step) target.searchParams.set("etape", options.step); else target.searchParams.delete("etape");
        if (!options.fromHistory) history.pushState({ cas: key }, "", target);
        doc.title = panel.dataset.title + " — Demetra";
        ws.classList.add("show-detail");
        if (options.focusTitle) { const title = $("#case-title", panel); if (title) title.focus({ preventScroll: true }); }
      })
      .catch((error) => { if (window.console) console.warn("Demetra : ouverture du cas en page entière", error); location.href = "?cas=" + encodeURIComponent(key); });
  }

  // « À comparer avec » : le cas comparé s'ouvre sur place, comme depuis la liste (il faut qu'il y soit).
  detail.addEventListener("click", (event) => {
    const link = event.target.closest("[data-open-case]");
    if (!link || event.metaKey || event.ctrlKey || event.shiftKey) return;
    if (!items.some((item) => item.dataset.key === link.dataset.openCase)) return;
    event.preventDefault();
    openCase(link.dataset.openCase, { focusTitle: true });
  });

  function move(delta) {
    const visible = visibleItems();
    if (!visible.length) return;
    const index = visible.indexOf(currentItem());
    const next = visible[Math.max(0, Math.min(visible.length - 1, index === -1 ? 0 : index + delta))];
    if (next && next !== currentItem()) openCase(next.dataset.key);
  }
  function nextToAnalyze() {
    const visible = visibleItems();
    const start = visible.indexOf(currentItem());
    const ordered = visible.slice(start + 1).concat(visible.slice(0, start + 1));
    const target = ordered.find((li) => li.dataset.decision === "to_analyze" && li !== currentItem());
    if (target) openCase(target.dataset.key);
    else showToast("Plus aucun cas à analyser dans cette liste.", false);
  }

  if (list) {
    list.addEventListener("click", (event) => {
      const link = event.target.closest("a.case");
      if (!link || event.metaKey || event.ctrlKey || event.shiftKey || event.button) return;
      event.preventDefault();
      openCase(link.closest(".case-item").dataset.key, { keepScroll: true, focusTitle: matchMedia("(max-width: 900px)").matches });
    });
    window.addEventListener("popstate", () => {
      const params = new URL(location.href).searchParams;
      const key = params.get("cas");
      if (key) openCase(key, { fromHistory: true, step: params.get("etape") });
    });
    if (new URL(location.href).searchParams.get("cas")) ws.classList.add("show-detail");
    const current = currentItem();
    if (current) $(".case", current).scrollIntoView({ block: "center" });
  }

  /* Avis */
  function updateCounts(counts) {
    if (!counts) return;
    $$("[data-count]", ws).forEach((el) => { if (counts[el.dataset.count] !== undefined) el.textContent = counts[el.dataset.count]; });
    $$("[data-bar]", ws).forEach((el) => { el.style.width = counts["pct_" + el.dataset.bar] + "%"; });
    const bar = $(".progress .progress-bar", ws);
    if (bar) bar.setAttribute("aria-label", "Avancement de votre revue : " + counts.accepted + " validés, " + counts.rejected + " refusés, " + counts.to_analyze + " à analyser");
  }
  function paintPanel(panel, decision) {
    panel.dataset.decision = decision;
    $$(".vbtn", panel).forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.decision === decision)));
    const notice = $("[data-stale-notice]", panel);
    if (notice) notice.remove();
  }
  function paintItem(key, decision, comment) {
    const li = items.find((item) => item.dataset.key === key);
    if (li) {
      li.dataset.decision = decision;
      li.removeAttribute("data-stale");
      const state = $("[data-vstate]", li);
      state.className = "vstate vstate-" + decision;
      $("use", state).setAttribute("href", "#ui-" + decision);
      $(".vstate-label", state).textContent = LABELS[decision];
      const changed = $(".flag-changed", li);
      if (changed) changed.remove();
      const flags = $(".case-flags", li);
      let mark = $("[data-flag-comment]", li);
      if (comment && comment.trim() && !mark) {
        flags.insertAdjacentHTML("beforeend", '<span class="flag" title="Vous avez laissé un commentaire" data-flag-comment><svg class="ic" aria-hidden="true"><use href="#ui-comment"/></svg><span class="sr-only">Commenté.</span></span>');
      } else if (mark && !(comment && comment.trim())) mark.remove();
    }
  }
  function sendVerdict(payload, options) {
    const panel = panelNow();
    if (!panel || !panel.dataset.verdictUrl) return Promise.resolve();
    const key = panel.dataset.key;
    const state = $("[data-verdict-state]", panel);
    const box = $("[data-comment]", panel);
    const before = { key: key, decision: panel.dataset.decision, comment: box ? box.defaultValue : "" };
    if (state) { state.textContent = "Enregistrement…"; state.classList.remove("is-error"); }
    return fetch(panel.dataset.verdictUrl, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf(), "X-Requested-With": "fetch" },
      body: JSON.stringify(payload),
    }).then((response) => response.json().then((data) => ({ ok: response.ok, data: data })))
      .then((result) => {
        if (!result.ok) throw new Error((result.data.error && result.data.error.message) || "Enregistrement impossible.");
        const data = result.data;
        paintItem(key, data.decision, data.comment);
        if (panelNow() === panel) {
          paintPanel(panel, data.decision);
          if (box) { box.defaultValue = data.comment; if (payload.comment !== undefined) box.value = data.comment; }
          const save = $("[data-comment-save]", panel); if (save) save.hidden = true;
          if (state) state.textContent = "Enregistré";
        }
        updateCounts(data.counts);
        applyFilters();
        if (!(options && options.silent)) {
          lastVerdict = before;
          if (payload.decision && payload.decision !== before.decision) showToast("Cas " + panel.dataset.title.split(" · ")[0] + " : " + LABELS[data.decision].toLowerCase() + ".", true);
        }
        return data;
      })
      .catch((error) => { if (state) { state.textContent = error.message; state.classList.add("is-error"); } });
  }
  function decide(decision) {
    const panel = panelNow();
    if (!panel || !$(".vbtn", panel)) return;
    const box = $("[data-comment]", panel);
    const payload = { decision: decision };
    if (box && box.value !== box.defaultValue) payload.comment = box.value;
    sendVerdict(payload).then((data) => {
      if (!data) return;
      if (decision === "rejected" && box && !box.value.trim()) { box.focus(); return; }
      if (decision !== "to_analyze" && store.get("demetra-advance") === "1") nextToAnalyze();
    });
  }
  function undo() {
    if (!lastVerdict) return;
    const previous = lastVerdict;
    lastVerdict = null;
    hideToast();
    const run = () => sendVerdict({ decision: previous.decision, comment: previous.comment }, { silent: true }).then(() => showToast("Avis précédent rétabli.", false));
    const panel = panelNow();
    if (panel && panel.dataset.key === previous.key) run(); else openCase(previous.key).then(run);
  }
  function showToast(text, withUndo) {
    const toast = $("[data-toast]");
    if (!toast) return;
    $("[data-toast-text]", toast).textContent = text;
    $("[data-toast-undo]", toast).hidden = !withUndo;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(hideToast, withUndo ? 7000 : 3000);
  }
  function hideToast() { const toast = $("[data-toast]"); if (toast) toast.hidden = true; }

  /* Mode focus */
  function syncFocusButton() {
    const on = doc.body.classList.contains("is-focus");
    $$("[data-focus-toggle]").forEach((button) => button.setAttribute("aria-pressed", String(on)));
  }
  function toggleFocus(force) {
    const on = force === undefined ? !doc.body.classList.contains("is-focus") : force;
    doc.body.classList.toggle("is-focus", on);
    store.set("demetra-focus", on ? "1" : "0");
    syncFocusButton();
  }
  if (store.get("demetra-focus") === "1" && panelNow()) toggleFocus(true);

  const help = $("[data-help-dialog]");
  const advance = $("[data-auto-advance]");
  if (advance) {
    advance.checked = store.get("demetra-advance") === "1";
    advance.addEventListener("change", () => store.set("demetra-advance", advance.checked ? "1" : "0"));
  }

  let engaged = false;      // la personne a commencé à travailler dans l'espace de revue
  let entered = false;      // Entrée a été pressée sur un cas : Tab parcourt ses commandes
  ws.addEventListener("pointerdown", () => { engaged = true; entered = false; });
  doc.addEventListener("click", (event) => {
    const target = event.target;
    if (event.detail > 0) { const pressed = target.closest("button"); if (pressed && ws.contains(pressed)) pressed.blur(); }
    const vbtn = target.closest(".vbtn");
    if (vbtn) return decide(vbtn.dataset.decision);
    if (target.closest("[data-comment-save]")) { const box = $("[data-comment]", panelNow()); return void sendVerdict({ comment: box.value }); }
    if (target.closest("[data-case-prev]")) return move(-1);
    if (target.closest("[data-case-next]")) return move(1);
    if (target.closest("[data-focus-toggle]")) return toggleFocus();
    if (target.closest("[data-help]") && help) return help.showModal();
    if (target.closest("[data-show-list]")) { ws.classList.remove("show-detail"); const current = currentItem(); if (current) $(".case", current).focus(); return; }
    if (target.closest("[data-filter-reset]")) return resetFilters();
    if (target.closest("[data-toast-undo]")) return undo();
    if (target.closest("[data-live-reload]")) return location.reload();
    if (target.closest("[data-live-dismiss]")) { $("[data-live]").hidden = true; return; }
    const filter = target.closest("[data-filter-decision]");
    if (filter) setDecisionFilter(filter.dataset.filterDecision);
  });
  doc.addEventListener("input", (event) => {
    if (!event.target.matches("[data-comment]")) return;
    const save = $("[data-comment-save]", panelNow());
    if (save) save.hidden = event.target.value === event.target.defaultValue;
  });
  doc.addEventListener("focusout", (event) => {
    if (event.target.matches && event.target.matches("[data-comment]") && event.target.value !== event.target.defaultValue) sendVerdict({ comment: event.target.value }, { silent: true });
  });

  /* Clavier */
  doc.addEventListener("keydown", (event) => {
    const target = event.target;
    const typing = target.matches("input, textarea, select") || target.isContentEditable;
    if (event.key === "Escape") {
      if (help && help.open) return;
      if (typing) {
        if (target.matches("[data-filter-q]") && filters.q) { target.value = ""; filters.q = ""; applyFilters(); }
        target.blur();
        return;
      }
      if (doc.body.classList.contains("is-focus")) { toggleFocus(false); return; }
      return;
    }
    if (typing) {
      if (target.matches("[data-comment]") && event.key === "Enter" && (event.metaKey || event.ctrlKey)) { event.preventDefault(); target.blur(); }
      return;
    }
    if (event.metaKey || event.ctrlKey || event.altKey || (help && help.open)) return;
    if (event.key === "Tab") {
      // Tab passe au cas suivant quand le focus est sur la liste des cas, ou nulle part une fois la revue commencée.
      // Partout ailleurs (champs, boutons, liens), Tab garde son rôle habituel ; aux deux bouts de la liste aussi.
      const onCase = target.closest && target.closest(".case-item");
      // « Au repos » : le focus n'est sur aucune commande (corps de page, ou zone cliquée à la souris).
      const atRest = !entered && !target.closest("a, button, input, select, textarea, summary, [contenteditable], [tabindex]:not([tabindex='-1'])");
      if (!onCase && !(atRest && engaged)) return;
      const visible = visibleItems();
      const index = visible.indexOf(currentItem());
      const next = index === -1 ? null : visible[index + (event.shiftKey ? -1 : 1)];
      if (!next) return;
      event.preventDefault();
      entered = false;
      openCase(next.dataset.key, { focusItem: true });
      return;
    }
    if (event.key !== "Shift") engaged = true;
    if (event.key === "Enter" && target.matches("a.case")) {
      // Entrée sur un cas : on entre dans le cas, Tab parcourt alors ses commandes.
      event.preventDefault();
      const key = target.closest(".case-item").dataset.key;
      const shown = panelNow();
      entered = true;
      if (shown && shown.dataset.key === key) { const title = $("#case-title", shown); if (title) title.focus({ preventScroll: true }); ws.classList.add("show-detail"); }
      else openCase(key, { focusTitle: true });
      return;
    }
    const panel = panelNow();
    const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
    const onControl = target.closest("button, a, summary, [role='tab']");
    switch (key) {
      case "j": case "ArrowDown": if (key === "ArrowDown" && target.closest(".rep-scroll, .cases")) return; event.preventDefault(); move(1); break;
      case "k": case "ArrowUp": if (key === "ArrowUp" && target.closest(".rep-scroll, .cases")) return; event.preventDefault(); move(-1); break;
      case "ArrowRight": if (panel && !target.closest(".rep-scroll")) { event.preventDefault(); setStep(panel, stepOf(panel) + 1); } break;
      case "ArrowLeft": if (panel && !target.closest(".rep-scroll")) { event.preventDefault(); setStep(panel, stepOf(panel) - 1); } break;
      case "v": decide("accepted"); break;
      case "r": event.preventDefault(); decide("rejected"); break;
      case "a": decide("to_analyze"); break;
      case "c": { const box = panel && $("[data-comment]", panel); if (box) { event.preventDefault(); box.focus(); } break; }
      case "z": undo(); break;
      case "n": nextToAnalyze(); break;
      case "f": toggleFocus(); break;
      case "l": setDock("list", !docked("list")); break;
      case "m": setDock("rail", !docked("rail")); break;
      case "/": { const q = $("[data-filter-q]", ws); if (q) { event.preventDefault(); if (doc.body.classList.contains("is-focus")) toggleFocus(false); if (docked("list")) setDock("list", false); ws.classList.remove("show-detail"); q.focus(); q.select(); } break; }
      case "?": if (help) help.showModal(); break;
      case "Enter": if (!onControl && target.closest(".case-item")) $(".case", target.closest(".case-item")).click(); break;
      default: break;
    }
  });

  /* Mise à jour en direct : l'API ou un autre membre modifie l'étude ouverte */
  let snapshot = {};
  const stateEl = doc.getElementById("study-state");
  if (stateEl) { try { snapshot = JSON.parse(stateEl.textContent); } catch (e) { snapshot = {}; } }
  function describe(state) {
    const before = snapshot.cases || {}, after = state.cases || {};
    let added = 0, changed = 0, retired = 0, restored = 0, cosmetic = 0, current = false;
    const open = panelNow() && panelNow().dataset.key;
    Object.keys(after).forEach((key) => {
      const now = after[key], was = before[key];
      if (!was) { added += 1; return; }
      if (now[0] !== was[0]) { changed += 1; if (key === open) current = true; }
      else if (now[1] !== was[1]) { cosmetic += 1; if (key === open) current = true; }
      if (now[2] && !was[2]) retired += 1;
      if (!now[2] && was[2]) restored += 1;
    });
    const plural = (n, one, many) => n + " " + (n > 1 ? many : one);
    const parts = [];
    if (added) parts.push(plural(added, "cas ajouté", "cas ajoutés"));
    if (changed) parts.push(plural(changed, "cas modifié", "cas modifiés"));
    if (cosmetic) parts.push(plural(cosmetic, "texte corrigé", "textes corrigés"));
    if (retired) parts.push(plural(retired, "cas retiré", "cas retirés"));
    if (restored) parts.push(plural(restored, "cas rétabli", "cas rétablis"));
    let text = parts.length ? "L'étude vient de changer : " + parts.join(", ") + "." : "L'étude vient d'être modifiée.";
    if (current) text += " Le cas affiché est concerné.";
    return text;
  }
  function onRevision() {
    fetch("/etudes/" + sid + "/etat/", { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" })
      .then((response) => (response.ok ? response.json() : null))
      .then((state) => {
        if (!state || state.revision === snapshot.revision) return;
        const live = $("[data-live]");
        if (!live) return;
        $("[data-live-text]", live).textContent = describe(state);
        live.hidden = false;
      }).catch(() => {});
  }
  if (window.EventSource && sid) {
    let source = null;
    const connect = () => {
      source = new EventSource("/etudes/" + sid + "/events");
      source.addEventListener("revision", onRevision);
      source.addEventListener("hello", (event) => { if (snapshot.revision !== undefined && Number(event.data) !== snapshot.revision) onRevision(); });
    };
    connect();
    window.addEventListener("pagehide", () => { if (source) source.close(); });
  }
})();
