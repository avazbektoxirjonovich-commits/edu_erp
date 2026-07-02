"""
Test settings — minimal, SQLite, no external services.
Used by pytest (pytest.ini) and makemigrations for face_auth.
"""
from datetime import timedelta
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = 'test-only-secret-key-do-not-use-in-production'
DEBUG      = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'apps.accounts',
    'apps.students',
    'apps.teachers',
    'apps.groups',
    'apps.attendance',
    'apps.payments',
    'apps.dashboard',
    'apps.notifications',
    'apps.homework',
    'apps.face_auth',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls_test'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME':   BASE_DIR / 'db_test.sqlite3',
    }
}

AUTH_USER_MODEL = 'accounts.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_RENDERER_CLASSES': ('rest_framework.renderers.JSONRenderer',),
    'DEFAULT_THROTTLE_RATES': {
        'anon':      '1000/min',
        'user':      '5000/min',
        'login':     '100/min',
        'face_auth': '100/min',   # OTP request + verify endpoints
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS':  True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN':      True,
    'AUTH_HEADER_TYPES':      ('Bearer',),
}

LANGUAGE_CODE = 'uz'
TIME_ZONE     = 'Asia/Tashkent'
USE_I18N      = True
USE_TZ        = True

STATIC_URL  = '/static/'
MEDIA_URL   = '/media/'
MEDIA_ROOT  = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD  = 'django.db.models.BigAutoField'
CORS_ALLOW_ALL_ORIGINS = True
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ── Face Auth ────────────────────────────────────────────────────────────────
FACE_AUTH_ENABLED      = False
FACE_ENCRYPTION_KEY    = ''   # overridden per-test by fernet_key fixture
FACE_COSINE_THRESHOLD  = 0.68
FACE_MAX_ATTEMPTS      = 5
FACE_LOCKOUT_MINUTES   = 5
FACE_REQUIRED_ROLES    = ['admin', 'developer']
FACE_OTP_BACKEND              = 'console'   # console | sms | telegram
FACE_SMS_PROVIDER             = 'eskiz'     # eskiz | playmobile
FACE_PASSIVE_LIVENESS_ENABLED = False
FACE_SPOOF_THRESHOLD          = 0.7   # raised from 0.5; env-configurable
FACE_LIVENESS_FAIL_OPEN       = False  # fail-CLOSED by default (secure)
FACE_LANDMARKER_MODEL         = ''   # empty = use default models_weights/ path

JAZZMIN_SETTINGS = {
    'site_title':   'VLT.erp',
    'site_header':  'VLT.erp Admin',
    'site_brand':   'VLT.erp',
    'welcome_sign': 'VLT.erp',
    'show_sidebar': True,
    'navigation_expanded': True,
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {'apps': {'handlers': ['console'], 'level': 'WARNING'}},
}
