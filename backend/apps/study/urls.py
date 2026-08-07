from django.urls import path

from . import views

urlpatterns = [
    # Participant flow (public)
    path("session/start/", views.StartSessionView.as_view(), name="session-start"),
    path("session/<uuid:public_id>/", views.SessionView.as_view(), name="session"),
    path(
        "session/<uuid:public_id>/consent/",
        views.ConsentView.as_view(),
        name="session-consent",
    ),
    path(
        "session/<uuid:public_id>/feedback/initial/",
        views.InitialFeedbackView.as_view(),
        name="session-feedback-initial",
    ),
    path(
        "session/<uuid:public_id>/feedback/chat/",
        views.AssistantChatView.as_view(),
        name="session-feedback-chat",
    ),
    path(
        "session/<uuid:public_id>/feedback/final-draft/",
        views.FinalDraftView.as_view(),
        name="session-feedback-final-draft",
    ),
    path(
        "session/<uuid:public_id>/feedback/final/",
        views.FinalFeedbackView.as_view(),
        name="session-feedback-final",
    ),
    path(
        "session/<uuid:public_id>/survey/",
        views.SurveyView.as_view(),
        name="session-survey",
    ),
    # Researcher dashboard
    path("research/overview/", views.OverviewView.as_view(), name="research-overview"),
    path(
        "research/responses/",
        views.ResponseListView.as_view(),
        name="research-responses",
    ),
    path(
        "research/responses/<int:pk>/",
        views.ResponseDetailView.as_view(),
        name="research-response-detail",
    ),
    path(
        "research/responses/<int:pk>/ratings/",
        views.RatingCreateView.as_view(),
        name="research-rating-create",
    ),
    path("research/export.csv", views.ExportView.as_view(), name="research-export"),
]
