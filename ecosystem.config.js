const path = require('path');
const ROOT = __dirname;

module.exports = {
  apps: [
    {
      name: 'myne-bot',
      script: 'bot.js',
      cwd: path.join(ROOT, 'bot'),
      interpreter: 'node',
      restart_delay: 3000,
      max_restarts: 20,
      min_uptime: '10s',
      out_file: path.join(ROOT, 'logs/bot-out.log'),
      error_file: path.join(ROOT, 'logs/bot-err.log'),
      merge_logs: true,
      time: true,
    },
    {
      name: 'myne-backend',
      script: path.join(ROOT, '.venv/bin/uvicorn'),
      args: 'main:app --host 0.0.0.0 --port 8000',
      cwd: path.join(ROOT, 'backend'),
      interpreter: 'none',
      restart_delay: 2000,
      max_restarts: 20,
      min_uptime: '10s',
      out_file: path.join(ROOT, 'logs/backend-out.log'),
      error_file: path.join(ROOT, 'logs/backend-err.log'),
      merge_logs: true,
      time: true,
    },
  ],
};
