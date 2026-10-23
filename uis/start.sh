#!/bin/sh
set -eu

cd /app/backoffice
npm run dev -- --hostname 0.0.0.0 --port "${NEXT_INTERNAL_PORT:-3002}" &
next_pid=$!

node /app/proxy-server.js &
proxy_pid=$!

cleanup() {
  kill "$next_pid" "$proxy_pid" 2>/dev/null || true
  wait "$next_pid" "$proxy_pid" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

while kill -0 "$next_pid" 2>/dev/null && kill -0 "$proxy_pid" 2>/dev/null; do
  sleep 1
done

exit 1
