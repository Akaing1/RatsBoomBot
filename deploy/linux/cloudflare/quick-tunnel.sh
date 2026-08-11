#!/usr/bin/env bash

set -euo pipefail

LOCAL_URL="http://127.0.0.1:4345"

echo "[Tunnel] Starting Cloudflare Quick Tunnel."
echo "[Tunnel] Forwarding to $LOCAL_URL"

cloudflared tunnel --url "$LOCAL_URL"
