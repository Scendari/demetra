"""Sonde de santé : GET /sante/ rend 200 si la base répond, 503 sinon.

Traitée tout en haut de la pile, avant la vérification d'hôte et la redirection HTTPS : la sonde du conteneur
appelle http://127.0.0.1:8000/sante/, qui serait sinon refusée (hôte non autorisé) ou redirigée vers HTTPS.
Elle ne dit rien d'autre que « ok » : aucune information sur le site n'en sort.
"""

from django.db import connection
from django.http import HttpResponse


class HealthMiddleware:
    path = "/sante/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path != self.path:
            return self.get_response(request)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            response = HttpResponse("base indisponible\n", status=503, content_type="text/plain; charset=utf-8")
        else:
            response = HttpResponse("ok\n", content_type="text/plain; charset=utf-8")
        response["Cache-Control"] = "no-store"
        return response
