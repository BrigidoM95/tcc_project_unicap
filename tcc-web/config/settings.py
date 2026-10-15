"""Configuração local e de produção. Valores externos em .env (não versionado)."""
import os
from pathlib import Path
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
def flag(nome, padrao=False):
    return os.getenv(nome, str(padrao)).lower() in ('1', 'true', 'yes', 'sim')
def lista(nome, padrao=''):
    return [x.strip() for x in os.getenv(nome, padrao).split(',') if x.strip()]
DEBUG = flag('DJANGO_DEBUG', True)
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Defina DJANGO_SECRET_KEY para produção.')
    # Chave local estável, sem segredo fixo distribuído no código.
    arquivo = BASE_DIR / '.local-secret'
    if not arquivo.exists():
        try:
            with arquivo.open('x') as f: f.write(get_random_secret_key())
            arquivo.chmod(0o600)
        except FileExistsError:
            pass
    SECRET_KEY = arquivo.read_text().strip()
ALLOWED_HOSTS = lista('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,10.0.2.2,[::1]')
CSRF_TRUSTED_ORIGINS = lista('DJANGO_CSRF_TRUSTED_ORIGINS')
INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'rest_framework_simplejwt.token_blacklist', 'corsheaders',
    'paginas', 'usuarios', 'onibus', 'rotas', 'embarques', 'relatorios', 'associados', 'gestao',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware', 'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'gestao.auditoria.AuditoriaMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[],'APP_DIRS':True,
 'OPTIONS':{'context_processors':['django.template.context_processors.request',
 'django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
if os.getenv('DB_ENGINE', 'sqlite') == 'postgres':
    DATABASES = {'default': {'ENGINE':'django.db.backends.postgresql',
        'NAME':os.environ['POSTGRES_DB'], 'USER':os.environ['POSTGRES_USER'],
        'PASSWORD':os.environ['POSTGRES_PASSWORD'], 'HOST':os.getenv('POSTGRES_HOST','localhost'),
        'PORT':os.getenv('POSTGRES_PORT','5432'), 'CONN_MAX_AGE':60,
        'CONN_HEALTH_CHECKS':True, 'OPTIONS':{'sslmode':os.getenv('POSTGRES_SSLMODE','prefer')}}}
else:
    DATABASES = {'default': {'ENGINE':'django.db.backends.sqlite3',
        'NAME':os.getenv('SQLITE_PATH', str(BASE_DIR / 'db.sqlite3')), 'OPTIONS':{'timeout':20}}}
AUTH_PASSWORD_VALIDATORS = [
 {'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
 {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},
 {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},
 {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = os.getenv('DJANGO_TIME_ZONE','America/Campo_Grande')
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STORAGES = {'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
 'staticfiles':{'BACKEND':'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'
REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES':('gestao.auditoria.AuditJWTAuthentication',),
 'DEFAULT_PERMISSION_CLASSES':('rest_framework.permissions.IsAuthenticated',),
 'DEFAULT_THROTTLE_RATES':{'login':'10/min','refresh':'30/min','senha':'5/min'}}
SIMPLE_JWT = {'ACCESS_TOKEN_LIFETIME':timedelta(minutes=5), 'REFRESH_TOKEN_LIFETIME':timedelta(days=1),
 'ROTATE_REFRESH_TOKENS':True, 'BLACKLIST_AFTER_ROTATION':True, 'CHECK_REVOKE_TOKEN':True}
CORS_ALLOWED_ORIGINS = lista('DJANGO_CORS_ORIGINS')
CORS_ALLOWED_ORIGIN_REGEXES = [r'^http://localhost:\d+$', r'^http://127\.0\.0\.1:\d+$'] if DEBUG else []
SECURE_SSL_REDIRECT = not DEBUG
SECURE_REDIRECT_EXEMPT = [r'^health/$']
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
if flag('DJANGO_BEHIND_PROXY'):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO','https')
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
# O proxy e o backend devem compartilhar o cache para limites em vários workers.
CACHES = {'default': {'BACKEND':'django.core.cache.backends.db.DatabaseCache', 'LOCATION':'unicap_cache'}}
MAP_TILE_URL = os.getenv('MAP_TILE_URL','https://tile.openstreetmap.org/{z}/{x}/{y}.png')
MAP_ATTRIBUTION = os.getenv('MAP_ATTRIBUTION','© OpenStreetMap contributors')
MAP_ATTRIBUTION_URL = os.getenv('MAP_ATTRIBUTION_URL','https://www.openstreetmap.org/copyright')
# Matrículas de anos anteriores não autorizam novos embarques.
EXIGIR_MATRICULA_ANUAL = flag('EXIGIR_MATRICULA_ANUAL', True)
