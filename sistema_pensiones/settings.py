# sistema_pensiones/settings.py
# Configuración global del proyecto Django. Este archivo solo se usa en
# desarrollo local. Para producción habría que revisar la lista de
# verificación en: https://docs.djangoproject.com/en/5.x/howto/deployment/checklist/

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Clave secreta de Django — NUNCA exponer en producción ni subir a repositorios públicos
SECRET_KEY = 'django-insecure-dp!m9^muy!x07)q-5606-#a^o!0pk$+1^!^mcp+^&ue(-w=3$%'

# En producción esto debe ser False y ALLOWED_HOSTS debe listar los dominios reales
DEBUG = True
ALLOWED_HOSTS = []


# ── Apps instaladas ──────────────────────────────────────────────────────────
# Las tres primeras entradas de django.contrib son necesarias para el admin y
# las sesiones. Las últimas tres son las apps propias del simulador.

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'datos',       # lectura de archivos Excel (BCCR / SUPEN)
    'simulador',   # motor Monte Carlo con GBM
    'interfaz',    # vistas, templates y assets estáticos
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',   # habilita request.session
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sistema_pensiones.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,   # busca templates en <app>/templates/ de cada app
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'sistema_pensiones.wsgi.application'


# ── Base de datos ────────────────────────────────────────────────────────────
# SQLite es suficiente para este proyecto porque no se persiste información
# de usuarios ni resultados de simulaciones; todo viaja en la sesión.

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# ── Internacionalización ─────────────────────────────────────────────────────

LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Costa_Rica'
USE_I18N = True
USE_TZ = True


# ── Archivos estáticos ───────────────────────────────────────────────────────
# CSS, JS e imágenes en interfaz/static/. En producción se ejecutaría
# "collectstatic" para consolidarlos en STATIC_ROOT.

STATIC_URL = 'static/'
