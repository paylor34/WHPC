#!/usr/bin/env bash
# Startup script for Render (and any gunicorn-based host).
# Imports the committed CSV into a fresh SQLite DB, fetches any missing
# product images, then serves with gunicorn.
set -e

echo "==> Seeding database from data/exports/listings.csv ..."
python run.py import

echo "==> Fetching missing product images ..."
python run.py fetch-images || echo "Image fetch had errors (non-fatal, continuing)"

echo "==> Starting gunicorn ..."
exec gunicorn "app:create_app()" \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 2 \
  --timeout 120 \
  --access-logfile -
