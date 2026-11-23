from django.contrib import admin
from django.urls import include, path

from core import sso
from core.api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("comptes/sso/", sso.start, name="sso_start"),
    path("comptes/sso/retour/", sso.callback, name="sso_callback"),
    path("comptes/", include("allauth.urls")),
    path("api/v1/", api.urls),
    path("", include("core.urls")),
]
