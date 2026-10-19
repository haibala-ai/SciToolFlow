#!/bin/bash
set -euo pipefail

# Required
: "${CELERY_QUEUE:?CELERY_QUEUE is not set}"

# Optional (with sane defaults)
CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-1}"
CELERY_MAX_TASKS_PER_CHILD="${CELERY_MAX_TASKS_PER_CHILD:-1}"
RXN_LOG_LEVEL="${RXN_LOG_LEVEL:-debug}"

echo "Starting Celery worker"
echo
echo "  Queue:        ${CELERY_QUEUE}"
echo "  Concurrency:  ${CELERY_CONCURRENCY}"
echo "  Log level:    ${RXN_LOG_LEVEL}"

mkdir -p celery

exec celery -A tasks worker -E \
  --concurrency "${CELERY_CONCURRENCY}" \
  -l "${RXN_LOG_LEVEL}" \
  --without-gossip \
  --without-mingle \
  --without-heartbeat \
  -Q "${CELERY_QUEUE}" \
  -Ofair \
  --max-tasks-per-child "${CELERY_MAX_TASKS_PER_CHILD}" \
  --pidfile=celery/%n.pid \
  --logfile=celery/%n.log
