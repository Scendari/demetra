"""Vide la corbeille : efface les études supprimées depuis plus de DEMETRA_TRASH_DAYS jours.

Le site le fait déjà de lui-même à l'ouverture de la liste des études ; cette commande sert à un cron
quotidien, pour qu'une étude oubliée soit effacée à date même si personne ne se connecte."""

from django.conf import settings
from django.core.management.base import BaseCommand

from core import services as svc


class Command(BaseCommand):
    help = (
        "Efface les études restées à la corbeille plus de DEMETRA_TRASH_DAYS "
        f"({settings.DEMETRA_TRASH_DAYS}) jours."
    )

    def handle(self, *args, **options):
        count = svc.purge_expired()
        self.stdout.write(f"{count} étude(s) effacée(s) de la corbeille.")
