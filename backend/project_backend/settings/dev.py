"""Development settings using PostgreSQL."""
from .base import *  # noqa: F401,F403
from .base import env

DEBUG = True

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://earn:change-me-db-password@127.0.0.1:5436/earn",
    )
}

CORS_ALLOW_ALL_ORIGINS = True
