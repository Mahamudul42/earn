"""
Settings for the EARN study platform.

EARN — Eliciting Actionable Recommendation Feedback from Users for News
Personalization. This backend powers a between-subjects online experiment that
shows participants a realistic personalized news newsletter and elicits
open-ended feedback under one of three conditions.

One module for every environment: the development machine and the experiment
VM run the same image and differ only in ``.env``. ``DJANGO_DEBUG`` is the one
switch that changes behaviour, and it stays ``0`` everywhere that collects real
participant data.
"""
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["*"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:3000"]),
)

# Read a .env file if present (local dev convenience).
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "corsheaders",
    # Local
    "apps.core",
    "apps.users",
    "apps.study",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "project_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "project_backend.wsgi.application"
ASGI_APPLICATION = "project_backend.asgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Django REST Framework -------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "EARN Study API",
    "DESCRIPTION": "Eliciting Actionable Recommendation Feedback for news personalization.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --- Frontend --------------------------------------------------------------
# The Docker build compiles web/ to static files and copies them here, so one
# container serves the participant site, the researcher dashboard and the API
# from a single port. Unset SERVE_FRONTEND to run the API on its own again.
FRONTEND_DIST = Path(env("FRONTEND_DIST", default=str(BASE_DIR / "frontend")))
SERVE_FRONTEND = env.bool("SERVE_FRONTEND", default=True) and FRONTEND_DIST.is_dir()

if SERVE_FRONTEND:
    MIDDLEWARE.insert(
        MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
        "whitenoise.middleware.WhiteNoiseMiddleware",
    )
    # Serve the exported bundle's own files (/_next/*, /favicon.ico, ...);
    # anything without a file on disk falls through to apps.core.FrontendAppView.
    WHITENOISE_ROOT = FRONTEND_DIST
    WHITENOISE_INDEX_FILE = False
    # Everything Next.js writes under /_next/static/ carries a content hash.
    WHITENOISE_IMMUTABLE_FILE_TEST = r"^/_next/static/"

# --- Security --------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# --- CORS ------------------------------------------------------------------
# The frontend is served from the same origin as the API, so this only matters
# when a Next dev server on another port talks to a running container.
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=False)

# --- Interactive Feedback Assistant (Condition 3) --------------------------
LOCAL_LLM_BASE_URL = env("LOCAL_LLM_BASE_URL", default="")
LOCAL_LLM_MODEL = env("LOCAL_LLM_MODEL", default="openai/gpt-oss-120b")
# Optional: the current local endpoint needs no key, so this is blank by default.
LOCAL_LLM_API_KEY = env("LOCAL_LLM_API_KEY", default="")
LOCAL_LLM_TIMEOUT_SECONDS = env.int("LOCAL_LLM_TIMEOUT_SECONDS", default=45)

# --- Study conditions ------------------------------------------------------
# Which elicitation conditions are active in normal (balanced) assignment.
# The forced-condition preview (?condition=N) still works for any condition.
STUDY_ENABLED_CONDITIONS = [
    int(c) for c in env.list("STUDY_ENABLED_CONDITIONS", default=["1", "2", "3"])
]
# Keep deployment testing out of the confirmatory analysis set until the
# researcher explicitly switches the environment to ``main``.
STUDY_PHASE = env("STUDY_PHASE", default="pilot")
