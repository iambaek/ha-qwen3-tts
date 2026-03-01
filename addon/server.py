#!/usr/bin/env python3
"""Flask HTTP server for Qwen3-TTS Add-on."""

from __future__ import annotations

import io
import json
import logging
import os
import sys
import threading
import traceback

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

_LOGGER.info("=== HA Qwen3 TTS server starting ===")
_LOGGER.info("Python %s", sys.version)
_LOGGER.info("HF_HOME=%s  TORCH_HOME=%s", os.environ.get("HF_HOME"), os.environ.get("TORCH_HOME"))

# ---------------------------------------------------------------------------
# Heavy imports — wrap individually so the exact failing package is logged
# ---------------------------------------------------------------------------
try:
    _LOGGER.info("Importing soundfile ...")
    import soundfile as sf
    _LOGGER.info("soundfile OK")
except Exception:
    _LOGGER.critical("Failed to import soundfile:\n%s", traceback.format_exc())
    sys.exit(1)

try:
    _LOGGER.info("Importing torch ...")
    import torch
    _LOGGER.info("torch %s OK", torch.__version__)
except Exception:
    _LOGGER.critical("Failed to import torch:\n%s", traceback.format_exc())
    sys.exit(1)

try:
    _LOGGER.info("Importing flask ...")
    from flask import Flask, jsonify, request, Response
    _LOGGER.info("flask OK")
except Exception:
    _LOGGER.critical("Failed to import flask:\n%s", traceback.format_exc())
    sys.exit(1)

try:
    _LOGGER.info("Importing qwen_tts ...")
    from qwen_tts import Qwen3TTSModel
    _LOGGER.info("qwen_tts OK")
except Exception:
    _LOGGER.critical("Failed to import qwen_tts:\n%s", traceback.format_exc())
    sys.exit(1)

_LOGGER.info("All imports succeeded")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OPTIONS_PATH = "/data/options.json"
DEFAULT_MODEL_ID = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
DEFAULT_SPEAKER = "Sohee"
DEFAULT_LANGUAGE = "Korean"

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
    try:
        with _load_lock:
            _model = Qwen3TTSModel.from_pretrained(
                model_id,
                device_map="cpu",
                dtype=torch.float32,
            )
            _model_ready = True
        _LOGGER.info("Model loaded and ready")
    except Exception:
        _model_error = traceback.format_exc()
        _LOGGER.error("Failed to load model:\n%s", _model_error)


@app.get("/health")
def health() -> Response:
    """Health check endpoint."""
    return jsonify({"status": "ok", "model_ready": _model_ready})


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

    _LOGGER.info("Generating TTS: speaker=%s language=%s text_len=%d", speaker, language, len(text))

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

    _LOGGER.info("TTS generated successfully")
    return Response(buf.read(), mimetype="audio/wav")


if __name__ == "__main__":
    _LOGGER.info("Starting model loader thread ...")
    thread = threading.Thread(target=load_model, daemon=True)
    thread.start()

    port = int(os.environ.get("PORT", 5000))
    _LOGGER.info("Starting Flask on 0.0.0.0:%d", port)
    app.run(host="0.0.0.0", port=port)
