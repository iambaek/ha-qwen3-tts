#!/usr/bin/env python3
"""Flask HTTP server for Qwen3-TTS Add-on."""

from __future__ import annotations

import faulthandler
import hashlib
import io
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import traceback

# Enable faulthandler FIRST — dumps C-level stack trace to stderr on SIGSEGV
faulthandler.enable(file=sys.stderr, all_threads=True)

# ---------------------------------------------------------------------------
# Logging must be configured BEFORE any heavy imports so that import errors
# are captured and visible in the Add-on log panel.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
    force=True,
)
_LOGGER = logging.getLogger(__name__)


def _flush() -> None:
    sys.stdout.flush()
    sys.stderr.flush()


def _log_memory(label: str) -> None:
    try:
        with open("/proc/meminfo") as f:
            lines = {
                line.split(":")[0]: line.split(":")[1].strip()
                for line in f
                if line.split(":")[0] in ("MemTotal", "MemFree", "MemAvailable")
            }
        _LOGGER.info(
            "[mem] %s — total=%s  free=%s  available=%s",
            label,
            lines.get("MemTotal", "?"),
            lines.get("MemFree", "?"),
            lines.get("MemAvailable", "?"),
        )
    except Exception:
        pass
    _flush()


def _signal_handler(signum, frame) -> None:
    sig_name = signal.Signals(signum).name
    _LOGGER.critical("Received signal %s (%d) — process is being killed", sig_name, signum)
    _flush()
    sys.exit(128 + signum)


for _sig in (signal.SIGTERM, signal.SIGHUP):
    signal.signal(_sig, _signal_handler)

_LOGGER.info("=== HA Qwen3 TTS server starting ===")
_LOGGER.info("Python %s", sys.version)
_LOGGER.info("Architecture: %s", os.uname().machine)
_LOGGER.info("HF_HOME=%s  TORCH_HOME=%s", os.environ.get("HF_HOME"), os.environ.get("TORCH_HOME"))
_log_memory("startup")

# ---------------------------------------------------------------------------
# torch import sanity check in a subprocess BEFORE importing in this process.
# If torch crashes at the C level (SIGSEGV), the child process dies and we
# capture its exit code / stderr here instead of crashing the server silently.
# ---------------------------------------------------------------------------
_LOGGER.info("Running torch import sanity check in subprocess ...")
_flush()
_torch_check = subprocess.run(
    [sys.executable, "-c",
     "import faulthandler, sys; faulthandler.enable(file=sys.stderr); "
     "import torch; print('torch', torch.__version__, 'OK')"],
    capture_output=True,
    text=True,
    timeout=120,
)
if _torch_check.returncode != 0:
    _LOGGER.critical(
        "torch subprocess check FAILED (exit=%d)\nstdout: %s\nstderr: %s",
        _torch_check.returncode,
        _torch_check.stdout.strip(),
        _torch_check.stderr.strip(),
    )
    _flush()
    sys.exit(1)
_LOGGER.info("torch subprocess check passed: %s", _torch_check.stdout.strip())
_flush()

# ---------------------------------------------------------------------------
# Heavy imports — wrap individually so the exact failing package is logged
# ---------------------------------------------------------------------------
try:
    _LOGGER.info("Importing soundfile ...")
    _flush()
    import soundfile as sf
    _LOGGER.info("soundfile OK")
    _flush()
except Exception:
    _LOGGER.critical("Failed to import soundfile:\n%s", traceback.format_exc())
    _flush()
    sys.exit(1)

try:
    _LOGGER.info("Importing torch ...")
    _log_memory("before torch import")
    import torch
    _log_memory("after torch import")
    _LOGGER.info("torch %s OK", torch.__version__)
    _flush()
except Exception:
    _LOGGER.critical("Failed to import torch:\n%s", traceback.format_exc())
    _flush()
    sys.exit(1)

try:
    _LOGGER.info("Importing flask ...")
    _flush()
    from flask import Flask, jsonify, request, Response
    _LOGGER.info("flask OK")
    _flush()
except Exception:
    _LOGGER.critical("Failed to import flask:\n%s", traceback.format_exc())
    _flush()
    sys.exit(1)

try:
    _LOGGER.info("Importing qwen_tts ...")
    _flush()
    from qwen_tts import Qwen3TTSModel
    _LOGGER.info("qwen_tts OK")
    _flush()
except Exception:
    _LOGGER.critical("Failed to import qwen_tts:\n%s", traceback.format_exc())
    _flush()
    sys.exit(1)

