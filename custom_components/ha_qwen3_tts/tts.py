"""TTS platform for Qwen3-TTS Add-on."""

from __future__ import annotations

import logging

from homeassistant.components.tts import Provider
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ADDON_URL,
    CONF_DEFAULT_LANGUAGE,
    CONF_DEFAULT_SPEAKER,
    DEFAULT_ADDON_URL,
    DEFAULT_LANGUAGE,
    DEFAULT_SPEAKER,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = [
    "Korean",
    "English",
    "Japanese",
    "Chinese",
]


async def async_get_engine(
    hass: HomeAssistant,
    config: dict,
    discovery_info: dict | None = None,
) -> QwenTTSProvider:
    """Set up Qwen3 TTS engine."""
    domain_data = hass.data.get(DOMAIN, {})
    addon_url = domain_data.get(CONF_ADDON_URL, DEFAULT_ADDON_URL)
    default_language = domain_data.get(CONF_DEFAULT_LANGUAGE, DEFAULT_LANGUAGE)
    default_speaker = domain_data.get(CONF_DEFAULT_SPEAKER, DEFAULT_SPEAKER)
    return QwenTTSProvider(hass, addon_url, default_language, default_speaker)


class QwenTTSProvider(Provider):
    """Qwen3-TTS provider."""

    def __init__(
        self,
        hass: HomeAssistant,
        addon_url: str,
        default_language: str,
        default_speaker: str,
    ) -> None:
        self.hass = hass
        self.name = "HA Qwen3 TTS"
        self._addon_url = addon_url
        self._default_language = default_language
        self._default_speaker = default_speaker

    @property
    def default_language(self) -> str:
        return self._default_language

    @property
    def supported_languages(self) -> list[str]:
        return SUPPORTED_LANGUAGES

    @property
    def supported_options(self) -> list[str]:
        return ["speaker"]

    async def async_get_tts_audio(
        self,
        message: str,
        language: str,
        options: dict | None = None,
    ) -> tuple[str | None, bytes | None]:
        """Request TTS audio from Qwen3-TTS Add-on and return WAV bytes."""
        speaker = (options or {}).get("speaker", self._default_speaker)

        _LOGGER.debug(
            "TTS request: language=%s speaker=%s text_len=%d",
            language,
            speaker,
            len(message),
        )

        session = async_get_clientsession(self.hass)
        try:
            resp = await session.post(
                f"{self._addon_url}/tts",
                json={"text": message, "language": language, "speaker": speaker},
                timeout=300,
            )
        except Exception as exc:
            _LOGGER.error("Failed to reach TTS Add-on at %s: %s", self._addon_url, exc)
            return None, None

        if resp.status != 200:
            body = await resp.text()
            _LOGGER.error("TTS Add-on returned HTTP %d: %s", resp.status, body)
            return None, None

        audio = await resp.read()
        _LOGGER.debug("TTS audio received: %d bytes", len(audio))
        return "wav", audio
