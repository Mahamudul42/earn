from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.core.views import FrontendAppView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.core.urls")),
    path("api/auth/", include("apps.users.urls")),
    path("api/", include("apps.study.urls")),
    # OpenAPI / docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

# The exported frontend is the last resort: anything that is not /api/, /admin/
# or a collected static file is a frontend route. The negative lookahead keeps a
# mistyped API path returning a 404 instead of an HTML 200 that the browser
# would then fail to parse as JSON.
if settings.SERVE_FRONTEND:
    urlpatterns += [
        re_path(r"^(?!api/|admin/|static/)(?P<path>.*)$", FrontendAppView.as_view()),
    ]
