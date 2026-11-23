"""Administration de Demetra (/admin/) : exploitation du site, pas relecture.

On y gère les comptes, les accès aux études, les jetons, et on lit le journal et les signalements. Le contenu
(cas, avis, représentations, définitions) n'y est pas modifiable : il passe par l'API ou l'interface, qui
le valident et l'historisent. Chaque geste qui touche une étude est inscrit dans son historique.
"""

from __future__ import annotations

from datetime import timedelta

from allauth.account.models import EmailAddress
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from . import models
from .models import AuditEvent, Role

User = get_user_model()

admin.site.site_header = "Administration Demetra"
admin.site.site_title = "Administration Demetra"
admin.site.index_title = "Exploitation du site"
admin.site.site_url = "/etudes/"
admin.site.empty_value_display = "—"

# Pas de suppression en masse : supprimer un compte efface aussi ses études. On désactive ; la suppression
# reste possible une par une, après l'écran de confirmation qui liste tout ce qui partira avec.
admin.site.disable_action("delete_selected")

# Ni groupes Django (les droits viennent des rôles d'étude), ni adresses allauth (pas de vérification d'e-mail).
for model in (Group, EmailAddress, User):
    if admin.site.is_registered(model):
        admin.site.unregister(model)


def _audit(request, study, action, target="", **detail):
    AuditEvent.objects.create(study=study, actor_user=request.user, channel="admin", action=action,
                              target=str(target)[:200], detail=detail)


