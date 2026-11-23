"""Copie à chaud de la base SQLite : `manage.py sauvegarde /backup --keep-days 30`.

Utilise l'API de sauvegarde de sqlite3 (cohérente même pendant les écritures, mode WAL compris), vérifie la
copie par `PRAGMA integrity_check`, puis efface les sauvegardes plus anciennes que --keep-days. Affiche le
chemin du fichier produit sur la sortie standard ; code de sortie non nul en cas d'échec.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

PREFIX = "demetra-"
SUFFIX = ".sqlite3"


class Command(BaseCommand):
    help = "Sauvegarde à chaud la base SQLite dans un dossier, vérifie la copie et purge les anciennes."

    def add_arguments(self, parser):
        parser.add_argument("dossier", help="Dossier de destination (par exemple /backup).")
        parser.add_argument("--keep-days", type=int, default=30,
                            help="Efface les sauvegardes de plus de N jours (0 : ne rien effacer). Défaut : 30.")

    def handle(self, *args, dossier, keep_days, **options):
        db = settings.DATABASES["default"]
        if db["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("La sauvegarde ne traite que la base SQLite.")
        source = Path(db["NAME"])
        if not source.exists():
            raise CommandError(f"Base introuvable : {source}")
        target_dir = Path(dossier)
        if not target_dir.is_dir():
            raise CommandError(f"Dossier de destination introuvable : {target_dir}")

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        final = target_dir / f"{PREFIX}{stamp}{SUFFIX}"
        partial = target_dir / f".{final.name}.partiel"
        try:
            with closing(sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30)) as src, \
                    closing(sqlite3.connect(partial)) as dst:
                src.backup(dst, pages=1024, sleep=0.05)
            with closing(sqlite3.connect(partial)) as check:
                result = check.execute("PRAGMA integrity_check").fetchone()[0]
                check.execute("PRAGMA journal_mode=DELETE")
            if result != "ok":
                raise CommandError(f"Copie corrompue (integrity_check : {result}).")
            partial.replace(final)
        except (sqlite3.Error, OSError) as exc:
            raise CommandError(f"Sauvegarde impossible : {exc}") from exc
        finally:
            partial.unlink(missing_ok=True)

        if keep_days > 0:
            limit = time.time() - keep_days * 86400
            for old in target_dir.glob(f"{PREFIX}*{SUFFIX}"):
                if old != final and old.stat().st_mtime < limit:
                    old.unlink()
        self.stdout.write(str(final))
