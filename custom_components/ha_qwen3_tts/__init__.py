"""Home Assistant integration for local Qwen3-TTS service."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import os
from pathlib import Path
from uuid import uuid4

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_AUTO_INSTALL,
    CONF_BASE_URL,
    CONF_DEFAULT_LANGUAGE,
    CONF_DEFAULT_SPEAKER,
    CONF_OUTPUT_DIR,
    CONF_PYTHON_BIN,
    CONF_QWEN_PACKAGE_URL,
    CONF_RUNTIME_DIR,
    DEFAULT_AUTO_INSTALL,
    DEFAULT_BASE_URL,
    DEFAULT_LANGUAGE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PYTHON_BIN,
    DEFAULT_QWEN_PACKAGE_URL,
    DEFAULT_RUNTIME_DIR,
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
                vol.Optional(CONF_RUNTIME_DIR, default=DEFAULT_RUNTIME_DIR): cv.string,
                vol.Optional(CONF_PYTHON_BIN, default=DEFAULT_PYTHON_BIN): cv.string,
                vol.Optional(CONF_AUTO_INSTALL, default=DEFAULT_AUTO_INSTALL): cv.boolean,
                vol.Optional(CONF_QWEN_PACKAGE_URL, default=DEFAULT_QWEN_PACKAGE_URL): cv.string,
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


async def _run_cmd(
    *cmd: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    out = stdout.decode("utf-8", errors="ignore").strip()
    err = stderr.decode("utf-8", errors="ignore").strip()
    return process.returncode, out, err


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration from YAML config."""
    domain_config = config.get(DOMAIN, {})
    runtime_dir = Path(domain_config[CONF_RUNTIME_DIR])
    python_bin = domain_config[CONF_PYTHON_BIN]
    auto_install = domain_config[CONF_AUTO_INSTALL]
    qwen_package_url = domain_config[CONF_QWEN_PACKAGE_URL]
    output_dir = Path(domain_config[CONF_OUTPUT_DIR])
    base_url = domain_config[CONF_BASE_URL].rstrip("/")
    default_language = domain_config[CONF_DEFAULT_LANGUAGE]
    default_speaker = domain_config[CONF_DEFAULT_SPEAKER]

    script_path = Path(__file__).with_name("qwen3_generate.py")
    venv_dir = Path(python_bin).parents[1]
    hf_home = runtime_dir / "hf_cache"
    torch_home = runtime_dir / "torch_cache"
    runtime_env = os.environ.copy()
    runtime_env["HF_HOME"] = str(hf_home)
    runtime_env["TORCH_HOME"] = str(torch_home)
    runtime_ready = False
    install_lock = asyncio.Lock()

    runtime_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    async def ensure_runtime() -> None:
        nonlocal runtime_ready
        if runtime_ready:
            return

        async with install_lock:
            if runtime_ready:
                return

            if not Path(python_bin).exists():
                if not auto_install:
                    raise HomeAssistantError(
                        f"Python runtime not found: {python_bin}. "
                        "Set auto_install: true or provide a valid python_bin."
                    )
                _LOGGER.info("Creating virtualenv for Qwen3-TTS at %s", venv_dir)
                code, _, err = await _run_cmd("python3", "-m", "venv", str(venv_dir))
                if code != 0:
                    raise HomeAssistantError(f"Failed to create venv: {err}")

            check_code, _, _ = await _run_cmd(
                python_bin, "-c", "import qwen_tts, soundfile, torch"
            )
            if check_code == 0:
                runtime_ready = True
                return

            if not auto_install:
                raise HomeAssistantError(
                    "Qwen3-TTS dependencies are missing. "
                    "Set auto_install: true to install automatically."
                )

            _LOGGER.info("Installing Qwen3-TTS dependencies into %s", venv_dir)
            code, _, err = await _run_cmd(
                python_bin,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "pip",
                "setuptools",
                "wheel",
            )
            if code != 0:
                raise HomeAssistantError(f"Failed to upgrade pip tooling: {err}")

            code, _, err = await _run_cmd(
                python_bin,
                "-m",
                "pip",
                "install",
                "--upgrade",
                qwen_package_url,
                "soundfile",
            )
            if code != 0:
                raise HomeAssistantError(f"Failed to install Qwen3-TTS package: {err}")

            verify_code, _, verify_err = await _run_cmd(
                python_bin, "-c", "import qwen_tts, soundfile, torch"
            )
            if verify_code != 0:
                raise HomeAssistantError(f"Runtime verification failed: {verify_err}")

            runtime_ready = True
            _LOGGER.info("Qwen3-TTS runtime is ready")

    async def handle_speak(call: ServiceCall) -> None:
        await ensure_runtime()

        text = call.data["text"]
        language = call.data.get("language", default_language)
        speaker = call.data.get("speaker", default_speaker)
        entity_id = call.data.get(CONF_MEDIA_PLAYER_ENTITY_ID) or call.data.get(CONF_ENTITY_ID)

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"qwen3_tts_{ts}_{uuid4().hex[:8]}.wav"
        output_path = output_dir / filename
        media_url = f"{base_url}/{filename}"

        cmd = [
            python_bin,
            str(script_path),
            "--text",
            text,
            "--language",
            language,
            "--speaker",
            speaker,
            "--output",
            str(output_path),
        ]
        _LOGGER.info("Generating TTS: speaker=%s language=%s output=%s", speaker, language, output_path)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(runtime_dir),
            env=runtime_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            _LOGGER.error(
                "Qwen3-TTS failed (code=%s): %s",
                process.returncode,
                stderr.decode("utf-8", errors="ignore").strip(),
            )
            return

        if stdout:
            _LOGGER.debug("Qwen3-TTS stdout: %s", stdout.decode("utf-8", errors="ignore").strip())

        _LOGGER.info("TTS generated: %s", media_url)

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
