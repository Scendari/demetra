from django.urls import path

from . import connect, views

urlpatterns = [
    path("", views.home, name="home"),
    path("llms.txt", views.llms_txt, name="llms_txt"),
    path("guide/", views.guide_page, name="guide"),
    path("guide/<slug:topic>/", views.guide_page, name="guide_topic"),
    path("briques/", views.bricks_page, name="bricks"),
    path("etudes/", views.studies, name="studies"),
    path("etudes/<str:sid>/", views.workspace, name="workspace"),
    path("etudes/<str:sid>/etat/", views.study_state, name="study_state"),
    path("etudes/<str:sid>/events", views.study_events, name="study_events"),
    path("etudes/<str:sid>/cas/<str:key>/panneau/", views.case_panel, name="case_panel"),
    path("etudes/<str:sid>/cas/<str:key>/avis/", views.case_verdict, name="case_verdict"),
    path("etudes/<str:sid>/couverture/", views.study_coverage, name="study_coverage"),
    path("etudes/<str:sid>/representation/", views.study_representations, name="study_representations"),
    path("etudes/<str:sid>/partage/", views.study_sharing, name="study_sharing"),
    path("etudes/<str:sid>/historique/", views.study_history, name="study_history"),
    path("etudes/<str:sid>/definitions/", views.study_setup, name="study_setup"),
    path("compte/jetons/", views.tokens, name="tokens"),
    path("connecter/", connect.approve_page, name="connect"),
]
