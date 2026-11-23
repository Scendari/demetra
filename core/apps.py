from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _load_system_representations(sender, **kwargs):
    from .services import ensure_system_representations
    ensure_system_representations()


class CoreConfig(AppConfig):
    name = "core"
    verbose_name = "Demetra"

    def ready(self):
        post_migrate.connect(_load_system_representations, sender=self)
