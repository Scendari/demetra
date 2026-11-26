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
    build: ["buildFolded", "demetra-build"],   // le panneau « Construire la situation » de l'atelier
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
      if ((name === "list" || name === "build") && event.detail === 0) { const other = $$('[data-dock="' + name + '"]').find((button) => button.offsetParent !== null); if (other) other.focus(); }
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

  /* ---------------------------------------------------------------- Atelier */
  // La page marche sans script (formulaire GET, liens). Ici, on redemande seulement le fragment quand la
  // situation change : tout l'état reste dans l'adresse, et le serveur reste le seul à appliquer les règles.
  const atelier = $("[data-atelier]");
  if (atelier) {
    let turn = 0;
    let playing = null;
    atelier.classList.add("is-live");
    const walk = () => $("[data-panel]", atelier);
    const focusKey = (el) => {
      if (!el || !atelier.contains(el)) return null;
      if (el.id) return { id: el.id };
      if (el.name) return { name: el.name, value: el.type === "text" ? null : el.value };
      return { text: el.textContent.trim() };
    };
    const refocus = (key) => {
      if (!key) return;
      let el = null;
      if (key.id) el = doc.getElementById(key.id);
      else if (key.name) el = $$("[name]", atelier).find((f) => f.name === key.name && (key.value === null || f.value === key.value));
      else el = $$("a", atelier).find((a) => a.textContent.trim() === key.text);
      if (!el || el.disabled) el = $("#at-build-title", atelier);
      if (el) el.focus({ preventScroll: true });
    };
    // Le pas affiché suit dans l'adresse ; le départ est celui qu'on voit par défaut, il ne s'écrit pas.
    const writeStep = () => {
      const panel = walk();
      if (!panel) return;
      const url = new URL(location.href);
      if (stepOf(panel) > 0) url.searchParams.set("etape", String(stepOf(panel) + 1)); else url.searchParams.delete("etape");
      history.replaceState(history.state, "", url);
    };
    const stop = () => {
      if (!playing) return;
      clearInterval(playing);
      playing = null;
      const button = $("[data-atelier-play]", atelier);
      if (button) { $("use", button).setAttribute("href", "#ui-play"); $("span", button).textContent = "Dérouler"; }
    };
    const play = () => {
      const panel = walk();
      const button = $("[data-atelier-play]", atelier);
      if (!panel || !button) return;
      if (playing) return stop();
      setStep(panel, 0);
      $("use", button).setAttribute("href", "#ui-pause");
      $("span", button).textContent = "Arrêter";
      playing = setInterval(() => {
        if (stepOf(panel) >= (panel._steps || []).length - 1) return stop();
        setStep(panel, stepOf(panel) + 1);
        writeStep();
      }, 900);
    };
    const ready = () => {
      $$("[data-panel]", atelier).forEach((panel) => setStep(panel, stepOf(panel), { quiet: true }));
      const button = $("[data-atelier-play]", atelier);
      if (button) button.hidden = (walk()._steps || []).length < 2;
      const hint = $("[data-at-hint]", atelier);   // un schéma sans nœuds ni barres (une table) ne se manie pas à la souris
      if (hint) hint.hidden = !$("[data-at-plan] .n[data-e], [data-at-plan] .tl-bar[data-p]", atelier);
      if (!historyRow(pinned)) pinned = null;
      trace(historyRow(pinned));
      choose(chosen);
      // Sur une frise, seules les périodes posées se déplacent : une ligne de l'historique n'a pas de bornes à soi.
      $$("[data-at-plan] .tl-bar[data-p]", atelier).forEach((bar) => bar.classList.toggle("is-movable", !!boundsOf(bar.dataset.p)));
    };
    /* D'où vient une ligne de l'historique (atelier de périodes) : la survoler ou la choisir fait ressortir ses
       périodes sources sur la frise et dans les fiches, et ses règles dans la liste. Le serveur a écrit la
       provenance dans la ligne ; ici on ne fait que la montrer. */
    let pinned = null;   // le début de la ligne dont on garde la provenance affichée
    const historyRow = (start) => (start === null ? null : $$(".at-history tr[data-start]", atelier).find((tr) => tr.dataset.start === start) || null);
    const trace = (tr) => {
      $$(".is-traced", atelier).forEach((el) => el.classList.remove("is-traced"));
      atelier.classList.toggle("is-tracing", !!tr);
      const line = $("[data-at-trace]", atelier);
      if (line) line.textContent = tr ? tr.dataset.why : line.dataset.idle;
      $$("[data-at-why]", atelier).forEach((button) => button.setAttribute("aria-pressed", String(pinned !== null && button.closest("tr").dataset.start === pinned)));
      if (!tr) return;
      tr.classList.add("is-traced");
      tr.dataset.from.split(" ").concat(tr.dataset.image).filter(Boolean).forEach((id) => {
        $$('[data-at-plan] [data-p="' + id + '"], .at-card[data-brick="' + id + '"]', atelier).forEach((el) => el.classList.add("is-traced"));
      });
      tr.dataset.rules.split(" ").filter(Boolean).forEach((key) => {
        const rule = $('.at-rules li[data-rule="' + key + '"]', atelier);
        if (rule) rule.classList.add("is-traced");
      });
    };
    const rowOf = (target) => (target && target.closest ? target.closest(".at-history tr[data-start]") : null);
    atelier.addEventListener("pointerover", (event) => { if (event.pointerType === "mouse" && rowOf(event.target)) trace(rowOf(event.target)); });
    atelier.addEventListener("pointerout", (event) => { if (event.pointerType === "mouse" && rowOf(event.target) && !rowOf(event.relatedTarget)) trace(historyRow(pinned)); });
    atelier.addEventListener("focusin", (event) => { if (rowOf(event.target)) trace(rowOf(event.target)); });
    atelier.addEventListener("focusout", (event) => { if (rowOf(event.target)) trace(historyRow(pinned)); });
    atelier.addEventListener("click", (event) => {
      const tr = rowOf(event.target);
      if (!tr) return;
      pinned = pinned === tr.dataset.start ? null : tr.dataset.start;
      trace(historyRow(pinned));
    });

    /* Ce que le dernier geste a changé dans l'historique. Les lignes d'avant sont lues dans la page au moment
       du geste, puis comparées aux nouvelles par leur début : le serveur ne garde rien d'une situation. */
    const historyNow = () => {
      const table = $(".at-history", atelier);
      return table ? $$("tbody tr[data-start]", table).map((tr) => ({ start: tr.dataset.start, sig: tr.dataset.sig, text: tr.dataset.text })) : null;
    };
    const deltaBadge = (kind, word) => {
      const badge = doc.createElement("span");
      const icon = badge.appendChild(doc.createElementNS(SVG_NS, "svg"));
      badge.className = "at-delta at-delta-" + kind;
      icon.setAttribute("class", "ic");
      icon.setAttribute("aria-hidden", "true");
      icon.appendChild(doc.createElementNS(SVG_NS, "use")).setAttribute("href", "#ui-" + { new: "plus", changed: "changed", gone: "close" }[kind]);
      badge.appendChild(doc.createTextNode(word));
      return badge;
    };
    const markRow = (table, tr, badge) => {   // petit écran : le mot a sa ligne, au-dessus de celle qu'il qualifie
      const mark = doc.createElement("tr");
      const cell = mark.appendChild(doc.createElement("td"));
      mark.className = "at-run-mark";
      cell.colSpan = table.tHead.rows[0].cells.length;
      cell.appendChild(badge);
      tr.parentNode.insertBefore(mark, tr);
    };
    const goneRow = (table, was) => {   // une ligne disparue reste lisible, barrée, à sa place parmi les débuts
      const tr = doc.createElement("tr");
      const text = tr.appendChild(doc.createElement("td"));
      const end = tr.appendChild(doc.createElement("td"));
      tr.className = "is-gone";
      text.colSpan = table.tHead.rows[0].cells.length - 1;
      text.appendChild(doc.createElement("del")).textContent = was.text;
      end.className = "at-row-end";
      end.appendChild(deltaBadge("gone", "disparue"));
      const next = $$("tbody tr[data-start]", table).find((row) => Number(row.dataset.start) > Number(was.start));
      const above = next && next.previousElementSibling;
      table.tBodies[0].insertBefore(tr, (above && above.classList.contains("at-run-mark") ? above : next) || null);
      markRow(table, tr, deltaBadge("gone", "disparue"));
    };
    const showDelta = (before) => {
      const table = $(".at-history", atelier);
      const note = $("[data-at-delta]", atelier);
      if (!table || !note || !before) return;
      const old = new Map(before.map((row) => [row.start, row]));
      const counts = { new: 0, changed: 0, gone: 0 };
      $$("tbody tr[data-start]", table).forEach((tr) => {
        const was = old.get(tr.dataset.start);
        old.delete(tr.dataset.start);
        if (was && was.sig === tr.dataset.sig) return;
        const kind = was ? "changed" : "new";
        const cell = $("[data-delta-cell]", tr);
        counts[kind] += 1;
        tr.classList.add("is-" + kind);
        cell.insertBefore(deltaBadge(kind, was ? "modifiée" : "nouvelle"), cell.firstChild);
        if (was) cell.firstChild.title = "Avant ce geste : " + was.text;
        markRow(table, tr, cell.firstChild.cloneNode(true));
        if (!was) return;
        const said = cell.appendChild(doc.createElement("span"));
        said.className = "sr-only";
        said.textContent = " Avant ce geste : " + was.text + ".";
      });
      old.forEach((was) => { counts.gone += 1; goneRow(table, was); });
      const parts = [];
      const count = (n, one, many) => { if (n) parts.push(n + " " + (n > 1 ? many : one)); };
      count(counts.new, "ligne nouvelle", "lignes nouvelles");
      count(counts.changed, "ligne modifiée", "lignes modifiées");
      count(counts.gone, "ligne disparue", "lignes disparues");
      note.textContent = parts.length ? "Votre dernier geste : " + parts.join(", ") + "." : "Votre dernier geste n'a pas changé l'historique.";
    };

    // « from » : le contrôle qui a lancé le geste. Safari ne donne pas le focus à une case ou à un bouton
    // qu'on clique : c'est lui, et non l'élément actif, qu'on rend après le nouveau résultat.
    const load = (url, from) => {
      const mine = ++turn;
      const before = historyNow();
      const key = focusKey(from || doc.activeElement);
      const open = $$("details[data-keep]", atelier).filter((d) => d.open).map((d) => d.dataset.keep);
      stop();
      closePop();
      atelier.setAttribute("aria-busy", "true");
      fetch(url, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" })
        .then((response) => { if (!response.ok) throw new Error(String(response.status)); return response.text().then((html) => [html, response.url]); })
        .then(([html, landed]) => {
          if (mine !== turn) return;   // une réponse plus récente est attendue
          atelier.innerHTML = html;
          atelier.removeAttribute("aria-busy");
          open.forEach((name) => { const d = $('details[data-keep="' + name + '"]', atelier); if (d) d.open = true; });
          ready();
          showDelta(before);
          history.replaceState(history.state, "", landed || url);   // le serveur a rangé l'adresse : on garde la sienne
          refocus(key);
        })
        .catch(() => { location.href = url; });   // le serveur répondra par la page entière, ou par son erreur
    };
    // L'adresse de la situation telle que le formulaire la porte, plus un geste (poser, relier, délier).
    const asked = (form, extra) => {
      const query = new URLSearchParams();
      // Une borne vide se garde : c'est une borne absente, pas un champ qu'on n'a pas rempli.
      new FormData(form).forEach((value, name) => { if (value !== "" || /^(de|a)\./.test(name)) query.append(name, value); });
      Object.keys(extra || {}).forEach((name) => query.append(name, extra[name]));
      return form.action + "?" + query.toString();
    };
    const submit = (form, submitter, from) => {
      const extra = {};
      if (submitter && submitter.name) extra[submitter.name] = submitter.value;
      load(asked(form, extra), from || submitter);
    };

    /* Glisser-déposer. Deux gestes sur le schéma : y déposer une brique de la palette, et tirer un lien d'une
       brique à une autre. Ce sont des raccourcis : chacun revient à une adresse que la page sait déjà
       demander (« add », « lk.<brique> », « unlink »), et le serveur revérifie ce que l'étude permet. Les
       boutons et les listes restent là pour le clavier. */
    const SVG_NS = "http://www.w3.org/2000/svg";
    let drag = null;
    let pop = null;
    let swallow = false;   // le clic qui suit un glisser ne vaut pas un clic sur le bouton
    const build = () => $("[data-atelier-form]", atelier);
    const gesture = (extra) => load(asked(build(), extra));
    const nameOf = (id) => { const field = doc.getElementById("at-name-" + id); return field ? field.value || field.placeholder : id; };
    const kindOf = (id) => { const card = $('.at-card[data-brick="' + id + '"]', atelier); return card ? card.dataset.kind : ""; };
    const linkTypes = () => JSON.parse(build().dataset.atLinks || "[]");
    const permitted = (from, kind) => linkTypes().filter((link) => link.from.includes(kindOf(from)) && link.to.includes(kind));
    const missing = (from, to) => {   // les liens permis de l'une à l'autre qui ne sont pas encore posés
      const placed = $$('input[name="l"]', build()).map((field) => field.value);
      return permitted(from, kindOf(to)).filter((link) => !placed.includes(from + ":" + link.type + ":" + to));
    };
    const say = (text) => { const hint = $("[data-at-hint-text]", atelier); if (hint) hint.textContent = text; };
    const mark = (el, name) => {
      $$("." + name, atelier).forEach((old) => { if (old !== el) old.classList.remove(name); });
      if (el) el.classList.add(name);
    };
    /* La brique (ou la période) choisie : celle dont la fiche a eu le focus en dernier, ou qu'on a cliquée dans le
       schéma. Sa fiche et son dessin portent la même marque, et la gardent d'un résultat au suivant. */
    let chosen = null;
    const choose = (id) => {
      const card = id === null ? null : $('.at-card[data-brick="' + id + '"]', atelier);
      chosen = card ? id : null;
      mark(card, "is-shown");
      $$("[data-at-plan] .is-chosen", atelier).forEach((el) => el.classList.remove("is-chosen"));
      if (!card) return;
      $$('[data-at-plan] .n[data-e="' + id + '"], [data-at-plan] .tl-bar[data-p="' + id + '"]', atelier).forEach((el) => el.classList.add("is-chosen"));
    };
    // Un clic dans une fiche la choisit aussi : Safari ne donne pas le focus aux cases ni aux boutons.
    ["focusin", "pointerdown"].forEach((type) => atelier.addEventListener(type, (event) => {
      const card = event.target.closest(".at-card");
      if (card && card.dataset.brick !== chosen) choose(card.dataset.brick);
    }));
    const under = (event, selector) => { const el = doc.elementFromPoint(event.clientX, event.clientY); return el ? el.closest(selector) : null; };
    const inSvg = (svg, x, y) => { const point = svg.createSVGPoint(); point.x = x; point.y = y; return point.matrixTransform(svg.getScreenCTM().inverse()); };
    const closePop = () => { if (pop) pop.remove(); pop = null; mark(null, "is-picked"); };
    /* Frise : déplacer une période, ou en tirer un bord. Le geste revient à changer ses deux champs de bornes ;
       il se cale sur le pas des champs et reste dans l'axe. Pendant le geste, seule la barre bouge. */
    const boundsOf = (id) => {
      const start = doc.getElementById("at-de-" + id);
      const end = doc.getElementById("at-a-" + id);
      const fine = start && end && start.value !== "" && end.value !== "" && Number(start.value) < Number(end.value);
      return fine ? { start: start, end: end } : null;
    };
    const tidy = (value) => Math.round(value * 1e6) / 1e6;
    const within = (value, low, high) => Math.min(Math.max(value, low), high);
    const drawBar = (bar, x1, x2) => {
      const width = Math.max(4, x2 - x1);
      const shape = $(".n-shape", bar);
      const halo = $(".n-halo", bar);
      shape.setAttribute("x", x1);
      shape.setAttribute("width", width);
      halo.setAttribute("x", x1 - 3);
      halo.setAttribute("width", width + 6);
    };
    const beginPeriod = () => {
      const fields = boundsOf(drag.period);
      const svg = drag.node.ownerSVGElement;
      const [low, high, origin, width] = svg.dataset.span.split(" ").map(Number);
      drag.fields = fields;
      drag.was = { start: Number(fields.start.value), end: Number(fields.end.value) };
      drag.now = drag.was;
      drag.step = Number(fields.start.dataset.grain) || Number(fields.start.step) || 1;   // le pas de l'axe
      drag.min = Number(fields.start.min);
      drag.max = Number(fields.start.max);
      drag.unit = width / (high - low) * svg.getScreenCTM().a;   // pixels d'écran par unité de l'axe
      drag.xOf = (value) => origin + (value - low) / (high - low) * width;
      drag.hint = ($("[data-at-hint-text]", atelier) || {}).textContent;
      drag.hintBox = $("[data-at-hint]", atelier);   // l'aide dit les bornes pendant le geste : sa hauteur ne bouge pas
      if (drag.hintBox) drag.hintBox.style.minHeight = drag.hintBox.getBoundingClientRect().height + "px";
      drag.node.classList.add("is-moving");
    };
    const movePeriod = (event) => {
      const raw = (event.clientX - drag.x) / drag.unit;
      const snap = (value) => drag.min + Math.round((value - drag.min) / drag.step) * drag.step;   // sur la grille de l'axe
      let start = drag.was.start;
      let end = drag.was.end;
      if (drag.grip === "start") {
        start = within(snap(start + raw), drag.min, drag.max);
        while (start >= end) start -= drag.step;
        if (start < drag.min) start = drag.was.start;
      } else if (drag.grip === "end") {
        end = within(snap(end + raw), drag.min, drag.max);
        while (end <= start) end += drag.step;
        if (end > drag.max) end = drag.was.end;
      } else {   // déplacée d'un nombre entier de pas : la durée ne change pas
        const by = within(Math.round(raw / drag.step) * drag.step, drag.min - start, drag.max - end);
        start += by;
        end += by;
      }
      drag.now = { start: tidy(start), end: tidy(end) };
      drawBar(drag.node, drag.xOf(start), drag.xOf(end));
      say(nameOf(drag.period) + " : du " + drag.now.start + " au " + drag.now.end + ", fin exclue.");
    };
    const dropPeriod = (done) => {
      if (done.now.start === done.was.start && done.now.end === done.was.end) return say(done.hint);
      done.fields.start.value = String(done.now.start);
      done.fields.end.value = String(done.now.end);
      submit(build());
    };
    const openPop = (plan, event, title, choices) => {
      closePop();
      pop = doc.createElement("div");
      pop.className = "at-pop";
      pop.setAttribute("role", "group");
      pop.setAttribute("aria-label", title);
      choices.forEach((choice) => {
        const button = doc.createElement("button");
        button.type = "button";
        button.className = "btn";
        button.textContent = choice.label;
        button.addEventListener("click", () => { closePop(); gesture(choice.extra); });
        pop.appendChild(button);
      });
      plan.appendChild(pop);
      const box = plan.getBoundingClientRect();
      pop.style.left = Math.max(0, Math.min(event.clientX - box.left, box.width - pop.offsetWidth)) + "px";
      pop.style.top = event.clientY - box.top + 10 + "px";
      pop.firstChild.focus({ preventScroll: true });
    };
    const showCard = (id) => {   // un clic sur une brique du schéma mène à sa fiche
      const field = doc.getElementById("at-name-" + id);
      if (!field) return;
      if (docked("build")) setDock("build", false);   // panneau replié : demander une fiche le rouvre
      field.closest(".at-card").scrollIntoView({ block: "nearest" });
      field.focus({ preventScroll: true });
      choose(id);
    };
    const begin = () => {
      drag.live = true;
      closePop();
      stop();
      atelier.classList.add("is-dragging");
      if (drag.type) {
        drag.ghost = doc.createElement("div");
        drag.ghost.className = "at-ghost";
        drag.ghost.textContent = drag.label;
        doc.body.appendChild(drag.ghost);
        return;
      }
      if (drag.period) return beginPeriod();
      const box = drag.node.getBoundingClientRect();
      drag.svg = drag.node.ownerSVGElement;
      drag.from = inSvg(drag.svg, box.left + box.width / 2, box.top + box.height / 2);
      drag.wire = doc.createElementNS(SVG_NS, "g");
      drag.wire.setAttribute("class", "at-wire");
      drag.wire.appendChild(doc.createElementNS(SVG_NS, "line"));
      drag.wire.appendChild(doc.createElementNS(SVG_NS, "circle")).setAttribute("r", "4.5");
      drag.svg.appendChild(drag.wire);
      drag.node.classList.add("is-source");
    };
    const move = (event) => {
      if (drag.period) return movePeriod(event);
      const node = under(event, "[data-at-plan] .n[data-e]");
      if (drag.type) {
        drag.ghost.style.transform = "translate(" + (event.clientX + 12) + "px," + (event.clientY + 14) + "px)";
        mark(under(event, "[data-at-plan]"), "is-over");
        return mark(node && permitted(node.dataset.e, drag.type).length ? node : null, "is-target");
      }
      const at = inSvg(drag.svg, event.clientX, event.clientY);
      const line = drag.wire.firstChild;
      line.setAttribute("x1", drag.from.x);
      line.setAttribute("y1", drag.from.y);
      line.setAttribute("x2", at.x);
      line.setAttribute("y2", at.y);
      drag.wire.lastChild.setAttribute("cx", at.x);
      drag.wire.lastChild.setAttribute("cy", at.y);
      const other = node && node !== drag.node ? node : null;
      const ok = other && missing(drag.id, other.dataset.e).length > 0;
      mark(ok ? other : null, "is-target");
      mark(other && !ok ? other : null, "is-refused");
    };
    const drop = (done, event) => {
      if (done.period) return dropPeriod(done);
      const node = under(event, "[data-at-plan] .n[data-e]");
      const plan = under(event, "[data-at-plan]");
      if (done.type) {
        if (!plan) return;
        const extra = { add: done.type };
        if (node && permitted(node.dataset.e, done.type).length) extra.on = node.dataset.e;
        return gesture(extra);
      }
      if (!node || node === done.node) return;
      const to = node.dataset.e;
      const links = missing(done.id, to);
      const lk = (link) => { const extra = {}; extra["lk." + to] = "in:" + link.type + ":" + done.id; return extra; };
      if (links.length === 1) return gesture(lk(links[0]));
      if (links.length) return openPop(plan, event, "Quel lien poser ?", links.map((link) => ({ label: nameOf(done.id) + " " + link.label + " " + nameOf(to), extra: lk(link) })));
      say(permitted(done.id, kindOf(to)).length
        ? nameOf(done.id) + " et " + nameOf(to) + " sont déjà reliées ainsi."
        : "L'étude ne permet pas de lien de " + nameOf(done.id) + " vers " + nameOf(to) + ".");
    };
    const finish = (event, cancelled) => {
      const done = drag;
      drag = null;
      if (!done) return;
      if (!done.live) { if (!done.type && !cancelled) showCard(done.id || done.period); return; }
      swallow = true;
      setTimeout(() => { swallow = false; }, 80);
      atelier.classList.remove("is-dragging");
      if (done.ghost) done.ghost.remove();
      if (done.wire) done.wire.remove();
      if (done.period) {
        done.node.classList.remove("is-moving");
        if (done.hintBox) done.hintBox.style.minHeight = "";
        if (cancelled) { drawBar(done.node, done.xOf(done.was.start), done.xOf(done.was.end)); say(done.hint); }
      }
      ["is-over", "is-target", "is-refused", "is-source"].forEach((name) => mark(null, name));
      if (!cancelled) drop(done, event);
    };
    atelier.addEventListener("pointerdown", (event) => {
      if (event.button || !event.isPrimary) return;
      const add = event.target.closest(".at-add");
      const node = event.target.closest("[data-at-plan] .n[data-e]");
      const bar = event.target.closest("[data-at-plan] .tl-bar.is-movable");
      const at = { x: event.clientX, y: event.clientY };
      // Au doigt, glisser depuis la palette ferait défiler la page : on y touche la brique pour la poser.
      if (add && !add.disabled && event.pointerType !== "touch" && $("[data-at-plan]", atelier)) drag = Object.assign(at, { type: add.value, label: add.textContent.trim() });
      else if (node) drag = Object.assign(at, { id: node.dataset.e, node: node });
      else if (bar) drag = Object.assign(at, { period: bar.dataset.p, node: bar, grip: event.target.dataset.grip || "move" });
    });
    // Au doigt : sans cela, le cadre défile sous la brique ou la barre qu'on veut glisser et le geste est annulé
    // (« touch-action » n'a pas d'effet sur les formes d'un dessin SVG dans tous les navigateurs).
    atelier.addEventListener("touchstart", (event) => {
      if (event.target.closest("[data-at-plan] .tl-bar.is-movable, [data-at-plan] .n[data-e]")) event.preventDefault();
    }, { passive: false });
    doc.addEventListener("pointermove", (event) => {
      if (!drag) return;
      if (!drag.live) {
        if (Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 6) return;
        begin();
      }
      move(event);
    });
    doc.addEventListener("pointerup", (event) => finish(event, false));
    doc.addEventListener("pointercancel", (event) => finish(event, true));
    doc.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      finish(event, true);
      closePop();
      if (pinned !== null) { pinned = null; trace(null); }
    });
    atelier.addEventListener("click", (event) => {
      if (!swallow) return;
      swallow = false;
      event.preventDefault();
      event.stopPropagation();
    }, true);
    atelier.addEventListener("click", (event) => {
      const link = event.target.closest("[data-at-plan] .lk[data-l]");
      if (!link) { if (pop && !pop.contains(event.target)) closePop(); return; }
      const [from, type, to] = link.dataset.l.split(":");
      const kind = linkTypes().find((item) => item.type === type) || { label: "→" };
      openPop(link.closest("[data-at-plan]"), event, "Lien", [{ label: "Retirer le lien : " + nameOf(from) + " " + kind.label + " " + nameOf(to), extra: { unlink: link.dataset.l } }]);
      mark(link, "is-picked");
    });
    atelier.addEventListener("change", (event) => {
      const form = event.target.form;
      if (form && form.matches("[data-atelier-form]")) submit(form, null, event.target);
    });
    atelier.addEventListener("submit", (event) => {
      if (!event.target.matches("[data-atelier-form]")) return;
      event.preventDefault();
      submit(event.target, event.submitter);
    });
    atelier.addEventListener("click", (event) => {
      if (event.target.closest("[data-atelier-play]")) return play();
      const link = event.target.closest("a[data-atelier-link], a[data-at-step]");
      if (link && !(event.metaKey || event.ctrlKey || event.shiftKey || event.button)) {
        event.preventDefault();
        if (link.matches("[data-atelier-link]")) return load(link.href);
        const panel = walk();
        const last = (panel._steps || []).length - 1;
        stop();
        setStep(panel, { first: 0, prev: stepOf(panel) - 1, next: stepOf(panel) + 1, last: last }[link.dataset.atStep]);
      } else if (!event.target.closest(".stop-btn, [data-step-is]")) return;
      else stop();
      setTimeout(writeStep, 0);   // après le gestionnaire commun, qui change de pas
    });
    doc.addEventListener("keydown", (event) => {
      if (event.target.matches("input, textarea, select") || event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      const panel = walk();
      if (!panel) return;
      event.preventDefault();
      stop();
      setStep(panel, stepOf(panel) + (event.key === "ArrowRight" ? 1 : -1));
      writeStep();
    });
    if (walk()) ready();
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
