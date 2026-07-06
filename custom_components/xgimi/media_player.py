"""Media player support for the XGIMI projector."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player.const import MediaPlayerState
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ALIVE_PORT, ADVANCE_PORT, COMMAND_PORT, DOMAIN
from .pyxgimi import XgimiApi

_LOGGER = logging.getLogger(__name__)

HOMEKIT_REMOTE_EVENT = "homekit_tv_remote_key_pressed"

HOMEKIT_KEY_COMMANDS = {
    "arrow_up": "up",
    "arrow_down": "down",
    "arrow_left": "left",
    "arrow_right": "right",
    "select": "ok",
    "back": "back",
    "exit": "back",
    "menu": "menu",
    "information": "menu",
    "home": "home",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the XGIMI projector media player."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    host = config[CONF_HOST]
    name = config[CONF_NAME]
    token = config[CONF_TOKEN]

    device_identifier = config_entry.unique_id
    assert device_identifier is not None
    unique_id = f"{device_identifier}-media_player"

    xgimi_api = XgimiApi(
        ip=host,
        command_port=COMMAND_PORT,
        advance_port=ADVANCE_PORT,
        alive_port=ALIVE_PORT,
        manufacturer_data=token,
    )
    async_add_entities([XgimiMediaPlayer(xgimi_api, name, unique_id, device_identifier)])


class XgimiMediaPlayer(MediaPlayerEntity):
    """TV-style media player for HomeKit remote control."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_icon = "mdi:projector"
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
    )
    _attr_volume_level = 0.5
    _attr_volume_step = 0.05
    _attr_is_volume_muted = False

    def __init__(
        self,
        xgimi_api: XgimiApi,
        name: str,
        unique_id: str,
        device_identifier: str,
    ) -> None:
        """Initialize the XGIMI media player."""
        self.xgimi_api = xgimi_api
        self._device_identifier = device_identifier
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_state = MediaPlayerState.OFF

    async def async_added_to_hass(self) -> None:
        """Register HomeKit remote-key event handling."""
        self.async_on_remove(
            self.hass.bus.async_listen(
                HOMEKIT_REMOTE_EVENT, self._async_handle_homekit_remote_key
            )
        )

    async def async_update(self) -> None:
        """Retrieve latest state."""
        await self.xgimi_api.async_fetch_data()
        self._attr_state = (
            MediaPlayerState.ON if self.xgimi_api.is_on else MediaPlayerState.OFF
        )

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information for the projector."""
        return {
            "identifiers": {(DOMAIN, self._device_identifier)},
            "manufacturer": "XGIMI",
            "name": self.name,
        }

    async def async_turn_on(self) -> None:
        """Turn the projector on."""
        await self.xgimi_api.async_send_command("poweron")
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the projector off."""
        await self.xgimi_api.async_send_command("poweroff")
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        """Send play/select to the projector."""
        await self.xgimi_api.async_send_command("play")
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        """Send pause/select to the projector."""
        await self.xgimi_api.async_send_command("pause")
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    async def async_media_play_pause(self) -> None:
        """Toggle play/pause."""
        await self.xgimi_api.async_send_command("play")
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        """Turn volume up."""
        await self.xgimi_api.async_send_command("volumeup")

    async def async_volume_down(self) -> None:
        """Turn volume down."""
        await self.xgimi_api.async_send_command("volumedown")

    async def async_mute_volume(self, mute: bool) -> None:
        """Toggle mute."""
        await self.xgimi_api.async_send_command("volumemute")
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()

    @callback
    def _async_handle_homekit_remote_key(self, event: Event) -> None:
        """Handle Apple TV remote-style key events from HomeKit."""
        if event.data.get("entity_id") != self.entity_id:
            return

        key_name = event.data.get("key_name")
        if command := HOMEKIT_KEY_COMMANDS.get(key_name):
            self.hass.async_create_task(self._async_send_homekit_command(command))
            return

        _LOGGER.debug("Unhandled HomeKit remote key for XGIMI: %s", key_name)

    async def _async_send_homekit_command(self, command: str) -> None:
        """Send a HomeKit remote command to the projector."""
        await self.xgimi_api.async_send_command(command)
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()
