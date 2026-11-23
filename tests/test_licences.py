"""Toute dépendance installée doit avoir une licence utilisable en entreprise."""

from __future__ import annotations

from importlib import metadata

ALLOWED = (
    "MIT",
    "BSD",
    "Apache",
    "PSF",
    "Python Software Foundation",
    "ISC",
    "Unlicense",
    "Public Domain",
    "0BSD",
)
# Copyleft fort ou faible, et usage non commercial : rien de tout cela n'entre, même en licence au choix.
FORBIDDEN = (
    "GPL",
    "AGPL",
    "LGPL",
    "MPL",
    "Mozilla Public",
    "EPL",
    "Eclipse Public",
    "SSPL",
    "Commons Clause",
    "NonCommercial",
    "Non-Commercial",
    "CC-BY-NC",
    "Artistic",
    "EUPL",
)


def licence_of(dist) -> str:
    meta = dist.metadata
    expression = meta.get("License-Expression")
    if expression:
        return expression
    classifiers = [
        c.split(" :: ")[-1] for c in meta.get_all("Classifier") or [] if c.startswith("License ::")
    ]
    return (
        ", ".join(classifiers) or (meta.get("License") or "").splitlines()[0][:80]
        if (classifiers or meta.get("License"))
        else ""
    )


def test_every_installed_package_has_a_permissive_licence():
    problems = []
    for dist in metadata.distributions():
        name, licence = dist.metadata["Name"], licence_of(dist)
        if not licence:
            problems.append(f"{name} : licence non déclarée")
        elif any(word.lower() in licence.lower() for word in FORBIDDEN):
            problems.append(f"{name} : {licence}")
        elif not any(word.lower() in licence.lower() for word in ALLOWED):
            problems.append(f"{name} : licence hors liste admise ({licence})")
    assert not problems, "Dépendances à examiner :\n" + "\n".join(sorted(problems))


def test_font_ships_with_its_licence():
    from pathlib import Path

    fonts = Path(__file__).resolve().parents[1] / "core" / "static" / "core" / "fonts"
    assert (fonts / "archivo-variable.woff2").exists()
    assert "SIL OPEN FONT LICENSE" in (fonts / "OFL.txt").read_text(encoding="utf-8")


def test_no_layout_library_is_pulled_in():
    """Les schémas sont calculés par le site : ni ELK (EPL) ni Graphviz (EPL), ni aucun paquet qui les
    enveloppe, ni script tiers."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    banned = re.compile(r"graphviz|pygraphviz|pydot|\belk|dagre|mermaid|cytoscape", re.IGNORECASE)
    installed = sorted(dist.metadata["Name"] for dist in metadata.distributions())
    assert not [name for name in installed if banned.search(name)], installed
    locked = re.findall(
        r'^name = "([^"]+)"', (root / "uv.lock").read_text(encoding="utf-8"), flags=re.MULTILINE
    )
    assert locked and not [name for name in locked if banned.search(name)]
    scripts = sorted(path.name for path in (root / "core" / "static" / "core").rglob("*.js"))
    assert scripts == ["app.js"], f"un seul script, écrit pour le projet : {scripts}"
