"""Modèle de données de Demetra.

Tout ce qui porte identité, droits et avis est relationnel ; le contenu d'un cas
(entités, liens, étapes) est un document JSON validé à l'entrée (voir core/casemodel.py).
"""

import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

User = settings.AUTH_USER_MODEL

_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"


def short_id(length: int = 10) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


class Role(models.TextChoices):
    OWNER = "owner", "Propriétaire"
    EDITOR = "editor", "Éditeur"
    COMMENTER = "commenter", "Commentateur"
    VIEWER = "viewer", "Lecteur"


ROLE_RANK = {Role.VIEWER: 1, Role.COMMENTER: 2, Role.EDITOR: 3, Role.OWNER: 4}


class Study(models.Model):
    class Kind(models.TextChoices):
        WORKFLOW = "workflow", "Workflows et états"
        DECISION = "decision", "Règles de décision"
        TEMPORAL = "temporal", "Règles temporelles"
        MIXED = "mixed", "Mixte"

    public_id = models.CharField(max_length=16, unique=True, default=short_id, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_studies")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.MIXED)
    statuses = models.JSONField(default=list, blank=True)
    dimensions = models.JSONField(default=list, blank=True)
    exclusions = models.JSONField(default=list, blank=True)
    rules = models.JSONField(default=list, blank=True)
    ruleset = models.JSONField(
        default=dict,
        blank=True,
        help_text="Jeu de règles partagé par les cas : conditions, lignes, politique de résolution.",
    )
    lifecycles = models.JSONField(
        default=list, blank=True, help_text="Cycles de vie déclarés par type d'entité : transitions permises."
    )
    attributes = models.JSONField(
        default=list, blank=True, help_text="Options portées par les entités : libellé lisible et définition."
    )
    workshop = models.JSONField(
        default=dict,
        blank=True,
        help_text="Atelier : briques, liens et table de règles que le site exécute sur une situation.",
    )
    representation = models.ForeignKey(
        "Representation", null=True, blank=True, on_delete=models.SET_NULL, related_name="default_for"
    )
    representation_by = models.CharField(
        max_length=8,
        blank=True,
        default="",
        help_text="Qui a fixé la représentation de l'étude : « ai » (par jeton) ou « human » (dans "
        "l'interface).",
    )
    revision = models.PositiveIntegerField(default=0)
    is_example = models.BooleanField(
        default=False, help_text="Étude d'exemple aux données fictives : affichée comme telle."
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "étude"
        verbose_name_plural = "études"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title


class Membership(models.Model):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=12, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "accès"
        verbose_name_plural = "accès"
        constraints = [models.UniqueConstraint(fields=["study", "user"], name="uniq_membership")]

    def __str__(self):
        return f"{self.user} · {self.get_role_display().lower()}"


class ApiToken(models.Model):
    """Jeton personnel d'accès à l'API. Le secret n'est jamais stocké : seul son condensé l'est."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_tokens")
    name = models.CharField(max_length=80)
    token_id = models.CharField(max_length=16, unique=True)
    token_hash = models.CharField(max_length=64)
    scopes = models.JSONField(default=list)
    studies = models.ManyToManyField(Study, blank=True, related_name="restricted_tokens")
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "jeton d'API"
        verbose_name_plural = "jetons d'API"
        ordering = ["-created_at"]

    @property
    def is_active(self) -> bool:
        if self.revoked_at:
            return False
        return not (self.expires_at and self.expires_at <= timezone.now())

    @property
    def display(self) -> str:
        return f"{settings.DEMETRA_TOKEN_PREFIX}_{self.token_id}_…"

    def __str__(self):
        return f"{self.name} ({self.display})"


class ShareRequest(models.Model):
    """Partage demandé par un jeton : reste en attente tant qu'un humain ne l'a pas confirmé dans
    l'interface."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        CONFIRMED = "confirmed", "Confirmé"
        REJECTED = "rejected", "Refusé"

    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="share_requests")
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    via_token = models.ForeignKey(
        ApiToken, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    invitee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="share_requests")
    role = models.CharField(max_length=12, choices=Role.choices)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "demande de partage"
        verbose_name_plural = "demandes de partage"
        ordering = ["-created_at"]


class Case(models.Model):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="cases")
    key = models.CharField(max_length=80)
    number = models.PositiveIntegerField(default=0)
    family = models.CharField(max_length=120, default="Général")
    title = models.CharField(max_length=300)
    summary = models.TextField(blank=True)
    content = models.JSONField(default=dict)
    dimensions = models.JSONField(default=dict, blank=True)
    content_hash = models.CharField(max_length=64)
    revision_no = models.PositiveIntegerField(default=1)
    retired_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    content_changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "cas"
        verbose_name_plural = "cas"
        ordering = ["number", "id"]
        constraints = [models.UniqueConstraint(fields=["study", "key"], name="uniq_case_key")]

    def __str__(self):
        return f"{self.display_number} · {self.title}"

    @property
    def display_number(self) -> str:
        return (self.content or {}).get("label") or f"{self.number:02d}"


