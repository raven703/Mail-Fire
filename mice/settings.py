"""MICE Django deployment configuration."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured("Set a dedicated DJANGO_SECRET_KEY for MICE")
DEBUG = False
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "records",
    "identity",
    "pipeline",
    "policy_engine",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "records.middleware.PrivateResponseMiddleware",
    "identity.middleware.AccessVersionMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "mice.urls"
WSGI_APPLICATION = "mice.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ]
        },
    }
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("MICE_DB_NAME", "mice"),
        "USER": os.environ.get("MICE_DB_USER", "mice"),
        "PASSWORD": os.environ.get("MICE_DB_PASSWORD", ""),
        "HOST": os.environ.get("MICE_DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("MICE_DB_PORT", "15433"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"options": "-c timezone=UTC", "connect_timeout": 5},
    }
}
if DATABASES["default"]["NAME"] == "mailfire":
    raise ImproperlyConfigured("The live mailfire database is forbidden in this experiment")
AUTH_USER_MODEL = "identity.User"
AUTHENTICATION_BACKENDS = ["identity.backends.RoleBackend"]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "identity.hashers.LegacyArgon2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "ru"
TIME_ZONE = "UTC"
# Historical tables use timestamp without time zone and store UTC.
# Do not reinterpret their values using the host timezone during adoption.
USE_TZ = False
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
SESSION_COOKIE_NAME = "mice_session"
SESSION_COOKIE_SECURE = os.environ.get("MICE_COOKIE_SECURE", "true").lower() == "true"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_AGE = 8 * 3600
CSRF_COOKIE_NAME = "mice_csrf"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_COOKIE_SAMESITE = "Strict"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

MICE_BROKER_URL = os.environ.get("MICE_BROKER_URL", "amqp://mice:invalid@127.0.0.1:15674/mice")
MICE_INTERNAL_DOMAINS = os.environ.get("MICE_INTERNAL_DOMAINS", "")
MICE_RABBIT_API_URL = os.environ.get("MICE_RABBIT_API_URL", "")
MICE_RABBIT_USER = os.environ.get("MICE_RABBIT_USER", "mice")
MICE_RABBIT_PASSWORD = os.environ.get("MICE_RABBIT_PASSWORD", "")
MICE_RABBIT_VHOST = os.environ.get("MICE_RABBIT_VHOST", "mice")
MICE_SEMANTIC_AUTO_INDEX = os.environ.get("MICE_SEMANTIC_AUTO_INDEX", "false").lower() == "true"
MICE_PARSER_URL = os.environ.get("MICE_PARSER_URL", "")
MICE_OCR_PARSER_URL = os.environ.get("MICE_OCR_PARSER_URL", "")
MICE_CONVERTER_URL = os.environ.get("MICE_CONVERTER_URL", "")
MICE_MAX_MESSAGE_BYTES = int(os.environ.get("MICE_MAX_MESSAGE_BYTES", str(50 * 1024**2)))
MICE_PARSER_RESPONSE_BYTES = int(os.environ.get("MICE_PARSER_RESPONSE_BYTES", str(128 * 1024**2)))
MICE_PARSER_TIMEOUT = int(os.environ.get("MICE_PARSER_TIMEOUT", "130"))
MICE_IMPORT_MAX_OBJECTS = int(os.environ.get("MICE_IMPORT_MAX_OBJECTS", "200"))
MICE_IMPORT_MAX_BYTES = int(os.environ.get("MICE_IMPORT_MAX_BYTES", str(100 * 1024**2)))
MICE_SMTP_NETWORKS = os.environ.get("MICE_SMTP_NETWORKS", "127.0.0.0/8,::1/128")
MICE_CLAMAV_HOST = os.environ.get("MICE_CLAMAV_HOST", "")
MICE_CLAMAV_PORT = int(os.environ.get("MICE_CLAMAV_PORT", "3310"))
MICE_OCR_ENABLED = os.environ.get("MICE_OCR_BACKEND", "rapidocr") != "disabled"

# Unified pipeline is opt-in until the legacy queues have drained.
MICE_UNIFIED_ANALYSIS_ENABLED = os.environ.get("MICE_UNIFIED_ANALYSIS_ENABLED", "false").lower() == "true"
MICE_ANALYSIS_WALL_TIMEOUT = int(os.environ.get("MICE_ANALYSIS_WALL_TIMEOUT", "600"))
