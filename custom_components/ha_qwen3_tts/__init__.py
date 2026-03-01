"""Home Assistant integration for local Qwen3-TTS Add-on."""

from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
from uuid import uuid4

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import (
    CONF_ADDON_URL,
    CONF_BASE_URL,
    CONF_DEFAULT_LANGUAGE,
    CONF_DEFAULT_SPEAKER,
    CONF_OUTPUT_DIR,
    DEFAULT_ADDON_URL,
    DEFAULT_BASE_URL,
    DEFAULT_LANGUAGE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SPEAKER,
    DOMAIN,
    SERVICE_SPEAK,
)

_LOGGER = logging.getLogger(__name__)
CONF_MEDIA_PLAYER_ENTITY_ID = "media_player_entity_id"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_ADDON_URL, default=DEFAULT_ADDON_URL): cv.string,
                vol.Optional(CONF_OUTPUT_DIR, default=DEFAULT_OUTPUT_DIR): cv.string,
                vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): cv.string,
                vol.Optional(CONF_DEFAULT_LANGUAGE, default=DEFAULT_LANGUAGE): cv.string,
                vol.Optional(CONF_DEFAULT_SPEAKER, default=DEFAULT_SPEAKER): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA_SPEAK = vol.Schema(
    {
        vol.Required("text"): cv.string,
        vol.Optional(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_MEDIA_PLAYER_ENTITY_ID): cv.entity_id,
        vol.Optional("language"): cv.string,
        vol.Optional("speaker"): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration from YAML config."""
    domain_config = config.get(DOMAIN, {})
    addon_url = domain_config.get(CONF_ADDON_URL, DEFAULT_ADDON_URL).rstrip("/")
    output_dir = Path(domain_config.get(CONF_OUTPUT_DIR, DEFAULT_OUTPUT_DIR))
    base_url = domain_config.get(CONF_BASE_URL, DEFAULT_BASE_URL).rstrip("/")
    default_language = domain_config.get(CONF_DEFAULT_LANGUAGE, DEFAULT_LANGUAGE)
    default_speaker = domain_config.get(CONF_DEFAULT_SPEAKER, DEFAULT_SPEAKER)

    await hass.async_add_executor_job(output_dir.mkdir, 0o755, True, True)

    async def handle_speak(call: ServiceCall) -> None:
        text = call.data["text"]
        language = call.data.get("language", default_language)
        speaker = call.data.get("speaker", default_speaker)
        entity_id = call.data.get(CONF_MEDIA_PLAYER_ENTITY_ID) or call.data.get(CONF_ENTITY_ID)

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"qwen3_tts_{ts}_{uuid4().hex[:8]}.wav"
        output_path = output_dir / filename

        if base_url.startswith(("http://", "https://")):
            media_url = f"{base_url}/{filename}"
        else:
            try:
                ha_base = get_url(hass, allow_internal=True, allow_external=False)
            except NoURLAvailableError:
                try:
                    ha_base = get_url(hass, allow_external=True)
                except NoURLAvailableError as exc:
                    raise HomeAssistantError(
                        "HA URL을 자동 감지할 수 없습니다. "
                        "packages/ha_qwen3_tts.yaml의 base_url을 "
                        "전체 URL로 지정해주세요. "
                        "예: base_url: https://your-domain.com/local/tts"
                    ) from exc
            media_url = f"{ha_base}{base_url}/{filename}"

        _LOGGER.info(
            "Requesting TTS from Add-on: speaker=%s language=%s", speaker, language
        )

        session = async_get_clientsession(hass)
        try:
            resp = await session.post(
                f"{addon_url}/tts",
                json={"text": text, "language": language, "speaker": speaker},
                timeout=300,
            )
        except Exception as exc:
            raise HomeAssistantError(f"Failed to reach TTS Add-on at {addon_url}: {exc}") from exc

        if resp.status != 200:
            body = await resp.text()
            raise HomeAssistantError(
                f"TTS Add-on returned HTTP {resp.status}: {body}"
            )

        wav_bytes = await resp.read()

        def _write_wav() -> None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(wav_bytes)

        await hass.async_add_executor_job(_write_wav)
        _LOGGER.info("TTS saved: %s", media_url)

        if entity_id:
            await hass.services.async_call(
                "media_player",
                "play_media",
                {
                    CONF_ENTITY_ID: entity_id,
                    "media_content_id": media_url,
                    "media_content_type": "music",
                },
                blocking=True,
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SPEAK,
        handle_speak,
        schema=SERVICE_SCHEMA_SPEAK,
    )

    return True
