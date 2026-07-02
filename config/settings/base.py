from pathlib import Path
from decouple import config
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'jazzmin',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'cloudinary_storage',
    'cloudinary',
]

LOCAL_APPS = [
    'apps.common',
    'apps.accounts',
    'apps.students',
    'apps.teachers',
    'apps.groups',
    'apps.attendance',
    'apps.payments',
    'apps.dashboard',
    'apps.notifications',
    'apps.homework',
    'apps.vlt_ai',
    'apps.face_auth',
    'apps.zukko',
]

# jazzmin must come BEFORE django.contrib.admin
INSTALLED_APPS = ['jazzmin'] + DJANGO_APPS + THIRD_PARTY_APPS[1:] + LOCAL_APPS

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

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

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
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='erp_db'),
        'USER': config('DB_USER', default='erp_user'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {'connect_timeout': 60},
        'CONN_MAX_AGE': 60,
    }
}

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

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
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    # Throttling - prevent brute force on auth
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon':      '30/min',
        'user':      '300/min',
        'login':     '5/min',
        'face_auth': '10/min',   # OTP request + verify endpoints
    },
    'DATE_FORMAT': '%Y-%m-%d',
    'DATETIME_FORMAT': '%Y-%m-%d %H:%M:%S',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        minutes=config('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=60, cast=int)
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        days=config('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=7, cast=int)
    ),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_CLAIM': 'jti',
}

LANGUAGE_CODE = 'uz'
TIME_ZONE = config('TIME_ZONE', default='Asia/Tashkent')
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Cloudinary konfiguratsiyasi (production uchun)
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME', default=''),
    'API_KEY':    config('CLOUDINARY_API_KEY',    default=''),
    'API_SECRET': config('CLOUDINARY_API_SECRET', default=''),
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('EMAIL_HOST_USER', default='noreply@erp.uz')

MONTHLY_FEE_DEFAULT = config('MONTHLY_FEE_DEFAULT', default=500000, cast=int)

# ── VLT AI ──────────────────────────────────────────────────────
VLT_AI_PROVIDER   = config('VLT_AI_PROVIDER',   default='anthropic')
VLT_AI_MODEL      = config('VLT_AI_MODEL',      default='claude-haiku-4-5-20251001')
VLT_AI_MAX_TOKENS = config('VLT_AI_MAX_TOKENS', default=1024, cast=int)
ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')

# Telegram notification settings (optional)
TELEGRAM_BOT_TOKEN = config('TELEGRAM_BOT_TOKEN', default='')
TELEGRAM_ADMIN_CHAT_ID = config('TELEGRAM_ADMIN_CHAT_ID', default='')

# ── FACE AUTH (ikki faktorli yuz autentifikatsiyasi) ─────────────────────────
# FACE_AUTH_ENABLED = False  →  face ID tekshiruvi o'chirilgan (xavfsiz standart)
# Yoqish uchun: FACE_AUTH_ENABLED=True + FACE_ENCRYPTION_KEY=<fernet key>
FACE_AUTH_ENABLED          = config('FACE_AUTH_ENABLED',           default=False, cast=bool)
FACE_LANDMARKER_MODEL      = config('FACE_LANDMARKER_MODEL',       default='')
FACE_SPOOF_THRESHOLD       = config('FACE_SPOOF_THRESHOLD',        default=0.7,   cast=float)
FACE_LIVENESS_FAIL_OPEN    = config('FACE_LIVENESS_FAIL_OPEN',     default=False, cast=bool)
FACE_ENCRYPTION_KEY   = config('FACE_ENCRYPTION_KEY',   default='')
FACE_COSINE_THRESHOLD = config('FACE_COSINE_THRESHOLD', default=0.68,  cast=float)
FACE_MAX_ATTEMPTS     = config('FACE_MAX_ATTEMPTS',     default=5,     cast=int)
FACE_LOCKOUT_MINUTES  = config('FACE_LOCKOUT_MINUTES',  default=5,     cast=int)
# Comma-separated roles that require face auth when FACE_AUTH_ENABLED=True
FACE_REQUIRED_ROLES   = config(
    'FACE_REQUIRED_ROLES',
    default='admin,developer',
    cast=lambda v: [r.strip() for r in v.split(',') if r.strip()],
)

JAZZMIN_SETTINGS = {
    "site_title": "VLT.erp",
    "site_header": "VLT.erp Admin",
    "site_brand": "VLT.erp",
    "welcome_sign": "VLT.erp — Ta'lim Markazi Boshqaruv Tizimiga Xush Kelibsiz",
    "copyright": "VLT.erp",
    "search_model": ["accounts.User", "students.Student"],
    "topmenu_links": [
        {"name": "Dashboard", "url": "/", "new_window": False},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "icons": {
        "accounts": "fas fa-users-cog",
        "accounts.User": "fas fa-user",
        "students.Student": "fas fa-user-graduate",
        "teachers.Teacher": "fas fa-chalkboard-teacher",
        "groups.Group": "fas fa-users",
        "attendance.Attendance": "fas fa-calendar-check",
        "payments.Payment": "fas fa-money-bill-wave",
        "notifications": "fas fa-bell",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": False,
    "use_google_fonts_cdn": False,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "language_chooser": False,
    "order_with_respect_to": [
        "accounts", "students", "teachers", "groups",
        "attendance", "payments", "notifications",
    ],
}
