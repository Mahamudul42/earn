FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=project_backend.settings.prod

WORKDIR /app

# System deps for psycopg / building wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt

COPY . .

EXPOSE 8000

# entrypoint runs migrations + seed, then gunicorn.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed_study && gunicorn project_backend.wsgi:application --bind 0.0.0.0:${BACKEND_PORT:-8000} --workers 3 --timeout 180"]
