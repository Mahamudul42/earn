"""Development settings using PostgreSQL."""
from .base import *  # noqa: F401,F403
from .base import env

DEBUG = True

DATABASES = {
    "default": env.db("DATABASE_URL")
}

CORS_ALLOW_ALL_ORIGINS = True
