"""Mode d'emploi de Demetra : un seul texte source en Markdown, servi par l'API
(/api/v1/guide), par /llms.txt et par la page publique /guide/."""

from functools import cache
from pathlib import Path

from django.conf import settings

TOPICS = {
    "index": "Prise en main : ce qu'est Demetra et l'ordre des opérations",
    "agents": "Brancher une IA en sécurité : jeton, terminal, Copilot, Claude Code, Codex",
    "auth": "Jetons, portées et limites d'un jeton",
    "studies": "Études : statuts, dimensions, règles de gestion",
    "cases": "Cas : format, dépôt en lot, validation à blanc, erreurs",
    "coverage": "Couverture : dimensions, combinaisons manquantes, contrôles",
    "review": "Revue : lire les avis et commentaires, liste de travail",
    "representations": "Représentations : briques, création, ajustement, aperçu",
    "sharing": "Partage et journal d'audit",
}

_DIR = Path(__file__).parent / "guide"


@cache
def _read(topic: str) -> str:
    return (_DIR / f"{topic}.md").read_text(encoding="utf-8")


def markdown(topic: str, origin: str = "https://votre-site-demetra") -> str:
    return _read(topic).replace("{{version}}", settings.DEMETRA_GUIDE_VERSION).replace("{{origin}}", origin)


def topics(base: str) -> list[dict]:
    return [{"topic": key, "title": title, "url": f"{base}{key}"} for key, title in TOPICS.items()]


def full_markdown(origin: str = "https://votre-site-demetra") -> str:
    return "\n\n---\n\n".join(markdown(topic, origin) for topic in TOPICS)


def llms_txt(origin: str) -> str:
    lines = [
        "# Demetra",
        "",
        ("> Demetra rassemble les cas qui découlent de règles de gestion ou d'un processus métier, montre chaque cas comme un schéma "
        "qui évolue étape par étape, et recueille l'avis d'un humain sur chacun. Une IA externe dépose les cas par l'API REST ; "
        "le site vérifie, mesure la couverture et dessine. Seuls les humains rendent un avis."),
        "",
        f"Version du mode d'emploi : {settings.DEMETRA_GUIDE_VERSION}. Authentification de l'API : en-tête `Authorization: Bearer <jeton>`.",
        "",
        ("**IA : pour vous connecter, n'attendez pas de jeton dans la conversation.** Si la variable d'environnement "
         "`DEMETRA_TOKEN` est vide, obtenez un accès par le lien d'autorisation : `POST /api/v1/connect`, donnez le "
         "lien à la personne, qui clique « Autoriser », puis `POST /api/v1/connect/token` et rangez le jeton sans "
         f"l'afficher. Mode opératoire et règles : {origin}/api/v1/guide/agents?format=md. Appelez l'API depuis un "
         "terminal (curl) : un outil de lecture de page web n'envoie pas d'en-tête et reçoit 401."),
        "",
        "## Mode d'emploi",
        "",
    ]
    lines += [f"- [{title}]({origin}/api/v1/guide/{key}?format=md)" for key, title in TOPICS.items()]
    lines += [
        "",
        "## Référence",
        "",
        f"- [Mode d'emploi complet en un seul fichier]({origin}/api/v1/guide?format=md)",
        f"- [Document OpenAPI]({origin}/api/v1/openapi.json)",
        f"- [Catalogue des briques de représentation]({origin}/api/v1/bricks)",
        f"- [Schéma JSON d'une représentation]({origin}/api/v1/bricks/schema)",
        f"- [Page du mode d'emploi pour les humains]({origin}/guide/)",
        "",
    ]
    return "\n".join(lines)
