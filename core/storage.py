"""Fichiers statiques en développement : une version dans l'adresse, pour que le navigateur reprenne un
fichier modifié au lieu de garder l'ancien en cache.

En production, `collectstatic` et le manifeste de WhiteNoise mettent déjà une empreinte dans le nom de chaque
fichier (`DEMETRA_STATIC_MANIFEST=1`). Sans eux, l'adresse reste la même d'une modification à l'autre : on y
ajoute la date de modification du fichier (`?v=…`).
"""

from __future__ import annotations

import os

from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import StaticFilesStorage


class VersionedStaticFilesStorage(StaticFilesStorage):
    def url(self, name: str | None) -> str:
        url = super().url(name)
        path = finders.find(name) if name else None
        if isinstance(path, str) and os.path.isfile(path):
            url += f"?v={int(os.path.getmtime(path))}"
        return url
