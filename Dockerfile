# EARN study platform — one image: Django plus the compiled frontend.
#
# The development machine and the experiment VM build and run this same image;
# they differ only in .env. Stage 1 compiles web/ to static files, stage 2 puts
# them next to Django so gunicorn serves the site and /api/ on one port.

# --- 1. Compile the frontend ----------------------------------------------
FROM node:22-slim AS frontend
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
# NEXT_PUBLIC_API_BASE_URL is deliberately unset: the bundle calls /api/ on
# whatever origin it was served from, so no host or port is baked in.
RUN npm run build

# --- 2. Django + the compiled frontend ------------------------------------
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=project_backend.settings \
    FRONTEND_DIST=/app/frontend \
    APP_PORT=3000

WORKDIR /app

# No apt step: psycopg[binary] ships its own libpq and every other dependency
# is a pure-Python wheel, so nothing here needs a compiler.
COPY backend/requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt

COPY backend/ .
COPY --from=frontend /web/out ./frontend

# collectstatic only reads settings, so the credentials here are throwaway.
RUN DJANGO_SECRET_KEY=build-only-not-a-secret \
    DATABASE_URL=postgres://build:build@127.0.0.1:5432/build \
    python manage.py collectstatic --noinput

EXPOSE 3000

# Migrate and seed, then serve the site and the API on one port.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed_study && exec gunicorn project_backend.wsgi:application --bind 0.0.0.0:${APP_PORT:-3000} --workers 3 --timeout 180"]
