#!/bin/sh
set -e

cmd="${1:-bot}"
shift 2>/dev/null || true

case "$cmd" in
  bot)
    exec uvicorn src.core.main:app --host 0.0.0.0 --port 8000 "$@"
    ;;
  worker)
    exec celery -A src.core.tasks.celery_app worker --loglevel=info "$@"
    ;;
  beat)
    exec celery -A src.core.tasks.celery_app beat -S redbeat.RedBeatScheduler --loglevel=info "$@"
    ;;
  *)
    echo "Error: unknown command '$cmd' (valid: bot, worker, beat)" >&2
    exit 1
    ;;
esac
