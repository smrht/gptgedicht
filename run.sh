#!/bin/bash
set -e
gunicorn poemgenerator.wsgi --log-file -