class ReadOnlyAdmin(admin.ModelAdmin):
    """Consultation seule : ni ajout, ni modification, ni suppression."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


def _study_link(study):
    if not study:
        return "—"
    return format_html('<a href="{}">{}</a>', reverse("admin:core_study_change", args=[study.pk]), study.title)


def _token_state(token) -> str:
    if token.revoked_at:
        return "révoqué"
    if token.expires_at and token.expires_at <= timezone.now():
        return "expiré"
    return "actif"


# ----- Comptes -----

class ExternalIdentityInline(admin.TabularInline):
    model = models.ExternalIdentity
    extra = 0
    can_delete = True
    fields = ("issuer", "subject", "created_at", "last_login_at")
    readonly_fields = fields
    verbose_name = "identité SSO"
    verbose_name_plural = "Identités SSO (supprimer délie le compte de l'annuaire)"

    def has_add_permission(self, request, obj=None):
        return False


class TokenInline(admin.TabularInline):
    model = models.ApiToken
    extra = 0
    can_delete = False
    fields = ("name", "token_display", "scopes", "state", "last_used_at", "expires_at")
    readonly_fields = fields
    verbose_name_plural = "Jetons d'API (révocation : liste des jetons)"

    @admin.display(description="jeton")
    def token_display(self, obj):
        return obj.display

    @admin.display(description="état")
    def state(self, obj):
        return _token_state(obj)

    def has_add_permission(self, request, obj=None):
        return False


class SSOFilter(admin.SimpleListFilter):
    title = "connexion"
    parameter_name = "sso"

    def lookups(self, request, model_admin):
        return (("1", "Par le SSO"), ("0", "Sans SSO"))

    def queryset(self, request, queryset):
        if self.value() == "1":
            return queryset.filter(external_identities__isnull=False).distinct()
        if self.value() == "0":
            return queryset.filter(external_identities__isnull=True)
        return queryset


@admin.register(User)
class DemetraUserAdmin(UserAdmin):
    list_display = ("username", "email", "full_name", "is_active", "is_staff", "owned", "active_tokens", "sso",
                    "last_login", "date_joined")
    list_filter = ("is_active", "is_staff", "is_superuser", SSOFilter)
    search_fields = ("username", "email", "first_name", "last_name", "external_identities__subject")
    ordering = ("-date_joined",)
    inlines = (ExternalIdentityInline, TokenInline)
    actions = ("deactivate",)
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Identité", {"fields": ("first_name", "last_name", "email")}),
        ("Droits", {"fields": ("is_active", "is_staff", "is_superuser"),
                    "description": "« Équipe » ouvre cette administration ; « superutilisateur » y donne tous les "
                                   "droits. Avec le SSO ou le LDAP, ces deux cases suivent le groupe d'administration "
                                   "à chaque connexion."}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )

    def get_queryset(self, request):
        now = timezone.now()
        return super().get_queryset(request).annotate(
            n_owned=Count("owned_studies", filter=Q(owned_studies__archived_at__isnull=True), distinct=True),
            n_tokens=Count("api_tokens", filter=Q(api_tokens__revoked_at__isnull=True)
                           & (Q(api_tokens__expires_at__isnull=True) | Q(api_tokens__expires_at__gt=now)), distinct=True),
            n_sso=Count("external_identities", distinct=True))

    @admin.display(description="nom")
    def full_name(self, obj):
        return obj.get_full_name() or "—"

    @admin.display(description="études possédées", ordering="n_owned")
    def owned(self, obj):
        return obj.n_owned

    @admin.display(description="jetons actifs", ordering="n_tokens")
    def active_tokens(self, obj):
        return obj.n_tokens

    @admin.display(description="SSO", boolean=True)
    def sso(self, obj):
        return obj.n_sso > 0

    @admin.action(description="Désactiver les comptes choisis et révoquer leurs jetons")
    def deactivate(self, request, queryset):
        queryset = queryset.exclude(pk=request.user.pk)
        now = timezone.now()
        with transaction.atomic():
            tokens = models.ApiToken.objects.filter(user__in=queryset, revoked_at__isnull=True)
            n_tokens = tokens.update(revoked_at=now)
            n_users = queryset.update(is_active=False)
        self.message_user(request, f"{n_users} compte(s) désactivé(s), {n_tokens} jeton(s) révoqué(s). Leurs études "
                                   "restent en place : transférez-les depuis la liste des études.", messages.SUCCESS)


# ----- Études et accès -----

class MembershipInline(admin.TabularInline):
    model = models.Membership
    extra = 0
    fields = ("user", "role", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("user",)
    verbose_name = "accès"
    verbose_name_plural = "Accès (le propriétaire se change plus haut)"

    def get_queryset(self, request):
        return super().get_queryset(request).exclude(role=Role.OWNER).select_related("user")

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "role":
            kwargs["choices"] = [(r.value, r.label) for r in Role if r != Role.OWNER]
        return super().formfield_for_choice_field(db_field, request, **kwargs)


class ArchivedFilter(admin.SimpleListFilter):
    title = "état"
    parameter_name = "etat"

    def lookups(self, request, model_admin):
        return (("active", "En cours"), ("archived", "Archivée"))

    def queryset(self, request, queryset):
        if self.value() == "active":
            return queryset.filter(archived_at__isnull=True)
        if self.value() == "archived":
            return queryset.filter(archived_at__isnull=False)
        return queryset


@admin.register(models.Study)
class StudyAdmin(admin.ModelAdmin):
    list_display = ("title", "public_id", "owner", "kind", "n_cases", "n_members", "is_example", "archived",
                    "updated_at", "open_link")
    list_filter = (ArchivedFilter, "kind", "is_example")
    search_fields = ("title", "public_id", "owner__username", "owner__email")
    list_select_related = ("owner",)
    autocomplete_fields = ("owner",)
    inlines = (MembershipInline,)
    actions = ("archive", "unarchive")
    fieldsets = (
        (None, {"fields": ("title", "public_id", "owner", "open_link")}),
        ("Repères", {"fields": ("kind", "is_example", "revision", "representation", "archived_at", "created_at",
                                "updated_at")}),
    )
    readonly_fields = ("public_id", "open_link", "kind", "is_example", "revision", "representation", "archived_at",
                       "created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            cases_n=Count("cases", filter=Q(cases__retired_at__isnull=True), distinct=True),
            members_n=Count("memberships", distinct=True))

    def has_add_permission(self, request):
        return False  # une étude se crée dans l'interface ou par l'API

    @admin.display(description="cas", ordering="cases_n")
    def n_cases(self, obj):
        return obj.cases_n

    @admin.display(description="membres", ordering="members_n")
    def n_members(self, obj):
        return obj.members_n

    @admin.display(description="archivée", boolean=True, ordering="archived_at")
    def archived(self, obj):
        return obj.archived_at is not None

    @admin.display(description="dans Demetra")
    def open_link(self, obj):
        if not obj.pk:
            return "—"
        return format_html('<a href="{}">Ouvrir</a>', reverse("workspace", args=[obj.public_id]))

    def save_model(self, request, obj, form, change):
        if change and "owner" in form.changed_data:
            previous = models.Study.objects.get(pk=obj.pk).owner
            with transaction.atomic():
                super().save_model(request, obj, form, change)
                models.Membership.objects.filter(study=obj, user=previous, role=Role.OWNER).update(role=Role.EDITOR)
                models.Membership.objects.update_or_create(study=obj, user=obj.owner, defaults={"role": Role.OWNER})
                _audit(request, obj, "admin.transfer", obj.owner.username, previous=previous.username,
                       owner=obj.owner.username)
            self.message_user(request, f"Étude transférée à {obj.owner.username} ; {previous.username} en reste "
                                       "éditeur (retirez son accès plus bas si besoin).", messages.SUCCESS)
            return
        if "title" in form.changed_data:
            _audit(request, obj, "study.update", obj.title, fields=["title"])
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        study = form.instance
        for inline_form in formset.forms:
            if not inline_form.has_changed():
                continue
            member = inline_form.instance
            if inline_form in formset.deleted_forms:
                if member.pk:
                    _audit(request, study, "share.revoke", member.user.username)
            elif member.pk is None:
                _audit(request, study, "share.grant", inline_form.cleaned_data["user"].username,
                       role=inline_form.cleaned_data["role"])
            elif "role" in inline_form.changed_data:
                _audit(request, study, "share.change", member.user.username, role=inline_form.cleaned_data["role"])
        super().save_formset(request, form, formset, change)

    @admin.action(description="Archiver les études choisies")
    def archive(self, request, queryset):
        for study in queryset.filter(archived_at__isnull=True):
            study.archived_at = timezone.now()
            study.save(update_fields=["archived_at"])
            _audit(request, study, "study.archive", study.title)

    @admin.action(description="Désarchiver les études choisies")
    def unarchive(self, request, queryset):
        for study in queryset.filter(archived_at__isnull=False):
            study.archived_at = None
            study.save(update_fields=["archived_at"])
            _audit(request, study, "admin.unarchive", study.title)


# ----- Jetons -----

class TokenStateFilter(admin.SimpleListFilter):
    title = "état"
    parameter_name = "etat"

    def lookups(self, request, model_admin):
        return (("active", "Actif"), ("revoked", "Révoqué"), ("expired", "Expiré"))

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == "active":
            return queryset.filter(revoked_at__isnull=True).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        if self.value() == "revoked":
            return queryset.filter(revoked_at__isnull=False)
        if self.value() == "expired":
            return queryset.filter(revoked_at__isnull=True, expires_at__lte=now)
        return queryset


@admin.register(models.ApiToken)
class ApiTokenAdmin(ReadOnlyAdmin):
    list_display = ("name", "token_display", "user", "scopes", "state", "last_used_at", "expires_at", "created_at")
    list_filter = (TokenStateFilter,)
    search_fields = ("name", "token_id", "user__username")
    list_select_related = ("user",)
    actions = ("revoke",)
    exclude = ("token_hash",)

    @admin.display(description="jeton")
    def token_display(self, obj):
        return obj.display

    @admin.display(description="état")
    def state(self, obj):
        return _token_state(obj)

    @admin.action(description="Révoquer les jetons choisis", permissions=["view"])
    def revoke(self, request, queryset):
        n = 0
        for token in queryset.filter(revoked_at__isnull=True).select_related("user"):
            token.revoked_at = timezone.now()
            token.save(update_fields=["revoked_at"])
            _audit(request, None, "token.revoke", token.name, token=token.display, owner=token.user.username)
            n += 1
        self.message_user(request, f"{n} jeton(s) révoqué(s). Les IA qui les utilisaient reçoivent désormais 401.",
                          messages.SUCCESS)


# ----- Signalements -----

@admin.register(models.BrickRequest)
class BrickRequestAdmin(admin.ModelAdmin):
    list_display = ("title", "family", "user", "study_link", "status", "created_at")
    list_filter = ("status", "family")
    search_fields = ("title", "need", "user__username")
    list_select_related = ("user", "study")
    list_editable = ("status",)
    fields = ("title", "need", "family", "example", "user", "via_token", "study", "status", "created_at")
    readonly_fields = ("title", "need", "family", "example", "user", "via_token", "study", "created_at")

    def has_add_permission(self, request):
        return False

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "status":
            from django import forms
            return forms.ChoiceField(choices=[("open", "À traiter"), ("planned", "Prévu"), ("done", "Fait"),
                                              ("declined", "Écarté")], label="état")
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @admin.display(description="étude")
    def study_link(self, obj):
        return _study_link(obj.study)


# ----- Consultation seule -----

@admin.register(models.AuditEvent)
class AuditEventAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "who", "actor_kind_label", "channel", "action_label", "target", "study_link")
    list_filter = ("channel", "action", ("study", admin.EmptyFieldListFilter))
    search_fields = ("action", "target", "actor_user__username", "study__title", "study__public_id")
    list_select_related = ("actor_user", "actor_token", "study")
    date_hierarchy = "created_at"

    @admin.display(description="action", ordering="action")
    def action_label(self, obj):
        from .views import ACTION_LABELS
        return ACTION_LABELS.get(obj.action, obj.action)

    @admin.display(description="qui", ordering="actor_user__username")
    def who(self, obj):
        return obj.actor_user.username if obj.actor_user else "—"

    @admin.display(description="par")
    def actor_kind_label(self, obj):
        return f"jeton « {obj.actor_token.name} »" if obj.actor_token else obj.actor_kind

    @admin.display(description="étude")
    def study_link(self, obj):
        return _study_link(obj.study)


@admin.register(models.Case)
class CaseAdmin(ReadOnlyAdmin):
    list_display = ("display_number", "title", "family", "study_link", "revision_no", "retired", "updated_at")
    list_filter = (("retired_at", admin.EmptyFieldListFilter),)
    search_fields = ("title", "key", "family", "study__title", "study__public_id")
    list_select_related = ("study",)
    exclude = ("content", "dimensions")

    @admin.display(description="n°")
    def display_number(self, obj):
        return obj.display_number

    @admin.display(description="retiré", boolean=True)
    def retired(self, obj):
        return obj.retired_at is not None

    @admin.display(description="étude")
    def study_link(self, obj):
        return _study_link(obj.study)


@admin.register(models.Verdict)
class VerdictAdmin(ReadOnlyAdmin):
    list_display = ("case", "reviewer", "decision", "stale_from", "updated_at")
    list_filter = ("decision",)
    search_fields = ("case__title", "case__study__title", "reviewer__username", "comment")
    list_select_related = ("case", "case__study", "reviewer")


@admin.register(models.Representation)
class RepresentationAdmin(ReadOnlyAdmin):
    list_display = ("name", "scope", "owner", "version", "archived", "updated_at")
    list_filter = ("scope", ("archived_at", admin.EmptyFieldListFilter))
    search_fields = ("name", "slug", "public_id", "owner__username")
    list_select_related = ("owner",)
    exclude = ("spec", "manifest")

    @admin.display(description="supprimée", boolean=True)
    def archived(self, obj):
        return obj.archived_at is not None


@admin.register(models.RepresentationProposal)
class ProposalAdmin(ReadOnlyAdmin):
    list_display = ("study", "representation", "proposed_by", "dismissed_at", "created_at")
    list_select_related = ("study", "representation", "proposed_by")


@admin.register(models.ShareRequest)
class ShareRequestAdmin(ReadOnlyAdmin):
    list_display = ("study", "invitee", "role", "requested_by", "status", "decided_by", "created_at")
    list_filter = ("status", "role")
    search_fields = ("study__title", "invitee__username", "requested_by__username")
    list_select_related = ("study", "invitee", "requested_by", "decided_by")


@admin.register(models.ExternalIdentity)
class ExternalIdentityAdmin(admin.ModelAdmin):
    list_display = ("user", "subject", "issuer", "created_at", "last_login_at")
    search_fields = ("user__username", "user__email", "subject")
    list_filter = ("issuer",)
    list_select_related = ("user",)
    readonly_fields = ("user", "issuer", "subject", "created_at", "last_login_at")

    def has_add_permission(self, request):
        return False


# ----- Tableau de bord -----

_index = admin.site.index


def _dashboard(request, extra_context=None):
    now = timezone.now()
    week = now - timedelta(days=7)
    tokens_active = models.ApiToken.objects.filter(revoked_at__isnull=True).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    figures = [
        ("Comptes actifs", User.objects.filter(is_active=True).count(), "admin:auth_user_changelist", "is_active__exact=1"),
        ("Connectés cette semaine", User.objects.filter(last_login__gte=week).count(), "admin:auth_user_changelist", ""),
        ("Études en cours", models.Study.objects.filter(archived_at__isnull=True).count(), "admin:core_study_changelist", "etat=active"),
        ("Jetons actifs", tokens_active.count(), "admin:core_apitoken_changelist", "etat=active"),
        ("Signalements à traiter", models.BrickRequest.objects.filter(status="open").count(), "admin:core_brickrequest_changelist", "status=open"),
        ("Événements, 7 jours", AuditEvent.objects.filter(created_at__gte=week).count(), "admin:core_auditevent_changelist", ""),
    ]
    context = {"demetra_figures": [{"label": label, "value": value,
                                    "url": reverse(name) + (f"?{query}" if query else "")}
                                   for label, value, name, query in figures],
               **(extra_context or {})}
    return _index(request, context)


admin.site.index = _dashboard
