#!/bin/sh

python manage.py makemigrations bundler
python manage.py migrate
python manage.py loaddata bundler/tokenSeed.json
python manage.py collectstatic --no-input

DJANGO_SUPERUSER_PASSWORD=$SUPER_USER_PASSWORD python manage.py createsuperuser --username $SUPER_USER_NAME --email $SUPER_USER_EMAIL --noinput

gunicorn bundler.wsgi:application --bind 0.0.0.0:8001