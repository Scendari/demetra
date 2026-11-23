"""Aperçu d'une représentation : image PNG (navigateur sans interface) et résumé textuel.

Le fragment est dessiné par core/render.py ; il est placé dans une page autonome avec
la feuille de style du site, puis photographié par Chromium (Playwright). Si Chromium
n'est pas installé, l'aperçu reste disponible sous forme de résumé textuel.
"""

from __future__ import annotations

import base64
import hashlib
import threading
from functools import lru_cache
from pathlib import Path

from django.conf import settings

from .render import icon_sprite

_LOCK = threading.Lock()
_CACHE: dict[str, bytes] = {}
_CACHE_MAX = 64


@lru_cache(maxsize=1)
def _css() -> str:
    """Feuilles de style du site, police incluse, pour une page d'aperçu sans aucune requête réseau."""
    base = Path(settings.BASE_DIR) / "core" / "static" / "core"
    css = "\n".join((base / name).read_text(encoding="utf-8") for name in ("tokens.css", "rep.css") if (base / name).exists())
    font = base / "fonts" / "archivo-variable.woff2"
    if font.exists():
        data = base64.b64encode(font.read_bytes()).decode("ascii")
        css = css.replace('url("fonts/archivo-variable.woff2")', f'url("data:font/woff2;base64,{data}")')
    return css


def preview_document(fragment: str, theme: str = "light", title: str = "") -> str:
    css = _css()
    return (f'<!doctype html><html lang="fr" data-theme="{theme}"><head><meta charset="utf-8"><style>{css}'
            "body{margin:0;padding:20px;background:var(--surface);color:var(--ink);font-family:var(--font);}"
            ".pv-title{font:600 15px/1.3 var(--font);margin:0 0 12px}</style></head>"
            f'<body>{icon_sprite()}<div id="shot" style="display:inline-block;min-width:480px;max-width:1500px">'
            f'{f"<p class=pv-title>{title}</p>" if title else ""}{fragment}</div></body></html>')


def screenshot(document: str, width: int = 1280) -> tuple[bytes | None, str | None]:
    """Renvoie (png, None) ou (None, raison)."""
    key = hashlib.sha256(document.encode("utf-8")).hexdigest()
    if key in _CACHE:
        return _CACHE[key], None
    result: dict = {}

    def work():
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                try:
                    page = browser.new_page(viewport={"width": width, "height": 800}, device_scale_factor=2)
                    page.route("**/*", lambda route: route.abort() if route.request.url.startswith("http") else route.continue_())
                    page.set_content(document, wait_until="load")
                    page.evaluate("document.fonts.ready")
                    result["png"] = page.locator("#shot").screenshot(type="png")
                finally:
                    browser.close()
        except Exception as exc:  # navigateur absent, bac à sable, etc.
            result["error"] = f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"

    with _LOCK:
        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        thread.join(timeout=45)
    if "png" in result:
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = result["png"]
        return result["png"], None
    return None, result.get("error") or "Délai dépassé pendant la capture."


def as_base64(png: bytes) -> str:
    return base64.b64encode(png).decode("ascii")
