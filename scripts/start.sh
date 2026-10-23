#!/usr/bin/env bash
# #34: one-command local start. Installs a CPU-only ComfyUI (the v1 host) next to this
# plugin, links ComfyArt into custom_nodes and starts it. No GPU, no local model files:
# every generation goes to WaveSpeed with your own key. Re-running reuses the install.
#
#   ./scripts/start.sh            # install if needed, then start on 127.0.0.1:8188
#   COMFYART_HOME=~/comfyart PORT=8190 ./scripts/start.sh
#   ./scripts/start.sh --install-only
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMFYART_HOME="${COMFYART_HOME:-$HOME/.comfyart-runtime}"
COMFYUI_REF="${COMFYUI_REF:-v0.42.1}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8188}"
PYTHON="${PYTHON:-python3}"
COMFY="$COMFYART_HOME/ComfyUI"
VENV="$COMFYART_HOME/venv"

[ -f "$PLUGIN_DIR/dist/index.html" ] || { echo "dist/ is missing: run 'npm ci && npm run build' first" >&2; exit 1; }
command -v git >/dev/null || { echo "git is required" >&2; exit 1; }
"$PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { echo "Python 3.10+ is required" >&2; exit 1; }
command -v ffmpeg >/dev/null || echo "note: ffmpeg not on PATH; only the video editor export needs it" >&2

mkdir -p "$COMFYART_HOME"
if [ ! -d "$COMFY/.git" ]; then
  echo "==> ComfyUI $COMFYUI_REF"
  git clone --depth 1 --branch "$COMFYUI_REF" https://github.com/comfyanonymous/ComfyUI.git "$COMFY"
fi
if [ ! -x "$VENV/bin/python" ]; then
  echo "==> Python venv"
  "$PYTHON" -m venv "$VENV"
fi
STAMP="$COMFYART_HOME/.installed-$COMFYUI_REF-$(cksum < "$PLUGIN_DIR/requirements.txt" | cut -d' ' -f1)"
if [ ! -f "$STAMP" ]; then
  echo "==> Python packages (CPU torch, no CUDA)"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
  "$VENV/bin/pip" install -q -r "$COMFY/requirements.txt" -r "$PLUGIN_DIR/requirements.txt"
  touch "$STAMP"
fi
LINK="$COMFY/custom_nodes/ComfyArt"
if [ ! -e "$LINK" ]; then ln -s "$PLUGIN_DIR" "$LINK"; fi

[ "${1:-}" = "--install-only" ] && { echo "installed in $COMFYART_HOME"; exit 0; }
echo "==> open http://$HOST:$PORT/comfyart/"
cd "$COMFY"
exec "$VENV/bin/python" main.py --cpu --listen "$HOST" --port "$PORT" --disable-auto-launch
