"""API REST de Demetra, destinée aux IA externes (et à tout client HTTP).

Authentification : en-tête « Authorization: Bearer <jeton personnel> ».
Mode d'emploi : GET /api/v1/guide (public). Document OpenAPI : /api/v1/openapi.json.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.dateparse import parse_datetime
from ninja import NinjaAPI, Query, Schema, Status
from ninja.errors import AuthenticationError, ValidationError
from ninja.security import HttpBearer
from pydantic import Field

from . import bricks, casemodel, connect, guide, parametric
from . import preview as pv
from . import services as svc
from .models import (
    AuditEvent,
    BrickRequest,
    Case,
    Decision,
    Membership,
    Representation,
    Role,
    ShareRequest,
    Study,
    Verdict,
)
from .recommend import recommend


class TokenAuth(HttpBearer):
    def authenticate(self, request: HttpRequest, token: str):
        actor = svc.authenticate_token(token)
        if actor:
            request.actor = actor
        return actor


api = NinjaAPI(
    title="Demetra — API pour IA externes",
    version="1",
    description=(
        "Déposer des règles et des cas, lire la couverture et les avis, composer des représentations avec "
        "des briques. "
        "Commencez par GET /api/v1/guide : le mode d'emploi y est servi sans authentification."
    ),
    auth=TokenAuth(),
    urls_namespace="api",
)


@api.exception_handler(svc.ServiceError)
def on_service_error(request, exc: svc.ServiceError):
    return JsonResponse(exc.payload(), status=exc.status, json_dumps_params={"ensure_ascii": False})


@api.exception_handler(AuthenticationError)
def on_auth_error(request, exc):
    return JsonResponse(
        svc.ServiceError(
            401,
            "unauthenticated",
            "Jeton absent, inconnu, expiré ou révoqué.",
            hint=(
                "Envoyez l'en-tête « Authorization: Bearer $DEMETRA_TOKEN » depuis un terminal (curl) : un "
                "outil de lecture "
                "de page web n'envoie pas d'en-tête. IA sans jeton : obtenez un accès par le lien "
                "d'autorisation "
                "(POST /api/v1/connect), ne demandez jamais le jeton dans la conversation et ne le mettez "
                "jamais dans "
                "une URL."
            ),
            guide="agents",
        ).payload(),
        status=401,
        json_dumps_params={"ensure_ascii": False},
    )


@api.exception_handler(ValidationError)
def on_validation_error(request, exc: ValidationError):
    details = [
        {
            "path": ".".join(str(p) for p in e.get("loc", [])[1:]) or "body",
            "code": e.get("type", "invalid"),
            "message": e.get("msg", ""),
        }
        for e in exc.errors
    ]
    return JsonResponse(
        svc.ServiceError(422, "validation_failed", "Requête mal formée.", details=details).payload(),
        status=422,
        json_dumps_params={"ensure_ascii": False},
    )


def actor_of(request) -> svc.Actor:
    return request.auth


# ---------------------------------------------------------------------------
# Schémas d'entrée
# ---------------------------------------------------------------------------


class StudyIn(Schema):
    title: str = Field(..., description="Titre de l'étude.")
    description: str = ""
    kind: str = Field("mixed", description="workflow | decision | temporal | mixed")
    statuses: list[dict] = Field(
        default_factory=list,
        description="Statuts possibles : [{key, label, role, short?, default?}]. role ∈ "
        + ", ".join(casemodel.ROLES),
    )
    dimensions: list[dict] = Field(
        default_factory=list,
        description="Facteurs qui varient d'un cas à l'autre : [{key, label, values: [...]}].",
    )
    rules: list[dict] = Field(
        default_factory=list, description="Règles de gestion : [{key, title, text, source?}]."
    )
    exclusions: list[dict] = Field(
        default_factory=list, description="Combinaisons impossibles : [{when: {dimension: valeur}, reason}]."
    )
    ruleset: dict | None = Field(
        None,
        description="Jeu de règles partagé par les cas : {policy, conditions: [{key, label}], rows: [{key, "
        "when, then}]}.",
    )
    lifecycles: list[dict] | None = Field(
        None,
        description="Cycles de vie par type d'entité : [{type, initial, transitions: [{from, to, label}]}].",
    )
    attributes: list[dict] | None = Field(
        None,
        description="Options portées par les entités (« attrs ») : [{key, label, text?}] — libellé lisible "
        "et définition.",
    )
    workshop: dict | None = Field(
        None,
        description="Atelier : {bricks: [{type, label, options, events}], links: [{type, label}], settings, "
        "rules: [{key, title, on?, when, then}], outcome} — chapitre « atelier » du mode d'emploi.",
    )


class StudyPatch(Schema):
    title: str | None = None
    description: str | None = None
    kind: str | None = None
    statuses: list[dict] | None = None
    dimensions: list[dict] | None = None
    rules: list[dict] | None = None
    exclusions: list[dict] | None = None
    ruleset: dict | None = None
    lifecycles: list[dict] | None = None
    attributes: list[dict] | None = None
    workshop: dict | None = None


class CasesIn(Schema):
    cases: list[dict] = Field(
        ...,
        description="Cas à créer ou mettre à jour, identifiés par leur clé stable « key ». Format : GET "
        "/api/v1/guide/cases.",
    )
    dry_run: bool = Field(False, description="true : valide et renvoie le diagnostic sans rien écrire.")
    atomic: bool = Field(False, description="true : n'écrit rien si un seul cas est invalide.")


class ShareRequestIn(Schema):
    user: str = Field(..., description="Nom d'utilisateur ou e-mail d'un compte existant.")
    role: str = Field("commenter", description="editor | commenter | viewer")
    message: str = ""


class RepresentationIn(Schema):
    name: str | None = None
    description: str = ""
    mode: str | None = Field(
        None,
        description="theme (nouveau thème, par défaut) | adjustment (ajustement personnel d'une "
        "représentation existante)",
    )
    parent: str | None = Field(None, description="Identifiant de la représentation de départ.")
    spec: dict | None = Field(None, description="Document complet (mode theme).")
    overrides: dict | None = Field(None, description="Ce qui change par rapport au parent.")
    manifest: dict | None = None


class RepresentationPatch(Schema):
    name: str | None = None
    description: str | None = None
    spec: dict | None = None
    overrides: dict | None = None
    note: str | None = None


class SpecIn(Schema):
    spec: dict


class ProposalIn(Schema):
    representation: str
    reason: str = ""


class ChoiceIn(Schema):
    representation: str | None = Field(
        None, description="Identifiant de la représentation ; null pour revenir au niveau du dessus."
    )
    level: str = Field(
        "study",
        description="study : pour toute l'étude (éditeur) ; me : pour moi sur cette étude ; case : pour moi "
        "sur un seul cas.",
    )
    case: str | None = Field(None, description="Clé du cas, quand level = case.")


class PreviewIn(Schema):
    representation: str | None = Field(None, description="Identifiant d'une représentation existante.")
    spec: dict | None = Field(
        None, description="Ou un document de représentation à essayer sans l'enregistrer."
    )
    step: int = Field(1, description="Étape à rendre (1 = première).")
    image: bool = Field(True, description="Joindre l'image PNG (base64).")
    theme: str = Field("light", description="light | dark")


class WorkshopRunIn(Schema):
    situation: dict = Field(
        ...,
        description="La situation construite : {elements: [{id, type, label?, options?, events?}], "
        "links: [{from, to, type}], settings?}.",
    )


class BrickRequestIn(Schema):
    title: str
    need: str
    family: str = ""
    example: dict | None = None
    study: str | None = None


class DuplicateIn(Schema):
    name: str | None = None


# ---------------------------------------------------------------------------
# Sérialisation
# ---------------------------------------------------------------------------


def study_out(study: Study, role: str | None = None, full: bool = True) -> dict:
    active = study.cases.filter(retired_at__isnull=True).count()
    out: dict[str, Any] = {
        "id": study.public_id,
        "title": study.title,
        "description": study.description,
        "kind": study.kind,
        "role": role or getattr(study, "my_role", None),
        "revision": study.revision,
        "example": study.is_example,
        "cases": active,
        "retired_cases": study.cases.filter(retired_at__isnull=False).count(),
        "updated_at": study.updated_at.isoformat(),
        "web_url": f"/etudes/{study.public_id}/",
    }
    if full:
        out.update(
            statuses=study.statuses,
            dimensions=study.dimensions,
            rules=study.rules,
            exclusions=study.exclusions,
            ruleset=study.ruleset or None,
            lifecycles=study.lifecycles or [],
            attributes=study.attributes or [],
            workshop=study.workshop or None,
            representation={"id": study.representation.public_id, "name": study.representation.name}
            if study.representation
            else None,
            review=svc.review_summary(study),
        )
    return out


def case_summary(case: Case, verdicts: dict | None = None) -> dict:
    content = case.content
    out = {
        "key": case.key,
        "number": case.number,
        "label": case.display_number,
        "family": case.family,
        "title": case.title,
        "kind": content.get("kind"),
        "dimensions": case.dimensions,
        "rules": content.get("rules", []),
        "entities": len(content.get("entities", [])),
        "steps": len(content.get("steps", [])),
        "revision": case.revision_no,
        "semantic_hash": case.content_hash[:12],
        "proof": content.get("proof", "asserted"),
        "retired": bool(case.retired_at),
        "updated_at": case.updated_at.isoformat(),
    }
    if verdicts is not None:
        out["verdicts"] = verdicts.get(case.pk, {"accepted": 0, "rejected": 0, "to_analyze": 0})
    return out


def representation_out(rep: Representation, full: bool = False) -> dict:
    spec = svc.resolved_spec(rep)
    out = {
        "id": rep.public_id,
        "slug": rep.slug,
        "name": rep.name,
        "description": rep.description,
        "scope": rep.scope,
        "version": rep.version,
        "owner": rep.owner.username if rep.owner else None,
        "parent": rep.parent.public_id if rep.parent else None,
        "editable": rep.scope != Representation.Scope.SYSTEM,
        "bricks": bricks.bricks_used(spec),
        "manifest": rep.manifest or {},
        "updated_at": rep.updated_at.isoformat(),
    }
    if full:
        out["spec"] = spec
        if rep.scope == Representation.Scope.ADJUSTMENT:
            out["overrides"] = rep.spec
    return out


def _verdict_counts(study: Study) -> dict:
    counts: dict[int, dict] = {}
    for case_id, decision in Verdict.objects.filter(case__study=study).values_list("case_id", "decision"):
        counts.setdefault(case_id, {"accepted": 0, "rejected": 0, "to_analyze": 0})[decision] += 1
    return counts


# ---------------------------------------------------------------------------
# Mode d'emploi et briques (publics)
# ---------------------------------------------------------------------------


@api.get("/guide", auth=None, tags=["Mode d'emploi"], summary="Mode d'emploi : sommaire et prise en main")
def guide_index(request, format: str = "json"):
    """À lire avant toute écriture. Sans authentification."""
    if format == "md":
        return HttpResponse(
            guide.full_markdown(_origin(request)), content_type="text/markdown; charset=utf-8"
        )
    return {
        "version": settings.DEMETRA_GUIDE_VERSION,
        "topics": guide.topics("/api/v1/guide/"),
        "start": guide.markdown("index", _origin(request)),
        "full_markdown": "/api/v1/guide?format=md",
        "openapi": "/api/v1/openapi.json",
        "llms_txt": "/llms.txt",
    }


@api.get("/guide/{topic}", auth=None, tags=["Mode d'emploi"], summary="Un chapitre du mode d'emploi")
def guide_topic(request, topic: str, format: str = "json"):
    if topic not in guide.TOPICS:
        raise svc.ServiceError(
            404,
            "not_found",
            f"Chapitre « {topic} » inconnu.",
            details=[{"path": "topic", "expected": list(guide.TOPICS)}],
        )
    if format == "md":
        return HttpResponse(
            guide.markdown(topic, _origin(request)), content_type="text/markdown; charset=utf-8"
        )
    return {
        "topic": topic,
        "title": guide.TOPICS[topic],
        "version": settings.DEMETRA_GUIDE_VERSION,
        "markdown": guide.markdown(topic, _origin(request)),
    }


def _origin(request) -> str:
    return request.build_absolute_uri("/").rstrip("/")


@api.get("/bricks", auth=None, tags=["Représentations"], summary="Catalogue des briques de représentation")
def bricks_catalog(request):
    return bricks.catalog_payload()


@api.get("/bricks/schema", auth=None, tags=["Représentations"], summary="Schéma JSON d'une représentation")
def bricks_schema(request):
    return bricks.json_schema()


# ---------------------------------------------------------------------------
# Compte
# ---------------------------------------------------------------------------


class ConnectIn(Schema):
    client_name: str = ""
    scopes: list[str] | None = None


class ConnectTokenIn(Schema):
    device_code: str


@api.post(
    "/connect",
    auth=None,
    tags=["Compte"],
    summary="Demander un accès par lien d'autorisation (sans jeton)",
    response={201: dict},
)
def connect_start(request, payload: ConnectIn):
    """Rend un lien à donner à la personne et un code secret (`device_code`) à garder pour soi. Voir le
    chapitre
    « Brancher une IA en sécurité »."""
    return Status(201, connect.start(payload.client_name, payload.scopes, _origin(request)))


@api.post(
    "/connect/token", auth=None, tags=["Compte"], summary="Récupérer le jeton une fois l'accès autorisé"
)
def connect_token(request, payload: ConnectTokenIn):
    """202 tant que la personne n'a pas autorisé ; 200 avec le jeton, une seule fois. Avec `Accept:
    text/plain`, le
    corps d'une réponse 200 est le jeton seul (pratique pour le ranger sans l'afficher) et les autres sont
    vides."""
    status, body = connect.fetch_token(payload.device_code)
    if "text/plain" in request.headers.get("Accept", ""):
        return HttpResponse(
            body.get("token", "") if status == 200 else "",
            status=status,
            content_type="text/plain; charset=utf-8",
        )
    return JsonResponse(body, status=status)


@api.get("/me", tags=["Compte"], summary="Qui suis-je, que peut ce jeton")
def me(request):
    actor = actor_of(request)
    token = actor.token
    return {
        "user": actor.user.username,
        "token": {
            "name": token.name,
            "scopes": token.scopes,
            "expires_at": token.expires_at.isoformat() if token.expires_at else None,
            "restricted_to_studies": [s.public_id for s in token.studies.all()] or None,
        },
        "cannot": [
            "rendre un avis (réservé aux humains)",
            "partager directement (demande confirmée par un humain)",
            "choisir la représentation affichée (l'utilisateur choisit)",
        ],
        "guide": "/api/v1/guide",
        "guide_version": settings.DEMETRA_GUIDE_VERSION,
    }


# ---------------------------------------------------------------------------
# Études
# ---------------------------------------------------------------------------


@api.get("/studies", tags=["Études"], summary="Lister mes études")
def list_studies(request):
    actor = actor_of(request)
    actor.require_scope("studies:read")
    roles = dict(Membership.objects.filter(user=actor.user).values_list("study_id", "role"))
    return {"items": [study_out(s, roles.get(s.pk), full=False) for s in svc.studies_for(actor)]}


@api.post("/studies", tags=["Études"], summary="Créer une étude", response={201: dict})
def create_study(request, payload: StudyIn):
    study = svc.create_study(actor_of(request), payload.dict())
    return Status(201, study_out(study))


@api.get(
    "/studies/{sid}",
    tags=["Études"],
    summary="Lire une étude : statuts, dimensions, règles, état de la revue",
)
def get_study(request, sid: str):
    return study_out(svc.get_study(actor_of(request), sid))


@api.patch("/studies/{sid}", tags=["Études"], summary="Modifier une étude (statuts, dimensions, règles…)")
def patch_study(request, sid: str, payload: StudyPatch):
    actor = actor_of(request)
    study = svc.get_study(actor, sid, Role.EDITOR, "studies:write")
    return study_out(svc.update_study(actor, study, payload.dict(exclude_unset=True)))


# ---------------------------------------------------------------------------
# Cas
# ---------------------------------------------------------------------------


@api.get("/studies/{sid}/cases", tags=["Cas"], summary="Lister les cas (vue sommaire, paginée)")
def list_cases(
    request,
    sid: str,
    family: str | None = None,
    verdict: str | None = None,
    q: str | None = None,
    changed_since: str | None = None,
    include_retired: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Filtres : family, verdict (accepted | rejected | to_analyze : au moins un relecteur), q (texte),
    changed_since (date ISO)."""
    study = svc.get_study(actor_of(request), sid)
    qs = study.cases.all() if include_retired else study.cases.filter(retired_at__isnull=True)
    if family:
        qs = qs.filter(family=family)
    if q:
        qs = qs.filter(title__icontains=q) | qs.filter(summary__icontains=q) | qs.filter(key__icontains=q)
    if changed_since:
        when = parse_datetime(changed_since)
        if not when:
            raise svc.ServiceError(
                422,
                "invalid",
                "« changed_since » doit être une date ISO 8601.",
                details=[{"path": "changed_since", "example": "2026-11-21T09:00:00+01:00"}],
            )
        qs = qs.filter(content_changed_at__gt=when)
    if verdict:
        if verdict not in Decision.values:
            raise svc.ServiceError(
                422,
                "invalid",
                "Valeur de « verdict » inconnue.",
                details=[{"path": "verdict", "expected": Decision.values}],
            )
        qs = qs.filter(verdicts__decision=verdict)
    qs = qs.distinct().order_by("number", "id")
    total = qs.count()
    counts = _verdict_counts(study)
    items = [case_summary(c, counts) for c in qs[offset : offset + limit]]
    nxt = offset + limit if offset + limit < total else None
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_offset": nxt,
        "families": sorted(set(study.cases.filter(retired_at__isnull=True).values_list("family", flat=True))),
    }


@api.post(
    "/studies/{sid}/cases/batch",
    tags=["Cas"],
    summary="Déposer un lot de cas (création ou mise à jour par clé stable)",
)
def batch_cases(request, sid: str, payload: CasesIn):
    """Rejouable : renvoyer le même lot ne change rien. En-tête facultatif « Idempotency-Key ».
    Chaque cas reçoit son résultat (created, updated, updated_cosmetic, unchanged, restored, error) ;
    les erreurs donnent le chemin, la règle, la valeur reçue et un exemple valide."""
    actor = actor_of(request)
    study = svc.get_study(actor, sid, Role.EDITOR, "studies:write")
    return svc.upsert_cases(
        actor,
        study,
        payload.cases,
        dry_run=payload.dry_run,
        atomic=payload.atomic,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )


@api.post("/studies/{sid}/cases/validate", tags=["Cas"], summary="Valider un lot à blanc, sans rien écrire")
def validate_cases(request, sid: str, payload: CasesIn):
    actor = actor_of(request)
    study = svc.get_study(actor, sid, Role.VIEWER, "studies:read")
    return svc.upsert_cases(actor, study, payload.cases, dry_run=True)


@api.get(
    "/studies/{sid}/cases/{key}", tags=["Cas"], summary="Lire un cas complet, ses états rejoués et ses avis"
)
def get_case(request, sid: str, key: str, frames: bool = True):
    study = svc.get_study(actor_of(request), sid)
    case = svc.get_case(study, key)
    out = case_summary(case, _verdict_counts(study))
    out["case"] = parametric.source_of(case.content)
    if parametric.is_parametric(case.content):
        out["parametric"] = {
            "combinations": [combo for combo, _ in parametric.expand(case.content)],
            "shown": "Les états rejoués ci-dessous sont ceux de la première combinaison.",
        }
    if frames:
        out["frames"] = [
            {
                "n": i + 1,
                "title": f["title"],
                "global": f["global"],
                "at": f["at"],
                "changed": f["changed"],
                "states": {k: v["status"] for k, v in f["states"].items()},
            }
            for i, f in enumerate(casemodel.replay(case.content, study.statuses))
        ]
    out["review"] = [f for f in svc.feedback(study) if f["case"] == case.key]
    return out


@api.delete(
    "/studies/{sid}/cases/{key}",
    tags=["Cas"],
    summary="Retirer un cas (il reste dans l'historique, avec ses avis)",
)
def retire_case(request, sid: str, key: str):
    actor = actor_of(request)
    study = svc.get_study(actor, sid, Role.EDITOR, "studies:write")
    case = svc.retire_case(actor, study, key)
    return {
        "key": case.key,
        "retired": True,
        "note": "Le cas est retiré, pas supprimé : POST …/restore le rétablit, ses avis sont conservés.",
    }


@api.post("/studies/{sid}/cases/{key}/restore", tags=["Cas"], summary="Rétablir un cas retiré")
def restore_case(request, sid: str, key: str):
    actor = actor_of(request)
    study = svc.get_study(actor, sid, Role.EDITOR, "studies:write")
    case = svc.restore_case(actor, study, key)
    return {"key": case.key, "retired": False}


@api.get("/studies/{sid}/cases/{key}/revisions", tags=["Cas"], summary="Historique des révisions d'un cas")
def case_revisions(request, sid: str, key: str):
    study = svc.get_study(actor_of(request), sid)
    case = svc.get_case(study, key)
    return {
        "items": [
            {
                "revision": r.number,
                "summary": r.summary,
                "semantic_change": r.semantic_change,
                "semantic_hash": r.content_hash[:12],
                "by": r.actor_user.username if r.actor_user else None,
                "via": "jeton" if r.actor_token_id else "interface",
                "at": r.created_at.isoformat(),
            }
            for r in case.revisions.select_related("actor_user")
        ]
    }


@api.post("/studies/{sid}/cases/{key}/verdict", tags=["Revue"], summary="Rendre un avis — refusé aux jetons")
def post_verdict(request, sid: str, key: str):
    """Toujours refusé (403) : un avis est rendu par un humain dans l'interface. Cette route existe pour le
    dire clairement."""
    actor = actor_of(request)
    study = svc.get_study(actor, sid)
    svc.set_verdict(actor, study, key, Decision.ACCEPTED)
    return {}


# ---------------------------------------------------------------------------
# Couverture, contrôles, revue
# ---------------------------------------------------------------------------


@api.get(
    "/studies/{sid}/coverage",
    tags=["Couverture"],
    summary="Couverture sur dimensions déclarées et combinaisons manquantes",
)
def coverage(request, sid: str, strength: int = Query(2, ge=1, le=3)):
    """strength = 1 : chaque valeur ; 2 : chaque paire de valeurs ; 3 : chaque triplet."""
    study = svc.get_study(actor_of(request), sid)
    return svc.coverage_report(study, strength)


@api.get(
    "/studies/{sid}/checks", tags=["Couverture"], summary="Contrôles de structure à l'échelle de l'étude"
)
def checks(request, sid: str):
    study = svc.get_study(actor_of(request), sid)
    findings = svc.checks_report(study)
    return {"findings": findings, "count": len(findings)}


@api.get("/studies/{sid}/verdicts", tags=["Revue"], summary="Lire les avis et commentaires des relecteurs")
def verdicts(
    request, sid: str, decision: str | None = None, since: str | None = None, commented: bool = False
):
    study = svc.get_study(actor_of(request), sid)
    when = parse_datetime(since) if since else None
    if since and not when:
        raise svc.ServiceError(422, "invalid", "« since » doit être une date ISO 8601.")
    if decision and decision not in Decision.values:
        raise svc.ServiceError(
            422,
            "invalid",
            "Valeur de « decision » inconnue.",
            details=[{"path": "decision", "expected": Decision.values}],
        )
    return {
        "summary": svc.review_summary(study),
        "items": svc.feedback(study, decision, when, commented),
        "labels": {d.value: d.label for d in Decision},
    }


@api.get(
    "/studies/{sid}/worklist",
    tags=["Revue"],
    summary="Ce qu'il reste à faire : cas refusés ou à analyser commentés, manques de couverture, alertes",
)
def worklist(request, sid: str):
    """Le point d'entrée d'une passe de correction : ne renvoie que ce qui appelle une action."""
    study = svc.get_study(actor_of(request), sid)
    items = svc.feedback(study)
    cover = svc.coverage_report(study, 2)
    return {
        "study_revision": study.revision,
        "rejected": [i for i in items if i["decision"] == Decision.REJECTED],
        "to_analyze_with_comment": [
            i for i in items if i["decision"] == Decision.TO_ANALYZE and i["comment"].strip()
        ],
        "coverage": {k: cover[k] for k in ("strength", "total", "covered", "missing_count", "ratio")}
        | {"missing_sample": cover["missing"][:20]},
        "checks": [f for f in svc.checks_report(study) if f["severity"] != "info"],
        "review": svc.review_summary(study),
    }


# ---------------------------------------------------------------------------
# Atelier
# ---------------------------------------------------------------------------


@api.get(
    "/studies/{sid}/workshop",
    tags=["Atelier"],
    summary="Les briques, les liens et la table de règles que l'étude déclare pour l'atelier",
)
def workshop_read(request, sid: str):
    study = svc.get_study(actor_of(request), sid)
    return svc.workshop_out(study)


@api.post(
    "/studies/{sid}/workshop/run",
    tags=["Atelier"],
    summary="Dérouler une situation construite avec les briques de l'étude, d'après ses règles",
)
def workshop_run(request, sid: str, payload: WorkshopRunIn):
    """Lecture seule : rien n'est écrit. Une situation de l'atelier ne reçoit jamais d'avis."""
    study = svc.get_study(actor_of(request), sid)
    return svc.workshop_run_out(study, payload.situation)


# ---------------------------------------------------------------------------
# Partage et audit
# ---------------------------------------------------------------------------


@api.get("/studies/{sid}/members", tags=["Partage"], summary="Qui a accès à l'étude")
def members(request, sid: str):
    study = svc.get_study(actor_of(request), sid)
    return {
        "items": [
            {"user": m.user.username, "role": m.role, "role_label": Role(m.role).label}
            for m in study.memberships.select_related("user")
        ]
    }


@api.post(
    "/studies/{sid}/share-requests",
    tags=["Partage"],
    summary="Demander un partage (en attente d'une confirmation humaine)",
    response={202: dict},
)
def post_share_request(request, sid: str, payload: ShareRequestIn):
    actor = actor_of(request)
    study = svc.get_study(actor, sid, Role.EDITOR, "share:request")
    req = svc.request_share(actor, study, payload.user, payload.role, payload.message)
    return Status(
        202,
        {
            "id": req.pk,
            "status": req.status,
            "user": req.invitee.username,
            "role": req.role,
            "note": "Demande enregistrée. Elle ne prend effet que lorsque le propriétaire la confirme dans "
            "l'interface (Étude › Partage).",
        },
    )


@api.get("/studies/{sid}/share-requests", tags=["Partage"], summary="Demandes de partage et leur état")
def get_share_requests(request, sid: str):
    study = svc.get_study(actor_of(request), sid)
    return {
        "items": [
            {
                "id": r.pk,
                "user": r.invitee.username,
                "role": r.role,
                "status": r.status,
                "status_label": ShareRequest.Status(r.status).label,
                "requested_by": r.requested_by.username,
                "via": "jeton" if r.via_token_id else "interface",
                "created_at": r.created_at.isoformat(),
            }
            for r in study.share_requests.select_related("invitee", "requested_by")
        ]
    }


@api.get(
    "/studies/{sid}/audit", tags=["Partage"], summary="Journal d'audit : qui (humain ou jeton) a fait quoi"
)
def audit_log(request, sid: str, limit: int = Query(50, ge=1, le=200)):
    study = svc.get_study(actor_of(request), sid)
    events = AuditEvent.objects.filter(study=study).select_related("actor_user", "actor_token")[:limit]
    return {
        "items": [
            {
                "at": e.created_at.isoformat(),
                "actor": e.actor_user.username if e.actor_user else None,
                "actor_kind": e.actor_kind,
                "token": e.actor_token.name if e.actor_token else None,
                "action": e.action,
                "target": e.target,
                "detail": e.detail,
            }
            for e in events
        ]
    }


# ---------------------------------------------------------------------------
# Représentations
# ---------------------------------------------------------------------------


@api.get(
    "/representations",
    tags=["Représentations"],
    summary="Représentations disponibles : système, les miennes, celles de mes études",
)
def list_representations(request):
    actor = actor_of(request)
    actor.require_scope("studies:read")
    return {
        "items": [
            representation_out(r) for r in svc.representations_for(actor).select_related("owner", "parent")
        ]
    }


@api.post(
    "/representations",
    tags=["Représentations"],
    summary="Créer une représentation : nouveau thème ou ajustement personnel",
    response={201: dict},
)
def create_representation(request, payload: RepresentationIn):
    rep = svc.create_representation(actor_of(request), payload.dict(exclude_none=True))
    return Status(201, representation_out(rep, full=True))


@api.post(
    "/representations/validate",
    tags=["Représentations"],
    summary="Valider un document de représentation sans l'enregistrer",
)
def validate_representation(request, payload: SpecIn):
    actor_of(request).require_scope("studies:read")
    report = svc.validate_representation(payload.spec)
    return {
        "valid": report.ok,
        "errors": [i.as_dict() for i in report.errors],
        "bricks": bricks.bricks_used(payload.spec) if report.ok else [],
    }


@api.get(
    "/representations/{rid}", tags=["Représentations"], summary="Lire une représentation et son document"
)
def get_representation(request, rid: str):
    actor = actor_of(request)
    actor.require_scope("studies:read")
    return representation_out(svc.get_representation(actor, rid), full=True)


@api.patch(
    "/representations/{rid}",
    tags=["Représentations"],
    summary="Ajuster une de mes représentations (nouvelle version)",
)
def patch_representation(request, rid: str, payload: RepresentationPatch):
    actor = actor_of(request)
    rep = svc.get_representation(actor, rid)
    return representation_out(
        svc.update_representation(actor, rep, payload.dict(exclude_none=True)), full=True
    )


@api.post(
    "/representations/{rid}/duplicate",
    tags=["Représentations"],
    summary="Dupliquer une représentation en nouveau thème",
    response={201: dict},
)
def duplicate_representation(request, rid: str, payload: DuplicateIn):
    actor = actor_of(request)
    rep = svc.get_representation(actor, rid)
    return Status(201, representation_out(svc.duplicate_representation(actor, rep, payload.name), full=True))


@api.delete(
    "/representations/{rid}", tags=["Représentations"], summary="Supprimer une de mes représentations"
)
def delete_representation(request, rid: str):
    actor = actor_of(request)
    actor.require_scope("representations:write")
    rep = svc.get_representation(actor, rid)
    svc.archive_representation(actor, rep)
    return {"id": rep.public_id, "deleted": True}


@api.get(
    "/studies/{sid}/representations/recommended",
    tags=["Représentations"],
    summary="Représentations recommandées pour cette étude, avec leurs raisons",
)
def recommended(request, sid: str):
    actor = actor_of(request)
    study = svc.get_study(actor, sid)
    candidates = svc.representations_for(actor).exclude(scope=Representation.Scope.ADJUSTMENT)
    result = recommend(study, candidates)
    result["proposed"] = [
        {
            "id": p.representation.public_id,
            "name": p.representation.name,
            "reason": p.reason,
            "by": p.proposed_by.username,
        }
        for p in study.proposals.filter(dismissed_at__isnull=True).select_related(
            "representation", "proposed_by"
        )
    ]
    current = svc.current_representation(actor.user, study)
    result["current"] = {"id": current.public_id, "name": current.name}
    return result


def _rep_ref(rep: Representation | None) -> dict | None:
    return {"id": rep.public_id, "slug": rep.slug, "name": rep.name} if rep else None


def _choice_out(actor, study: Study) -> dict:
    choices = svc.representation_choices(actor.user, study)
    effective = svc.current_representation(actor.user, study)
    return {
        "principle": "Une étude a une représentation. Chacun peut en changer pour lui (me), pour un seul cas "
        "(case), ou pour toute l'étude (study, éditeur).",
        "study": _rep_ref(choices["study"]),
        "study_chosen_by": choices["study_by"] or None,
        "me": _rep_ref(choices["mine"]),
        "cases": [{"case": case.key, "representation": _rep_ref(rep)} for case, rep in choices["cases"]],
        "effective": _rep_ref(effective),
    }


@api.get(
    "/studies/{sid}/representation",
    tags=["Représentations"],
    summary="Représentation de l'étude, et ce que j'ai choisi pour moi ou pour un cas",
)
def get_choice(request, sid: str):
    actor = actor_of(request)
    return _choice_out(actor, svc.get_study(actor, sid))


@api.put(
    "/studies/{sid}/representation",
    tags=["Représentations"],
    summary="Choisir la représentation : pour l'étude, pour moi, ou pour un cas",
)
def put_choice(request, sid: str, payload: ChoiceIn):
    """level = study fixe la représentation de toute l'étude (rôle éditeur) : c'est le geste de l'IA qui
    dépose une étude.
    Si un humain a déjà choisi dans l'interface, le jeton reçoit 409 human_choice et propose à la place."""
    actor = actor_of(request)
    if payload.level not in ("study", "me", "case"):
        raise svc.ServiceError(
            422,
            "invalid",
            "« level » vaut study, me ou case.",
            details=[{"path": "level", "received": payload.level, "expected": ["study", "me", "case"]}],
            guide="representations",
        )
    study = svc.get_study(
        actor, sid, Role.EDITOR if payload.level == "study" else Role.VIEWER, "representations:write"
    )
    rep = svc.get_representation(actor, payload.representation) if payload.representation else None
    case = None
    if payload.level == "case":
        if not payload.case:
            raise svc.ServiceError(
                422,
                "invalid",
                "Pour level = case, indiquez la clé du cas dans « case ».",
                details=[{"path": "case", "example": "chaine-simple"}],
                guide="representations",
            )
        case = svc.get_case(study, payload.case, include_retired=False)
    svc.choose_representation(actor, study, rep, for_study=payload.level == "study", case=case)
    study.refresh_from_db()
    return _choice_out(actor, study)


@api.post(
    "/studies/{sid}/representations/proposals",
    tags=["Représentations"],
    summary="Proposer une représentation à l'utilisateur pour cette étude",
    response={201: dict},
)
def propose(request, sid: str, payload: ProposalIn):
    actor = actor_of(request)
    study = svc.get_study(actor, sid, Role.EDITOR, "representations:write")
    rep = svc.get_representation(actor, payload.representation)
    proposal = svc.propose_representation(actor, study, rep, payload.reason)
    return Status(
        201,
        {
            "id": proposal.pk,
            "representation": rep.public_id,
            "name": rep.name,
            "note": "Proposition affichée à l'utilisateur dans Étude › Représentation. C'est lui qui "
            "choisit.",
        },
    )


@api.post(
    "/studies/{sid}/cases/{key}/preview",
    tags=["Représentations"],
    summary="Aperçu d'un cas dans une représentation : image et résumé textuel",
)
def preview(request, sid: str, key: str, payload: PreviewIn):
    """Fournir « representation » (existante) ou « spec » (à l'essai). Le résumé textuel décrit ce qui est
    dessiné,
    ce qui est tronqué ou absent ; l'image PNG est jointe en base64 si le serveur dispose de Chromium."""
    actor = actor_of(request)
    study = svc.get_study(actor, sid)
    case = svc.get_case(study, key, include_retired=False)
    if payload.spec is not None:
        report = svc.validate_representation(payload.spec)
        if not report.ok:
            raise svc.ServiceError(
                422,
                "validation_failed",
                "La représentation à l'essai n'est pas valide.",
                details=[i.as_dict() for i in report.errors],
                guide="representations",
            )
        spec, name = payload.spec, "(à l'essai)"
    elif payload.representation:
        rep = svc.get_representation(actor, payload.representation)
        spec, name = svc.resolved_spec(rep), rep.name
    else:
        rep = svc.current_representation(actor.user, study, case)
        spec, name = svc.resolved_spec(rep), rep.name
    html, summary, frames = svc.render_case(study, case, spec, step=max(0, payload.step - 1))
    out = {"case": case.key, "representation": name, "summary": summary, "image": None}
    if payload.image:
        document = pv.preview_document(html, "dark" if payload.theme == "dark" else "light")
        png, error = pv.screenshot(document)
        if png:
            out["image"] = {
                "media_type": "image/png",
                "encoding": "base64",
                "bytes": len(png),
                "data": pv.as_base64(png),
            }
        else:
            out["image_unavailable"] = f"Image non produite ({error}). Le résumé textuel reste valable."
    return out


@api.post(
    "/bricks/requests",
    tags=["Représentations"],
    summary="Signaler une brique manquante",
    response={201: dict},
)
def post_brick_request(request, payload: BrickRequestIn):
    actor = actor_of(request)
    study = svc.get_study(actor, payload.study) if payload.study else None
    req = svc.report_missing_brick(actor, payload.dict(exclude_none=True), study)
    return Status(
        201,
        {
            "id": req.pk,
            "title": req.title,
            "status": req.status,
            "note": "Signalement enregistré : il alimente la liste des évolutions du site. En attendant, "
            "composez avec les briques existantes.",
        },
    )


@api.get("/bricks/requests", tags=["Représentations"], summary="Briques manquantes déjà signalées")
def get_brick_requests(request):
    actor = actor_of(request)
    actor.require_scope("studies:read")
    return {
        "items": [
            {
                "id": r.pk,
                "title": r.title,
                "need": r.need,
                "family": r.family,
                "status": r.status,
                "by": r.user.username,
                "created_at": r.created_at.isoformat(),
            }
            for r in BrickRequest.objects.select_related("user")[:100]
        ]
    }
