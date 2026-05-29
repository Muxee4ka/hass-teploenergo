from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_LS, DOMAIN, PLATFORMS
from .coordinator import TeploenergoCoordinator
from .teploenergo_api import TeploenergoApi

type TeploenergoConfigEntry = ConfigEntry[TeploenergoCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TeploenergoConfigEntry) -> bool:
    api = TeploenergoApi(
        login=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )
    coordinator = TeploenergoCoordinator(hass, api, entry.data[CONF_LS])
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TeploenergoConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: TeploenergoCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.api.close()
    return unloaded
