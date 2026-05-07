#!/bin/bash
set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${BOLD}$1${NC}"; }
success() { echo -e "${GREEN}✓ $1${NC}"; }
warn()    { echo -e "${YELLOW}⚠ $1${NC}"; }
error()   { echo -e "${RED}✗ $1${NC}"; exit 1; }

echo ""
echo -e "${BOLD}Myne — Linux / Raspberry Pi Installer${NC}"
echo "─────────────────────────────────────"
echo ""

# ── 1. Docker ────────────────────────────────────────────────────────────────
info "Checking Docker..."
if ! command -v docker &>/dev/null; then
  warn "Docker not found. Installing..."
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
  warn "Docker installed. You may need to log out and back in for group membership to take effect."
  warn "If the next step fails, run: newgrp docker"
else
  success "Docker $(docker --version | awk '{print $3}' | tr -d ',')"
fi

# ── 2. Docker Compose (v2 plugin) ────────────────────────────────────────────
info "Checking Docker Compose..."
if ! docker compose version &>/dev/null; then
  warn "Docker Compose v2 not found. Installing plugin..."
  DOCKER_CONFIG="${DOCKER_CONFIG:-$HOME/.docker}"
  mkdir -p "$DOCKER_CONFIG/cli-plugins"
  ARCH=$(uname -m)
  case $ARCH in
    aarch64|arm64) ARCH="aarch64" ;;
    armv7l)        ARCH="armv7" ;;
    x86_64)        ARCH="x86_64" ;;
    *)             error "Unsupported architecture: $ARCH" ;;
  esac
  COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name"' | cut -d'"' -f4)
  curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-${ARCH}" \
    -o "$DOCKER_CONFIG/cli-plugins/docker-compose"
  chmod +x "$DOCKER_CONFIG/cli-plugins/docker-compose"
  success "Docker Compose ${COMPOSE_VERSION}"
else
  success "Docker Compose $(docker compose version --short)"
fi

# ── 3. .env file ─────────────────────────────────────────────────────────────
info "Setting up configuration..."
if [ ! -f .env ]; then
  cp .env.example .env
  success "Created .env from .env.example"
else
  success ".env already exists — skipping"
fi

# ── 4. Data directory ─────────────────────────────────────────────────────────
info "Creating data directory..."
mkdir -p data
success "data/ ready"

# ── 5. Build & start ─────────────────────────────────────────────────────────
info "Building containers (first build takes a few minutes)..."
docker compose build

info "Starting services..."
docker compose up -d

# ── 6. Done ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}✓ Myne is running!${NC}"
echo ""
PORT=$(grep -E '^PORT=' .env 2>/dev/null | cut -d= -f2 | tr -d ' ' || echo "8000")
PORT="${PORT:-8000}"
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo "  Local:   http://localhost:${PORT}"
[ -n "$IP" ] && echo "  Network: http://${IP}:${PORT}"
echo ""
echo "  On first run the WhatsApp bot needs to pair."
echo "  Open the URL above → go to Settings → scan the QR code."
echo ""
echo "  Useful commands:"
echo "    docker compose logs -f        # view live logs"
echo "    docker compose restart        # restart services"
echo "    docker compose down           # stop everything"
echo "    git pull && docker compose up --build -d  # update"
echo ""
