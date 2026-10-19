#!/bin/sh
set -e

echo "Starting FastMCP on port 8001"
python server.py &

echo "Starting MCPO on port 8000"
exec mcpo \
  --host 0.0.0.0 \
  --port 8000 \
  --server-type streamable_http \
  -- http://127.0.0.1:8001/mcp
