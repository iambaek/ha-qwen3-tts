"""Constants for HA Qwen3 TTS."""

DOMAIN = "ha_qwen3_tts"

CONF_RUNTIME_DIR = "runtime_dir"
CONF_PYTHON_BIN = "python_bin"
CONF_AUTO_INSTALL = "auto_install"
CONF_QWEN_PACKAGE_URL = "qwen_package_url"
CONF_OUTPUT_DIR = "output_dir"
CONF_BASE_URL = "base_url"
CONF_DEFAULT_LANGUAGE = "default_language"
CONF_DEFAULT_SPEAKER = "default_speaker"

DEFAULT_RUNTIME_DIR = "/config/ha_qwen3_tts/runtime"
DEFAULT_PYTHON_BIN = "/config/ha_qwen3_tts/runtime/venv/bin/python"
DEFAULT_AUTO_INSTALL = True
DEFAULT_QWEN_PACKAGE_URL = "https://github.com/QwenLM/Qwen3-TTS/archive/refs/heads/main.zip"
DEFAULT_OUTPUT_DIR = "/config/www/tts"
DEFAULT_BASE_URL = "/local/tts"
DEFAULT_LANGUAGE = "Korean"
DEFAULT_SPEAKER = "Sohee"

SERVICE_SPEAK = "speak"
