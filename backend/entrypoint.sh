#!/bin/bash
# Backend Entrypoint Script for Railway

set -e

export DISABLE_TQDM=1

echo "=========================================="
echo "VOS Tool Backend - Railway Startup"
echo "=========================================="

echo ""
echo "[1/2] Checking environment..."
echo "  Python version: $(python --version)"
echo "  Working directory: $(pwd)"
echo "  PORT: ${PORT:-8000}"
echo "  HF_HOME: ${HF_HOME:-not set}"

echo ""
echo "[2/2] Starting backend server..."
echo "  Command: uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"
echo "  Note: model preload and schema setup run in backend.main lifespan."
echo "=========================================="
echo ""

Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac >/tmp/xvfb.log 2>&1 &
export DISPLAY=:99

# Optional: route ReadyMode traffic through a trusted Tailscale exit node (the
# user's own laptop) instead of Railway's shared IP pool. Non-blocking — if this
# fails or TAILSCALE_AUTHKEY isn't set, the app still starts normally and ReadyMode
# falls back to the Cloudflare browser-challenge path (automation/readymode_browser_login.py).
if [ -n "$TAILSCALE_AUTHKEY" ]; then
  echo "[tailscale] starting tailscaled (userspace-networking)..."
  mkdir -p /tmp/tailscale
  tailscaled --tun=userspace-networking \
             --socks5-server=localhost:1055 \
             --outbound-http-proxy-listen=localhost:1055 \
             --state=/tmp/tailscale/tailscaled.state \
             >/tmp/tailscale/tailscaled.log 2>&1 &
  sleep 2
  TS_EXIT_NODE_ARGS=""
  if [ -n "$TAILSCALE_EXIT_NODE_IP" ]; then
    TS_EXIT_NODE_ARGS="--exit-node=$TAILSCALE_EXIT_NODE_IP --exit-node-allow-lan-access=false"
  fi
  # shellcheck disable=SC2086
  tailscale up --authkey="$TAILSCALE_AUTHKEY" --hostname=vos-backend-railway \
               --accept-dns=false $TS_EXIT_NODE_ARGS \
    && echo "[tailscale] up (exit-node=${TAILSCALE_EXIT_NODE_IP:-none})" \
    || echo "[tailscale] WARNING: tailscale up failed - continuing without it (see /tmp/tailscale/tailscaled.log)"
else
  echo "[tailscale] TAILSCALE_AUTHKEY not set - skipping"
fi

exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
