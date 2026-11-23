# Demetra : image de production (voir DEPLOIEMENT.md).
# Construction : docker build -t demetra:<commit> .
# Le conteneur écoute sur 8000, tourne en 1000:1000 et n'écrit que dans /data (base SQLite).

FROM python:3.14-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
# collectstatic n'a besoin ni de la base ni de la vraie clé secrète.
RUN DEMETRA_DEBUG=1 DEMETRA_STATIC_MANIFEST=1 /app/.venv/bin/python manage.py collectstatic --noinput \
    && /app/.venv/bin/python -m compileall -q core demetra

FROM python:3.14-slim
RUN groupadd -g 1000 demetra \
    && useradd -u 1000 -g 1000 -M -d /app -s /usr/sbin/nologin demetra \
    && mkdir -p /data && chown 1000:1000 /data
COPY --from=build --chown=0:0 /app /app
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEMETRA_DEBUG=0 \
    DEMETRA_STATIC_MANIFEST=1 \
    DEMETRA_DB=/data/demetra.sqlite3
USER 1000:1000
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/sante/', timeout=4).status == 200 else 1)"]
# Migrations puis gunicorn : 2 processus × 8 fils (le flux d'événements en direct garde un fil par étude ouverte).
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn demetra.wsgi:application --bind 0.0.0.0:8000 --worker-class gthread --workers 2 --threads 8 --timeout 90 --graceful-timeout 30 --worker-tmp-dir /dev/shm --no-control-socket --forwarded-allow-ips '*' --access-logfile - --error-logfile -"]
