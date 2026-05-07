<p align="center">
  <img src="backend/static/logo.png" alt="Myne" width="120" />
</p>

# Myne

**Find your kids in WhatsApp group photos — automatically.**

A self-hosted face recognition tool that watches your WhatsApp groups and forwards any photo or video where your kids appear. Runs entirely on your own machine — no data leaves your device.

---

## How it works

1. Enroll your kids with a few face photos.
2. Choose which WhatsApp groups to watch (school, sports, activities).
3. When a photo or video arrives in a watched group, Myne runs face recognition against your enrolled kids.
4. Matches are forwarded to a WhatsApp chat of your choice, saved to a local folder, or uploaded to Google Photos — whichever actions you configure.

---

## Features

- **Face recognition** on incoming photos and videos
- **Forward to WhatsApp** — instant or via daily digest at a scheduled time
- **Save to folder** — automatically save matched media locally, organized by group or kid
- **Google Photos** — upload matched media to an album, organized by group or kid
- **Test panel** — try a photo or video without needing WhatsApp
- **Activity log** — browsable history with thumbnails and filters
- **Active hours** — auto-disconnect the bot outside a time window so your phone gets notifications normally
- **Adjustable confidence threshold** — tune how strict the face match is
- **PIN lock** — protect the web UI on your network
- **Backup & restore** — export/import all settings and enrolled kids
- **Dark mode**
- **English and Hebrew UI**

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python · FastAPI · SQLAlchemy (SQLite) |
| Face recognition | InsightFace · OpenCV · ONNX Runtime |
| WhatsApp bot | Node.js · Baileys (linked device) |
| Frontend | Plain HTML · Tailwind CSS |

---

## Setup (macOS / Linux)

### Prerequisites

- Python 3.11+
- Node.js 18+
- A WhatsApp account to link

### Install

```bash
git clone https://github.com/urihersh/myne.git
cd myne

# Python backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Node bot
cd bot && npm install && cd ..

# Config
cp .env.example .env
```

### Start

```bash
bash start.sh
```

Open **http://localhost:8000**. Go to the **Settings** tab to scan the QR code and link your WhatsApp account.

### Stop

```bash
bash stop.sh
```

---

## Docker (Linux / Raspberry Pi)

```bash
git clone https://github.com/urihersh/myne.git
cd myne
bash install-linux.sh
```

Installs Docker if needed, builds the containers, and starts everything. On first run, open the URL shown and scan the QR code in the Settings tab.

Both containers are configured with `restart: unless-stopped`, so they recover automatically after a crash or a Docker restart.

### Persist across machine reboots

**Linux:** enable Docker to start on boot:
```bash
sudo systemctl enable docker
```

**Windows (Docker Desktop):** open Docker Desktop → Settings → General → enable **"Start Docker Desktop when you log in"**.

Once Docker starts on boot, Myne's containers come back up automatically — no manual intervention needed.

---

## PM2 (optional, for auto-restart on reboot)

```bash
npm install -g pm2
pm2 start ecosystem.config.js
pm2 save && pm2 startup
```

---

## Project structure

```
myne/
├── backend/
│   ├── main.py              # FastAPI app, media processing, recognition pipeline
│   ├── database.py          # SQLAlchemy models + helpers (SQLite)
│   ├── face_service.py      # InsightFace wrapper (buffalo_l, CPU)
│   ├── google_photos.py     # Google Photos OAuth2 + upload
│   ├── routers/
│   │   ├── auth.py          # PIN session auth
│   │   ├── backup.py        # Backup & restore (zip)
│   │   ├── dashboard.py     # Activity log + stats API
│   │   ├── digest.py        # Daily digest scheduler
│   │   ├── enrollment.py    # Kid management + photo enrollment API
│   │   └── settings.py      # App settings + WhatsApp status / QR
│   └── static/
│       ├── myne.html        # Main app UI
│       ├── onboarding.html  # First-run setup wizard
│       ├── settings.html    # Standalone settings page
│       ├── lang.js          # i18n (English + Hebrew)
│       ├── dark.js          # Dark mode
│       ├── kbd-nav.js       # Keyboard navigation
│       └── pin_lock.js      # PIN lock overlay
├── bot/
│   └── bot.js               # Baileys WhatsApp bot
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.bot
├── ecosystem.config.js      # PM2 config
├── install-linux.sh         # Docker setup for Linux / Raspberry Pi
├── start.sh / stop.sh       # Native start / stop scripts
└── requirements.txt
```

---

## Data & privacy

- All processing runs on your machine.
- Face embeddings, photos, and settings are stored in `data/` (git-ignored).
- The WhatsApp bot runs as a **linked device** — like WhatsApp Web. Your phone still receives all messages and notifications normally.
- `data/` is created automatically on first run.

---

## Google Photos setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create or select a project.
2. Go to **APIs & Services → Library**, search for **Photos Library API** and enable it.
3. Go to **APIs & Services → OAuth consent screen**. Set User Type to **External** and publishing status to **In production**.
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth Client ID**. Application type: **Web application**.
5. Under **Authorized redirect URIs**, add: `http://localhost:8000/api/settings/google-photos/callback`
   (Replace `localhost:8000` with your `BACKEND_PUBLIC_URL` if accessing from another machine.)
6. Copy the **Client ID** and **Client Secret** into **Settings → Integrations → Google Photos**, save, then click **Connect with Google**.

---

## Configuration

Copy `.env.example` to `.env`. The defaults work for a single-machine install.

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Web UI port |
| `BOT_PORT` | `3001` | WhatsApp bot API port |
| `BOT_API_URL` | `http://localhost:3001` | Backend → bot URL |
| `PYTHON_API_URL` | `http://localhost:8000` | Bot → backend URL |
| `DATA_DIR` | `./data` | Where to store all data |
| `BACKEND_PUBLIC_URL` | `http://localhost:8000` | Public URL used as the Google Photos OAuth redirect URI — set this to your machine's address when running on a Raspberry Pi or remote server |

---

## License

Personal use only — see [LICENSE](LICENSE).
