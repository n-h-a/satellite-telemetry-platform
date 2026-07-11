#!/bin/sh
set -e

case "$1" in
  server)
    alembic upgrade head
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
  worker)
    exec python worker.py
    ;;
  *)
    exec "$@"
    ;;
esac
