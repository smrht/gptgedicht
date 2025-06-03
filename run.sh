#!/bin/bash
set -e

PORT=${PORT:-8000}
WORKERS=${WORKERS:-3}

exec gunicorn poemgenerator.wsgi:application --bind "0.0.0.0:$PORT" --workers "$WORKERS" --log-file -
