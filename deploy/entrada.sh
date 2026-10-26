#!/bin/sh
set -eu
python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers "${WEB_WORKERS:-3}" --threads 4 --timeout 60 --access-logfile - --error-logfile -
