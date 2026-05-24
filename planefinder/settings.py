"""Django settings for the plane-finder service.

Configuration is env-driven so the same image runs locally and on Coolify.

Env vars:
- DJANGO_SECRET_KEY        required in prod (Coolify SERVICE_BASE64_SECRET)
- DJANGO_DEBUG             "1"/"true" enables debug; default off
- DJANGO_ALLOWED_HOSTS     comma-separated; default "*"
- DJANGO_CSRF_TRUSTED      comma-separated origin URLs; default empty
- DATABASE_URL             postgres://... ; falls back to a local sqlite file
- POLL_INTERVAL_MINUTES    schedule cadence for the Craigslist poller (default 60)
- POLL_QUERY               optional keyword filter applied to every site
- POLL_SITES               optional comma-separated subdomain allowlist
- POLL_WORKERS             concurrent requests per poll cycle (default 8)
- POLL_USER_AGENT          override scraper UA
"""

from __future__ import annotations

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [v.strip() for v in raw.split(",") if v.strip()]


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    # Insecure dev fallback. Coolify injects a real one via SERVICE_BASE64_SECRET.
    "dev-insecure-not-for-production-xxxxxxxxxxxxxxxxxxxxxxxx",
)

DEBUG = _env_bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS", default="*")

# Trust the Coolify-issued HTTPS origin(s) for CSRF on POST/admin.
CSRF_TRUSTED_ORIGINS = _env_list("DJANGO_CSRF_TRUSTED")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_q",
    "listings",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "planefinder.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "planefinder.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    ),
}

# Behind Traefik on Coolify — trust X-Forwarded-Proto for HTTPS detection.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

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

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---- django-q2 -------------------------------------------------------
# Uses the database as the broker so we don't need Redis. The worker
# container runs `python manage.py qcluster`.
Q_CLUSTER = {
    "name": "planefinder",
    "workers": int(os.environ.get("Q_WORKERS", "2")),
    "recycle": 500,
    "timeout": 1500,  # a full sweep can take a while when polling 700+ sites
    "retry": 1800,    # must exceed timeout
    "max_attempts": 1,
    "compress": True,
    "save_limit": 250,
    "queue_limit": 100,
    "label": "Plane Finder",
    "orm": "default",
    "catch_up": False,
    "ack_failures": True,
}

# ---- Scraper knobs ---------------------------------------------------
POLL_INTERVAL_MINUTES = int(os.environ.get("POLL_INTERVAL_MINUTES", "60"))
POLL_QUERY = os.environ.get("POLL_QUERY", "").strip() or None
POLL_SITES = _env_list("POLL_SITES")
POLL_WORKERS = int(os.environ.get("POLL_WORKERS", "8"))
POLL_USER_AGENT = os.environ.get(
    "POLL_USER_AGENT",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "propagate": True},
    },
}
