"""Contrastes des jetons de couleur, calculés depuis tokens.css (WCAG 2.2 AA), en clair et en sombre."""
from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

TOKENS = (Path(__file__).resolve().parents[1] / "core" / "static" / "core" / "tokens.css").read_text(encoding="utf-8")
ROLES = ["neutral", "waiting", "active", "success", "warning", "error", "blocked", "disabled", "info"]


def _block(selector: str) -> dict[str, tuple[float, float, float]]:
    body = TOKENS[TOKENS.index(selector):]
    body = body[body.index("{") + 1:body.index("\n}")]
    return {name: (float(l), float(c), float(h)) for name, l, c, h in re.findall(r"--([\w-]+):\s*oklch\(([\d.]+) ([\d.]+) ([\d.]+)\)", body)}


LIGHT = _block(":root {")
DARK = {**LIGHT, **_block(':root[data-theme="dark"] {')}


def _luminance(colour: tuple[float, float, float]) -> float:
    lightness, chroma, hue = colour
    a, b = chroma * math.cos(math.radians(hue)), chroma * math.sin(math.radians(hue))
    l_, m_, s_ = lightness + 0.3963377774 * a + 0.2158037573 * b, lightness - 0.1055613458 * a - 0.0638541728 * b, lightness - 0.0894841775 * a - 1.2914855480 * b
    l3, m3, s3 = l_ ** 3, m_ ** 3, s_ ** 3
    rgb = (4.0767416621 * l3 - 3.3077115913 * m3 + 0.2309699292 * s3,
           -1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3,
           -0.0041960863 * l3 - 0.7034186147 * m3 + 1.7076147010 * s3)
    r, g, b_ = (min(1.0, max(0.0, channel)) for channel in rgb)     # sRGB linéaire, ramené dans la gamme
    return 0.2126 * r + 0.7152 * g + 0.0722 * b_


def contrast(theme: dict, front: str, back: str) -> float:
    first, second = _luminance(theme[front]), _luminance(theme[back])
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


TEXT = [("ink", "surface"), ("ink", "panel"), ("ink", "raised"), ("ink-2", "surface"), ("ink-2", "panel"), ("ink-2", "sunken"),
        ("ink-3", "surface"), ("ink-3", "panel"), ("ink-3", "raised"), ("accent", "surface"), ("accent", "panel"), ("accent", "accent-soft"),
        ("accent-ink", "accent"), ("accent-ink", "accent-hover"), ("ink", "accent-soft"), ("danger", "surface"), ("danger", "raised"),
        ("rail-ink", "rail"), ("rail-ink-2", "rail"), ("rail-ink", "rail-raised")]
TEXT += [(f"r-{role}-fg", f"r-{role}-bg") for role in ROLES] + [("on-solid", f"r-{role}-solid") for role in ("success", "error")]
TEXT += [(f"r-{role}-fg", ground) for role in ("success", "error", "warning") for ground in ("surface", "panel")]
OUTLINES = [("field-line", "raised"), ("field-line", "surface"), ("field-line", "panel"), ("focus", "surface"), ("focus", "panel"), ("focus", "raised"),
            ("accent", "panel"), ("ink-2", "raised")]
OUTLINES += [(f"r-{role}-line", "raised") for role in ("active", "success", "warning", "error", "blocked", "info")]


@pytest.mark.parametrize("theme_name, theme", [("clair", LIGHT), ("sombre", DARK)])
def test_text_contrast_is_at_least_4_5(theme_name, theme):
    weak = [f"{front} sur {back} : {contrast(theme, front, back):.2f}" for front, back in TEXT if contrast(theme, front, back) < 4.5]
    assert not weak, f"Thème {theme_name}, texte sous 4,5:1 — " + " ; ".join(weak)


@pytest.mark.parametrize("theme_name, theme", [("clair", LIGHT), ("sombre", DARK)])
def test_control_outlines_and_focus_are_at_least_3(theme_name, theme):
    weak = [f"{front} sur {back} : {contrast(theme, front, back):.2f}" for front, back in OUTLINES if contrast(theme, front, back) < 3]
    assert not weak, f"Thème {theme_name}, contour sous 3:1 — " + " ; ".join(weak)


# Représentations du catalogue élargi : textes et traits posés sur le fond du schéma, sur la ligne ou la bande de l'étape en cours.
EXTENDED_TEXT = [("ink-2", "raised"), ("ink-2", "accent-soft"), ("ink-3", "panel"), ("r-error-fg", "raised"), ("r-error-fg", "accent-soft"),
                 ("accent", "raised"), ("ink", "panel")]
EXTENDED_TEXT += [(f"r-{role}-fg", "accent-soft") for role in ("success", "warning", "error")]
EXTENDED_LINES = [("ink-3", "raised"), ("ink-3", "panel"), ("ink-2", "raised"), ("accent", "raised"), ("accent", "accent-soft"),
                  ("r-error-fg", "raised"), ("r-error-fg", "accent-soft"), ("ink", "accent-soft")]


@pytest.mark.parametrize("theme_name, theme", [("clair", LIGHT), ("sombre", DARK)])
def test_extended_representations_keep_text_at_4_5_and_lines_at_3(theme_name, theme):
    weak = [f"texte {front} sur {back} : {contrast(theme, front, back):.2f}" for front, back in EXTENDED_TEXT if contrast(theme, front, back) < 4.5]
    weak += [f"trait {front} sur {back} : {contrast(theme, front, back):.2f}" for front, back in EXTENDED_LINES if contrast(theme, front, back) < 3]
    assert not weak, f"Thème {theme_name} — " + " ; ".join(weak)


def test_extended_representations_never_dim_text_by_transparency():
    """Un texte estompé par opacité perd son contraste : les états « à venir » ou « écarté » passent par une couleur de texte."""
    css = (Path(__file__).resolve().parents[1] / "core" / "static" / "core" / "rep.css").read_text(encoding="utf-8")
    extended = css[css.index("Représentations élargies"):]
    assert "opacity" not in extended
