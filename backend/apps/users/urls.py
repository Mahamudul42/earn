from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .views import MeView, RaterDetailView, RaterListCreateView

urlpatterns = [
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("raters/", RaterListCreateView.as_view(), name="rater-list-create"),
    path("raters/<int:pk>/", RaterDetailView.as_view(), name="rater-detail"),
]
