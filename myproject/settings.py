import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# -------------------- Core --------------------
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-0omas^2ujpg3gfa8f@und=^mhf24-aie+o3&z_1j-fgl)vo!hm'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = [
    "lioraeco-production.up.railway.app",
    "127.0.0.1",
    "localhost",
]

# For Railway / production CSRF
CSRF_TRUSTED_ORIGINS = [
    "https://lioraeco-production.up.railway.app",
]

# -------------------- Apps --------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'myApp',
]

# -------------------- Middleware --------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # serve static files in prod
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'myproject.urls'

# -------------------- Templates --------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'myproject.wsgi.application'

# -------------------- Database --------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# -------------------- Auth --------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# -------------------- I18N --------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# -------------------- Static / Media --------------------
# Use leading & trailing slash for STATIC_URL
STATIC_URL = "/static/"

# Where `collectstatic` dumps built assets (absolute path)
STATIC_ROOT = BASE_DIR / "staticfiles"

# Optional extra static sources (keep only if you have this folder)
# Project-level: BASE_DIR / "static"
STATICFILES_DIRS = [
    # BASE_DIR / "static",
]

# Whitenoise: compressed + hashed filenames for long-term caching
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Media (user uploads) — only if/when you add file uploads
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# -------------------- Defaults --------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# -------------------- Email --------------------
# Dev uses console; Prod uses SMTP (configure via env)
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = "smtp.gmail.com"
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = "no-reply@liorae.co"
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    DEFAULT_FROM_EMAIL = "Lioraè Co. <no-reply@liorae.co>"
    CONTACT_RECIPIENT = "hello@liorae.co"

# -------------------- API Keys / Env --------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