_LOGGER.info("All imports succeeded")
_flush()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OPTIONS_PATH = "/data/options.json"
CACHE_DIR = "/data/tts_cache"
DEFAULT_MODEL_ID = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
DEFAULT_SPEAKER = "Sohee"
DEFAULT_LANGUAGE = "Korean"

os.makedirs(CACHE_DIR, exist_ok=True)

app = Flask(__name__)

_model: Qwen3TTSModel | None = None
_model_ready = False
_model_error: str | None = None
_load_lock = threading.Lock()


def load_options() -> dict:
    """Read Add-on options from /data/options.json."""
    try:
        with open(OPTIONS_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        _LOGGER.warning("options.json not found at %s, using defaults", OPTIONS_PATH)
        return {}
    except json.JSONDecodeError as exc:
        _LOGGER.error("Failed to parse options.json: %s", exc)
        return {}


def load_model() -> None:
    """Load the Qwen3-TTS model once at startup in a background thread."""
    global _model, _model_ready, _model_error
    options = load_options()
    model_id = options.get("model_id", DEFAULT_MODEL_ID)

    _LOGGER.info("Loading model: %s", model_id)
    _log_memory("before model load")
    try:
        with _load_lock:
            _model = Qwen3TTSModel.from_pretrained(
                model_id,
                device_map="cpu",
                dtype=torch.float32,
            )
            _model_ready = True
        _log_memory("after model load")
        _LOGGER.info("Model loaded and ready")
        _flush()
    except Exception:
        _model_error = traceback.format_exc()
        _LOGGER.error("Failed to load model:\n%s", _model_error)
        _flush()


@app.get("/health")
def health() -> Response:
    """Health check endpoint."""
    return jsonify({"status": "ok", "model_ready": _model_ready})


def _cache_path(text: str, language: str, speaker: str) -> str:
    """Return the file path for a cached TTS result."""
    cache_key = hashlib.sha256(
        f"{text}|{language}|{speaker}".encode()
    ).hexdigest()[:16]
    return os.path.join(CACHE_DIR, f"{cache_key}.wav")


@app.post("/tts")
def tts() -> Response:
    """Generate speech and return WAV binary.

    Request body (JSON):
        text      (str, required)
        language  (str, optional)
        speaker   (str, optional)
    """
    if not _model_ready:
        if _model_error:
            return jsonify({"error": f"Model failed to load: {_model_error}"}), 503
        return jsonify({"error": "Model is still loading, please retry"}), 503

    body = request.get_json(silent=True) or {}
    text = body.get("text", "").strip()
    if not text:
        return jsonify({"error": "text field is required"}), 400

    options = load_options()
    language = body.get("language") or options.get("language", DEFAULT_LANGUAGE)
    speaker = body.get("speaker") or options.get("speaker", DEFAULT_SPEAKER)

    # Check cache first
    cache_file = _cache_path(text, language, speaker)
    if os.path.isfile(cache_file):
        _LOGGER.info("TTS cache hit: %s", os.path.basename(cache_file))
        with open(cache_file, "rb") as f:
            return Response(f.read(), mimetype="audio/wav")

    _LOGGER.info("TTS cache miss, generating: speaker=%s language=%s text_len=%d", speaker, language, len(text))

    try:
        wavs, sample_rate = _model.generate_custom_voice(
            text=text,
            language=language,
            speaker=speaker,
        )
    except Exception:
        _LOGGER.error("TTS generation failed:\n%s", traceback.format_exc())
        return jsonify({"error": traceback.format_exc()}), 500

    buf = io.BytesIO()
    sf.write(buf, wavs[0], sample_rate, format="WAV")
    buf.seek(0)
    wav_bytes = buf.read()

    # Save to cache
    try:
        with open(cache_file, "wb") as f:
            f.write(wav_bytes)
        _LOGGER.info("TTS cached: %s", os.path.basename(cache_file))
    except Exception:
        _LOGGER.warning("Failed to write cache file: %s", traceback.format_exc())

    return Response(wav_bytes, mimetype="audio/wav")


if __name__ == "__main__":
    _LOGGER.info("Starting model loader thread ...")
    thread = threading.Thread(target=load_model, daemon=True)
    thread.start()

    port = int(os.environ.get("PORT", 5000))
    _LOGGER.info("Starting Flask on 0.0.0.0:%d", port)
    app.run(host="0.0.0.0", port=port)
