"""Parcours de bout en bout dans un vrai navigateur (Chromium piloté par Playwright).

Le test lance le site dans un processus à part, sur une base temporaire remplie par `seed_demo`,
puis joue : connexion, revue d'un cas au clavier, changement de représentation, partage, et mise à
jour en direct quand l'API modifie l'étude ouverte.

Captures d'écran : définir DEMETRA_CAPTURES=<dossier> pour les enregistrer.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")
expect = playwright_api.expect

ROOT = Path(__file__).resolve().parents[2]
CAPTURES = os.environ.get("DEMETRA_CAPTURES")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """Le site, servi par `manage.py runserver` sur une base temporaire de démonstration."""
    database = tmp_path_factory.mktemp("demetra") / "e2e.sqlite3"
    env = {**os.environ, "DEMETRA_DB": str(database), "DEMETRA_SSE_MAX_SECONDS": "20"}
    manage = [sys.executable, str(ROOT / "manage.py")]
    subprocess.run([*manage, "migrate", "-v0"], cwd=ROOT, env=env, check=True)
    subprocess.run([*manage, "seed_demo"], cwd=ROOT, env=env, check=True, capture_output=True)
    port = _free_port()
    server = subprocess.Popen([*manage, "runserver", f"127.0.0.1:{port}", "--noreload"], cwd=ROOT, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(base + "/llms.txt", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Le serveur n'a pas démarré.")
        yield base
    finally:
        server.terminate()
        server.wait(timeout=10)


@pytest.fixture(scope="module")
def browser():
    with playwright_api.sync_playwright() as pw:
        try:
            chromium = pw.chromium.launch()
        except Exception as error:  # Chromium absent : `uv run playwright install chromium`
            pytest.skip(f"Chromium indisponible : {error}")
        yield chromium
        chromium.close()


def shot(page, name: str, full_page: bool = False):
    if CAPTURES:
        Path(CAPTURES).mkdir(parents=True, exist_ok=True)
        page.wait_for_timeout(350)                         # laisse les transitions d'état se terminer
        page.screenshot(path=str(Path(CAPTURES) / f"{name}.png"), full_page=full_page)


def login(page, base: str, username: str):
    page.goto(base + "/comptes/login/")
    page.fill("#id_login", username)
    page.fill("#id_password", "demetra-demo")
    page.click("button[type=submit]")
    page.wait_for_url("**/etudes/")


# Une étude et un cas aux étapes volontairement inégales : note absente, courte ou très longue ; un ou plusieurs
# changements ; libellés de statut très courts ou très longs. Sert à vérifier que l'affichage ne bouge pas.
STABLE_STUDY = {
    "title": "Stabilité de l'affichage",
    "kind": "workflow",
    "statuses": [
        {"key": "ATT", "label": "À venir", "role": "waiting", "default": True},
        {"key": "OK", "label": "Fait", "role": "success"},
        {"key": "LONG", "label": "En cours de vérification approfondie par le service", "short": "Vérification", "role": "active"},
        {"key": "KO", "label": "Refusé après contrôle", "role": "error"},
    ],
}
STABLE_CASE = {
    "key": "inegal", "number": 1, "family": "Affichage", "title": "Des étapes très inégales", "kind": "workflow",
    "entities": [
        {"id": "a", "label": "Premier contrôle", "type": "task"},
        {"id": "b", "label": "Second contrôle, au libellé nettement plus long que les autres", "type": "task"},
        {"id": "c", "label": "Clôture", "type": "task"},
    ],
    "links": [{"from": "a", "to": "b", "type": "depends"}, {"from": "b", "to": "c", "type": "depends"}],
    "steps": [
        {"title": "Départ", "changes": {"a": "LONG"}, "at": 0},
        {"title": "Une étape au titre long, qui occupe presque toute la largeur de la liste des étapes",
         "note": "Cette note est volontairement longue. Elle décrit en plusieurs phrases ce qui se passe à cette étape, pour "
                 "occuper plusieurs lignes dans le bloc du déroulé. Aucune autre étape du cas n'a une note de cette taille, "
                 "et c'est justement ce qui faisait bouger le schéma.",
         "changes": {"a": "OK", "b": {"status": "LONG", "note": "un motif assez long pour passer à la ligne dans une cellule étroite"}, "c": "KO"},
         "annotations": {"a": "terminé sans réserve"}, "global": "LONG", "at": 5},
        {"title": "Fin", "note": "Courte.", "changes": {"b": "OK"}, "global": "OK", "at": 30},
        {"title": "Rien ne change", "changes": {}, "at": 45},
    ],
    "proof": "asserted",
}


def api_call(base: str, token: str, method: str, path: str, body=None):
    request = urllib.request.Request(base + "/api/v1" + path, data=json.dumps(body).encode() if body is not None else None, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


def test_parcours_complet(site, browser):
    context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="fr-FR")
    page = context.new_page()
    problems: list[str] = []
    page.on("pageerror", lambda error: problems.append(f"erreur de script : {error}"))
    page.on("console", lambda message: problems.append(f"console : {message.text}") if message.type == "error" else None)
    page.on("response", lambda response: problems.append(f"{response.status} {response.url}") if response.status >= 500 else None)

    # ---- Accueil et connexion
    page.goto(site + "/")
    expect(page.get_by_role("heading", level=1)).to_contain_text("Demetra")
    expect(page.locator(".home-tagline")).to_contain_text("étape")
    # La démonstration : un cas qui avance seul dans le diagramme d'états ; une flèche arrête la lecture ; le schéma ne bouge pas.
    demo = page.locator(".home-demo")
    expect(demo.locator(".rep-states")).to_have_count(1)
    canvas = demo.locator(".rep-canvas").bounding_box()
    expect(demo.locator("[data-step-n]")).not_to_have_text("1", timeout=6000)
    expect(demo.locator("[data-autoplay-btn]")).to_have_attribute("aria-pressed", "true")
    page.keyboard.press("ArrowRight")
    expect(demo.locator("[data-autoplay-btn]")).to_have_attribute("aria-pressed", "false")
    held = demo.locator("[data-step-n]").inner_text()
    page.wait_for_timeout(2600)
    assert demo.locator("[data-step-n]").inner_text() == held, "après une flèche, la lecture s'arrête"
    assert demo.locator(".rep-canvas").bounding_box() == canvas, "le schéma de l'accueil ne bouge pas d'une étape à l'autre"
    shot(page, "01-accueil", full_page=True)
    page.get_by_role("link", name="Se connecter").first.click()
    page.fill("#id_login", "demo")
    page.fill("#id_password", "demetra-demo")
    shot(page, "02-connexion")
    page.click("button[type=submit]")
    page.wait_for_url("**/etudes/")
    expect(page.get_by_role("heading", level=1)).to_have_text("Études")
    expect(page.locator("a.row-link")).to_have_count(12)   # le catalogue, deux exemples, et un exemple par représentation élargie
    shot(page, "03-etudes", full_page=True)

    # ---- Revue d'un cas, au clavier
    page.get_by_role("link", name="Remboursement d'une commande").click()
    panel = page.locator("[data-panel]")
    expect(panel).to_be_visible()
    expect(page.locator(".cp-rep-head strong")).to_have_text("Table de décision")
    done_before = int(page.locator('[data-count="done"]').inner_text())

    shown = panel.get_attribute("data-key")
    page.keyboard.press("n")                               # cas suivant à analyser
    expect(panel).not_to_have_attribute("data-key", shown)
    expect(panel).to_have_attribute("data-decision", "to_analyze")
    key = panel.get_attribute("data-key")
    expect(page.locator("[data-step-n]")).to_have_text("1")
    page.keyboard.press("ArrowRight")                      # étape suivante
    expect(page.locator("[data-step-n]")).to_have_text("2")
    expect(page.locator('.stop-btn[aria-current="step"] .stop-n')).to_have_text("Étape 2")
    page.keyboard.press("ArrowLeft")
    expect(page.locator("[data-step-n]")).to_have_text("1")

    page.keyboard.press("v")                               # valider
    expect(page.locator(".vbtn-accepted")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("[data-verdict-state]")).to_have_text("Enregistré")
    item = page.locator(f'.case-item[data-key="{key}"]')
    expect(item).to_have_attribute("data-decision", "accepted")
    expect(item.locator(".vstate-label")).to_have_text("Validé")
    expect(page.locator('[data-count="done"]')).to_have_text(str(done_before + 1))
    expect(page.locator("[data-toast]")).to_be_visible()

    page.keyboard.press("z")                               # annuler
    expect(item).to_have_attribute("data-decision", "to_analyze")
    expect(page.locator('[data-count="done"]')).to_have_text(str(done_before))

    page.keyboard.press("r")                               # refuser : le commentaire prend le focus
    expect(page.locator(".vbtn-rejected")).to_have_attribute("aria-pressed", "true")
    comment = page.locator("[data-comment]")
    expect(comment).to_be_focused()
    comment.fill("Le délai se compte à partir de la réception, pas de la livraison.")
    page.keyboard.press("Control+Enter")
    expect(page.locator("[data-verdict-state]")).to_have_text("Enregistré")
    shot(page, "04-revue-table-de-decision")

    page.reload()
    panel = page.locator("[data-panel]")
    expect(panel).to_have_attribute("data-key", key)
    expect(panel).to_have_attribute("data-decision", "rejected")
    expect(page.locator("[data-comment]")).to_have_value("Le délai se compte à partir de la réception, pas de la livraison.")

    # ---- Filtres, recherche, mode focus, aide
    page.locator('[data-filter-decision="rejected"]').click()
    expect(page.locator(".case-item:visible")).to_have_count(1)
    page.locator('[data-filter-decision=""]').click()
    page.keyboard.press("/")
    expect(page.locator("[data-filter-q]")).to_be_focused()
    page.keyboard.type("premium")
    visible = page.locator(".case-item:visible").count()
    assert 0 < visible < 12
    expect(page.locator("[data-list-count]")).to_contain_text(f"{visible} cas affichés sur 12")
    page.keyboard.press("Escape")                          # Échap vide la recherche et rend la main au clavier
    expect(page.locator(".case-item:visible")).to_have_count(12)
    expect(page.locator("[data-filter-q]")).not_to_be_focused()
    page.locator("[data-sort]").select_option("todo")      # tri : ce qui reste à faire d'abord
    expect(page.locator(".case-item:visible").first).to_have_attribute("data-decision", "to_analyze")
    expect(page.locator(".fam:visible")).to_have_count(0)
    page.locator("[data-sort]").select_option("number")
    expect(page.locator(".case-item:visible").first).to_have_attribute("data-n", "0")
    page.locator("[data-detail]").click(position={"x": 400, "y": 40})
    page.keyboard.press("f")                               # mode focus : le cas seul
    expect(page.locator(".ws-list")).to_be_hidden()
    shot(page, "05-mode-focus")
    page.keyboard.press("Escape")
    expect(page.locator(".ws-list")).to_be_visible()
    page.keyboard.press("?")
    expect(page.locator("dialog[data-help-dialog]")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("dialog[data-help-dialog]")).to_be_hidden()

    # ---- Tab passe d'un cas à l'autre ; Entrée entre dans le cas, où Tab retrouve son rôle habituel
    panel = page.locator("[data-panel]")
    here = panel.get_attribute("data-key")
    page.keyboard.press("Tab")
    expect(panel).not_to_have_attribute("data-key", here)
    after = panel.get_attribute("data-key")
    expect(page.locator('.case[aria-current="true"]')).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#case-title")).to_be_focused()
    page.keyboard.press("Tab")
    expect(panel).to_have_attribute("data-key", after)     # dans le cas, Tab ne change pas de cas
    page.locator('.case[aria-current="true"]').focus()
    page.keyboard.press("Shift+Tab")
    expect(panel).to_have_attribute("data-key", here)

    # ---- Panneaux repliables : menu réduit à ses icônes, liste masquée, état mémorisé
    page.locator('[data-dock="rail"]').click()
    page.locator('.list-dock').click()
    expect(page.locator(".ws-list")).to_be_hidden()
    expect(page.locator("html")).to_have_attribute("data-rail-mini", "1")
    assert page.locator(".rail").bounding_box()["width"] < 80
    page.reload()
    expect(page.locator(".ws-list")).to_be_hidden()
    expect(page.locator("html")).to_have_attribute("data-rail-mini", "1")
    shot(page, "18-panneaux-replies")
    page.locator('.only-list-hidden[data-dock="list"]').click()
    page.locator('[data-dock="rail"]').click()
    expect(page.locator(".ws-list")).to_be_visible()
    expect(page.locator(".rail-label").first).to_be_visible()

    # ---- Changement de représentation
    page.locator(".cp-rep-head a").click()
    page.wait_for_url("**/representation/**")
    expect(page.get_by_role("heading", name="Recommandées par Demetra")).to_be_visible()
    shot(page, "06-representations", full_page=True)
    card = page.locator(".rep-card", has=page.get_by_role("heading", name="Table de trace"))
    card.get_by_role("button", name="Utiliser pour moi").click()
    expect(page.locator(".flash")).to_contain_text("Table de trace")
    page.get_by_role("link", name="Cas", exact=True).click()
    expect(page.locator(".cp-rep-head strong")).to_have_text("Table de trace")
    expect(page.locator("[data-panel] .rep-grid").first).to_be_visible()
    page.keyboard.press("ArrowRight")
    expect(page.locator("[data-panel] .rep-grid thead .col-step.is-current")).to_have_text("2")
    shot(page, "07-revue-table-de-trace")

    # ---- Partage
    page.get_by_role("link", name="Partage", exact=True).click()
    page.fill("#share-user", "marc")
    page.locator('input[name="role"][value="viewer"]').check()
    page.get_by_role("button", name="Partager").click()
    expect(page.locator(".flash")).to_contain_text("marc")
    expect(page.locator("table.data tbody tr", has_text="marc")).to_have_count(1)
    shot(page, "08-partage")

    other = browser.new_context(viewport={"width": 1440, "height": 900}, locale="fr-FR")
    marc = other.new_page()
    login(marc, site, "marc")
    expect(marc.locator("a.row-link")).to_have_count(1)
    marc.get_by_role("link", name="Remboursement d'une commande").click()
    expect(marc.locator("[data-panel]")).to_be_visible()
    expect(marc.locator(".vbtn")).to_have_count(0)          # lecteur : pas d'avis
    expect(marc.locator(".cp-rep-head strong")).to_have_text("Table de décision")  # le choix de demo est personnel
    other.close()

    # ---- Jeton créé dans l'interface, puis mise à jour en direct par l'API
    page.goto(site + "/compte/jetons/")
    page.fill("#tk-name", "Essai de bout en bout")
    page.get_by_role("button", name="Créer le jeton").click()
    token = page.locator('[data-testid="new-token"]').inner_text().strip()
    assert token.startswith("dmt_")
    shot(page, "09-jeton-cree", full_page=True)

    page.goto(site + "/etudes/")
    page.get_by_role("link", name="Remboursement d'une commande").click()
    expect(page.locator("[data-panel]")).to_be_visible()
    sid = page.locator("[data-workspace]").get_attribute("data-sid")
    expect(page.locator("[data-live]")).to_be_hidden()
    new_case = api_call(site, token, "GET", f"/studies/{sid}/cases/{key}")["case"]   # un cas lu se redépose tel quel
    new_case.update(key="ajoute-par-l-ia", title="Cas ajouté par l'IA pendant la revue", number=None)
    report = api_call(site, token, "POST", f"/studies/{sid}/cases/batch", {"cases": [new_case]})
    assert report["counts"] == {"created": 1}, report
    expect(page.locator("[data-live]")).to_be_visible(timeout=8000)
    expect(page.locator("[data-live-text]")).to_contain_text("1 cas ajouté")
    shot(page, "10-mise-a-jour-en-direct")
    page.locator("[data-live-reload]").click()
    expect(page.locator('.case-item[data-key="ajoute-par-l-ia"]')).to_have_count(1)
    expect(page.locator('.progress [data-count="total"]')).to_have_text("13")

    # ---- Couverture, historique, thème sombre
    page.get_by_role("link", name="Couverture", exact=True).click()
    expect(page.get_by_role("heading", name="Combinaisons manquantes")).to_be_visible()
    shot(page, "11-couverture", full_page=True)
    page.get_by_role("link", name="Historique", exact=True).click()
    expect(page.locator("table.data")).to_contain_text("Essai de bout en bout")
    shot(page, "12-historique", full_page=True)
    page.locator("[data-theme-toggle]").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.get_by_role("link", name="Cas", exact=True).click()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    shot(page, "13-revue-sombre")
    page.locator("[data-theme-toggle]").click()

    # ---- Les deux autres études : graphe en couches et frise temporelle
    page.goto(site + "/etudes/")
    page.get_by_role("link", name="Catalogue des runs Lancelot").click()
    expect(page.locator(".cp-rep-head strong")).to_have_text("Graphe en couches à statuts")
    expect(page.locator('.progress [data-count="total"]')).to_have_text("136")
    page.keyboard.press("j")
    page.keyboard.press("ArrowRight")
    expect(page.locator("[data-step-n]")).to_have_text("2")
    shot(page, "14-revue-graphe")
    page.goto(site + "/etudes/")
    page.get_by_role("link", name="Relances d'une facture impayée").click()
    expect(page.locator(".cp-rep-head strong")).to_have_text("Frise temporelle")
    expect(page.locator("[data-panel] svg.rep-timeline")).to_be_visible()
    shot(page, "15-revue-frise")

    # ---- Le schéma ne bouge pas d'une étape à l'autre, quel que soit le cas : étude déposée par l'API avec des
    #      étapes volontairement inégales (notes et libellés très courts ou très longs), dans chaque représentation.
    made = api_call(site, token, "POST", "/studies", STABLE_STUDY)
    report = api_call(site, token, "POST", f"/studies/{made['id']}/cases/batch", {"cases": [STABLE_CASE]})
    assert report["counts"] == {"created": 1}, report
    measure = """() => {
      const rep = document.querySelector('.cp-rep'), steps = document.querySelector('.steps'), detail = document.querySelector('[data-detail]');
      return [Math.round(rep.getBoundingClientRect().top + detail.scrollTop), Math.round(steps.getBoundingClientRect().height), Math.round(rep.getBoundingClientRect().height)];
    }"""
    checked = 0
    for name in ("Graphe en couches à statuts", "Table de décision", "Frise temporelle", "Table de trace"):
        page.goto(f"{site}/etudes/{made['id']}/representation/")
        card = page.locator(".rep-card", has=page.get_by_role("heading", name=name, exact=True))
        if card.get_by_role("button", name="Utiliser pour moi").count():
            card.get_by_role("button", name="Utiliser pour moi").click()
            expect(page.locator(".flash")).to_contain_text(name)
        for width in (1440, 1000):
            page.set_viewport_size({"width": width, "height": 900})
            page.goto(f"{site}/etudes/{made['id']}/?cas=inegal")
            expect(page.locator(".cp-rep-head strong")).to_have_text(name)
            seen = [page.evaluate(measure)]
            for _ in range(len(STABLE_CASE["steps"]) - 1):
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(250)
                seen.append(page.evaluate(measure))
            assert all(item == seen[0] for item in seen), f"{name} à {width}px : le schéma bouge entre les étapes {seen}"
            checked += 1
    assert checked == 8
    page.set_viewport_size({"width": 1440, "height": 900})

    # ---- Petit écran
    phone = browser.new_context(viewport={"width": 390, "height": 844}, locale="fr-FR", storage_state=context.storage_state(), is_mobile=True, has_touch=True)
    small = phone.new_page()
    small.goto(site + "/etudes/")
    small.get_by_role("link", name="Catalogue des runs Lancelot").tap()
    expect(small.locator(".case-item").first).to_be_visible()
    shot(small, "16-mobile-liste")
    small.locator(".case-item a.case").nth(2).tap()
    expect(small.locator("[data-panel]")).to_be_visible()
    expect(small.locator(".vbtn-accepted")).to_be_visible()
    width = small.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    assert width[0] <= width[1], f"défilement horizontal de la page sur petit écran : {width}"
    shot(small, "17-mobile-cas")
    phone.close()

    context.close()
    assert not problems, problems


# Une étude de démonstration par représentation du catalogue élargi : (nom affiché, titre de l'étude, capture, cas montré sur la capture, étape)
EXTENDED = [
    ("Matrice croisée", "Droits d'accès aux documents", "19-matrice-croisee", 4, 2),
    ("Calcul pas à pas", "Prix à payer d'une commande", "20-calcul-pas-a-pas", 2, 3),
    ("Axe à bandes", "Validation d'une note de frais", "21-axe-a-bandes", 2, 1),
    ("Avant / après", "Changement d'adresse d'un assuré", "22-avant-apres", 1, 2),
    ("Table de règles", "Priorité d'un ticket de support", "23-table-de-regles", 3, 1),
    ("Arbre de décision", "Mode de livraison proposé", "24-arbre-de-decision", 2, 2),
    ("Table d'états", "Validation d'un document", "25-table-d-etats", 1, 3),
    ("Diagramme d'états", "Cycle de vie d'une commande en ligne", "26-diagramme-d-etats", 1, 3),
    ("Diagramme de séquence", "Paiement par carte d'une commande", "27-diagramme-de-sequence", 2, 3),
]

# Place et taille du schéma, de ce qui le précède, et de son contenu défilant : rien de tout cela ne doit changer d'une étape à l'autre.
MEASURE = """() => {
  const rep = document.querySelector('.cp-rep'), steps = document.querySelector('.steps'), detail = document.querySelector('[data-detail]');
  const inner = rep.querySelector('.rep'), box = inner.getBoundingClientRect(), scroll = rep.querySelector('.rep-scroll');
  return [Math.round(rep.getBoundingClientRect().top + detail.scrollTop), Math.round(steps.getBoundingClientRect().height),
          Math.round(rep.getBoundingClientRect().height), Math.round(box.width), Math.round(box.height),
          scroll ? scroll.scrollWidth : 0, scroll ? scroll.scrollHeight : 0];
}"""


def test_representations_elargies(site, browser):
    """Les neuf représentations du catalogue élargi, chacune sur son étude de démonstration : affichage stable d'une
    étape à l'autre, thèmes clair et sombre, largeur mobile, choix à trois niveaux dans l'interface."""
    context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="fr-FR")
    page = context.new_page()
    problems: list[str] = []
    page.on("pageerror", lambda error: problems.append(f"erreur de script : {error}"))
    page.on("console", lambda message: problems.append(f"console : {message.text}") if message.type == "error" else None)
    page.on("response", lambda response: problems.append(f"{response.status} {response.url}") if response.status >= 500 else None)
    login(page, site, "demo")

    checked = 0
    for name, title, capture, shown_case, shown_step in EXTENDED:
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(site + "/etudes/")
        page.get_by_role("link", name=title).click()
        expect(page.locator(".cp-rep-head strong")).to_have_text(name)       # l'étude porte la représentation qu'elle illustre
        expect(page.locator(".study-head .chip").first).to_contain_text("Exemple")
        sid = page.locator("[data-workspace]").get_attribute("data-sid")
        keys = page.locator(".case-item").evaluate_all("items => items.map(item => item.dataset.key)")
        assert len(keys) >= 3
        for width in (1440, 1000):
            page.set_viewport_size({"width": width, "height": 900})
            for key in keys:
                page.goto(f"{site}/etudes/{sid}/?cas={key}")
                expect(page.locator("[data-panel]")).to_have_attribute("data-key", key)
                expect(page.locator("[data-panel] .rep-empty")).to_have_count(0)
                steps = page.locator(".stop-btn").count()
                seen = [page.evaluate(MEASURE)]
                for _ in range(steps - 1):
                    page.keyboard.press("ArrowRight")
                    page.wait_for_timeout(220)
                    seen.append(page.evaluate(MEASURE))
                expect(page.locator("[data-step-n]")).to_have_text(str(steps))
                assert all(item == seen[0] for item in seen), f"{name}, cas {key}, {width}px : le schéma bouge entre les étapes {seen}"
                checked += 1
        # Capture : un cas parlant, à une étape du milieu, en clair ; puis le même en sombre.
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(f"{site}/etudes/{sid}/?cas={keys[min(shown_case, len(keys) - 1)]}")
        for _ in range(shown_step):
            page.keyboard.press("ArrowRight")
        expect(page.locator("[data-panel] .rep").first).to_be_visible()
        shot(page, capture)
        page.locator("[data-theme-toggle]").click()
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")
        ink = page.evaluate("getComputedStyle(document.querySelector('[data-panel] .rep')).color")
        ground = page.evaluate("getComputedStyle(document.body).backgroundColor")
        assert ink != ground
        if capture.startswith(("26", "27")):
            shot(page, capture + "-sombre")
        page.locator("[data-theme-toggle]").click()
        expect(page.locator("html")).not_to_have_attribute("data-theme", "dark")
    assert checked >= 2 * 3 * len(EXTENDED)

    # ---- Une étude = une représentation ; on en change pour soi, pour un cas, ou pour toute l'étude
    page.goto(site + "/etudes/")
    page.get_by_role("link", name="Validation d'un document").click()
    expect(page.locator(".cp-rep-head strong")).to_have_text("Table d'états")
    first = page.locator("[data-panel]").get_attribute("data-key")
    page.locator(".cp-rep-head a").click()
    page.wait_for_url("**/representation/**")
    expect(page.locator(".rep-current")).to_contain_text("Une étude a une représentation")
    card = page.locator(".rep-card", has=page.get_by_role("heading", name="Diagramme d'états"))
    expect(card.get_by_role("button", name="Utiliser pour moi")).to_be_visible()
    expect(card.get_by_role("button", name="Utiliser pour toute l'étude")).to_be_visible()
    shot(page, "28-choix-a-trois-niveaux", full_page=True)
    card.get_by_role("button", name="seulement").click()                    # pour ce cas seulement
    page.wait_for_url(f"**/?cas={first}")
    expect(page.locator(".cp-rep-head strong")).to_have_text("Diagramme d'états")
    expect(page.locator(".cp-rep-head .chip")).to_have_text("pour ce cas")
    page.keyboard.press("j")                                                # le cas suivant garde la représentation de l'étude
    expect(page.locator("[data-panel]")).not_to_have_attribute("data-key", first)
    expect(page.locator(".cp-rep-head strong")).to_have_text("Table d'états")
    expect(page.locator(".cp-rep-head .chip")).to_have_count(0)
    page.keyboard.press("k")
    expect(page.locator(".cp-rep-head strong")).to_have_text("Diagramme d'états")
    page.get_by_role("button", name="Suivre l'étude").click()
    expect(page.locator(".cp-rep-head strong")).to_have_text("Table d'états")

    # ---- Page Briques : les neuf exemples s'affichent et se parcourent
    page.goto(site + "/briques/")
    expect(page.locator(".samples-wide .sample")).to_have_count(9)
    sample = page.locator("#exemple-diagramme-sequence")
    before = sample.locator("[data-step-n]").inner_text()
    sample.locator("[data-step-next]").click()
    expect(sample.locator("[data-step-n]")).not_to_have_text(before)
    shot(page, "29-briques-regles-et-processus", full_page=True)

    # ---- Petit écran : la page ne défile pas en largeur ; le schéma défile dans son cadre
    phone = browser.new_context(viewport={"width": 390, "height": 844}, locale="fr-FR", storage_state=context.storage_state(), is_mobile=True, has_touch=True)
    small = phone.new_page()
    small.on("pageerror", lambda error: problems.append(f"erreur de script (mobile) : {error}"))
    for name, title, capture, shown_case, _ in EXTENDED:
        small.goto(site + "/etudes/")
        small.get_by_role("link", name=title).tap()
        small.locator(".case-item a.case").nth(min(shown_case, 2)).tap()
        expect(small.locator("[data-panel]")).to_be_visible()
        expect(small.locator(".cp-rep-head strong")).to_have_text(name)
        expect(small.locator(".vbtn-accepted")).to_be_visible()
        width = small.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        assert width[0] <= width[1], f"{name} : défilement horizontal de la page sur petit écran : {width}"
        box = small.evaluate("(() => { const r = document.querySelector('[data-panel] .rep').getBoundingClientRect(); return [r.width, r.height]; })()")
        assert box[0] > 200 and box[1] > 60, f"{name} : schéma illisible sur petit écran {box}"
    small.locator("[data-panel] .cp-rep").scroll_into_view_if_needed()
    shot(small, "30-mobile-diagramme-de-sequence")
    phone.close()

    context.close()
    assert not problems, problems
