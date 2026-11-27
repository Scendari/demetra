"""Le chapitre « Étude complète » : quatre prompts à copier, l'adresse de l'instance insérée, aucun secret."""

from __future__ import annotations

import re

import pytest
from django.conf import settings

from core import guide

pytestmark = pytest.mark.django_db  # le message de l'organisation se lit en base

PHASES = ("1. Inventaire", "2. Construction", "3. Reprise", "4. Contre-vérification")


def _prompts(text: str) -> list[str]:
    return re.findall(r"```prompt\n(.*?)```", text, flags=re.DOTALL)


def test_quatre_prompts_avec_l_adresse_de_l_instance():
    text = guide.markdown("complete", "https://demetra.exemple.org")
    prompts = _prompts(text)
    assert len(prompts) == 4 and all(f"### {phase}" in text for phase in PHASES)
    assert all("https://demetra.exemple.org/llms.txt" in p for p in prompts)
    assert "{{origin}}" not in text and "{{version}}" not in text


def test_aucun_secret_ni_avis_dans_les_prompts():
    for prompt in _prompts(guide.markdown("complete", "https://x")):
        assert "Bearer" not in prompt and f"{settings.DEMETRA_TOKEN_PREFIX}_" not in prompt
        assert not re.search(r"DEMETRA_TOKEN\s*=", prompt), "jamais de jeton dans un texte copié"
    construction, verification = _prompts(guide.markdown("complete", "https://x"))[1::2]
    assert "aucun avis" in construction and "aucun avis" in verification
    assert "inventory.open vaut 0" in construction, "un critère d'arrêt explicite"
    assert "nouvelle étude" in _prompts(guide.markdown("complete", "https://x"))[0]


def test_servi_partout(client):
    assert "/api/v1/guide/complete?format=md" in client.get("/llms.txt").content.decode()
    api = client.get("/api/v1/guide/complete?format=md").content.decode()
    assert len(_prompts(api)) == 4


def test_page_avec_boutons_copier(client):
    html = client.get("/guide/complete/").content.decode()
    assert html.count('data-copy="#prompt-') == 4 and html.count('id="prompt-') == 4
    assert "http://testserver/llms.txt" in html
    assert "Étude complète" in client.get("/guide/agents/").content.decode()


def test_la_page_des_etudes_y_mene(web):
    client = web("ana")
    page = client.get("/etudes/").content.decode()
    assert (
        'href="/guide/complete/"' in page and "Prompts d&#x27;analyse" in page or "Prompts d'analyse" in page
    )
