#!/usr/bin/env bash
set -e

echo "[run.sh] Starting HA Qwen3 TTS Add-on"
echo "[run.sh] Python: $(python --version 2>&1)"
echo "[run.sh] Working directory: $(pwd)"
echo "[run.sh] /data contents: $(ls /data 2>/dev/null || echo '(empty)')"

exec python -u /app/server.py
