"""Constants for HA Qwen3 TTS."""

DOMAIN = "ha_qwen3_tts"

CONF_ADDON_URL = "addon_url"
CONF_OUTPUT_DIR = "output_dir"
CONF_BASE_URL = "base_url"
CONF_DEFAULT_LANGUAGE = "default_language"
CONF_DEFAULT_SPEAKER = "default_speaker"

DEFAULT_ADDON_URL = "http://localhost:5000"
DEFAULT_OUTPUT_DIR = "/config/www/tts"
DEFAULT_BASE_URL = "/local/tts"
DEFAULT_LANGUAGE = "Korean"
DEFAULT_SPEAKER = "Sohee"

SERVICE_SPEAK = "speak"
