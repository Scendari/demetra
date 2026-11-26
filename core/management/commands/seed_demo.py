"""Charge les données de démonstration : comptes, catalogue importé, étude de décision, étude temporelle,
et une étude d'exemple par représentation du catalogue élargi (règles et processus)."""

import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core import services as svc
from core.demo import catalogue, circuit, decision, elargi, magasin, parametre, temporal
from core.models import Decision, Membership, Representation, Role, Study

PASSWORD = "demetra-demo"
USERS = [("demo", "demo@demetra.test"), ("lea", "lea@demetra.test"), ("marc", "marc@demetra.test")]


LEA_COMMENTS = {
    "workflow": "Ce cas me paraît incomplet : que se passe-t-il si l'élément suivant est désactivé ?",
    "decision": "À confirmer avec le service client : la règle écrite ne dit pas cela pour ce type de "
    "client.",
    "temporal": "Le délai me semble compté en jours ouvrés dans nos procédures, pas en jours calendaires.",
}


class Command(BaseCommand):
    help = (
        "Crée les comptes et les quatorze études de démonstration : le catalogue et treize exemples à "
        "données fictives (rejouable sans doublon)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--token",
            action="store_true",
            help="Crée aussi un jeton d'API pour « demo » et l'affiche une fois.",
        )
        parser.add_argument("--no-verdicts", action="store_true", help="Ne pose aucun avis de démonstration.")
        parser.add_argument(
            "--password-env",
            metavar="VARIABLE",
            help="Lit le mot de passe des comptes de démonstration dans cette variable d'environnement "
            "(appliqué aussi aux comptes existants). Obligatoire quand DEMETRA_DEBUG=0.",
        )

    def handle(self, *args, **options):
        password, from_env = self._password(options)
        svc.ensure_system_representations()
        users = self._users(password, from_env)
        demo = svc.Actor(users["demo"])
        for definition, cases, is_example, slug in self._studies():
            study = self._sync_study(demo, users, definition, is_example, slug)
            counts = self._load_cases(demo, study, cases)
            Membership.objects.get_or_create(
                study=study, user=users["lea"], defaults={"role": Role.COMMENTER}
            )
            families = study.cases.values_list("family", flat=True).distinct().count()
            steps = sum(len(c.content["steps"]) for c in study.cases.all())
            self.stdout.write(
                f"« {study.title} » [{study.public_id}] : {study.cases.count()} cas, {families} familles, "
                f"{steps} étapes — {counts}"
            )
            if not options["no_verdicts"]:
                self._verdicts(study, users)

        shown = (
            f"mot de passe lu dans {options['password_env']}" if from_env else f"mot de passe : {PASSWORD}"
        )
        self.stdout.write(f"Comptes : {', '.join(u for u, _ in USERS)} — {shown}")
        if options["token"]:
            _, secret = svc.create_token(users["demo"], "Démonstration", list(svc.SCOPES), days=30)
            self.stdout.write(f"Jeton d'API (affiché une seule fois) : {secret}")

    @staticmethod
    def _password(options) -> tuple[str, bool]:
        """Le mot de passe des comptes de démonstration, et s'il vient de l'environnement."""
        if options["password_env"]:
            password = os.environ.get(options["password_env"], "")
            if len(password) < 12:
                raise CommandError(
                    f"La variable {options['password_env']} est vide ou trop courte (12 caractères au moins)."
                )
            return password, True
        if settings.DEMETRA_PRODUCTION:
            raise CommandError(
                "En production, le mot de passe public de démonstration est refusé : "
                "passez --password-env NOM_DE_VARIABLE."
            )
        return PASSWORD, False

    @staticmethod
    def _users(password: str, from_env: bool) -> dict:
        User = get_user_model()
        users = {}
        for username, email in USERS:
            user, created = User.objects.get_or_create(username=username, defaults={"email": email})
            if created or from_env:
                user.set_password(password)
                user.save()
            users[username] = user
        return users

    @staticmethod
    def _studies() -> list[tuple]:
        """(définition, cas, est un exemple, représentation imposée) pour chaque étude de démonstration."""
        data = catalogue.load()
        # Le catalogue vient d'un prototype réel ; les autres études sont des exemples aux données
        # fictives.
        return [
            (catalogue.study_definition(data), catalogue.cases(data), False, None),
            (decision.DEFINITION, decision.cases(), True, None),
            (temporal.DEFINITION, temporal.cases(), True, None),
            (parametre.DEFINITION, parametre.cases(), True, None),
            (circuit.DEFINITION, circuit.cases(), True, None),
            # L'atelier de périodes se lit sur une frise : l'étude porte cette représentation.
            (magasin.DEFINITION, magasin.cases(), True, "frise-temporelle"),
            # Une étude par représentation du catalogue élargi : elle porte la représentation qu'elle
            # illustre.
            *[(definition, build(), True, slug) for slug, definition, build in elargi.STUDIES],
        ]

    @staticmethod
    def _sync_study(demo, users: dict, definition: dict, is_example: bool, slug: str | None) -> Study:
        """Crée l'étude ou remet ses définitions à jour, sans toucher aux cas."""
        study = Study.objects.filter(
            owner=users["demo"], title=definition["title"], archived_at__isnull=True
        ).first()
        if study is not None and study.deleted_at:  # mise à la corbeille : la démonstration la rétablit
            Study.objects.filter(pk=study.pk).update(deleted_at=None, deleted_by=None)
            study.deleted_at = None
        if study is None:
            study = svc.create_study(demo, definition)
        else:
            study.my_role = Role.OWNER
            always = ("statuses", "dimensions", "rules", "exclusions", "description")
            svc.update_study(
                demo,
                study,
                {
                    k: definition.get(k)
                    for k in (*always, "ruleset", "lifecycles", "attributes", "workshop")
                    if k in definition or k in always
                },
            )
        if study.is_example != is_example:
            Study.objects.filter(pk=study.pk).update(is_example=is_example)
        if slug and study.representation_id is None:
            rep = Representation.objects.get(scope=Representation.Scope.SYSTEM, slug=slug)
            Study.objects.filter(pk=study.pk).update(representation=rep)
        return study

    def _load_cases(self, demo, study: Study, cases: list[dict]) -> dict:
        """Dépose les cas par lots de 100 ; rend les comptes par statut."""
        counts: dict = {}
        for start in range(0, len(cases), 100):
            result = svc.upsert_cases(demo, study, cases[start : start + 100])
            for key, value in result["counts"].items():
                counts[key] = counts.get(key, 0) + value
            for item in result["results"]:
                if item["status"] == "error":
                    self.stderr.write(f"  {item['key']}: {item['errors'][:2]}")
        return counts

    def _verdicts(self, study, users):
        """Quelques avis pour que la revue ne parte pas d'une page vide."""
        cases = list(study.cases.filter(retired_at__isnull=True).order_by("number"))
        if study.cases.filter(verdicts__isnull=False).exists():
            return
        demo, lea = svc.Actor(users["demo"]), svc.Actor(users["lea"])
        study.my_role = Role.OWNER
        for index, case in enumerate(cases[: max(4, len(cases) // 3)]):
            if index % 9 == 4:
                svc.set_verdict(
                    demo,
                    study,
                    case.key,
                    Decision.REJECTED,
                    "Le dernier état ne correspond pas à ce que j'observe : à revoir avec l'équipe.",
                )
            elif index % 7 == 5:
                svc.set_verdict(
                    demo,
                    study,
                    case.key,
                    Decision.TO_ANALYZE,
                    "Je ne suis pas sûr de l'ordre des deux dernières étapes.",
                )
            else:
                svc.set_verdict(demo, study, case.key, Decision.ACCEPTED)
        for index, case in enumerate(cases[:6]):
            svc.set_verdict(
                lea,
                study,
                case.key,
                Decision.REJECTED if index == 2 else Decision.ACCEPTED,
                LEA_COMMENTS.get(study.kind, LEA_COMMENTS["workflow"]) if index == 2 else "",
            )
