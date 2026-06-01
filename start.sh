#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$DIR/data/logs"

echo "Starting Myne backend..."
cd "$DIR/backend"
"$DIR/.venv/bin/python" -m uvicorn main:app --host 0.0.0.0 --port 8000 >> "$DIR/data/logs/backend.log" 2>&1 &
echo $! > /tmp/myne-backend.pid

echo "Starting Myne bot..."
cd "$DIR/bot"
node bot.js >> "$DIR/data/logs/bot.log" 2>&1 &
echo $! > /tmp/myne-bot.pid

PORT=$(grep -E '^PORT=' "$DIR/.env" 2>/dev/null | cut -d= -f2 | tr -d ' ')
PORT="${PORT:-8000}"
echo ""
echo "Myne is running."
echo "  Open: http://localhost:${PORT}"
echo "  Logs: $DIR/data/logs/backend.log  $DIR/data/logs/bot.log"
