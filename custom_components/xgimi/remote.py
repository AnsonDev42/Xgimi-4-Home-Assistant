"""Support for the Xgimi Projector."""

from collections.abc import Iterable

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ALIVE_PORT, ADVANCE_PORT, COMMAND_PORT, DOMAIN
from .pyxgimi import XgimiApi


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Xiaomi TV platform."""

    # If a hostname is set. Discovery is skipped.
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)
    unique_id = f"xgimi-{host}"

    xgimi_api = XgimiApi(
        ip=host,
        command_port=COMMAND_PORT,
        advance_port=ADVANCE_PORT,
        alive_port=ALIVE_PORT,
        manufacturer_data=token,
    )
    async_add_entities([XgimiRemote(xgimi_api, name, unique_id)])


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    config = hass.data[DOMAIN][config_entry.entry_id]
    host = config[CONF_HOST]
    name = config[CONF_NAME]
    token = config[CONF_TOKEN]

    unique_id = config_entry.unique_id
    assert unique_id is not None

    xgimi_api = XgimiApi(
        ip=host,
        command_port=COMMAND_PORT,
        advance_port=ADVANCE_PORT,
        alive_port=ALIVE_PORT,
        manufacturer_data=token,
    )
    async_add_entities([XgimiRemote(xgimi_api, name, unique_id)])


class XgimiRemote(RemoteEntity):
    """An entity for Xgimi Projector
    """

    def __init__(self, xgimi_api, name, unique_id):
        self.xgimi_api = xgimi_api
        self._attr_name = name
        self._attr_icon = "mdi:projector"
        self._attr_unique_id = unique_id

    async def async_update(self):
        """Retrieve latest state."""
        await self.xgimi_api.async_fetch_data()

    @property
    def is_on(self):
        """Return true if remote is on."""
        return self.xgimi_api.is_on

    @property
    def device_info(self):
        """Return device information for the projector."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": "XGIMI",
            "name": self.name,
        }

    async def async_turn_on(self, **kwargs):
        """Turn the Xgimi Projector On."""
        await self.xgimi_api.async_send_command("poweron")
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the Xgimi Projector Off."""
        await self.xgimi_api.async_send_command("poweroff")
        self.async_write_ha_state()

    async def async_send_command(
        self, command: Iterable[str] | str, **kwargs
    ) -> None:
        """Send a command to one of the devices."""
        commands = [command] if isinstance(command, str) else command
        for single_command in commands:
            await self.xgimi_api.async_send_command(single_command)
        self.async_write_ha_state()
