"""Mode d'emploi de Demetra : un seul texte source en Markdown, servi par l'API
(/api/v1/guide), par /llms.txt et par la page publique /guide/."""

import re
from functools import cache
from html import escape
from pathlib import Path

import markdown as md
from django.conf import settings

from .models import SiteNotice

TOPICS = {
    "index": "Prise en main : ce qu'est Demetra et l'ordre des opérations",
    "agents": "Brancher une IA en sécurité : jeton, terminal, Copilot, Claude Code, Codex",
    "auth": "Jetons, portées et limites d'un jeton",
    "studies": "Études : statuts, dimensions, règles de gestion",
    "cases": "Cas : format, dépôt en lot, validation à blanc, erreurs",
    "coverage": "Couverture : dimensions, combinaisons manquantes, contrôles",
    "review": "Revue : lire les avis et commentaires, liste de travail",
    "atelier": "Atelier : déclarer les règles d'une étude, dérouler une situation construite",
    "representations": "Représentations : briques, création, ajustement, aperçu",
    "sharing": "Partage et journal d'audit",
}

_DIR = Path(__file__).parent / "guide"


@cache
def _read(topic: str) -> str:
    return (_DIR / f"{topic}.md").read_text(encoding="utf-8")


# Chapitres qui portent le message de l'administrateur, juste après leur ligne « Version ».
NOTICE_TOPICS = ("index", "agents")
# Ligne du bloc à copier après laquelle viennent les consignes de l'organisation (chapitre « agents »).
_LAST_PROJECT_LINE = "- Commencer par GET {{origin}}/api/v1/me, puis GET {{origin}}/api/v1/guide?format=md.\n"


def markdown(topic: str, origin: str = "https://votre-site-demetra", html: bool = False) -> str:
    """Le chapitre, avec ce que l'administrateur a ajouté. `html` : pour la page /guide/, où le message est
    échappé (le bloc à copier l'est déjà par le rendu des blocs de code)."""
    text = _with_notice(topic, _read(topic), SiteNotice.current(), html)
    return text.replace("{{version}}", settings.DEMETRA_GUIDE_VERSION).replace("{{origin}}", origin)


# Un bloc de code délimité, en retrait : il appartient à l'élément de liste au-dessus de lui.
_NESTED_FENCE = re.compile(
    r"^(?P<pad>[ ]+)```(?P<lang>[\w-]*)[ ]*\n(?P<body>.*?)^(?P=pad)```[ ]*$", re.MULTILINE | re.DOTALL
)


def to_html(text: str) -> str:
    """Le Markdown du mode d'emploi en HTML, pour la page /guide/.

    Python-Markdown ne reconnaît pas un bloc ``` placé dans un élément de liste : il en ferait un paragraphe
    d'une ligne. Ces blocs sont mis de côté, remplacés par une marque à la même place, puis rendus en
    <pre>."""
    kept: list[str] = []

    def keep(match: re.Match) -> str:
        pad, lang = match["pad"], match["lang"]
        body = "".join(line.removeprefix(pad) for line in match["body"].splitlines(keepends=True))
        cls = f' class="language-{lang}"' if lang else ""
        kept.append(f"<pre><code{cls}>{escape(body, quote=False)}</code></pre>")
        return f"{pad}DEMETRA-CODE-{len(kept) - 1}"

    # Le guide met 3 espaces sous un élément de liste numérotée (« 1. ») ; Python-Markdown en attend 4.
    extensions = ["tables", "fenced_code", "toc"]
    html = md.markdown(_NESTED_FENCE.sub(keep, text), extensions=extensions, tab_length=3)
    for n, block in enumerate(kept):
        html = re.sub(rf"<p>DEMETRA-CODE-{n}</p>|DEMETRA-CODE-{n}\b", lambda _m, b=block: b, html, count=1)
    return html


def notice_block(message: str, html: bool = False) -> str:
    """Le message de l'administrateur en citation, signé : une IA le lit comme ce qu'il est, une information
    donnée par l'exploitant du site, pas une consigne du mode d'emploi."""
    lines = [escape(line, quote=False) if html else line for line in message.strip().splitlines()]
    quoted = "\n".join(f"> {line}".rstrip() for line in lines)
    return f"**Message de l'administrateur de ce site**\n\n{quoted}\n"


def project_lines(raw: str) -> list[str]:
    """Une consigne par ligne non vide, en liste Markdown ; sans clôture de bloc de code possible."""
    lines = []
    for line in raw.splitlines():
        line = line.strip().replace("```", "` ` `")
        if line:
            lines.append(line if line.startswith("- ") else f"- {line}")
    return lines


def _with_notice(topic: str, text: str, notice: SiteNotice | None, html: bool) -> str:
    if notice is None:
        return text
    if notice.message.strip() and topic in NOTICE_TOPICS:
        head, sep, rest = text.partition("\n\n")  # titre, puis la ligne « Version »
        version, sep2, rest = rest.partition("\n\n")
        text = f"{head}{sep}{version}{sep2}{notice_block(notice.message, html)}\n{rest}"
    lines = project_lines(notice.project_lines)
    if lines and topic == "agents":
        added = "".join(f"{line}\n" for line in lines)
        text = text.replace(_LAST_PROJECT_LINE, _LAST_PROJECT_LINE + added, 1)
    return text


def topics(base: str) -> list[dict]:
    return [{"topic": key, "title": title, "url": f"{base}{key}"} for key, title in TOPICS.items()]


def full_markdown(origin: str = "https://votre-site-demetra") -> str:
    return "\n\n---\n\n".join(markdown(topic, origin) for topic in TOPICS)


def llms_txt(origin: str) -> str:
    lines = [
        "# Demetra",
        "",
        (
            "> Demetra rassemble les cas qui découlent de règles de gestion ou d'un processus métier, montre "
            "chaque cas comme un schéma "
            "qui évolue étape par étape, et recueille l'avis d'un humain sur chacun. Une IA externe dépose "
            "les cas par l'API REST ; "
            "le site vérifie, mesure la couverture et dessine. Seuls les humains rendent un avis."
        ),
        "",
        *_llms_notice(),
        (
            f"Version du mode d'emploi : {settings.DEMETRA_GUIDE_VERSION}. "
            "Authentification de l'API : en-tête `Authorization: Bearer <jeton>`."
        ),
        "",
        (
            "**IA : pour vous connecter, n'attendez pas de jeton dans la conversation.** Si la variable "
            "d'environnement "
            "`DEMETRA_TOKEN` est vide, obtenez un accès par le lien d'autorisation : `POST /api/v1/connect`, "
            "donnez le "
            "lien à la personne, qui clique « Autoriser », puis `POST /api/v1/connect/token` et rangez le "
            "jeton sans "
            f"l'afficher. Mode opératoire et règles : {origin}/api/v1/guide/agents?format=md. Appelez l'API "
            "depuis un "
            "terminal (curl) : un outil de lecture de page web n'envoie pas d'en-tête et reçoit 401."
        ),
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


def _llms_notice() -> list[str]:
    notice = SiteNotice.current()
    if notice is None or not notice.message.strip():
        return []
    return [notice_block(notice.message), ""]
