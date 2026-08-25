import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'local-villacapital-development-key')
DEBUG = os.getenv('DJANGO_DEBUG', 'false').lower() == 'true'
ALLOWED_HOSTS = list({x.strip() for x in os.getenv('DJANGO_ALLOWED_HOSTS', '*').split(',') if x.strip()} | {'localhost', '127.0.0.1', 'backend', 'frontend', '192.168.1.34'})
INSTALLED_APPS = ['django.contrib.contenttypes', 'django.contrib.staticfiles', 'corsheaders', 'monitor']
MIDDLEWARE = ['corsheaders.middleware.CorsMiddleware', 'django.middleware.common.CommonMiddleware']
ROOT_URLCONF = 'config.urls'
USE_TZ = True
TIME_ZONE = 'UTC'
DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': os.getenv('POSTGRES_DB', 'mt5_monitor'), 'USER': os.getenv('POSTGRES_USER', 'hernan'), 'PASSWORD': os.getenv('POSTGRES_PASSWORD', '0808'), 'HOST': os.getenv('POSTGRES_HOST', '192.168.1.34'), 'PORT': os.getenv('POSTGRES_PORT', '5432'), 'CONN_MAX_AGE': 60}}
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
CORS_ALLOW_ALL_ORIGINS = True
