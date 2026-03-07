#!/usr/bin/env bash
set -euo pipefail

# Install script for Kairos on a Debian/Ubuntu droplet
# - creates a virtualenv at /opt/kairos/venv (if missing)
# - activates venv, upgrades pip, installs CPU PyTorch, then requirements
# - does NOT auto-restart the service unless run with --restart

ROOT_DIR="/opt/kairos"
VENV_DIR="$ROOT_DIR/venv"

usage(){
  echo "Usage: $0 [--restart]"
  exit 1
}

RESTART=0
if [ "${1-}" = "--restart" ]; then
  RESTART=1
fi

if [ ! -d "$ROOT_DIR" ]; then
  echo "Directory $ROOT_DIR not found. Run from the server where Kairos is deployed." >&2
  exit 2
fi

cd "$ROOT_DIR"

# Create venv if missing
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtualenv at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip setuptools wheel

echo "Installing CPU-only PyTorch (recommended before surya-ocr)..."
# Use PyTorch CPU wheels; adapt if you need CUDA-enabled builds
pip install --upgrade "torch" --index-url https://download.pytorch.org/whl/cpu

echo "Installing python requirements..."
pip install -r requirements.txt

# Ensure transformers is pinned below 5.x (surya-ocr compat)
pip install "transformers>=4.56.1,<5.0.0"

echo "Installation complete."

if [ "$RESTART" -eq 1 ]; then
  echo "Restarting kairos service"
  sudo systemctl restart kairos
fi

echo "Done."
