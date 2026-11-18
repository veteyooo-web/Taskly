"""
Настройки Django-проекта Taskly (биржа фриланс-заказов).

Значения читаются из файла .env в корне проекта (если он существует)
и из переменных окружения — переменные окружения имеют приоритет.

В режиме единого EXE-файла (PyInstaller, sys.frozen) ресурсы — шаблоны и
статика — берутся из временной распаковки (_MEIPASS), а все записываемые
данные (база, media, секреты) складываются в каталог TASKLY_HOME
(по умолчанию %LOCALAPPDATA%\\Taskly), чтобы EXE можно было держать
в любой папке без прав записи в неё.
"""
import os
import sys
from pathlib import Path

# Режим единого EXE (PyInstaller)
FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    # Только что прочитанное (шаблоны, статика) — внутри распакованного архива
    RESOURCES_DIR = Path(sys._MEIPASS)
    # Записываемое (БД, media, секреты) — в каталоге пользователя
    _home = os.environ.get("TASKLY_HOME")
    if not _home:
        _local = os.environ.get("LOCALAPPDATA")
        _home = str(Path(_local) / "Taskly") if _local else str(Path.home() / ".taskly")
    BASE_DIR = Path(_home)
    BASE_DIR.mkdir(parents=True, exist_ok=True)
else:
    RESOURCES_DIR = Path(__file__).resolve().parent.parent
    BASE_DIR = RESOURCES_DIR


def load_env_file(path=None):
    """Минимальный загрузчик .env без внешних зависимостей.

    Уже установленные переменные окружения не перезаписываются.
    """
    env_path = path or BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env_file()


def env(key, default=""):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def env_list(key, default=""):
    raw = os.environ.get(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ------------------------------------------------------------------ #
# Core
# ------------------------------------------------------------------ #
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-key-измените-её-в-продакшене",
)
if FROZEN and "DJANGO_SECRET_KEY" not in os.environ:
    # В EXE-режиме генерируем один стабильный ключ и храним его рядом с БД,
    # иначе после каждого перезапуска слетают сессии и CSRF-токены.
    _key_file = BASE_DIR / ".secret_key"
    if _key_file.exists():
        SECRET_KEY = _key_file.read_text(encoding="utf-8").strip()
    else:
        from django.core.management.utils import get_random_secret_key

        SECRET_KEY = get_random_secret_key()
        try:
            _key_file.write_text(SECRET_KEY, encoding="utf-8")
        except OSError:
            pass
DEBUG = env_bool("DJANGO_DEBUG", not FROZEN)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Приложения проекта
    "apps.users",
    "apps.orders",
    "apps.applications",
    "apps.projects",
    "apps.reviews",
    "apps.messages",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
]

# WhiteNoise — раздаёт статику напрямую, без отдельного веб-сервера.
# Нужен в EXE-режиме (waitress не имеет встроенной раздачи static).
if FROZEN:
    MIDDLEWARE.append("whitenoise.middleware.WhiteNoiseMiddleware")
    # Отдаём файлы прямо из каталога static/ внутри архива без collectstatic
    WHITENOISE_USE_FINDERS = True

MIDDLEWARE += [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [RESOURCES_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.users.context_processors.user_counters",
                "apps.orders.context_processors.menu_categories",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ------------------------------------------------------------------ #
# Database: PostgreSQL для docker-контура, SQLite для локальной разработки
# ------------------------------------------------------------------ #
if env("DB_ENGINE", "sqlite").lower().startswith("postgres"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", "taskly"),
            "USER": env("POSTGRES_USER", "taskly"),
            "PASSWORD": env("POSTGRES_PASSWORD", "taskly"),
            "HOST": env("POSTGRES_HOST", "db"),
            "PORT": env("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / env("SQLITE_PATH", "db.sqlite3"),
        }
    }

# ------------------------------------------------------------------ #
# Auth
# ------------------------------------------------------------------ #
AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

# ------------------------------------------------------------------ #
# I18N
# ------------------------------------------------------------------ #
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = env("DJANGO_TIME_ZONE", "Europe/Moscow")
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------ #
# Static & Media
# ------------------------------------------------------------------ #
STATIC_URL = "/static/"
STATICFILES_DIRS = [RESOURCES_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------------------ #
# Security / misc
# ------------------------------------------------------------------ #
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # В EXE-режиме сайт доступен по http://127.0.0.1, поэтому secure-куки
    # по умолчанию выключены (иначе браузер не принял бы сессии).
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not FROZEN)
    CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not FROZEN)
    SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "0"))

X_FRAME_OPTIONS = "DENY"

# ------------------------------------------------------------------ #
# Email (консольная отправка в режиме разработки)
# ------------------------------------------------------------------ #
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
if EMAIL_BACKEND.endswith("smtp.EmailBackend"):
    EMAIL_HOST = env("EMAIL_HOST", "localhost")
    EMAIL_PORT = int(env("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Taskly <noreply@taskly.local>")