class CaseRevision(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="revisions")
    number = models.PositiveIntegerField()
    payload = models.JSONField()
    content_hash = models.CharField(max_length=64)
    semantic_change = models.BooleanField(default=True)
    summary = models.CharField(max_length=300, blank=True)
    actor_user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    actor_token = models.ForeignKey(
        ApiToken, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    channel = models.CharField(max_length=8, default="web")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]


class Decision(models.TextChoices):
    TO_ANALYZE = "to_analyze", "À analyser"
    ACCEPTED = "accepted", "Validé"
    REJECTED = "rejected", "Refusé"


class Verdict(models.Model):
    """Avis d'un relecteur sur un cas. Attaché à l'empreinte du contenu jugé."""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="verdicts")
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verdicts")
    decision = models.CharField(max_length=12, choices=Decision.choices, default=Decision.TO_ANALYZE)
    comment = models.TextField(blank=True)
    content_hash = models.CharField(max_length=64, blank=True)
    stale_from = models.CharField(max_length=12, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "avis"
        verbose_name_plural = "avis"
        constraints = [models.UniqueConstraint(fields=["case", "reviewer"], name="uniq_verdict")]


class VerdictEvent(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="verdict_events")
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    decision = models.CharField(max_length=12, choices=Decision.choices)
    comment = models.TextField(blank=True)
    content_hash = models.CharField(max_length=64, blank=True)
    reason = models.CharField(max_length=12, default="review")  # review | reset
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class Representation(models.Model):
    class Scope(models.TextChoices):
        SYSTEM = "system", "Système"
        THEME = "theme", "Thème"
        ADJUSTMENT = "adjustment", "Ajustement personnel"

    public_id = models.CharField(max_length=16, unique=True, default=short_id, editable=False)
    slug = models.SlugField(max_length=60, blank=True)
    owner = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.CASCADE, related_name="representations"
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    scope = models.CharField(max_length=12, choices=Scope.choices, default=Scope.THEME)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    spec = models.JSONField(default=dict)
    manifest = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)
    via_token = models.ForeignKey(
        ApiToken, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "représentation"
        verbose_name_plural = "représentations"
        ordering = ["scope", "name"]

    def __str__(self):
        return self.name


class RepresentationVersion(models.Model):
    representation = models.ForeignKey(Representation, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()
    spec = models.JSONField()
    note = models.CharField(max_length=300, blank=True)
    actor_user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    actor_token = models.ForeignKey(
        ApiToken, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version"]


class RepresentationProposal(models.Model):
    """Représentation proposée (en général par l'IA) pour une étude ; l'utilisateur choisit dans
    l'interface."""

    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="proposals")
    representation = models.ForeignKey(Representation, on_delete=models.CASCADE, related_name="proposals")
    proposed_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    via_token = models.ForeignKey(
        ApiToken, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reason = models.TextField(blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "proposition de représentation"
        verbose_name_plural = "propositions de représentation"
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["study", "representation"], name="uniq_proposal")]


class StudyPreference(models.Model):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="preferences")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="study_preferences")
    representation = models.ForeignKey(
        Representation, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["study", "user"], name="uniq_preference")]


