"""Fichiers statiques : en développement, l'adresse change quand le fichier change."""

from __future__ import annotations

import os
import re
from pathlib import Path

from django.templatetags.static import static

APP_JS = Path(__file__).resolve().parents[1] / "core" / "static" / "core" / "app.js"


def test_a_static_address_carries_the_file_date():
    stamp = int(os.path.getmtime(APP_JS))
    assert static("core/app.js") == f"/static/core/app.js?v={stamp}"


def test_the_address_changes_when_the_file_changes():
    before = static("core/app.js")
    stat = APP_JS.stat()
    try:
        os.utime(APP_JS, (stat.st_atime, stat.st_mtime + 60))
        assert static("core/app.js") != before
    finally:
        os.utime(APP_JS, (stat.st_atime, stat.st_mtime))


def test_an_unknown_file_keeps_a_plain_address():
    assert static("core/absent.js") == "/static/core/absent.js"


def test_pages_ask_for_the_versioned_script(client):
    page = client.get("/comptes/login/").content.decode()
    assert re.search(r'src="/static/core/app\.js\?v=\d+"', page)
    assert re.search(r'href="/static/core/app\.css\?v=\d+"', page)
