"""Charge les données de démonstration : comptes, catalogue importé, étude de décision, étude temporelle,
et une étude d'exemple par représentation du catalogue élargi (règles et processus)."""

import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core import services as svc
from core.demo import catalogue, decision, elargi, temporal
from core.models import Decision, Membership, Representation, Role, Study

PASSWORD = "demetra-demo"
USERS = [("demo", "demo@demetra.test"), ("lea", "lea@demetra.test"), ("marc", "marc@demetra.test")]


LEA_COMMENTS = {
    "workflow": "Ce cas me paraît incomplet : que se passe-t-il si l'élément suivant est désactivé ?",
    "decision": "À confirmer avec le service client : la règle écrite ne dit pas cela pour ce type de client.",
    "temporal": "Le délai me semble compté en jours ouvrés dans nos procédures, pas en jours calendaires.",
}


class Command(BaseCommand):
    help = "Crée les comptes et les douze études de démonstration : le catalogue et onze exemples à données fictives (rejouable sans doublon)."

    def add_arguments(self, parser):
        parser.add_argument("--token", action="store_true", help="Crée aussi un jeton d'API pour « demo » et l'affiche une fois.")
        parser.add_argument("--no-verdicts", action="store_true", help="Ne pose aucun avis de démonstration.")
        parser.add_argument("--password-env", metavar="VARIABLE",
                            help="Lit le mot de passe des comptes de démonstration dans cette variable d'environnement "
                                 "(appliqué aussi aux comptes existants). Obligatoire quand DEMETRA_DEBUG=0.")

    def handle(self, *args, **options):
        password, from_env = PASSWORD, False
        if options["password_env"]:
            password, from_env = os.environ.get(options["password_env"], ""), True
            if len(password) < 12:
                raise CommandError(f"La variable {options['password_env']} est vide ou trop courte (12 caractères au moins).")
        elif settings.DEMETRA_PRODUCTION:
            raise CommandError("En production, le mot de passe public de démonstration est refusé : "
                               "passez --password-env NOM_DE_VARIABLE.")
        svc.ensure_system_representations()
        User = get_user_model()
        users = {}
        for username, email in USERS:
            user, created = User.objects.get_or_create(username=username, defaults={"email": email})
            if created or from_env:
                user.set_password(password)
                user.save()
            users[username] = user
        demo = svc.Actor(users["demo"])

        data = catalogue.load()
        # Le catalogue vient d'un prototype réel ; les deux autres études sont des exemples aux données fictives.
        studies = [
            (catalogue.study_definition(data), catalogue.cases(data), False, None),
            (decision.DEFINITION, decision.cases(), True, None),
            (temporal.DEFINITION, temporal.cases(), True, None),
            # Une étude par représentation du catalogue élargi : elle porte la représentation qu'elle illustre.
            *[(definition, build(), True, slug) for slug, definition, build in elargi.STUDIES],
        ]
        for definition, cases, is_example, slug in studies:
            study = Study.objects.filter(owner=users["demo"], title=definition["title"], archived_at__isnull=True).first()
            if study is None:
                study = svc.create_study(demo, definition)
            else:
                study.my_role = Role.OWNER
                svc.update_study(demo, study, {k: definition.get(k) for k in ("statuses", "dimensions", "rules", "exclusions", "description", "ruleset", "lifecycles", "attributes")
                                               if k in definition or k in ("statuses", "dimensions", "rules", "exclusions", "description")})
            if study.is_example != is_example:
                Study.objects.filter(pk=study.pk).update(is_example=is_example)
            if slug and study.representation_id is None:
                rep = Representation.objects.get(scope=Representation.Scope.SYSTEM, slug=slug)
                Study.objects.filter(pk=study.pk).update(representation=rep)
            counts = {}
            for start in range(0, len(cases), 100):
                result = svc.upsert_cases(demo, study, cases[start:start + 100])
                for key, value in result["counts"].items():
                    counts[key] = counts.get(key, 0) + value
                for item in result["results"]:
                    if item["status"] == "error":
                        self.stderr.write(f"  {item['key']}: {item['errors'][:2]}")
            Membership.objects.get_or_create(study=study, user=users["lea"], defaults={"role": Role.COMMENTER})
            families = study.cases.values_list("family", flat=True).distinct().count()
            steps = sum(len(c.content["steps"]) for c in study.cases.all())
            self.stdout.write(f"« {study.title} » [{study.public_id}] : {study.cases.count()} cas, {families} familles, {steps} étapes — {counts}")
            if not options["no_verdicts"]:
                self._verdicts(study, users)

        shown = f"mot de passe lu dans {options['password_env']}" if from_env else f"mot de passe : {PASSWORD}"
        self.stdout.write(f"Comptes : {', '.join(u for u, _ in USERS)} — {shown}")
        if options["token"]:
            _, secret = svc.create_token(users["demo"], "Démonstration", list(svc.SCOPES), days=30)
            self.stdout.write(f"Jeton d'API (affiché une seule fois) : {secret}")

    def _verdicts(self, study, users):
        """Quelques avis pour que la revue ne parte pas d'une page vide."""
        cases = list(study.cases.filter(retired_at__isnull=True).order_by("number"))
        if study.cases.filter(verdicts__isnull=False).exists():
            return
        demo, lea = svc.Actor(users["demo"]), svc.Actor(users["lea"])
        study.my_role = Role.OWNER
        for index, case in enumerate(cases[: max(4, len(cases) // 3)]):
            if index % 9 == 4:
                svc.set_verdict(demo, study, case.key, Decision.REJECTED, "Le dernier état ne correspond pas à ce que j'observe : à revoir avec l'équipe.")
            elif index % 7 == 5:
                svc.set_verdict(demo, study, case.key, Decision.TO_ANALYZE, "Je ne suis pas sûr de l'ordre des deux dernières étapes.")
            else:
                svc.set_verdict(demo, study, case.key, Decision.ACCEPTED)
        for index, case in enumerate(cases[:6]):
            svc.set_verdict(lea, study, case.key, Decision.REJECTED if index == 2 else Decision.ACCEPTED,
                            LEA_COMMENTS.get(study.kind, LEA_COMMENTS["workflow"]) if index == 2 else "")
