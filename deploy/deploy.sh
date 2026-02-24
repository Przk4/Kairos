#!/usr/bin/env bash
# ============================================
# deploy.sh — Kairos production deployment
# Run as: bash deploy.sh
# ============================================
set -euo pipefail

APP_DIR="/home/ubuntu/Kairos"
VENV="$APP_DIR/venv"
BRANCH="feature/semantic-chunking"

echo "══════════════════════════════════════"
echo "  Kairos — Deploy script"
echo "══════════════════════════════════════"

# ── 1. Pull latest code ────────────────────
cd "$APP_DIR"
echo "[1/6] Pulling latest from $BRANCH..."
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

# ── 2. Virtual environment ─────────────────
if [ ! -d "$VENV" ]; then
    echo "[2/6] Creating virtual environment..."
    python3 -m venv "$VENV"
else
    echo "[2/6] Virtual environment exists."
fi
source "$VENV/bin/activate"

# ── 3. Install dependencies ────────────────
echo "[3/6] Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# ── 4. Django management ───────────────────
echo "[4/6] Running collectstatic..."
python manage.py collectstatic --noinput

echo "[5/6] Running migrations..."
python manage.py migrate --noinput

# ── 5. Restart services ───────────────────
echo "[6/6] Restarting Gunicorn..."
sudo systemctl daemon-reload
sudo systemctl restart kairos
sudo systemctl enable kairos

echo ""
echo "✅ Deploy complete!"
echo "   Status: sudo systemctl status kairos"
echo "   Logs:   sudo journalctl -u kairos -f"
