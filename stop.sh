#!/bin/bash

stop_pid() {
  local name="$1" pidfile="$2"
  if [ -f "$pidfile" ]; then
    local pid=$(cat "$pidfile")
    if kill "$pid" 2>/dev/null; then
      echo "Stopped $name (pid $pid)"
    else
      echo "$name was not running"
    fi
    rm -f "$pidfile"
  else
    echo "$name pid file not found — trying pkill..."
    pkill -f "$name" 2>/dev/null && echo "Stopped $name" || echo "$name was not running"
  fi
}

stop_pid "uvicorn" /tmp/myne-backend.pid
stop_pid "bot/bot.js" /tmp/myne-bot.pid
