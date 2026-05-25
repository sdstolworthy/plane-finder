FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

WORKDIR /app

# Build deps (psycopg) + healthcheck curl. Playwright's `install --with-deps`
# pulls system browser deps separately below.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

# Install Chromium for the Trade-A-Plane scraper. ~500MB. The TAP
# scraper itself is opt-in via POLL_TRADEAPLANE_ENABLED, but the binary
# ships in the image so the worker can be flipped on without a rebuild.
RUN playwright install --with-deps chromium

COPY . .

# Pre-collect static assets (idempotent — runtime collectstatic also works).
RUN DJANGO_SECRET_KEY=build-only DJANGO_DEBUG=0 \
    python manage.py collectstatic --no-input || true

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --no-input && gunicorn planefinder.wsgi:application --bind 0.0.0.0:8000 --workers 2 --access-logfile - --error-logfile -"]
