"""Parcours de bout en bout dans un vrai navigateur (Chromium piloté par Playwright).

Le test lance le site dans un processus à part, sur une base temporaire remplie par `seed_demo`,
puis joue : connexion, revue d'un cas au clavier, changement de représentation, partage, et mise à
jour en direct quand l'API modifie l'étude ouverte.

Captures d'écran : définir DEMETRA_CAPTURES=<dossier> pour les enregistrer.
"""

from __future__ import annotations

import json
import os
import re
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


SITE_ENV: dict[str, str] = {}  # l'environnement du site servi : pour y préparer une étude d'essai


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """Le site, servi par `manage.py runserver` sur une base temporaire de démonstration."""
    database = tmp_path_factory.mktemp("demetra") / "e2e.sqlite3"
    env = {**os.environ, "DEMETRA_DB": str(database), "DEMETRA_SSE_MAX_SECONDS": "20"}
    SITE_ENV.update(env)
    manage = [sys.executable, str(ROOT / "manage.py")]
    subprocess.run([*manage, "migrate", "-v0"], cwd=ROOT, env=env, check=True)
    subprocess.run([*manage, "seed_demo"], cwd=ROOT, env=env, check=True, capture_output=True)
    port = _free_port()
    server = subprocess.Popen(
        [*manage, "runserver", f"127.0.0.1:{port}", "--noreload"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
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
        page.wait_for_timeout(350)  # laisse les transitions d'état se terminer
        page.screenshot(path=str(Path(CAPTURES) / f"{name}.png"), full_page=full_page)


def login(page, base: str, username: str):
    page.goto(base + "/comptes/login/")
    page.fill("#id_login", username)
    page.fill("#id_password", "demetra-demo")
    page.click("button[type=submit]")
    page.wait_for_url("**/etudes/")


# Une étude et un cas aux étapes volontairement inégales : note absente, courte ou très longue ; un ou
# plusieurs
# changements ; libellés de statut très courts ou très longs. Sert à vérifier que l'affichage ne bouge pas.
STABLE_STUDY = {
    "title": "Stabilité de l'affichage",
    "kind": "workflow",
    "statuses": [
        {"key": "ATT", "label": "À venir", "role": "waiting", "default": True},
        {"key": "OK", "label": "Fait", "role": "success"},
        {
            "key": "LONG",
            "label": "En cours de vérification approfondie par le service",
            "short": "Vérification",
            "role": "active",
        },
        {"key": "KO", "label": "Refusé après contrôle", "role": "error"},
    ],
}
STABLE_CASE = {
    "key": "inegal",
    "number": 1,
    "family": "Affichage",
    "title": "Des étapes très inégales",
    "kind": "workflow",
    "entities": [
        {"id": "a", "label": "Premier contrôle", "type": "task"},
        {
            "id": "b",
            "label": "Second contrôle, au libellé nettement plus long que les autres",
            "type": "task",
        },
        {"id": "c", "label": "Clôture", "type": "task"},
    ],
    "links": [{"from": "a", "to": "b", "type": "depends"}, {"from": "b", "to": "c", "type": "depends"}],
    "steps": [
        {"title": "Départ", "changes": {"a": "LONG"}, "at": 0},
        {
            "title": "Une étape au titre long, qui occupe presque toute la largeur de la liste des étapes",
            "note": "Cette note est volontairement longue. Elle décrit en plusieurs phrases ce qui se passe "
            "à cette étape, pour "
            "occuper plusieurs lignes dans le bloc du déroulé. Aucune autre étape du cas n'a une note de "
            "cette taille, "
            "et c'est justement ce qui faisait bouger le schéma.",
            "changes": {
                "a": "OK",
                "b": {
                    "status": "LONG",
                    "note": "un motif assez long pour passer à la ligne dans une cellule étroite",
                },
                "c": "KO",
            },
            "annotations": {"a": "terminé sans réserve"},
            "global": "LONG",
            "at": 5,
        },
        {"title": "Fin", "note": "Courte.", "changes": {"b": "OK"}, "global": "OK", "at": 30},
        {"title": "Rien ne change", "changes": {}, "at": 45},
    ],
    "proof": "asserted",
}


def api_call(base: str, token: str, method: str, path: str, body=None):
    request = urllib.request.Request(
        base + "/api/v1" + path, data=json.dumps(body).encode() if body is not None else None, method=method
    )
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


def test_parcours_complet(site, browser):
    context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="fr-FR")
    page = context.new_page()
    problems: list[str] = []
    page.on("pageerror", lambda error: problems.append(f"erreur de script : {error}"))
    page.on(
        "console",
        lambda message: problems.append(f"console : {message.text}") if message.type == "error" else None,
    )
    page.on(
        "response",
        lambda response: (
            problems.append(f"{response.status} {response.url}") if response.status >= 500 else None
        ),
    )

    # ---- Accueil et connexion
    page.goto(site + "/")
    expect(page.get_by_role("heading", level=1)).to_contain_text("Demetra")
    expect(page.locator(".home-tagline")).to_contain_text("étape")
    # La démonstration : un cas qui avance seul dans le diagramme d'états ; une flèche arrête la lecture ; le
    # schéma ne bouge pas.
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
    assert demo.locator(".rep-canvas").bounding_box() == canvas, (
        "le schéma de l'accueil ne bouge pas d'une étape à l'autre"
    )
    shot(page, "01-accueil", full_page=True)
    page.get_by_role("link", name="Se connecter").first.click()
    page.fill("#id_login", "demo")
    page.fill("#id_password", "demetra-demo")
    shot(page, "02-connexion")
    page.click("button[type=submit]")
    page.wait_for_url("**/etudes/")
    expect(page.get_by_role("heading", level=1)).to_have_text("Études")
    # Le catalogue, cinq exemples (décision, temps, cas paramétrés, deux ateliers), un exemple par
    # représentation élargie.
    expect(page.locator("a.row-link")).to_have_count(15)
    shot(page, "03-etudes", full_page=True)

    # ---- Revue d'un cas, au clavier
    page.get_by_role("link", name="Remboursement d'une commande").click()
    panel = page.locator("[data-panel]")
    expect(panel).to_be_visible()
    expect(page.locator(".cp-rep-head strong")).to_have_text("Table de décision")
    done_before = int(page.locator('[data-count="done"]').inner_text())

    shown = panel.get_attribute("data-key")
    page.keyboard.press("n")  # cas suivant à analyser
    expect(panel).not_to_have_attribute("data-key", shown)
    expect(panel).to_have_attribute("data-decision", "to_analyze")
    key = panel.get_attribute("data-key")
    expect(page.locator("[data-step-n]")).to_have_text("1")
    page.keyboard.press("ArrowRight")  # étape suivante
    expect(page.locator("[data-step-n]")).to_have_text("2")
    expect(page.locator('.stop-btn[aria-current="step"] .stop-n')).to_have_text("Étape 2")
    page.keyboard.press("ArrowLeft")
    expect(page.locator("[data-step-n]")).to_have_text("1")

    page.keyboard.press("v")  # valider
    expect(page.locator(".vbtn-accepted")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("[data-verdict-state]")).to_have_text("Enregistré")
    item = page.locator(f'.case-item[data-key="{key}"]')
    expect(item).to_have_attribute("data-decision", "accepted")
    expect(item.locator(".vstate-label")).to_have_text("Validé")
    expect(page.locator('[data-count="done"]')).to_have_text(str(done_before + 1))
    expect(page.locator("[data-toast]")).to_be_visible()

    page.keyboard.press("z")  # annuler
    expect(item).to_have_attribute("data-decision", "to_analyze")
    expect(page.locator('[data-count="done"]')).to_have_text(str(done_before))

    page.keyboard.press("r")  # refuser : le commentaire prend le focus
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
    expect(page.locator("[data-comment]")).to_have_value(
        "Le délai se compte à partir de la réception, pas de la livraison."
    )

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
    page.keyboard.press("Escape")  # Échap vide la recherche et rend la main au clavier
    expect(page.locator(".case-item:visible")).to_have_count(12)
    expect(page.locator("[data-filter-q]")).not_to_be_focused()
    page.locator("[data-sort]").select_option("todo")  # tri : ce qui reste à faire d'abord
    expect(page.locator(".case-item:visible").first).to_have_attribute("data-decision", "to_analyze")
    expect(page.locator(".fam:visible")).to_have_count(0)
    page.locator("[data-sort]").select_option("number")
    expect(page.locator(".case-item:visible").first).to_have_attribute("data-n", "0")
    page.locator("[data-detail]").click(position={"x": 400, "y": 40})
    page.keyboard.press("f")  # mode focus : le cas seul
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
    expect(panel).to_have_attribute("data-key", after)  # dans le cas, Tab ne change pas de cas
    page.locator('.case[aria-current="true"]').focus()
    page.keyboard.press("Shift+Tab")
    expect(panel).to_have_attribute("data-key", here)

    # ---- Panneaux repliables : menu réduit à ses icônes, liste masquée, état mémorisé
    page.locator('[data-dock="rail"]').click()
    page.locator(".list-dock").click()
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
    expect(marc.locator(".vbtn")).to_have_count(0)  # lecteur : pas d'avis
    expect(marc.locator(".cp-rep-head strong")).to_have_text(
        "Table de décision"
    )  # le choix de demo est personnel
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
    new_case = api_call(site, token, "GET", f"/studies/{sid}/cases/{key}")[
        "case"
    ]  # un cas lu se redépose tel quel
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

    # ---- Le schéma ne bouge pas d'une étape à l'autre, quel que soit le cas : étude déposée par l'API avec
    # des
    # étapes volontairement inégales (notes et libellés très courts ou très longs), dans chaque
    # représentation.
    made = api_call(site, token, "POST", "/studies", STABLE_STUDY)
    report = api_call(site, token, "POST", f"/studies/{made['id']}/cases/batch", {"cases": [STABLE_CASE]})
    assert report["counts"] == {"created": 1}, report
    measure = """() => {
      const rep = document.querySelector('.cp-rep'), steps = document.querySelector('.steps');
      const detail = document.querySelector('[data-detail]');
      return [Math.round(rep.getBoundingClientRect().top + detail.scrollTop),
              Math.round(steps.getBoundingClientRect().height),
              Math.round(rep.getBoundingClientRect().height)];
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
            assert all(item == seen[0] for item in seen), (
                f"{name} à {width}px : le schéma bouge entre les étapes {seen}"
            )
            checked += 1
    assert checked == 8
    page.set_viewport_size({"width": 1440, "height": 900})

    # ---- Petit écran
    phone = browser.new_context(
        viewport={"width": 390, "height": 844},
        locale="fr-FR",
        storage_state=context.storage_state(),
        is_mobile=True,
        has_touch=True,
    )
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


# Une étude de démonstration par représentation du catalogue élargi : (nom affiché, titre de l'étude, capture,
# cas montré sur la capture, étape)
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

# Place et taille du schéma, de ce qui le précède, et de son contenu défilant : rien de tout cela ne doit
# changer d'une étape à l'autre.
MEASURE = """() => {
  const rep = document.querySelector('.cp-rep'), steps = document.querySelector('.steps');
  const detail = document.querySelector('[data-detail]');
  const inner = rep.querySelector('.rep'), box = inner.getBoundingClientRect();
  const scroll = rep.querySelector('.rep-scroll');
  return [Math.round(rep.getBoundingClientRect().top + detail.scrollTop),
          Math.round(steps.getBoundingClientRect().height),
          Math.round(rep.getBoundingClientRect().height), Math.round(box.width), Math.round(box.height),
          scroll ? scroll.scrollWidth : 0, scroll ? scroll.scrollHeight : 0];
}"""


def test_representations_elargies(site, browser):
    """Les neuf représentations du catalogue élargi, chacune sur son étude de démonstration : affichage stable
    d'une
    étape à l'autre, thèmes clair et sombre, largeur mobile, choix à trois niveaux dans l'interface."""
    context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="fr-FR")
    page = context.new_page()
    problems: list[str] = []
    page.on("pageerror", lambda error: problems.append(f"erreur de script : {error}"))
    page.on(
        "console",
        lambda message: problems.append(f"console : {message.text}") if message.type == "error" else None,
    )
    page.on(
        "response",
        lambda response: (
            problems.append(f"{response.status} {response.url}") if response.status >= 500 else None
        ),
    )
    login(page, site, "demo")

    checked = 0
    for name, title, capture, shown_case, shown_step in EXTENDED:
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(site + "/etudes/")
        page.get_by_role("link", name=title, exact=True).click()
        expect(page.locator(".cp-rep-head strong")).to_have_text(
            name
        )  # l'étude porte la représentation qu'elle illustre
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
                assert all(item == seen[0] for item in seen), (
                    f"{name}, cas {key}, {width}px : le schéma bouge entre les étapes {seen}"
                )
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
    page.get_by_role("link", name="Validation d'un document", exact=True).click()
    expect(page.locator(".cp-rep-head strong")).to_have_text("Table d'états")
    first = page.locator("[data-panel]").get_attribute("data-key")
    page.locator(".cp-rep-head a").click()
    page.wait_for_url("**/representation/**")
    expect(page.locator(".rep-current")).to_contain_text("Une étude a une représentation")
    card = page.locator(".rep-card", has=page.get_by_role("heading", name="Diagramme d'états"))
    expect(card.get_by_role("button", name="Utiliser pour moi")).to_be_visible()
    expect(card.get_by_role("button", name="Utiliser pour toute l'étude")).to_be_visible()
    shot(page, "28-choix-a-trois-niveaux", full_page=True)
    card.get_by_role("button", name="seulement").click()  # pour ce cas seulement
    page.wait_for_url(f"**/?cas={first}")
    expect(page.locator(".cp-rep-head strong")).to_have_text("Diagramme d'états")
    expect(page.locator(".cp-rep-head .chip")).to_have_text("pour ce cas")
    page.keyboard.press("j")  # le cas suivant garde la représentation de l'étude
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
    phone = browser.new_context(
        viewport={"width": 390, "height": 844},
        locale="fr-FR",
        storage_state=context.storage_state(),
        is_mobile=True,
        has_touch=True,
    )
    small = phone.new_page()
    small.on("pageerror", lambda error: problems.append(f"erreur de script (mobile) : {error}"))
    for name, title, capture, shown_case, _ in EXTENDED:
        small.goto(site + "/etudes/")
        small.get_by_role("link", name=title, exact=True).tap()
        small.locator(".case-item a.case").nth(min(shown_case, 2)).tap()
        expect(small.locator("[data-panel]")).to_be_visible()
        expect(small.locator(".cp-rep-head strong")).to_have_text(name)
        expect(small.locator(".vbtn-accepted")).to_be_visible()
        width = small.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        assert width[0] <= width[1], f"{name} : défilement horizontal de la page sur petit écran : {width}"
        box = small.evaluate(
            "(() => { const r = document.querySelector('[data-panel] .rep').getBoundingClientRect(); return "
            "[r.width, r.height]; })()"
        )
        assert box[0] > 200 and box[1] > 60, f"{name} : schéma illisible sur petit écran {box}"
    small.locator("[data-panel] .cp-rep").scroll_into_view_if_needed()
    shot(small, "30-mobile-diagramme-de-sequence")
    phone.close()

    context.close()
    assert not problems, problems


def test_atelier(site, browser):
    """L'onglet « Atelier » : on part d'une page vide, on pose trois Tasks, on les relie, on change une
    option, on provoque un échec, on déroule, et on lit l'état final de chaque Task. Aucun cas déposé
    n'apparaît. Le résultat se redessine sur place, le schéma ne bouge pas d'un pas à l'autre. Une seconde
    étude sans rapport a son atelier par ses seules déclarations ; une étude sans règles le dit. En clair, en
    sombre et sur mobile."""
    context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="fr-FR")
    page = context.new_page()
    problems: list[str] = []
    page.on("pageerror", lambda error: problems.append(f"erreur de script : {error}"))
    page.on(
        "console",
        lambda message: problems.append(f"console : {message.text}") if message.type == "error" else None,
    )
    login(page, site, "demo")
    page.get_by_role("link", name="Catalogue des runs Lancelot").click()
    page.get_by_role("link", name="Atelier", exact=True).click()

    # Page vide : la palette de l'étude, ses règles, aucune brique, aucun cas déposé.
    expect(page.locator(".at-empty h2")).to_have_text("Composer un Workflow")
    expect(page.locator(".at-card")).to_have_count(0)
    expect(page.locator(".at-rules li")).to_have_count(11)
    assert page.locator(".case-item, .case, [data-case]").count() == 0
    assert "Une seule Task" not in page.locator("main").inner_text()  # titre du premier cas du catalogue
    shot(page, "40-atelier-vide", full_page=True)

    # Poser trois Tasks : le fragment est remplacé sans recharger la page.
    page.evaluate("window.__meme_page = true")
    for count in (1, 2, 3):
        page.get_by_role("button", name="Task", exact=True).click()
        expect(page.locator(".at-card")).to_have_count(count)
    assert page.evaluate("window.__meme_page") is True
    assert page.evaluate("document.activeElement.name") == "add"

    # Les relier : B et C dépendent de A.
    page.select_option("#at-link-B", "in:prerequisite:A")
    expect(page.locator('[data-brick="B"] .at-links li')).to_have_text("dépend de Task A")
    page.select_option("#at-link-C", "in:prerequisite:A")
    expect(page.locator('[data-brick="A"] .at-links li')).to_have_count(2)
    for key in "ABC":
        expect(page.locator(f'[data-brick="{key}"] [data-final]')).to_have_attribute(
            "data-final", "FINISHED_OK"
        )
    expect(page.locator("[data-result]")).to_contain_text("Workflow FINISHED_OK")

    # Changer une option, puis provoquer un échec : le résultat se redessine à chaque changement.
    page.check('input[name="o.C.always_run"]')
    expect(page).to_have_url(re.compile(r"o\.C\.always_run=true"))
    page.check('input[name="ev"][value="A:echec"]')
    expect(page.locator("[data-result]")).to_contain_text("Workflow FINISHED_KO")
    final = {"A": "FINISHED_KO", "B": "BLOCKED", "C": "FINISHED_OK"}
    for key, status in final.items():
        expect(page.locator(f'[data-brick="{key}"] [data-final]')).to_have_attribute("data-final", status)
    # Tout l'état tient dans l'adresse, sans trace du geste qui y a mené.
    query = page.url.split("?", 1)[1]
    assert query == (
        "e=A%3Atask&e=B%3Atask&e=C%3Atask&o.C.always_run=true&ev=A%3Aechec"
        "&l=A%3Aprerequisite%3AB&l=A%3Aprerequisite%3AC"
    )
    shot(page, "41-atelier-construit", full_page=True)

    # Dérouler pas à pas : du départ à la fin, le schéma garde ses dimensions.
    page.locator('a[data-at-step="first"]').click()
    expect(page.locator(".at-walk .stop-btn[aria-current=step]")).to_have_attribute("data-step", "0")
    expect(page.locator(".at-walk .step-pane.is-current")).to_contain_text(
        "Aucune règle n'a encore été appliquée"
    )
    box = page.locator(".at-walk [data-rep]").first.bounding_box()
    page.locator('a[data-at-step="next"]').click()
    expect(page.locator(".at-walk .stop-btn[aria-current=step]")).to_have_attribute("data-step", "1")
    expect(page).to_have_url(re.compile(r"etape=2"))
    after = page.locator(".at-walk [data-rep]").first.bounding_box()
    assert (box["width"], box["height"]) == (after["width"], after["height"])
    page.get_by_role("button", name="Dérouler").click()
    expect(page.locator(".at-walk .stop-btn[aria-current=step]")).to_have_attribute(
        "data-step", "5", timeout=9000
    )
    expect(page.get_by_role("button", name="Dérouler")).to_be_visible()

    # La même adresse, ouverte sans script, donne la même situation et le même résultat.
    plain = browser.new_context(
        java_script_enabled=False, storage_state=context.storage_state(), locale="fr-FR"
    )
    static = plain.new_page()
    static.goto(page.url.split("&etape")[0])
    for key, status in final.items():
        expect(static.locator(f'[data-brick="{key}"] [data-final]')).to_have_attribute("data-final", status)
    static.locator('button[name="del"][value="B"]').click()
    expect(static.locator(".at-card")).to_have_count(2)
    assert "B%3Atask" not in static.url and "del=" not in static.url
    plain.close()

    # Enregistrer la situation comme cas : un geste humain, le cas attend un avis.
    page.fill("#at-title", "A échoue, C nettoie")
    page.get_by_role("button", name="Enregistrer comme cas").click()
    expect(page).to_have_url(re.compile(r"cas=atelier-1"))
    expect(page.locator(".cp-title, [data-panel] h2").first).to_contain_text("A échoue, C nettoie")

    # Une seconde étude, sans rapport avec un workflow de tâches : ses seules déclarations font son atelier.
    page.goto(f"{site}/etudes/")
    page.get_by_role("link", name="Circuit de validation d'un document").click()
    page.get_by_role("link", name="Atelier", exact=True).click()
    expect(page.locator(".at-add")).to_have_text(["Relecture", "Signature", "Publication"])
    page.get_by_role("button", name="Relecture", exact=True).click()
    expect(page.locator(".at-card")).to_have_count(1)
    page.get_by_role("button", name="Publication", exact=True).click()
    expect(page.locator(".at-card")).to_have_count(2)
    page.select_option("#at-link-B", "in:puis:A")
    expect(page.locator("[data-result]")).to_contain_text("Document publié")
    page.check('input[name="ev"][value="A:refus"]')
    expect(page.locator("[data-result]")).to_contain_text("Document refusé")
    expect(page.locator('[data-brick="B"] [data-final]')).to_have_attribute("data-final", "ABANDONNE")
    page.select_option('select[name="r.procedure"]', "urgente")
    expect(page).to_have_url(re.compile(r"r\.procedure=urgente"))
    shot(page, "42-atelier-autre-etude", full_page=True)

    # Une étude qui ne déclare pas de règles n'a pas d'atelier : l'écran le dit et renvoie vers ses cas.
    page.goto(f"{site}/etudes/")
    page.get_by_role("link", name="Remboursement d'une commande").click()
    page.get_by_role("link", name="Atelier", exact=True).click()
    expect(page.locator(".empty h2")).to_contain_text("ne déclare pas de règles")
    expect(page.get_by_role("link", name="Voir les cas de l'étude")).to_be_visible()

    # Thème sombre et largeur mobile : rien ne déborde.
    page.goto(f"{site}/etudes/")
    page.get_by_role("link", name="Catalogue des runs Lancelot").click()
    page.get_by_role("link", name="Atelier", exact=True).click()
    page.goto(page.url + "?" + query)
    page.evaluate("localStorage.setItem('demetra-theme', 'dark')")
    for width, height in ((1280, 900), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        page.reload()
        expect(page.locator(".at-card")).to_have_count(3)
        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    shot(page, "43-atelier-mobile-sombre", full_page=True)
    page.evaluate("localStorage.setItem('demetra-theme', 'light')")
    page.reload()
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    assert not problems, problems
    context.close()


def _centre(locator) -> tuple[float, float]:
    box = locator.bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def _glisser(page, start: tuple[float, float], end: tuple[float, float]) -> None:
    """Un glisser à la souris, en plusieurs pas, puis l'attente du fragment redemandé."""
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(start[0] + 10, start[1] + 10, steps=3)
    page.mouse.move(*end, steps=8)
    page.mouse.up()
    expect(page.locator("[data-atelier]")).not_to_have_attribute("aria-busy", "true")


def test_atelier_glisser_deposer(site, browser):
    """Dans l'atelier, à la souris : glisser une brique de la palette sur la page vide, sur le schéma, sur une
    autre brique (elle s'y enchaîne) ; tirer un lien d'une brique à l'autre ; retirer un lien en le cliquant ;
    cliquer une brique mène à sa fiche. Un simple clic sur la palette pose toujours une brique. Une étude à
    plusieurs types de briques ne relie que ce qu'elle permet."""
    context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="fr-FR")
    page = context.new_page()
    problems: list[str] = []
    page.on("pageerror", lambda error: problems.append(f"erreur de script : {error}"))
    page.on(
        "console",
        lambda message: problems.append(f"console : {message.text}") if message.type == "error" else None,
    )
    login(page, site, "demo")
    page.get_by_role("link", name="Catalogue des runs Lancelot").click()
    page.get_by_role("link", name="Atelier", exact=True).click()
    task = page.locator(".at-add").first
    links = page.locator('input[name="l"]')

    # Page vide : la brique se dépose dans le cadre prévu.
    expect(page.locator(".at-drop")).to_be_visible()
    _glisser(page, _centre(task), _centre(page.locator(".at-drop")))
    expect(page.locator(".at-card")).to_have_count(1)
    # Sur le schéma, hors de toute brique : une brique de plus, sans lien.
    plan = page.locator("[data-at-plan]").bounding_box()
    _glisser(page, _centre(task), (plan["x"] + plan["width"] - 40, plan["y"] + plan["height"] - 40))
    expect(page.locator(".at-card")).to_have_count(2)
    expect(links).to_have_count(0)
    # Sur la brique A : la nouvelle brique s'y enchaîne.
    _glisser(page, _centre(task), _centre(page.locator('.n[data-e="A"]')))
    expect(page.locator(".at-card")).to_have_count(3)
    expect(links).to_have_count(1)
    expect(links.first).to_have_value("A:prerequisite:C")
    # Tirer un lien de B vers C.
    _glisser(page, _centre(page.locator('.n[data-e="B"]')), _centre(page.locator('.n[data-e="C"]')))
    expect(links).to_have_count(2)
    expect(page.locator('[data-brick="C"] .at-links li')).to_have_text(
        ["dépend de Task A", "dépend de Task B"]
    )
    expect(page.locator('.lk[data-l="B:prerequisite:C"]')).to_have_count(1)
    assert page.url.endswith(
        "?e=A%3Atask&e=B%3Atask&e=C%3Atask&l=A%3Aprerequisite%3AC&l=B%3Aprerequisite%3AC"
    )
    # Le même lien une seconde fois : rien ne change, le site dit pourquoi.
    _glisser(page, _centre(page.locator('.n[data-e="B"]')), _centre(page.locator('.n[data-e="C"]')))
    expect(page.locator("[data-at-hint-text]")).to_have_text("Task B et Task C sont déjà reliées ainsi.")
    expect(links).to_have_count(2)
    shot(page, "44-atelier-glisser-deposer", full_page=True)
    # Cliquer un lien propose de le retirer.
    page.locator('.lk[data-l="A:prerequisite:C"] .lk-hit').click(force=True)
    expect(page.locator(".at-pop button")).to_have_text(["Retirer le lien : Task A précède Task C"])
    page.locator(".at-pop button").click()
    expect(links).to_have_count(1)
    expect(links.first).to_have_value("B:prerequisite:C")
    # Cliquer une brique du schéma mène à sa fiche ; un simple clic sur la palette pose une brique.
    page.locator('.n[data-e="B"]').click()
    assert page.evaluate("document.activeElement.id") == "at-name-B"
    task.click()
    expect(page.locator(".at-card")).to_have_count(4)
    # Relâcher un lien dans le vide ne pose rien.
    _glisser(page, _centre(page.locator('.n[data-e="B"]')), (plan["x"] + 12, plan["y"] + plan["height"] - 12))
    expect(links).to_have_count(1)

    # Une étude à plusieurs types de briques : un lien que l'étude ne permet pas n'est pas posé.
    page.goto(f"{site}/etudes/")
    page.get_by_role("link", name="Circuit de validation d'un document").click()
    page.get_by_role("link", name="Atelier", exact=True).click()
    relecture = page.get_by_role("button", name="Relecture", exact=True)
    publication = page.get_by_role("button", name="Publication", exact=True)
    _glisser(page, _centre(publication), _centre(page.locator(".at-drop")))
    _glisser(page, _centre(relecture), _centre(page.locator('.n[data-e="A"]')))
    expect(page.locator(".at-card")).to_have_count(2)
    expect(links).to_have_count(0)  # rien ne suit une publication : la relecture est posée sans lien
    _glisser(page, _centre(page.locator('.n[data-e="A"]')), _centre(page.locator('.n[data-e="B"]')))
    expect(page.locator("[data-at-hint-text]")).to_contain_text(
        "L'étude ne permet pas de lien de Publication A"
    )
    expect(links).to_have_count(0)
    _glisser(page, _centre(page.locator('.n[data-e="B"]')), _centre(page.locator('.n[data-e="A"]')))
    expect(links).to_have_count(1)
    expect(links.first).to_have_value("B:puis:A")
    expect(page.locator("[data-result]")).to_contain_text("Document publié")
    assert not problems, problems
    context.close()


