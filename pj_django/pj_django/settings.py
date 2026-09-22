from pathlib import Path

import environ


# =========================================================
# 기본 경로 / 환경변수
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEPLOY=(bool, False),
    DEBUG=(bool, True),
)

# manage.py와 같은 폴더의 .env를 읽는다.
# 실제 키/비밀번호는 settings.py에 직접 작성하지 않는다.
environ.Env.read_env(
    BASE_DIR / ".env"
)

DEPLOY = env.bool(
    "DEPLOY",
    default=False,
)

DEBUG = env.bool(
    "DEBUG",
    default=not DEPLOY,
)


# =========================================================
# 보안 / 호스트
# =========================================================

# 운영(PythonAnywhere)에서는 반드시 .env에 SECRET_KEY를 넣는다.
# 로컬 개발에서는 .env가 없어도 서버가 켜지도록 개발 전용 fallback만 둔다.
if DEPLOY:
    SECRET_KEY = env("SECRET_KEY")
else:
    SECRET_KEY = env(
        "SECRET_KEY",
        default="django-insecure-local-development-only-change-me",
    )

ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=[
        "127.0.0.1",
        "localhost",
    ],
)

CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[],
)


# =========================================================
# 외부 API KEY
# =========================================================

# 브라우저에서 사용하는 Web / JavaScript 키
KAKAO_MAP_API_KEY = env(
    "KAKAO_MAP_API_KEY",
    default="",
)

ODSAY_WEB_API_KEY = env(
    "ODSAY_WEB_API_KEY",
    default="",
)

# 서버에서만 사용하는 REST 키
# context processor나 HTML에 전달하지 않는다.
KAKAO_REST_API_KEY = env(
    "KAKAO_REST_API_KEY",
    default="",
)


# =========================================================
# Application definition
# =========================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "sherpaapp",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "pj_django.urls"

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
                "sherpaapp.context_processors.login_member",
                "sherpaapp.context_processors.kakao_api_key",
                "sherpaapp.context_processors.odsay_api_key",
            ],
        },
    },
]

WSGI_APPLICATION = "pj_django.wsgi.application"


# =========================================================
# Database
# =========================================================

# PythonAnywhere 운영환경은 현재 SQLite 사용.
# 로컬 개발환경은 MariaDB / MySQL 사용.
if DEPLOY:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env(
                "DB_NAME",
                default="sherpa_schema",
            ),
            "USER": env(
                "DB_USER",
                default="sherpa",
            ),
            "PASSWORD": env(
                "DB_PASSWORD",
                default="",
            ),
            "HOST": env(
                "DB_HOST",
                default="127.0.0.1",
            ),
            "PORT": env(
                "DB_PORT",
                default="3306",
            ),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }


# =========================================================
# Password validation
# =========================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# =========================================================
# Internationalization
# =========================================================

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Seoul"

USE_I18N = True

# 현재 프로젝트의 기존 동작을 유지한다.
USE_TZ = False


# =========================================================
# Static / Media
# =========================================================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# =========================================================
# Session / browser
# =========================================================

SESSION_COOKIE_AGE = env.int(
    "SESSION_COOKIE_AGE",
    default=1800,
)

SESSION_SAVE_EVERY_REQUEST = env.bool(
    "SESSION_SAVE_EVERY_REQUEST",
    default=True,
)

# ODsay Web API의 Referer 전달과 현재 프로젝트 동작을 유지한다.
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# 필요하면 운영 .env에서 True로 전환할 수 있다.
SESSION_COOKIE_SECURE = env.bool(
    "SESSION_COOKIE_SECURE",
    default=False,
)

CSRF_COOKIE_SECURE = env.bool(
    "CSRF_COOKIE_SECURE",
    default=False,
)


# =========================================================
# 기타
# =========================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
