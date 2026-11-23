#!/usr/bin/env python3
"""Passe les écrans rendus de Demetra au détecteur impeccable et échoue sur tout constat non accepté.

    uv run python scripts/controle_impeccable.py --detecteur ~/.claude/skills/impeccable/scripts/impeccable

Le serveur de démonstration doit tourner (seed_demo puis runserver). Chaque écran est passé à 1440 et 390 px,
en thème clair puis sombre. Un constat est accepté s'il figure dans ACCEPTES pour cet écran ; tout autre
constat fait échouer le script (code 1). Les constats acceptés sont antérieurs au catalogue élargi et ont été
acceptés le 22/11/2026 ; ils sont décrits dans le README, section « Ce qui n'a pas été vérifié ».
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from playwright.sync_api import sync_playwright

PORT = 9337

# Écran (préfixe du libellé) → types de constat acceptés. « * » vaut pour tous les écrans.
ACCEPTES = {
    "*": {"codex-grid-background"},  # fond quadrillé du schéma, choix de design
    "onglet ": {"flat-type-hierarchy"},  # titres des onglets d'étude : 20, 17 et 15 px
    "onglet couverture": {
        "repeating-stripes-gradient"
    },  # hachures des combinaisons exclues : elles portent du sens
    "revue Relances": {
        "em-dash-overuse",
        "content-hidden-at-rest",
    },  # textes et étapes repliées de cette étude
}

PUBLICS = [
    ("accueil", "/"),
    ("connexion", "/comptes/login/"),
    ("inscription", "/comptes/signup/"),
    ("page introuvable", "/page-inexistante/"),
    ("briques", "/briques/"),
] + [
    (f"mode d'emploi {t}", f"/guide/{t}/")
    for t in ("index", "studies", "cases", "representations", "auth", "review", "coverage", "sharing")
]
REVUES = [
    "Catalogue des runs Lancelot",
    "Remboursement d'une commande",
    "Relances d'une facture impayée",
    "Droits d'accès aux documents",
    "Prix à payer d'une commande",
    "Validation d'une note de frais",
    "Changement d'adresse d'un assuré",
    "Priorité d'un ticket de support",
    "Mode de livraison proposé",
    "Validation d'un document",
    "Cycle de vie d'une commande en ligne",
    "Paiement par carte d'une commande",
]
ONGLETS = [
    ("couverture", "couverture/"),
    ("partage", "partage/"),
    ("historique", "historique/"),
    ("définitions", "definitions/"),
    ("représentation", "representation/"),
]


def acceptes(ecran: str) -> set[str]:
    return set().union(
        *(kinds for prefix, kinds in ACCEPTES.items() if prefix == "*" or ecran.startswith(prefix))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--detecteur", required=True, help="lanceur du détecteur impeccable")
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    host = args.base.split("//", 1)[-1]
    ecarts, ecrans, sautes = [], 0, set()

    def scan(page, ecran: str) -> None:
        nonlocal ecrans
        page.wait_for_load_state("networkidle")
        out = subprocess.run(
            [args.detecteur, "detect", "--json", "--cdp", str(PORT), "--target", host],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        ).stdout
        try:
            items = json.loads(out)
        except ValueError:
            raise SystemExit(f"détecteur : sortie illisible sur « {ecran} » : {out[:200]}") from None
        ecrans += 1
        for item in items:
            if item["antipattern"] not in acceptes(ecran):
                ecarts.append(
                    f"{ecran} : {item['antipattern']} — {item.get('selector', '')} — "
                    f"{item.get('snippet', '')}"
                )

    with sync_playwright() as pw:
        for theme in ("light", "dark"):
            for width, height in ((1440, 900), (390, 844)):
                browser = pw.chromium.launch(args=[f"--remote-debugging-port={PORT}"])
                page = browser.new_page(viewport={"width": width, "height": height})
                page.add_init_script(
                    f"try {{ localStorage.setItem('demetra-theme', '{theme}'); }} catch (e) {{}}"
                )
                tag = f"[{theme}, {width} px]"
                for ecran, url in PUBLICS:
                    page.goto(args.base + url)
                    if page.title().startswith("Page not found at"):
                        sautes.add(
                            f"{ecran} : page de débogage de Django (serveur lancé avec DEMETRA_DEBUG=1)"
                        )
                        continue
                    scan(page, f"{ecran} {tag}")
                page.goto(args.base + "/comptes/login/")
                page.fill('input[name="login"]', "demo")
                page.fill('input[name="password"]', "demetra-demo")
                page.click('button[type="submit"]')
                page.wait_for_url("**/etudes/")
                scan(page, f"liste des études {tag}")
                page.goto(args.base + "/compte/jetons/")
                scan(page, f"jetons {tag}")
                for titre in REVUES:
                    page.goto(args.base + "/etudes/")
                    page.get_by_role("link", name=titre, exact=True).click()
                    page.wait_for_load_state("networkidle")
                    sid = page.locator("[data-workspace]").get_attribute("data-sid")
                    page.keyboard.press("j")
                    page.keyboard.press("ArrowRight")
                    page.wait_for_timeout(300)
                    scan(page, f"revue {titre} {tag}")
                    for onglet, tail in ONGLETS:
                        page.goto(f"{args.base}/etudes/{sid}/{tail}")
                        scan(page, f"onglet {onglet} ({titre}) {tag}")
                browser.close()

    print(f"{ecrans} écrans passés au détecteur, {len(ecarts)} constat(s) non accepté(s)")
    for saute in sorted(sautes):
        print("   non passé :", saute)
    for ecart in ecarts:
        print("  ", ecart)
    return 1 if ecarts else 0


if __name__ == "__main__":
    sys.exit(main())