PERIODS_STUDY = """
from django.contrib.auth import get_user_model
from core import services as svc
from core.models import Representation
from tests.test_periodes import STUDY, WORKSHOP
owner = get_user_model().objects.get(username="demo")
frise = Representation.objects.get(name="Frise temporelle", owner=None)
actor = svc.Actor(owner)
study = svc.get_study(actor, svc.create_study(actor, {**STUDY, "workshop": WORKSHOP}).public_id)
svc.choose_representation(actor, study, frise, for_study=True)
print(study.public_id)
"""


def test_atelier_periodes(site, browser):
    """L'atelier d'une étude qui déclare des périodes : on part d'une page vide, on pose un contrat, une
    remise et un barème, on change des bornes au clavier puis un réglage, on vide une borne, et l'historique
    obtenu suit à chaque geste. La touche Entrée dans une borne ne pose pas de période. Tout l'état tient
    dans l'adresse. En clair, en sombre et sur mobile ; la situation s'enregistre comme cas."""
    made = subprocess.run(
        [sys.executable, str(ROOT / "manage.py"), "shell", "-c", PERIODS_STUDY],
        cwd=ROOT,
        env=SITE_ENV,
        check=True,
        capture_output=True,
        text=True,
    )
    sid = made.stdout.strip().splitlines()[-1]
    context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="fr-FR")
    page = context.new_page()
    problems: list[str] = []
    page.on("pageerror", lambda error: problems.append(f"erreur de script : {error}"))
    page.on(
        "console",
        lambda message: problems.append(f"console : {message.text}") if message.type == "error" else None,
    )
    login(page, site, "demo")
    page.goto(f"{site}/etudes/{sid}/atelier/")
    rows = page.locator(".at-history tbody tr[data-start]")

    # Page vide : les sources de l'étude, les règles que sa déclaration revient à poser, aucune période.
    expect(page.locator(".at-empty h2")).to_have_text("Composer un tarif")
    expect(page.locator(".at-add")).to_have_text(["Contrat", "Remise", "Barème"])
    expect(page.locator(".at-rules li")).to_have_count(7)
    expect(page.locator(".at-card")).to_have_count(0)

    # Poser un contrat, une remise, un barème : chacun arrive avec ses bornes, l'historique se compose.
    page.evaluate("window.__meme_page = true")
    for count, name in enumerate(("Contrat", "Remise", "Barème"), 1):
        page.get_by_role("button", name=name, exact=True).click()
        expect(page.locator(".at-card")).to_have_count(count)
    assert page.evaluate("window.__meme_page") is True
    expect(page.locator('input[name="de.A"]')).to_have_value("1")
    expect(page.locator('input[name="a.A"]')).to_have_value("3")
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("Tarif remisé")
    expect(page.locator(".at-plan .rep-timeline")).to_be_visible()
    # Une frise n'a pas de briques à relier : son aide parle de déplacer et d'étirer une période.
    expect(page.locator("[data-at-hint]")).to_contain_text("Glissez une période pour la déplacer")

    # Changer une borne au clavier : Entrée met à jour le résultat et ne pose rien.
    page.fill('input[name="a.A"]', "6")
    page.press('input[name="a.A"]', "Enter")
    expect(rows).to_have_count(2)
    expect(page.locator(".at-card")).to_have_count(3)
    expect(rows.nth(1)).to_contain_text("Plein tarif")
    expect(rows.nth(1).locator("td").nth(3)).to_have_text("vide")
    page.fill('input[name="de.B"]', "2")
    page.locator('input[name="de.B"]').blur()
    expect(rows).to_have_count(3)
    expect(page).to_have_url(re.compile(r"de\.B=2"))
    assert [rows.nth(n).locator("td").nth(0).inner_text() for n in range(3)] == ["1", "2", "3"]

    # Un réglage de la situation retire les mois sans remise ; une borne vidée bloque le traitement.
    page.select_option('select[name="r.sans_remise"]', "retirés")
    expect(rows).to_have_count(1)
    page.select_option('select[name="r.sans_remise"]', "gardés")
    expect(rows).to_have_count(3)
    query = page.url.split("?", 1)[1]
    assert query == "e=A%3Acontrat&e=B%3Aremise&e=C%3Abareme&de.A=1&a.A=6&de.B=2&a.B=3&de.C=1&a.C=3"
    page.fill('input[name="a.C"]', "")
    page.locator('input[name="a.C"]').blur()
    expect(page.locator(".at-out .notice")).to_contain_text("Le traitement est bloqué")
    expect(page.locator("[data-result]")).to_contain_text("Tarif non publié")
    expect(page.locator('input[name="a.C"]')).to_have_value("")
    expect(page).to_have_url(re.compile(r"a\.C=(&|$)"))

    # Dérouler pas à pas : la frise garde ses dimensions.
    page.goto(f"{site}/etudes/{sid}/atelier/?{query}")
    page.locator('a[data-at-step="first"]').click()
    expect(page.locator(".at-walk .stop-btn[aria-current=step]")).to_have_attribute("data-step", "0")
    box = page.locator(".at-walk [data-rep]").first.bounding_box()
    page.locator('a[data-at-step="next"]').click()
    expect(page).to_have_url(re.compile(r"etape=2"))
    after = page.locator(".at-walk [data-rep]").first.bounding_box()
    assert (box["width"], box["height"]) == (after["width"], after["height"])
    expect(page.locator(".at-walk .step-pane.is-current")).to_contain_text("Contrat : Contrat A")

    # Thème sombre et largeur mobile : rien ne déborde.
    page.goto(f"{site}/etudes/{sid}/atelier/?{query}")
    page.evaluate("localStorage.setItem('demetra-theme', 'dark')")
    for width, height in ((1280, 900), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        page.reload()
        expect(rows).to_have_count(3)
        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    page.evaluate("localStorage.setItem('demetra-theme', 'light')")
    page.set_viewport_size({"width": 1280, "height": 900})
    page.reload()

    # Enregistrer la situation comme cas : les périodes posées et l'historique obtenu y figurent.
    page.fill("#at-title", "Remise d'un mois")
    page.get_by_role("button", name="Enregistrer comme cas").click()
    expect(page).to_have_url(re.compile(r"cas=atelier-1"))
    expect(page.locator(".cp-title, [data-panel] h2").first).to_contain_text("Remise d'un mois")
    assert not problems, problems
    context.close()


def watched(page) -> list[str]:
    """Les erreurs de script et de console d'une page, relevées au fil du test."""
    problems: list[str] = []
    page.on("pageerror", lambda error: problems.append(f"erreur de script : {error}"))
    page.on(
        "console",
        lambda message: problems.append(f"console : {message.text}") if message.type == "error" else None,
    )
    return problems


def test_atelier_frise_au_doigt(site, browser):
    """Sur un téléphone, au doigt : glisser une période sur la frise la déplace, sans que le cadre ni la page
    ne défilent sous elle ; toucher une barre mène à sa fiche."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, locale="fr-FR", has_touch=True, is_mobile=True
    )
    page = context.new_page()
    problems = watched(page)
    login(page, site, "demo")
    page.goto(f"{site}/etudes/")
    page.get_by_role("link", name="Responsable d'un magasin au fil du temps").click()
    page.goto(page.url.split("?")[0] + "atelier/?e=A%3Amagasin&e=B%3Anomination&de.A=1&a.A=7&de.B=1&a.B=3")
    cdp = context.new_cdp_session(page)

    def finger(kind: str, x: float | None = None, y: float | None = None) -> None:
        points = [] if x is None else [{"x": x, "y": y, "id": 1}]
        cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": points})

    bar = page.locator('[data-at-plan] .tl-bar[data-p="B"]')
    bar.scroll_into_view_if_needed()
    box = bar.locator(".n-shape").bounding_box()
    unit = page.evaluate(
        """() => { const svg = document.querySelector('[data-at-plan] svg[data-span]');
        const [lo, hi, , w] = svg.dataset.span.split(' ').map(Number);
        return w / (hi - lo) * svg.getScreenCTM().a; }"""
    )
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    offsets = """() => { const all = [scrollY];
        let e = document.querySelector('[data-at-plan] .tl-bar[data-p="B"]');
        for (; e; e = e.parentElement) all.push(e.scrollLeft || 0);
        return all; }"""
    scrolled = page.evaluate(offsets)
    finger("touchStart", x, y)
    for n in range(1, 9):
        finger("touchMove", x + 2 * unit * n / 8, y)
        page.wait_for_timeout(20)
    expect(page.locator("[data-at-hint-text]")).to_have_text("Nomination B : du 3 au 5, fin exclue.")
    assert page.evaluate(offsets) == scrolled
    finger("touchEnd")
    expect(page.locator('input[name="de.B"]')).to_have_value("3")
    expect(page.locator('input[name="a.B"]')).to_have_value("5")
    # Toucher sans glisser : la fiche de la période.
    box = page.locator('[data-at-plan] .tl-bar[data-p="A"] .n-shape').bounding_box()
    page.touchscreen.tap(box["x"] + 20, box["y"] + box["height"] / 2)
    expect(page.locator("#at-name-A")).to_be_focused()
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    assert not problems, problems
    context.close()


def test_atelier_executions_successives(site, browser):
    """L'étude de démonstration déclare des exécutions successives : on dit qu'une période n'est connue qu'à
    partir d'une exécution, et chaque exécution montre ce qu'elle ajoute, ferme, modifie, retire ou laisse."""
    context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="fr-FR")
    page = context.new_page()
    problems = watched(page)
    login(page, site, "demo")
    page.goto(f"{site}/etudes/")
    page.get_by_role("link", name="Responsable d'un magasin au fil du temps").click()
    page.get_by_role("link", name="Atelier", exact=True).click()
    base = page.url.split("?")[0]
    page.goto(
        base + "?e=A%3Amagasin&e=B%3Anomination&e=C%3Anomination&e=D%3Aagent&e=E%3Aagent"
        "&de.A=1&a.A=7&de.B=1&a.B=3&de.C=5&a.C=7&o.C.agent=A2&de.D=1&a.D=7"
        "&de.E=1&a.E=7&o.E.matricule=A2&o.E.nom=Bruno"
    )
    # Une seule exécution : rien de plus à l'écran que le réglage.
    expect(page.locator(".at-runs")).to_have_count(0)
    expect(page.locator(".at-known")).to_have_count(0)
    page.select_option('select[name="x"]', "3")
    runs = page.locator(".at-run")
    expect(runs).to_have_count(3)
    expect(page.locator(".at-known")).to_have_count(5)
    # La seconde nomination et la fiche de son agent n'arrivent qu'à la deuxième exécution.
    page.select_option('select[name="c.C"]', "2")
    page.select_option('select[name="c.E"]', "2")
    expect(runs.nth(0).locator(".at-run-text")).to_have_text(
        "2 lignes ajoutées ; à l'écriture : 2 lignes écrites."
    )
    expect(runs.nth(1).locator(".at-run-text")).to_have_text(
        "1 ligne ajoutée, 1 ligne fermée et 1 ligne inchangée ; "
        "à l'écriture : 1 ligne supprimée et 2 lignes écrites."
    )
    expect(runs.nth(1).locator(".at-run-known")).to_have_text(
        "Connues depuis cette exécution : Nomination C, Fiche d'agent E."
    )
    words = "tr[data-change] .at-delta"  # le mot en tête de ligne ; sur petit écran, il a sa propre ligne
    expect(runs.nth(1).locator(words)).to_have_text(["inchangée", "fermée", "ajoutée"])
    expect(runs.nth(1).locator('tr[data-change="closed"] .at-delta')).to_have_attribute(
        "title", "Avant : du 3 au 7 · Halle du Port · vide · Publiée sans responsable"
    )
    expect(runs.nth(2).locator(".at-run-text")).to_have_text("3 lignes inchangées ; rien n'est écrit.")
    # À la troisième, la première nomination n'est plus connue : sa ligne change, une autre est retirée.
    page.select_option('select[name="j.B"]', "2")
    expect(runs.nth(2).locator(".at-run-text")).to_have_text(
        "1 ligne modifiée, 1 ligne inchangée et 1 ligne retirée ; "
        "à l'écriture : 2 lignes supprimées et 1 ligne écrite."
    )
    expect(runs.nth(2).locator(words)).to_have_text(["modifiée", "inchangée", "retirée"])
    expect(runs.nth(2).locator("del")).to_have_text(
        "du 3 au 5 · Halle du Port · vide · Publiée sans responsable"
    )
    expect(page.locator('.at-card[data-brick="B"] .at-final')).to_contain_text("Hors du calcul")
    expect(page.locator(".at-history caption").first).to_have_text(
        "Historique obtenu à la dernière exécution"
    )
    expect(page.locator(".at-rules li.is-used b")).to_contain_text(["P8"])
    assert page.url.endswith("&x=3") and "c.C=2" in page.url and "j.B=2" in page.url
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    shot(page, "49-atelier-executions", full_page=True)
    # Sur un téléphone, le mot passe au-dessus de sa ligne : chaque tableau tient dans la fenêtre.
    page.set_viewport_size({"width": 390, "height": 844})
    expect(runs.nth(2).locator(".at-run-mark .at-delta")).to_have_text(["modifiée", "inchangée", "retirée"])
    expect(runs.nth(2).locator(words).first).to_be_hidden()
    assert page.evaluate(
        "[...document.querySelectorAll('.at-run .at-history-wrap')]"
        ".every(e => e.scrollWidth <= e.clientWidth)"
    )
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    assert not problems, problems
    context.close()


def test_atelier_etude_de_periodes_semee(site, browser):
    """L'étude de démonstration qui déclare un atelier de périodes : on y arrive par la liste des études, la
    page part vide, et une situation à trois sources donne l'historique attendu, avec des jours sans
    responsable gardés puis retirés."""
    context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="fr-FR")
    page = context.new_page()
    problems = watched(page)
    login(page, site, "demo")
    page.goto(f"{site}/etudes/")
    page.get_by_role("link", name="Responsable d'un magasin au fil du temps").click()
    page.get_by_role("link", name="Atelier", exact=True).click()
    expect(page.locator(".at-empty h2")).to_have_text("Composer l'historique d'un magasin")
    expect(page.locator(".at-add")).to_have_text(["Magasin", "Nomination", "Fiche d'agent"])
    expect(page.locator(".at-rules li")).to_have_count(8)

    # Un magasin, deux nominations séparées par deux jours, les fiches des deux agents.
    base = page.url.split("?")[0]
    page.goto(
        base + "?e=A%3Amagasin&e=B%3Anomination&e=C%3Anomination&e=D%3Aagent&e=E%3Aagent"
        "&de.A=1&a.A=7&de.B=1&a.B=3&de.C=5&a.C=7&o.C.agent=A2&de.D=1&a.D=7"
        "&de.E=1&a.E=7&o.E.matricule=A2&o.E.nom=Bruno"
    )
    rows = page.locator(".at-history tbody tr[data-start]")
    expect(rows).to_have_count(3)
    cells = [rows.nth(n).locator("td").all_inner_texts()[:4] for n in range(3)]
    assert cells == [
        ["1", "3", "Halle du Port", "Alice"],
        ["3", "5", "Halle du Port", "vide"],
        ["5", "7", "Halle du Port", "Bruno"],
    ]
    expect(page.locator("[data-result]")).to_contain_text("avec des jours sans responsable")
    expect(page.locator(".at-plan .rep-timeline")).to_be_visible()
    shot(page, "45-atelier-periodes", full_page=True)

    # D'où vient une ligne : au survol, ses périodes sources se détachent sur la frise, la règle est nommée,
    # et la frise garde ses dimensions.
    traced = page.locator(".at-plan .tl-bar.is-traced")
    box = page.locator(".at-walk [data-rep]").first.bounding_box()
    rows.nth(1).hover()
    assert traced.evaluate_all("els => els.map(e => e.dataset.p)") == ["A", "I2"]
    expect(page.locator("[data-at-trace]")).to_contain_text(
        "Nomination : aucune en vigueur, la ligne est gardée"
    )
    expect(page.locator("[data-at-trace]")).to_contain_text("Règles P1, P5, P6 et P7.")
    expect(page.locator(".at-rules li.is-traced b")).to_have_text(["P1", "P5", "P6", "P7"])
    assert page.locator(".at-walk [data-rep]").first.bounding_box() == box
    page.mouse.move(2, 2)
    expect(traced).to_have_count(0)
    # Au clavier : le bouton de la ligne la garde, même quand le focus s'en va ; Échap la lâche.
    why = rows.nth(0).locator("[data-at-why]")
    why.focus()
    page.keyboard.press("Enter")
    expect(why).to_have_attribute("aria-pressed", "true")
    page.locator("#at-build-title").focus()
    assert sorted(traced.evaluate_all("els => els.map(e => e.dataset.p)")) == ["A", "B", "D", "I1"]
    expect(page.locator(".at-card.is-traced")).to_have_count(3)
    expect(page.locator("[data-at-trace]")).to_contain_text("Du 1 au 3 — Magasin : Magasin A")
    shot(page, "46-atelier-provenance", full_page=True)
    page.keyboard.press("Escape")
    expect(traced).to_have_count(0)
    expect(why).to_have_attribute("aria-pressed", "false")
    # Une fiche dit les lignes que sa période alimente.
    expect(page.locator('.at-card[data-brick="A"] .at-feeds')).to_contain_text(
        "du 1 au 3, du 3 au 5, du 5 au 7"
    )

    # Ce que le dernier geste a changé : la seconde nomination commence un jour plus tôt. Une ligne est
    # modifiée, une autre nouvelle, une troisième disparaît et reste lisible, barrée ; chacune porte un mot.
    note = page.locator("[data-at-delta]")
    expect(note).to_have_text("")
    writes: list[str] = []
    page.on("request", lambda request: writes.append(request.url) if request.method != "GET" else None)
    page.fill('input[name="de.C"]', "4")
    page.locator('input[name="de.C"]').blur()
    expect(note).to_have_text("Votre dernier geste : 1 ligne nouvelle, 1 ligne modifiée, 1 ligne disparue.")
    expect(rows.nth(0).locator(".at-delta")).to_have_count(0)
    expect(rows.nth(1).locator(".at-delta")).to_have_text("modifiée")
    expect(rows.nth(1).locator(".at-delta")).to_have_attribute(
        "title", "Avant ce geste : du 3 au 5 · Halle du Port · vide · Publiée sans responsable"
    )
    expect(rows.nth(2).locator(".at-delta")).to_have_text("nouvelle")
    gone = page.locator(".at-history tbody tr.is-gone")
    expect(gone.locator("del")).to_have_text("du 5 au 7 · Halle du Port · Bruno · Publiée")
    expect(gone.locator(".at-delta")).to_have_text("disparue")
    shot(page, "47-atelier-changement", full_page=True)
    # Sur un téléphone, chaque mot passe au-dessus de sa ligne : le tableau tient dans la fenêtre.
    marks = page.locator(".at-history .at-run-mark .at-delta")
    expect(marks.first).to_be_hidden()
    page.set_viewport_size({"width": 390, "height": 844})
    expect(marks).to_have_text(["modifiée", "nouvelle", "disparue"])
    expect(rows.nth(1).locator(".at-delta")).to_be_hidden()
    assert page.evaluate(
        "[...document.querySelectorAll('.at-history-wrap')].every(e => e.scrollWidth <= e.clientWidth)"
    )
    page.set_viewport_size({"width": 1280, "height": 900})
    # Un champ que l'historique ne restitue pas ne change rien, et l'écran le dit. Rien n'est écrit au
    # serveur.
    page.select_option('select[name="o.A.caisse"]', "v2")
    expect(note).to_have_text("Votre dernier geste n'a pas changé l'historique.")
    expect(page.locator(".at-delta")).to_have_count(0)
    assert writes == []

    # La frise se manie : tirer le bord droit de la nomination B d'un peu plus d'un jour la fait finir au
    # jour 4 (calée sur le pas de l'axe) ; pendant le geste l'aide dit les bornes et le schéma garde ses
    # dimensions ; au lâcher, le champ « Fin, exclue » et l'historique suivent.
    geo = """(id) => {
      const svg = document.querySelector('[data-at-plan] svg[data-span]');
      const [lo, hi, , w] = svg.dataset.span.split(' ').map(Number);
      const bar = document.querySelector('[data-at-plan] .tl-bar[data-p="' + id + '"] .n-shape');
      const box = bar.getBoundingClientRect();
      const all = svg.getBoundingClientRect();
      return {unit: w / (hi - lo) * svg.getScreenCTM().a, x: box.x, y: box.y, w: box.width, h: box.height,
              svg: [all.width, all.height]};
    }"""
    hint = page.locator("[data-at-hint-text]")
    expect(hint).to_have_text(re.compile(r"^Glissez une période pour la déplacer"))
    page.locator('[data-at-plan] .tl-bar[data-p="B"]').scroll_into_view_if_needed()
    was = page.evaluate(geo, "B")
    page.mouse.move(was["x"] + was["w"] - 2, was["y"] + was["h"] / 2)
    page.mouse.down()
    page.mouse.move(was["x"] + was["w"] - 2 + 1.3 * was["unit"], was["y"] + was["h"] / 2 + 2, steps=6)
    expect(hint).to_have_text("Nomination B : du 1 au 4, fin exclue.")
    now = page.evaluate(geo, "B")
    assert now["svg"] == was["svg"] and round(now["w"] - was["w"]) == round(was["unit"])
    expect(page.locator('input[name="a.B"]')).to_have_value("3")  # rien n'est décidé avant de lâcher
    page.mouse.up()
    expect(page.locator('input[name="a.B"]')).to_have_value("4")
    expect(note).to_have_text("Votre dernier geste : 1 ligne modifiée, 1 ligne disparue.")
    expect(rows).to_have_count(2)
    # Déplacer la nomination C : sa durée ne change pas. Échap pendant le geste ne change rien.
    was = page.evaluate(geo, "C")
    page.mouse.move(was["x"] + was["w"] / 2, was["y"] + was["h"] / 2)
    page.mouse.down()
    page.mouse.move(was["x"] + was["w"] / 2 + 3 * was["unit"], was["y"] + was["h"] / 2, steps=6)
    expect(hint).to_have_text("Nomination C : du 7 au 10, fin exclue.")
    page.keyboard.press("Escape")
    page.mouse.up()
    assert round(page.evaluate(geo, "C")["x"]) == round(was["x"])
    expect(page.locator('input[name="de.C"]')).to_have_value("4")
    page.mouse.move(was["x"] + was["w"] / 2, was["y"] + was["h"] / 2)
    page.mouse.down()
    page.mouse.move(was["x"] + was["w"] / 2 + 0.9 * was["unit"], was["y"] + was["h"] / 2, steps=6)
    expect(hint).to_have_text("Nomination C : du 5 au 8, fin exclue.")
    shot(page, "48-atelier-frise", full_page=True)
    page.mouse.up()
    expect(page.locator('input[name="de.C"]')).to_have_value("5")
    expect(page.locator('input[name="a.C"]')).to_have_value("8")
    expect(rows).to_have_count(3)
    assert writes == []

    page.select_option('select[name="r.sans_responsable"]', "retirés")
    expect(rows).to_have_count(2)
    expect(page.locator("[data-result]")).to_have_text(re.compile(r"^Historique publié"))
    assert not problems, problems
    context.close()
