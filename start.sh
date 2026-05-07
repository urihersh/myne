#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Starting Myne backend..."
cd "$DIR/backend"
"$DIR/.venv/bin/python" -m uvicorn main:app --host 0.0.0.0 --port 8000 &> /tmp/myne-backend.log &
echo $! > /tmp/myne-backend.pid

echo "Starting Myne bot..."
cd "$DIR/bot"
node bot.js &> /tmp/myne-bot.log &
echo $! > /tmp/myne-bot.pid

PORT=$(grep -E '^PORT=' "$DIR/.env" 2>/dev/null | cut -d= -f2 | tr -d ' ')
PORT="${PORT:-8000}"
echo ""
echo "Myne is running."
echo "  Open: http://localhost:${PORT}"
echo "  Logs: /tmp/myne-backend.log  /tmp/myne-bot.log"
