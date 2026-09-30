#!/bin/sh
set -eu
export DJANGO_SETTINGS_MODULE=config.production
python manage.py check --deploy --fail-level ERROR
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py seed_image_library
exec gunicorn config.wsgi:application --config gunicorn.conf.py