class CasePreference(models.Model):
    """Représentation choisie par un relecteur pour un seul cas ; elle passe avant son choix pour l'étude."""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="preferences")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="case_preferences")
    representation = models.ForeignKey(Representation, on_delete=models.CASCADE, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["case", "user"], name="uniq_case_preference")]


class BrickRequest(models.Model):
    """Brique manquante signalée par une IA ou un utilisateur : alimente la liste des évolutions du site."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="brick_requests")
    via_token = models.ForeignKey(
        ApiToken, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    study = models.ForeignKey(
        Study, null=True, blank=True, on_delete=models.SET_NULL, related_name="brick_requests"
    )
    title = models.CharField(max_length=160)
    need = models.TextField()
    family = models.CharField(max_length=24, blank=True)
    example = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=12, default="open")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "signalement de brique"
        verbose_name_plural = "signalements de brique"
        ordering = ["-created_at"]


class AuditEvent(models.Model):
    study = models.ForeignKey(
        Study, null=True, blank=True, on_delete=models.CASCADE, related_name="audit_events"
    )
    actor_user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    actor_token = models.ForeignKey(
        ApiToken, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    channel = models.CharField(max_length=8, default="web")  # web | api | system
    action = models.CharField(max_length=60)
    target = models.CharField(max_length=200, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "événement du journal"
        verbose_name_plural = "journal"
        ordering = ["-created_at", "-id"]

    @property
    def actor_kind(self) -> str:
        return "jeton" if self.actor_token_id else ("système" if self.channel == "system" else "humain")


class ExternalIdentity(models.Model):
    """Lien entre un compte Demetra et une identité de l'annuaire d'entreprise (SSO OpenID Connect).

    Le compte est retrouvé par l'émetteur et l'identifiant stable (« sub ») du fournisseur, jamais par
    l'e-mail :
    une adresse modifiable chez le fournisseur ne doit pas ouvrir le compte de quelqu'un d'autre.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="external_identities")
    issuer = models.CharField(max_length=300)
    subject = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "identité SSO"
        verbose_name_plural = "identités SSO"
        constraints = [models.UniqueConstraint(fields=["issuer", "subject"], name="uniq_external_identity")]

    def __str__(self) -> str:
        return f"{self.subject} @ {self.issuer}"


