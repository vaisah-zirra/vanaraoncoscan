"""Production only: secrets come from the hosting environment, never local .env."""
from .settings import *

DEBUG = False
def required(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise ImproperlyConfigured(f'Set {name} in the hosting environment.')
    return value

if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith('django-insecure-'):
    raise ImproperlyConfigured('Use a new, strong production DJANGO_SECRET_KEY (50+ characters).')
ALLOWED_HOSTS = [host.strip() for host in required('DJANGO_ALLOWED_HOSTS').split(',') if host.strip()]
if not ALLOWED_HOSTS or any('*' in host or '/' in host for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS must contain explicit hostnames, without schemes or wildcards.')
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in required('DJANGO_CSRF_TRUSTED_ORIGINS').split(',') if origin.strip()]
if not CSRF_TRUSTED_ORIGINS or any(not origin.startswith('https://') or '*' in origin for origin in CSRF_TRUSTED_ORIGINS):
    raise ImproperlyConfigured('Use explicit HTTPS origins for DJANGO_CSRF_TRUSTED_ORIGINS.')
for key in ('MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_HOST'):
    required(key)
DATABASES['default']['CONN_MAX_AGE'] = 60
DATABASES['default']['CONN_HEALTH_CHECKS'] = True
SECURE_SSL_REDIRECT = True
# Railway terminates TLS and sets this header. Do not expose Gunicorn directly.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_REFERRER_POLICY = 'same-origin'
MIDDLEWARE = [MIDDLEWARE[0], 'whitenoise.middleware.WhiteNoiseMiddleware', *MIDDLEWARE[1:]]
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
MEDIA_ROOT = Path(required('DJANGO_MEDIA_ROOT'))
if not MEDIA_ROOT.is_absolute():
    raise ImproperlyConfigured('DJANGO_MEDIA_ROOT must be an absolute persistent-volume path.')
