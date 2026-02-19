#!/usr/bin/env bash
# Startup script for Render (and any gunicorn-based host).
# Imports the committed CSV into a fresh SQLite DB, then serves with gunicorn.
set -e

echo "==> Seeding database from data/exports/listings.csv ..."
python run.py import

echo "==> Starting gunicorn ..."
exec gunicorn "app:create_app()" \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 2 \
  --timeout 60 \
  --access-logfile -
