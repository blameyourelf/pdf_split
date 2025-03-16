#!/bin/bash
echo "Starting application with Gunicorn..."
gunicorn --config gunicorn_config.py wsgi:app
