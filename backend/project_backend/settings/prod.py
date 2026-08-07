"""Production settings — PostgreSQL with stricter security."""
from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://earn:change-me-db-password@db:5432/earn",
    )
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# --- CORS -----------------------------------------------------------------
# Production uses the explicit CORS_ALLOWED_ORIGINS allowlist by default.
# Set CORS_ALLOW_ALL_ORIGINS=1 only for a short-lived development environment.
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=False)
