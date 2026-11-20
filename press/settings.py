import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
PRODUCTION = os.getenv("PRESS_ENV", "local") == "production"
SECRET_KEY = os.getenv("PRESS_SECRET", "")
if PRODUCTION and len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("生产环境需要至少 50 字符的随机 PRESS_SECRET")
SECRET_KEY = SECRET_KEY or "local-only-key-for-loopback-development"
DEBUG = False
ALLOWED_HOSTS = os.getenv("PRESS_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "desk",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "press.urls"
WSGI_APPLICATION = "press.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
STATE = Path(os.getenv("PRESS_STATE", BASE_DIR / "state"))
if os.getenv("PGDATABASE"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["PGDATABASE"],
            "USER": os.getenv("PGUSER", ""),
            "HOST": os.getenv("PGHOST", ""),
            "PORT": os.getenv("PGPORT", ""),
            "PASSWORD": os.getenv("PGPASSWORD", ""),
        }
    }
elif PRODUCTION:
    raise ImproperlyConfigured("生产环境需要配置 PostgreSQL")
else:
    STATE.mkdir(parents=True, exist_ok=True)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": STATE / "desk.sqlite3",
            "OPTIONS": {"timeout": 15, "transaction_mode": "IMMEDIATE"},
        }
    }
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT = PRODUCTION
SECURE_HSTS_SECONDS = 31536000 if PRODUCTION else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_PRELOAD = False
if os.getenv("PRESS_TRUST_TLS_PROXY") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_AGE = 43200
WHITENOISE_ROOT = BASE_DIR / "web" / "dist"
DATA_UPLOAD_MAX_MEMORY_SIZE = 262144
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]