class ConnectRequest(models.Model):
    """Demande d'accès d'une IA par lien d'autorisation (même principe que « gh auth login »).

    L'IA demande un lien ; l'utilisateur l'ouvre, connecté, et autorise ; l'IA récupère alors un jeton, une
    seule
    fois, avec le code secret reçu au départ. Le site ne garde que le condensé de ce code, jamais de jeton en
    clair :
    le jeton est créé au moment où l'IA vient le chercher.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Autorisée"
        DENIED = "denied", "Refusée"
        CONSUMED = "consumed", "Jeton remis"

    device_hash = models.CharField(max_length=64, unique=True)
    user_code = models.CharField(max_length=9)
    client_name = models.CharField(max_length=60)
    requested_scopes = models.JSONField(default=list)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    scopes = models.JSONField(default=list, blank=True)
    study_ids = models.JSONField(default=list, blank=True)
    days = models.PositiveIntegerField(null=True, blank=True)
    token = models.ForeignKey(ApiToken, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_poll_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "demande de connexion d'IA"
        verbose_name_plural = "demandes de connexion d'IA"


class IdempotencyRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    key = models.CharField(max_length=120)
    endpoint = models.CharField(max_length=120)
    request_hash = models.CharField(max_length=64)
    response = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "key", "endpoint"], name="uniq_idempotency")]


class SiteNotice(models.Model):
    """Ce que l'administrateur ajoute au mode d'emploi : une seule ligne (pk=1), modifiée dans /admin/.

    `message` paraît en tête de /llms.txt et des chapitres « Prise en main » et « Brancher une IA », comme un
    message de l'administrateur du site. `project_lines` s'ajoute au bloc que la personne copie dans le
    fichier d'instructions de son projet : c'est là qu'une IA lit une consigne de son propre projet."""

    message = models.TextField(
        blank=True,
        help_text=(
            "Affiché en tête de /llms.txt et du mode d'emploi, présenté comme un message de l'administrateur "
            "de ce site. Exemple : qui contacter, ce que l'organisation a validé. "
            "Pas de secret : c'est public."
        ),
    )
    project_lines = models.TextField(
        blank=True,
        help_text=(
            "Une consigne par ligne, ajoutée au bloc « Instructions permanentes pour l'IA » que chacun copie "
            "dans le fichier d'instructions de son projet (CLAUDE.md, AGENTS.md, copilot-instructions.md). "
            "Exemple : « Demetra (ce site) est validé par la DSI pour recevoir les cas tirés de ce code. »"
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = "message de l'organisation"
        verbose_name_plural = "message de l'organisation"

    def __str__(self) -> str:
        return "Message de l'organisation"

    @classmethod
    def current(cls) -> SiteNotice | None:
        return cls.objects.filter(pk=1).first()


# Libellés français des champs, lus par l'administration (/admin/).
def _labels(model, **labels):
    for name, label in labels.items():
        model._meta.get_field(name).verbose_name = label


_COMMON = {"created_at": "créé le", "updated_at": "modifié le"}
_labels(
    Study,
    title="titre",
    owner="propriétaire",
    kind="nature",
    public_id="identifiant",
    revision="révision",
    representation="représentation",
    is_example="exemple",
    archived_at="archivée le",
    **_COMMON,
)
_labels(Membership, study="étude", user="compte", role="rôle", created_at="depuis le")
_labels(
    ApiToken,
    user="compte",
    name="nom",
    scopes="portées",
    studies="études autorisées",
    expires_at="expire le",
    last_used_at="dernier usage",
    revoked_at="révoqué le",
    created_at="créé le",
    token_id="identifiant",
)
_labels(
    ShareRequest,
    study="étude",
    requested_by="demandé par",
    via_token="par le jeton",
    invitee="invité",
    role="rôle",
    status="état",
    decided_by="décidé par",
    decided_at="décidé le",
    created_at="demandé le",
)
_labels(
    Case,
    study="étude",
    key="clé",
    number="numéro",
    family="famille",
    title="titre",
    summary="résumé",
    content_hash="empreinte",
    revision_no="révision",
    retired_at="retiré le",
    content_changed_at="contenu modifié le",
    **_COMMON,
)
_labels(
    Verdict,
    case="cas",
    reviewer="relecteur",
    decision="avis",
    comment="commentaire",
    content_hash="empreinte",
    stale_from="ancien avis",
    updated_at="rendu le",
)
_labels(
    Representation,
    slug="nom court",
    owner="propriétaire",
    name="nom",
    scope="portée",
    parent="dérivée de",
    version="version",
    via_token="par le jeton",
    archived_at="supprimée le",
    public_id="identifiant",
    **_COMMON,
)
_labels(
    RepresentationProposal,
    study="étude",
    representation="représentation",
    proposed_by="proposée par",
    via_token="par le jeton",
    reason="raison",
    dismissed_at="écartée le",
    created_at="proposée le",
)
_labels(
    BrickRequest,
    user="compte",
    via_token="par le jeton",
    study="étude",
    title="titre",
    need="besoin",
    family="famille",
    example="exemple",
    status="état",
    created_at="signalé le",
)
_labels(
    AuditEvent,
    study="étude",
    actor_user="compte",
    actor_token="jeton",
    channel="canal",
    action="action",
    target="objet",
    detail="détail",
    created_at="le",
)
_labels(
    ExternalIdentity,
    user="compte",
    issuer="émetteur",
    subject="identifiant chez le fournisseur",
    created_at="lié le",
    last_login_at="dernière connexion",
)
_labels(
    SiteNotice,
    message="message aux lecteurs du mode d'emploi",
    project_lines="consignes à copier dans chaque projet",
    updated_at="modifié le",
    updated_by="modifié par",
)
