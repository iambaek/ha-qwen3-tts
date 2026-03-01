#!/usr/bin/env bash
set -e

echo "[run.sh] Starting HA Qwen3 TTS Add-on"
echo "[run.sh] Python: $(python --version 2>&1)"
echo "[run.sh] Architecture: $(uname -m)"
echo "[run.sh] Working directory: $(pwd)"
echo "[run.sh] /data contents: $(ls /data 2>/dev/null || echo '(empty)')"
echo "[run.sh] Memory info:"
cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable" || true

exec python -u /app/server.py
