"""
Django settings for Fogata MVP (Fase 0 - Fase 6).
Django 5.2 LTS, SQLite, Server-Side Rendering (SSR), Multi-User Ready.
"""

import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Modo DEBUG controlado por entorno (True por defecto en desarrollo local)
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1')

# Configuración estricta de SECRET_KEY (Criterio 15)
if DEBUG:
    SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-fogata-mvp-fase0-segura-y-minimalista')
else:
    SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
    if not SECRET_KEY:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY es obligatoria cuando DEBUG=False en producción.")

# Configuración estricta de ALLOWED_HOSTS (Criterio 15)
if DEBUG:
    allowed_hosts_env = os.environ.get('DJANGO_ALLOWED_HOSTS')
    ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(',') if h.strip()] if allowed_hosts_env else ['*']
else:
    allowed_hosts_env = os.environ.get('DJANGO_ALLOWED_HOSTS')
    if not allowed_hosts_env:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS debe configurarse explícitamente cuando DEBUG=False en producción.")
    ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(',') if h.strip()]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Aplicaciones del proyecto Fogata
    'apps.core.apps.CoreConfig',
    'apps.canciones.apps.CancionesConfig',
    'apps.fogatas.apps.FogatasConfig',
    'apps.gestion.apps.GestionConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.PrivateCacheMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'


# Database: SQLite para desarrollo y MVP
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
db_path_env = os.environ.get('DJANGO_DB_PATH')
DB_NAME = Path(db_path_env) if db_path_env else BASE_DIR / 'db.sqlite3'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DB_NAME,
        'OPTIONS': {
            'timeout': 20,
        },
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'es'

TIME_ZONE = 'America/Santiago'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Autenticación Nativa (Fase 6)
AUTHENTICATION_BACKENDS = [
    'apps.core.backends.EmailAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL = 'core:login'
LOGIN_REDIRECT_URL = 'core:home'
LOGOUT_REDIRECT_URL = 'core:home'

# Configuración de Correo Electrónico (Fase 6 - Criterio 18)
EMAIL_BACKEND = os.environ.get('DJANGO_EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1')
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False').lower() in ('true', '1')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Fogata <no-reply@humm.cl>')

# Orígenes confiables CSRF
csrf_trusted_env = os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS')
if csrf_trusted_env:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_trusted_env.split(',') if o.strip()]

# Seguridad de Producción y Cookies HTTPS (Fase 6 - Criterio 16)
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

# Fase 7 — Fogata Control Center & Analítica de Comportamiento (Criterio 4)
FOGATA_ANALYTICS_START_DATE = os.environ.get('FOGATA_ANALYTICS_START_DATE', '2026-09-28')


